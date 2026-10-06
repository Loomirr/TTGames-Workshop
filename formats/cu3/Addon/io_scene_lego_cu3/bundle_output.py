"""Native source proposals and verified, non-replacing directory publication.

This module has no Blender dependency. A bundle is assembled in a uniquely
owned sibling directory and reread before one same-filesystem rename. Windows
uses os.rename's non-replacing semantics; Linux requires renameat2 with
RENAME_NOREPLACE; macOS requires renamex_np with RENAME_EXCL. Other platforms
and filesystems without those operations fail closed. There is deliberately no
check-then-rename fallback, cross-filesystem copy, or power-loss durability claim.
"""
import copy
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unicodedata
import warnings

from .cu3 import FormatError


MANIFEST_NAME = 'TT_Source_Export.json'


def destination_path(destination):
    """Resolve the parent while retaining the leaf, including dangling links."""
    path = Path(os.path.abspath(Path(destination).expanduser()))
    return path.parent.resolve() / path.name


def require_absent(destination):
    # Path.exists() alone misses dangling symlinks. Existing empty folders also
    # belong to the user (or a concurrent exporter) and must never be replaced.
    if os.path.lexists(destination):
        raise FormatError('Choose a fresh export folder; destination already exists: '
                          + str(destination))


def _path_key(parts):
    # Native PC assets and exported bundles are routinely moved to Windows or
    # macOS. Reject portable aliases even when the current host is case-sensitive.
    return tuple(unicodedata.normalize('NFC', part).casefold() for part in parts)


def relative_output_path(value):
    """Preserve logical spelling, rejecting unsafe or nonportable file paths."""
    if not isinstance(value, (str, Path)):
        raise FormatError('Native export needs a logical relative file path')
    name = str(value).replace('\\', '/')
    parts = name.split('/')
    reserved = {'con', 'prn', 'aux', 'nul', 'conin$', 'conout$'}
    reserved.update(prefix + digit for prefix in ('com', 'lpt')
                    for digit in '123456789\u00b9\u00b2\u00b3')
    if any(not part or part in ('.', '..') or part.endswith((' ', '.'))
           or any(ord(char) < 32 or ord(char) == 127 or char in '<>:"|?*' for char in part)
           or part.split('.')[0].casefold() in reserved for part in parts):
        raise FormatError('Unsafe native export path: ' + repr(str(value)))
    path = Path(*parts)
    if path.is_absolute():
        raise FormatError('Unsafe native export path: ' + repr(str(value)))
    return path


def _plan_payloads(payloads, manifest_name=MANIFEST_NAME, forbidden_suffixes=()):
    """Preflight every file and directory alias before creating staging."""
    manifest_name = relative_output_path(manifest_name).as_posix()
    if len(Path(manifest_name).parts) != 1:
        raise FormatError('The bundle manifest must be at the bundle root')
    planned, files, directories = [], {_path_key((manifest_name,))}, {}
    for logical, data in payloads:
        path = relative_output_path(logical)
        if path.suffix.casefold() in forbidden_suffixes:
            raise FormatError('Forbidden native export extension: ' + str(path))
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise FormatError('Native export payload must contain bytes: ' + str(path))
        data = bytes(data)
        key = _path_key(path.parts)
        if key in files or key in directories:
            raise FormatError('Duplicate or conflicting native export path: ' + str(path))
        for end in range(1, len(path.parts)):
            spelling = path.parts[:end]
            parent = _path_key(spelling)
            if parent in files:
                raise FormatError('Native export file/directory collision: ' + str(path))
            if parent in directories and directories[parent] != spelling:
                raise FormatError('Native export directory spelling collision: ' + str(path))
            directories[parent] = spelling
        files.add(key)
        planned.append((path, data))
    return sorted(planned, key=lambda item: item[0].as_posix())


def _native_publisher():
    """Return a no-replace directory rename and its exact platform contract."""
    if os.name == 'nt':
        return os.rename, 'Windows os.rename (destination must not exist)'
    if sys.platform not in ('linux', 'darwin'):
        raise FormatError('Safe native bundle publication is unsupported on this platform; '
                          'a no-replace directory rename is required')
    library = ctypes.CDLL(None, use_errno=True)
    symbol = 'renameat2' if sys.platform == 'linux' else 'renamex_np'
    try:
        rename = getattr(library, symbol)
    except AttributeError as error:
        raise FormatError('Safe native bundle publication requires ' + symbol
                          + '; this runtime does not expose it') from error
    rename.restype = ctypes.c_int
    if sys.platform == 'linux':
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        def invoke(source, target):
            return rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)
        method = 'Linux renameat2(RENAME_NOREPLACE)'
    else:
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        def invoke(source, target):
            return rename(os.fsencode(source), os.fsencode(target), 0x4)
        method = 'macOS renamex_np(RENAME_EXCL)'

    def publish(source, target):
        if invoke(source, target) == 0:
            return
        code = ctypes.get_errno()
        if code in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP):
            raise FormatError(method + ' is unsupported by this filesystem/runtime; '
                              'no bundle was published')
        if code == errno.EXDEV:
            raise FormatError('Native bundle publication requires a same-filesystem rename; '
                              'no cross-filesystem fallback is permitted')
        raise OSError(code, os.strerror(code), str(target))
    return publish, method


def _write_exclusive(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        if stream.write(data) != len(data):
            raise OSError('Short native bundle write: ' + str(path))
        stream.flush()
        os.fsync(stream.fileno())


def _stage_identity(stage):
    info = stage.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise FormatError('Native bundle staging is not an owned directory')
    return info.st_dev, info.st_ino


def _verify_stage(stage, planned, report, manifest_bytes, manifest_name=MANIFEST_NAME):
    expected = {path.as_posix() for path, _ in planned} | {manifest_name}
    expected_dirs = {parent.as_posix() for path, _ in planned for parent in path.parents
                     if parent != Path('.')}
    actual, actual_dirs = set(), set()
    for parent, dirs, files in os.walk(stage, followlinks=False):
        for name in dirs + files:
            entry = Path(parent) / name
            mode = entry.lstat().st_mode
            relative = entry.relative_to(stage).as_posix()
            if stat.S_ISREG(mode):
                actual.add(relative)
            elif stat.S_ISDIR(mode):
                actual_dirs.add(relative)
            else:
                raise FormatError('Non-regular entry in native bundle staging: ' + relative)
    if actual != expected or actual_dirs != expected_dirs:
        raise FormatError('Native bundle staging inventory does not match the planned bundle')
    for entry in report['files']:
        path = stage / entry['path']
        digest, size = hashlib.sha256(), 0
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        if size != entry['bytes'] or digest.hexdigest() != entry['sha256']:
            raise FormatError('Native bundle payload verification failed: ' + entry['path'])
    stored_manifest = (stage / manifest_name).read_bytes()
    if stored_manifest != manifest_bytes:
        raise FormatError('Native bundle manifest verification failed')
    if json.loads(stored_manifest) != report:
        raise FormatError('Native bundle manifest does not describe the planned bundle')


def _cleanup_owned_stage(stage, identity):
    try:
        current = _stage_identity(stage)
    except FileNotFoundError:
        return
    except (OSError, FormatError):
        warnings.warn('Staging ownership could not be verified; left untouched: ' + str(stage))
        return
    if current != identity:
        warnings.warn('Staging ownership changed; left untouched: ' + str(stage))
        return
    try:
        shutil.rmtree(stage)
    except OSError as error:
        warnings.warn('Could not remove owned native export staging ' + str(stage) + ': ' + str(error))


class OwnedStage:
    """A uniquely owned sibling stage, with explicit no-replace publication.

    Use as a context manager, write only beneath ``path``, then verify all output
    before calling ``publish()``. This lower-level API is also used by archive
    extractors that stream their files rather than retaining payload bytes.
    Leaving the context removes only staging that still has this operation's
    identity. The final destination is never removed, even on an exception.
    """
    def __init__(self, destination):
        self.destination = destination_path(destination)
        require_absent(self.destination)
        self._publish, self.method = _native_publisher()
        self.path = None
        self.identity = None
        self.published = False

    def __enter__(self):
        if self.path is not None:
            raise RuntimeError('Native output staging cannot be reused')
        require_absent(self.destination)
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.path = Path(tempfile.mkdtemp(
            prefix='.' + self.destination.name[:48] + '.tt-stage-',
            dir=self.destination.parent))
        self.identity = _stage_identity(self.path)
        return self

    def check_owned(self):
        if self.path is None or _stage_identity(self.path) != self.identity:
            raise FormatError('Native bundle staging ownership changed during verification')

    def publish(self):
        if self.published:
            raise RuntimeError('Native output staging was already published')
        self.check_owned()
        try:
            self._publish(self.path, self.destination)
        except FileExistsError as error:
            raise FormatError('Native export destination was created during publication; '
                              'left it untouched: ' + str(self.destination)) from error
        self.published = True

    def __exit__(self, exc_type, exc_value, traceback):
        _cleanup_owned_stage(self.path, self.identity)


def publish_bundle(destination, payloads, report, *, manifest_name=MANIFEST_NAME,
                   forbidden_suffixes=(), expected_paths=None):
    """Write, verify and publish the complete bundle to an absent destination.

    ``payloads`` is an iterable of (logical relative path, bytes). Supply the
    full ``expected_paths`` list to preflight names before consuming a streaming
    payload generator. Every expected file must be yielded exactly once. Without
    it, payloads are materialized for preflight. Report fields are copied after
    consumption, allowing a bounded decoder to add verified entry metadata.
    Only the
    uniquely created staging directory is removed on failure. Preexisting and
    concurrently created destinations, sibling stages and parents are retained.
    Files are flushed before verification; process interruptions may leave an
    identifiable staging directory, and power-loss durability is not guaranteed.
    """
    destination = destination_path(destination)
    require_absent(destination)
    manifest_name = relative_output_path(manifest_name).as_posix()
    if expected_paths is None:
        prepared = _plan_payloads(payloads, manifest_name, forbidden_suffixes)
        payloads = prepared
        planned = [(path, None) for path, _ in prepared]
    else:
        planned = [(path, None) for path, _ in _plan_payloads(
            ((path, b'') for path in expected_paths), manifest_name, forbidden_suffixes)]
    expected = {path for path, _ in planned}
    staging = OwnedStage(destination)
    if not isinstance(report.get('schema'), str) or not report['schema']:
        raise FormatError('Native source bundle manifest requires a schema')
    # Reject initially unserializable metadata before creating any output. A
    # streaming decoder may add fields later; their serialization is also checked.
    json.dumps(report, allow_nan=False)
    with staging:
        written, files = set(), []
        for relative, data in payloads:
            relative = relative_output_path(relative)
            if relative not in expected or relative in written:
                raise FormatError('Unexpected or duplicate streamed native output: ' + str(relative))
            if not isinstance(data, (bytes, bytearray, memoryview)):
                raise FormatError('Native export payload must contain bytes: ' + str(relative))
            data = bytes(data)
            _write_exclusive(staging.path / relative, data)
            files.append(dict(path=relative.as_posix(), bytes=len(data),
                              sha256=hashlib.sha256(data).hexdigest()))
            written.add(relative)
            del data
        if written != expected:
            raise FormatError('Streamed native output omitted planned files')
        report = copy.deepcopy(report)
        report['files'] = sorted(files, key=lambda entry: entry['path'])
        report['publication'] = dict(method=staging.method, replaces_existing=False,
                                   scope='same-filesystem directory rename',
                                   verification='Reread payload hashes, manifest and complete staging inventory',
                                   power_loss_durability='not guaranteed')
        manifest_bytes = (json.dumps(report, indent=2, allow_nan=False) + '\n').encode('utf-8')
        _write_exclusive(staging.path / manifest_name, manifest_bytes)
        _verify_stage(staging.path, planned, report, manifest_bytes, manifest_name)
        staging.publish()
    return report

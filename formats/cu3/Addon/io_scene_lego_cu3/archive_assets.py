"""Read-only installed-game companion lookup with an external extraction cache.

Only requested files are decoded. Installed archives are never modified.
The observed LB3 -6 index follows the format documented by ttgames.bms;
this bounded implementation and chunk decoder use no external runtime.
"""
from pathlib import Path, PurePosixPath
import hashlib
import errno
import os
import secrets
import struct
from .cu3 import FormatError
from .archive_compression import decode_entry
from .archive_paths import safe_path, validate_paths

MAX_ENTRY_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024


def _cache_io_error(error, target):
    """Explain OS path failures without relaxing cache ownership checks."""
    if (getattr(error, 'winerror', None) == 206 or error.errno == errno.ENAMETOOLONG or
            (os.name == 'nt' and error.errno == errno.ENOENT and len(str(target.absolute())) >= 240)):
        raise FormatError('Archive cache write failed; this may exceed the Windows path limit. '
                          'Choose a shorter cache folder outside the game installation. '
                          f'Target: {target}; OS error: {error}') from error
    raise error


def _archive_stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _path_archive_stamp(path):
    # Windows directory metadata can lag handle metadata after a rewrite.
    # Compare handle-derived stamps consistently; retain every identity field.
    with path.open('rb') as stream:
        return _archive_stamp(os.fstat(stream.fileno()))


def _safe_path(name):
    try:
        return safe_path(name)
    except ValueError as error:
        raise FormatError(str(error)) from error


def _path_hash(name):
    value = 0x811c9dc5
    for byte in name.upper().replace('/', '\\').encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def index_v6(path, *, version_expected=-6):
    if version_expected not in (-5, -6):
        raise FormatError('Unsupported parent-index layout')
    path = Path(path)
    archive_size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(8)
        if len(header) != 8:
            raise FormatError('Truncated DAT header')
        offset, size = struct.unpack('<II', header)
        if offset & 0x80000000:
            offset = ((offset ^ 0xffffffff) << 8) + 256
        if not 8 <= offset <= archive_size or not 8 <= size <= min(256 * 1024 * 1024, archive_size - offset):
            raise FormatError('DAT index exceeds archive bounds')
        stream.seek(offset)
        data = stream.read(size)
        if len(data) != size:
            raise FormatError('DAT index could not be read completely')
    def get(fmt, at):
        n = struct.calcsize('<' + fmt)
        if at < 0 or at + n > len(data):
            raise FormatError('DAT index table exceeds bounds')
        values = struct.unpack_from('<' + fmt, data, at)
        return values[0] if len(values) == 1 else values
    version, count = get('iI', 0)
    if version != version_expected or not 0 < count <= 1000000:
        raise FormatError('Unverified DAT index version/count')
    names_at = 8 + count * 16
    names_count = get('I', names_at)
    if not 0 < names_count <= 1000000:
        raise FormatError('Unreasonable DAT name count')
    names_at += 4
    strings_at = names_at + names_count * 12 + 4
    strings_size = get('I', strings_at - 4)
    hashes_at = strings_at + strings_size
    if not strings_size or hashes_at + count * 4 > len(data):
        raise FormatError('DAT strings or hashes exceed index')
    by_hash = {}
    for i in range(count):
        key = get('I', hashes_at + i * 4)
        if key in by_hash:
            raise FormatError('Ambiguous DAT path hash')
        by_hash[key] = i
    folders, mapped = {}, {}
    for i in range(names_count):
        child, previous, name_offset, parent = get('hhiI', names_at + i * 12)
        # Original LB3 (-6) and Hobbit (-5) archives carry a nameless root
        # sentinel in record zero with the native 16-bit no-parent value.
        # It is metadata, not a forward reference or an output path.
        if i == 0 and name_offset < 0 and parent == 0xffff:
            folders[i] = ''
            continue
        name = ''
        if name_offset >= 0:
            start = strings_at + name_offset
            if start >= hashes_at:
                raise FormatError('DAT name outside string table')
            end = data.find(b'\0', start, hashes_at)
            if end < 0:
                raise FormatError('Unterminated DAT path name')
            name = data[start:end].decode('ascii')
        if parent not in folders and parent not in (0, 0xffffffff):
            raise FormatError('DAT name parent is unresolved')
        prefix = folders.get(parent, '')
        if len(name)>255 or len(prefix)+len(name)>4096:
            raise FormatError('DAT path exceeds supported name/depth limits')
        folders[i] = prefix
        if child > 0:
            folders[i] = (_safe_path(prefix + name) + '\\') if prefix or name else ''
            continue
        if not name:
            continue
        full = _safe_path(prefix + name)
        number = by_hash.get(_path_hash(full))
        if number is None or number in mapped:
            raise FormatError('DAT path has no unique matching file hash')
        low, packed, raw, flags = get('4I', 8 + number * 16)
        file_offset = (low << 8) | (flags >> 24)
        if (file_offset < 8 or file_offset + packed > archive_size or
                file_offset < offset + size and file_offset + packed > offset):
            raise FormatError('DAT file extent overlaps header/index or exceeds payload region')
        mode = flags & 0xffffff
        if bool(packed) != bool(raw) or (mode == 0 and packed != raw):
            raise FormatError('Invalid DAT packed/decoded sizes')
        mapped[number] = {'path':full,'offset':file_offset,'packed_size':packed,'size':raw,'flags':flags & 0xffffff}
    if len(mapped) != count:
        raise FormatError('DAT index contains unresolved file paths')
    try:
        validate_paths(entry['path'] for entry in mapped.values())
    except ValueError as error:
        raise FormatError(str(error)) from error
    return [mapped[i] for i in range(count)]


class ArchiveAssetIndex:
    """AssetIndex-compatible provider for explicitly profiled PC DAT layouts."""
    def __init__(self, root, profile, cache_root=None, *, max_total_bytes=MAX_TOTAL_BYTES):
        if not isinstance(max_total_bytes, int) or not 0 <= max_total_bytes <= MAX_TOTAL_BYTES:
            raise FormatError('Invalid cumulative archive extraction limit')
        self.max_total_bytes = max_total_bytes
        self._packed_total = self._decoded_total = 0
        self._archive_stats = {}
        self.game_root = Path(root).resolve()
        if profile not in ('LB3', 'LMSH1', 'AVENGERS', 'TFA', 'DCSV', 'LMSH2', 'HOBBIT', 'LOTR', 'LB1', 'TCS', 'LB2', 'SW3', 'MOVIE1'):
            raise FormatError('Unsupported installed archive profile')
        archives = sorted(p for p in self.game_root.iterdir() if p.is_file() and p.suffix.casefold()=='.dat'
                          and p.stem.upper().startswith(('GAME','DLC','HERO','VILLAIN','EPISODE') if profile in ('LB1','TCS') else ('GAME','DLC')))
        if not archives:
            raise FormatError('No supported game archives in the selected folder')
        if cache_root is None:
            base = Path(os.environ['LOCALAPPDATA']) if os.environ.get('LOCALAPPDATA') else Path.home() / '.cache'
            cache_root = base / 'TTGamesWorkshop' / 'asset-cache'
        cache_root = Path(cache_root).expanduser().resolve()
        if cache_root.is_relative_to(self.game_root):
            raise FormatError('Choose an extraction cache outside the installed game')
        fingerprint = hashlib.sha256()
        fingerprint.update(str(self.game_root).encode('utf-8'))
        for archive in archives:
            stamp = _path_archive_stamp(archive)
            self._archive_stats[archive] = stamp
            fingerprint.update(f'{archive.name}:{stamp}'.encode('utf-8'))
        self.root = cache_root / (profile.lower() + '-' + fingerprint.hexdigest()[:20])
        self.cache_base = cache_root
        self._validate_cache_root()
        self.files, self.events = {}, []
        if profile in ('LB1', 'TCS', 'LB2', 'SW3'):
            from .archive_v5 import index_v5
            reader = lambda path: index_v5(path, layout={'LB1': -2, 'TCS': -3, 'LB2': -4, 'SW3': -4}[profile])
        elif profile == 'LMSH1':
            from .archive_v5 import index_v5
            reader = index_v5
        elif profile == 'LOTR':
            from .archive_v5 import index_v5
            reader = lambda path: index_v5(path, name_tags=True)
        elif profile == 'LB3':
            reader = index_v6
        elif profile in ('HOBBIT', 'MOVIE1'):
            reader = lambda path: index_v6(path, version_expected=-5)
        else:
            from .archive_cc import index
            reader = index
        for archive in archives:
            for entry in reader(archive):
                if PurePosixPath(entry['path']).suffix.casefold() in ('.ghg','.gsc','.cd','.tex','.nxg_textures','.cu3','.an4','.as','.pak','.txt','.led','.cu2','.an3','.giz'):
                    self.files.setdefault(PurePosixPath(entry['path']).name.casefold(), []).append((archive, entry))
        self.profile, self.archive_count = profile, len(archives)

    def _validate_cache_root(self):
        resolved = self.root.resolve()
        if not resolved.is_relative_to(self.cache_base) or resolved.is_relative_to(self.game_root):
            raise FormatError('Archive cache link escapes its selected directory or points into the game')
        return resolved

    def _read(self, archive, entry):
        if (not isinstance(entry['packed_size'], int) or not 0 <= entry['packed_size'] <= MAX_ENTRY_BYTES or
                not isinstance(entry['size'], int) or not 0 <= entry['size'] <= MAX_ENTRY_BYTES):
            raise FormatError('Requested archive companion exceeds the 256 MiB limit')
        if entry['flags'] not in (0, 2):
            raise FormatError(f"Unverified archive storage mode {entry['flags']}; LOTR mode 3 DFLT remains unsupported")
        if (self._packed_total + entry['packed_size'] > self.max_total_bytes or
                self._decoded_total + entry['size'] > self.max_total_bytes):
            raise FormatError('Cumulative archive extraction exceeds configured limit; open a new provider for a separate operation')
        with archive.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if _archive_stamp(before) != self._archive_stats[archive]:
                raise FormatError('Archive changed since its index was loaded')
            stream.seek(entry['offset'])
            packed = stream.read(entry['packed_size'])
            after = os.fstat(stream.fileno())
        if _archive_stamp(before) != _archive_stamp(after):
            raise FormatError('Archive changed while its companion was read')
        if len(packed) != entry['packed_size']:
            raise FormatError('Archive changed or companion payload is truncated')
        self._packed_total += entry['packed_size']
        self._decoded_total += entry['size']
        return decode_entry(packed, entry['size'], storage_mode=entry['flags'])

    @staticmethod
    def _atomic_write(target, data):
        # A short sibling name avoids repeating a long asset/digest basename.
        temporary = target.with_name('.tt-' + secrets.token_hex(8) + '.tmp')
        created = False
        try:
            with temporary.open('xb') as output:
                created = True
                output.write(data)
            os.replace(temporary, target)
        except OSError as error:
            _cache_io_error(error, target)
        finally:
            if created and temporary.exists():
                temporary.unlink()

    def find_exact(self, reference, required=True):
        return self.find(reference, required=required, exact=True)

    def find(self, reference, suffix='', extension='', required=True, exact=False):
        clean = _safe_path(str(reference))
        parts = PurePosixPath(clean).parts
        basename = parts[-1]
        if extension:
            stem = PurePosixPath(basename).stem
            if suffix and not stem.casefold().endswith(suffix.casefold()):
                stem += suffix
            basename = stem + extension
        candidates = self.files.get(basename.casefold(), [])
        if exact or len(parts) > 1:
            ending = '/'.join((*parts[:-1],basename)).casefold()
            candidates = [(a,e) for a,e in candidates if e['path'].casefold()==ending]
        if not candidates:
            if required:
                raise FormatError('Missing archive companion: ' + basename)
            return None
        logical_paths = {e['path'].casefold() for _, e in candidates}
        spellings = {e['path'] for _, e in candidates}
        if len(logical_paths) > 1:
            raise FormatError('Ambiguous archive asset basename; use an exact logical path: ' + str(reference))
        if len(spellings) > 1:
            raise FormatError('Case-colliding archive asset paths: ' + ', '.join(sorted(spellings)))
        archive, entry = candidates[0]
        if any(e['packed_size'] > MAX_ENTRY_BYTES or e['size'] > MAX_ENTRY_BYTES for _, e in candidates):
            raise FormatError('Requested archive companion exceeds the 256 MiB limit')
        if any(e['flags'] not in (0, 2) for _, e in candidates):
            raise FormatError('Unverified archive storage mode; LOTR mode 3 DFLT remains unsupported')
        if any(_path_archive_stamp(source) != self._archive_stats[source] for source, _ in candidates):
            raise FormatError('Archive changed since its index was loaded')
        cache_boundary = self._validate_cache_root()
        target = self.root / _safe_path(entry['path'])
        digest_file = target.with_name(target.name + '.sha256')
        if not target.resolve().is_relative_to(cache_boundary) or not digest_file.resolve().is_relative_to(cache_boundary):
            raise FormatError('Archive cache target escapes selected cache')
        if target.is_file() and digest_file.is_file() and len(candidates)==1:
            if digest_file.stat().st_size != 64:
                raise FormatError('Cached companion digest is damaged; choose a fresh cache folder')
            digest = digest_file.read_text(encoding='ascii').strip()
            if (target.stat().st_size != entry['size'] or len(digest)!=64 or
                    hashlib.sha256(target.read_bytes()).hexdigest()!=digest):
                raise FormatError('Cached companion was modified or damaged; choose a fresh cache folder')
            return target
        if (self._packed_total + sum(e['packed_size'] for _, e in candidates) > self.max_total_bytes or
                self._decoded_total + sum(e['size'] for _, e in candidates) > self.max_total_bytes):
            raise FormatError('Cumulative archive extraction exceeds configured limit')
        data = self._read(archive, entry)
        if any(self._read(a,e)!=data for a,e in candidates[1:]):
            raise FormatError('Ambiguous archive asset reference: ' + str(reference))
        if target.exists():
            if target.read_bytes() != data:
                raise FormatError('Existing cached companion differs; choose a fresh cache folder')
        else:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                _cache_io_error(error, target)
            self._atomic_write(target, data)
            self.events.append({'path':entry['path'],'bytes':len(data),'archive':archive.name})
        self._atomic_write(digest_file, hashlib.sha256(data).hexdigest().encode('ascii'))
        return target

    def get_info(self):
        return {'kind':'installed_archives','profile':self.profile,'archive_count':self.archive_count,
                'cache':str(self.root),'extracted_files':len(self.events),
                'packed_bytes_read':self._packed_total, 'decoded_bytes_requested':self._decoded_total,
                'cumulative_byte_limit':self.max_total_bytes,
                'scope':'Requested model, definition, texture, configuration and declared stage companions. Installed archives are read only; extraction does not establish rendering fidelity.'}

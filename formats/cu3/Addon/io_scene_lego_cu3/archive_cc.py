"""Read observed Avengers/TFA/DCSV CC40TAD archive indexes without runtimes.

This is an inventory reader, not an archive writer. Entries retain compression
flags; callers must use a compatible decoder before treating bytes as a file.
Unknown versions, unresolved names and out-of-bounds tables are rejected.
"""
from pathlib import Path
import struct
from .archive_paths import safe_path, validate_paths

MAX_INDEX_BYTES = 256 * 1024 * 1024


def path_hash(name):
    value = 0x811c9dc5
    for byte in name.upper().replace('/', '\\').encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def _safe_name(name):
    return safe_path(name)


def parse_index(data, archive_limit=None, *, expected_layout=None):
    if len(data) > MAX_INDEX_BYTES:
        raise ValueError('CC8 index exceeds size limit')
    if archive_limit is not None and (not isinstance(archive_limit, int) or archive_limit < 8):
        raise ValueError('Invalid CC8 archive data region')
    def read(fmt, at):
        size = struct.calcsize('>' + fmt)
        if at < 0 or at + size > len(data):
            raise ValueError('CC8 table exceeds index bounds')
        result = struct.unpack_from('>' + fmt, data, at)
        return result[0] if len(result) == 1 else result

    def string(at, end):
        if not 0 <= at < end <= len(data):
            raise ValueError('CC8 string exceeds its table')
        null = data.find(b'\0', at, end)
        if null < 0:
            raise ValueError('Unterminated CC8 name')
        return data[at:null].decode('ascii'), null + 1

    size, magic, kind, version, files, names, string_size = read('I8si4I', 0)
    if size + 4 != len(data) or magic != b'.CC40TAD' or (kind, version) not in ((-8, 1), (-8, 2), (-12, 2)):
        raise ValueError('Unverified CC8 index version or declared size')
    if expected_layout is not None and (kind, version) != expected_layout:
        raise ValueError(f'Unverified CC archive version {(kind, version)}; expected {expected_layout}')
    if not 0 < files <= 1000000 or not 0 < names <= 1000000:
        raise ValueError('Implausible CC8 counts')
    strings_end = 32 + string_size
    read('I', strings_end)  # Serialized separator before the name records.
    at = strings_end + 4
    folders, paths = {}, []
    for i in range(names):
        if version == 1:
            name_offset, parent, sibling, file_marker = read('IHhH', at)
            at += 10
        else:
            name_offset, parent, unused, sibling, file_marker = read('IHHhH', at)
            at += 12
        if name_offset == 0xffffffff:
            continue
        if name_offset >= string_size:
            raise ValueError('CC8 name offset exceeds string table')
        name, _ = string(32 + name_offset, strings_end)
        if parent not in folders and parent not in (0, 65535):
            raise ValueError('CC8 name parent is unresolved')
        prefix = folders.get(parent, '')
        if not name and not prefix and not file_marker and i != names - 1 and parent in (0, 65535):
            folders[i] = ''
            continue
        full = _safe_name(prefix + '/' + name if prefix else name)
        # The terminal name omits its file marker in observed archives. It
        # still has to match a file hash or explicit named-override record.
        if file_marker or i == names - 1:
            paths.append(_safe_name(full))
        else:
            if parent not in folders and parent not in (0, 65535):
                raise ValueError('CC8 folder parent is unresolved')
            folders[i] = full
    validate_paths(paths)
    table_kind, count = read('iI', at)
    at += 8
    if table_kind != kind or count != files:
        raise ValueError('CC8 file table disagrees with header')
    entries = []
    for i in range(files):
        if kind == -12:
            offset, packed, raw = read('QII', at)
            flags = (2 << 24) if raw & 0x80000000 else 0
            raw &= 0x7fffffff
        else:
            high, packed, raw, flags = read('4I', at)
            if flags & 0x00ffff00:
                raise ValueError('Unverified CC8 offset/flag bits')
            offset = (high << 8) + (flags & 255)
        at += 16
        if archive_limit is not None and (offset < 8 or offset + packed > archive_limit):
            raise ValueError('CC8 file bytes exceed archive data region')
        if bool(packed) != bool(raw) or (flags >> 24 == 0 and packed != raw):
            raise ValueError('Invalid CC8 packed/decoded sizes')
        entries.append(dict(offset=offset, packed_size=packed, size=raw, flags=flags >> 24))
    hash_size = 8 if kind == -12 else 4
    hashes = [read('Q' if kind == -12 else 'I', at + i * hash_size) for i in range(files)]
    at += files * hash_size
    by_hash = {value: i for i, value in enumerate(hashes) if value}
    if len(by_hash) != sum(bool(value) for value in hashes):
        raise ValueError('Ambiguous CC8 path hash')
    override_count, override_size = (0, 0) if kind == -12 else read('2I', at)
    at += 0 if kind == -12 else 8
    override_end = at + override_size
    if override_count > files or override_end > len(data):
        raise ValueError('CC8 named override table exceeds bounds')
    overrides = {}
    for _ in range(override_count):
        name, cursor = string(at, override_end)
        # Names include their terminator and pad to an even byte count.
        cursor += (cursor - at) & 1
        if cursor + 2 > override_end:
            raise ValueError('Truncated CC8 named override')
        file_id = read('H', cursor)
        if file_id >= files or hashes[file_id] != 0:
            raise ValueError('CC8 named override must identify a zero-hash entry')
        name = _safe_name(name)
        key = name.casefold()
        if key in overrides or file_id in overrides.values():
            raise ValueError('Duplicate CC8 named override')
        overrides[key] = file_id
        at = cursor + 2
    if at != override_end:
        raise ValueError('CC8 named override size disagrees with records')
    if at != len(data):
        raise ValueError('Unverified bytes after CC8 index tables')
    mapped = {}
    for name in paths:
        if kind == -12:
            value = 0xcbf29ce484222325
            for byte in name.upper().replace('/', '\\').encode('ascii'):
                value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
        else:
            value = path_hash(name)
        file_id = overrides.get(name.casefold(), by_hash.get(value))
        if file_id is None:
            raise ValueError('CC8 path has no verified file reference: ' + name)
        if file_id in mapped:
            raise ValueError('Duplicate CC8 file reference')
        mapped[file_id] = dict(path=name, **entries[file_id])
    if len(mapped) != files:
        raise ValueError(f'CC8 mapped {len(mapped)} of {files} files')
    return [mapped[i] for i in range(files)]


def index(path, *, expected_layout=None):
    path = Path(path)
    if path.suffix.lower() == '.hdr':
        if not 32 <= path.stat().st_size <= MAX_INDEX_BYTES:
            raise ValueError('CC archive header exceeds size limit')
        with path.open('rb') as stream:
            return parse_index(stream.read(MAX_INDEX_BYTES + 1), expected_layout=expected_layout)
    with path.open('rb') as stream:
        header = stream.read(8)
        if len(header) != 8:
            raise ValueError('Truncated DAT archive header')
        offset, size = struct.unpack('<II', header)
        if offset & 0x80000000:
            offset = ((offset ^ 0xffffffff) << 8) + 0x100
        if offset < 8 or not 32 <= size <= MAX_INDEX_BYTES or offset + size > path.stat().st_size:
            raise ValueError('CC8 index lies outside archive')
        stream.seek(offset)
        return parse_index(stream.read(size), archive_limit=offset, expected_layout=expected_layout)

"""Read-only index for observed PC DAT layouts -2, -3, -4 and -5.

Name records form a tree through last-child and previous-sibling indices.
They do not contain the explicit parent field used by the later -6 layout.
Leaf ordinals are cross-checked against stored path hashes; TCS -3 instead
requires a unique full-path hash match because its leaf order differs.
This module only inventories bounded archive ranges; it never extracts files.
"""
from pathlib import Path
import struct
from .archive_paths import safe_path, validate_paths


MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_NAMES = 32768  # Child/sibling fields are signed 16-bit indices.


def _path_hash(path):
    value = 0x811c9dc5
    for byte in path.upper().replace('/', '\\').encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def _safe_segment(name):
    if '/' in name or '\\' in name:
        raise ValueError('Unsafe DAT name segment')
    safe_path(name)


def _parse_index(data, payload_limit, *, name_tags=False, layout=-5):
    """Decode one explicitly selected layout; payload_limit is the index offset."""
    if not isinstance(payload_limit, int) or payload_limit < 8:
        raise ValueError('Invalid DAT payload extent')
    if len(data) > MAX_INDEX_BYTES:
        raise ValueError('DAT index exceeds configured size limit')
    def get(fmt, at):
        size = struct.calcsize('<' + fmt)
        if at < 0 or at + size > len(data):
            raise ValueError('Truncated DAT index')
        return struct.unpack_from('<' + fmt, data, at)
    version, count = get('iI', 0)
    if layout not in (-2, -3, -4, -5) or version != layout:
        raise ValueError(f'Unsupported DAT index version {version}; expected {layout}')
    record_size = 12 if layout == -5 else 8
    if not 0 < count < MAX_NAMES:
        raise ValueError('Unsupported DAT file count')
    names_count_at = 8 + count * 16
    names_count, = get('I', names_count_at)
    if not count < names_count <= MAX_NAMES:
        raise ValueError('Unsupported DAT name count')
    names_at = names_count_at + 4
    string_length_at = names_at + names_count * record_size
    string_length, = get('I', string_length_at)
    strings_at = string_length_at + 4
    hashes_at = strings_at + string_length
    end = hashes_at + count * 4
    if string_length < 1 or end + 8 != len(data) or data[end:] != b'\0' * 8:
        raise ValueError('Unsupported DAT index bounds or trailer')
    strings = data[strings_at:hashes_at]
    nodes = []
    for index in range(names_count):
        row = get('hhiI' if record_size == 12 else 'hhi', names_at + index * record_size)
        child, previous, name_offset = row[:3]
        padding = row[3] if record_size == 12 else 0
        if (padding and not name_tags) or not 0 <= previous < names_count or child >= names_count:
            raise ValueError('Invalid DAT name-tree reference')
        if not 0 <= name_offset < string_length or (name_offset and strings[name_offset-1] != 0):
            raise ValueError('Invalid DAT string reference')
        stop = strings.find(b'\0', name_offset)
        if stop < 0 or stop-name_offset > 1024:
            raise ValueError('Unterminated or overlong DAT name')
        try:
            name = strings[name_offset:stop].decode('ascii')
        except UnicodeDecodeError as error:
            raise ValueError('Unsupported DAT name encoding') from error
        if index:
            _safe_segment(name)
        elif name or previous or child <= 0:
            raise ValueError('Invalid DAT root name record')
        nodes.append((child, previous, name))
    hashes = [get('I', hashes_at + i*4)[0] for i in range(count)]
    if len(set(hashes)) != count:
        raise ValueError('Ambiguous duplicate DAT path hashes')
    hash_ordinals = {value: i for i, value in enumerate(hashes)}
    queue, seen, queued, paths = [(0, '', 0)], set(), {0}, [None] * count
    while queue:
        index, parent, depth = queue.pop()
        if index in seen or depth > 256:
            raise ValueError('Cyclic or multiply-owned DAT name tree')
        seen.add(index)
        child, previous, name = nodes[index]
        path = parent + name
        if len(path) > 4096:
            raise ValueError('DAT path exceeds supported length')
        if child > 0:
            siblings = set()
            while child:
                if child in siblings:
                    raise ValueError('Cyclic DAT sibling chain')
                siblings.add(child)
                if child in queued:
                    raise ValueError('Cyclic or multiply-owned DAT name tree')
                queued.add(child)
                queue.append((child, path+'\\' if path else '', depth+1))
                child = nodes[child][1]
        else:
            ordinal = hash_ordinals.get(_path_hash(path), count) if layout == -3 else -child
            if ordinal >= count or paths[ordinal] is not None:
                raise ValueError('Invalid or duplicate DAT file ordinal')
            if _path_hash(path) != hashes[ordinal]:
                raise ValueError('DAT filename hash does not match its file ordinal')
            paths[ordinal] = path.replace('\\', '/')
    if len(seen) != names_count or any(path is None for path in paths) or len(set(paths)) != count:
        raise ValueError('Incomplete or ambiguous DAT name tree')
    validate_paths(paths)
    result = []
    for index, path in enumerate(paths):
        high_offset, packed, size, flags = get('4I', 8 + index * 16)
        offset = ((high_offset << 8) + (flags >> 24) if layout == -5 else
                  (high_offset << 8) if layout == -4 else
                  (high_offset << 8) + ((flags >> 8) & 255))
        flags &= 0xffffff if layout == -5 else 0xff
        if name_tags:
            # LOTR retains opaque tag bits above the storage-mode byte.
            # Paths still have to match the separate complete file hash table.
            flags &= 0xff
        if flags not in (0, 2):
            raise ValueError(f'Unverified DAT storage flags/mode {flags}; LOTR mode 3 DFLT remains unsupported')
        if offset < 8 or offset > payload_limit or packed > payload_limit-offset:
            raise ValueError('DAT entry is outside its payload extent')
        if not packed or not size or (flags == 0 and packed != size):
            raise ValueError('Invalid DAT entry sizes')
        result.append(dict(path=path, offset=offset, packed_size=packed, size=size, flags=flags))
    return result


def index_v5(path, *, name_tags=False, layout=-5):
    """Return checked entries for an explicit layout (default -5), read-only."""
    path = Path(path)
    with path.open('rb') as source:
        source.seek(0, 2)
        archive_size = source.tell()
        source.seek(0)
        header = source.read(8)
        if len(header) != 8:
            raise ValueError('Truncated DAT archive header')
        offset, size = struct.unpack('<2I', header)
        if offset & 0x80000000:
            offset = ((offset ^ 0xffffffff) << 8) + 256
        if offset < 8 or not 16 <= size <= MAX_INDEX_BYTES or offset > archive_size or size > archive_size-offset:
            raise ValueError('DAT index is outside its archive extent')
        source.seek(offset)
        data = source.read(size)
        if len(data) != size:
            raise ValueError('DAT index could not be read completely')
    return _parse_index(data, offset, name_tags=name_tags, layout=layout)

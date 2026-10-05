"""Read-only index for the observed LMSH1 PC DAT version -5.

Name records form a tree through last-child and previous-sibling indices.
They do not contain the explicit parent field used by the later -6 layout.
Each leaf's negative ordinal is cross-checked against its stored path hash.
This module only inventories bounded archive ranges; it never extracts files.
"""
from pathlib import Path
import struct


MAX_INDEX_BYTES = 64 * 1024 * 1024
MAX_NAMES = 32768  # Child/sibling fields are signed 16-bit indices.


def _path_hash(path):
    value = 0x811c9dc5
    for byte in path.encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def _safe_segment(name):
    if (not name or name in ('.', '..') or name[-1] in '. ' or
            any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)):
        raise ValueError('Unsafe DAT name segment')
    stem = name.split('.', 1)[0].upper()
    if stem in {'CON', 'PRN', 'AUX', 'NUL'} or (len(stem) == 4 and stem[:3] in {'COM', 'LPT'} and stem[3] in '123456789'):
        raise ValueError('Reserved device name in DAT path')


def _parse_index(data, payload_limit, *, name_tags=False):
    """Decode a complete -5 index; payload_limit is its archive file offset."""
    if not isinstance(payload_limit, int) or payload_limit < 8:
        raise ValueError('Invalid DAT payload extent')
    def get(fmt, at):
        size = struct.calcsize('<' + fmt)
        if at < 0 or at + size > len(data):
            raise ValueError('Truncated DAT index')
        return struct.unpack_from('<' + fmt, data, at)
    version, count = get('iI', 0)
    if version != -5:
        raise ValueError(f'Unsupported DAT index version {version}; expected -5')
    if not 0 < count < MAX_NAMES:
        raise ValueError('Unsupported DAT file count')
    names_count_at = 8 + count * 16
    names_count, = get('I', names_count_at)
    if not count < names_count <= MAX_NAMES:
        raise ValueError('Unsupported DAT name count')
    names_at = names_count_at + 4
    string_length_at = names_at + names_count * 12
    string_length, = get('I', string_length_at)
    strings_at = string_length_at + 4
    hashes_at = strings_at + string_length
    end = hashes_at + count * 4
    if string_length < 1 or end + 8 != len(data) or data[end:] != b'\0' * 8:
        raise ValueError('Unsupported DAT index bounds or trailer')
    strings = data[strings_at:hashes_at]
    nodes = []
    for index in range(names_count):
        child, previous, name_offset, padding = get('hhiI', names_at + index * 12)
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
        nodes.append((child, previous, name.upper()))
    hashes = [get('I', hashes_at + i*4)[0] for i in range(count)]
    if len(set(hashes)) != count:
        raise ValueError('Ambiguous duplicate DAT path hashes')
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
            ordinal = -child
            if ordinal >= count or paths[ordinal] is not None:
                raise ValueError('Invalid or duplicate DAT file ordinal')
            if _path_hash(path) != hashes[ordinal]:
                raise ValueError('DAT filename hash does not match its file ordinal')
            paths[ordinal] = path.replace('\\', '/')
    if len(seen) != names_count or any(path is None for path in paths) or len(set(paths)) != count:
        raise ValueError('Incomplete or ambiguous DAT name tree')
    result = []
    for index, path in enumerate(paths):
        high_offset, packed, size, flags = get('4I', 8 + index * 16)
        offset = (high_offset << 8) + (flags >> 24)
        flags &= 0xffffff
        if name_tags:
            # LOTR retains opaque tag bits above the storage-mode byte.
            # Paths still have to match the separate complete file hash table.
            flags &= 0xff
        if flags not in (0, 2):
            raise ValueError('Unverified DAT storage flags')
        if offset < 8 or offset > payload_limit or packed > payload_limit-offset:
            raise ValueError('DAT entry is outside its payload extent')
        if not packed or not size or (flags == 0 and packed != size):
            raise ValueError('Invalid DAT entry sizes')
        result.append(dict(path=path, offset=offset, packed_size=packed, size=size, flags=flags))
    return result


def index_v5(path, *, name_tags=False):
    """Return validated -5 file entries from an installed archive, read-only."""
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
    return _parse_index(data, offset, name_tags=name_tags)

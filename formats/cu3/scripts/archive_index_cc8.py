"""Read the observed TFA .CC40TAD v2/-8 archive index without game runtimes.

This is an inventory reader, not an archive writer. Entries retain compression
flags; callers must use a compatible decoder before treating bytes as a file.
Unknown versions, unresolved names and out-of-bounds tables are rejected.
"""
from pathlib import Path
import argparse
import json
import struct


def path_hash(name):
    value = 0x811c9dc5
    for byte in name.upper().replace('/', '\\').encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def _safe_name(name):
    name = name.replace('\\', '/').upper()
    if not name or name.startswith('/') or ':' in name or any(
            part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('Unsafe CC8 archive path')
    return name


def parse_index(data, archive_limit=None):
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
    if size + 4 != len(data) or magic != b'.CC40TAD' or kind != -8 or version != 2:
        raise ValueError('Unverified CC8 index version or declared size')
    if not 0 < files <= 1000000 or not 0 < names <= 1000000:
        raise ValueError('Implausible CC8 counts')
    strings_end = 32 + string_size
    read('I', strings_end)  # Serialized separator before the name records.
    at = strings_end + 4
    folders, paths = {}, []
    for i in range(names):
        name_offset, parent, unused, sibling, file_marker = read('IHHhH', at)
        at += 12
        if name_offset == 0xffffffff:
            continue
        if name_offset >= string_size:
            raise ValueError('CC8 name offset exceeds string table')
        name, _ = string(32 + name_offset, strings_end)
        prefix = folders.get(parent, '')
        full = (prefix + '\\' + name).lstrip('\\')
        # The terminal name omits its file marker in observed archives. It
        # still has to match a file hash or explicit named-override record.
        if file_marker or i == names - 1:
            paths.append(_safe_name(full))
        else:
            if parent not in folders and parent not in (0, 65535):
                raise ValueError('CC8 folder parent is unresolved')
            folders[i] = full
    table_kind, count = read('iI', at)
    at += 8
    if table_kind != -8 or count != files:
        raise ValueError('CC8 file table disagrees with header')
    entries = []
    for i in range(files):
        high, packed, raw, flags = read('4I', at)
        at += 16
        if flags & 0x00ffff00:
            raise ValueError('Unverified CC8 offset/flag bits')
        offset = (high << 8) + (flags & 255)
        if archive_limit is not None and (offset < 8 or offset + packed > archive_limit):
            raise ValueError('CC8 file bytes exceed archive data region')
        entries.append(dict(offset=offset, packed_size=packed, size=raw, flags=flags >> 24))
    hashes = [read('I', at + i * 4) for i in range(files)]
    at += files * 4
    by_hash = {value: i for i, value in enumerate(hashes) if value}
    if len(by_hash) != sum(bool(value) for value in hashes):
        raise ValueError('Ambiguous CC8 path hash')
    override_count, override_size = read('2I', at)
    at += 8
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
        if name in overrides or file_id in overrides.values():
            raise ValueError('Duplicate CC8 named override')
        overrides[name] = file_id
        at = cursor + 2
    if at != override_end:
        raise ValueError('CC8 named override size disagrees with records')
    mapped = {}
    for name in paths:
        file_id = overrides.get(name, by_hash.get(path_hash(name)))
        if file_id is None:
            raise ValueError('CC8 path has no verified file reference: ' + name)
        if file_id in mapped:
            raise ValueError('Duplicate CC8 file reference')
        mapped[file_id] = dict(path=name, **entries[file_id])
    if len(mapped) != files:
        raise ValueError(f'CC8 mapped {len(mapped)} of {files} files')
    return [mapped[i] for i in range(files)]


def index(path):
    path = Path(path)
    if path.suffix.lower() == '.hdr':
        return parse_index(path.read_bytes())
    with path.open('rb') as stream:
        header = stream.read(8)
        if len(header) != 8:
            raise ValueError('Truncated DAT archive header')
        offset, size = struct.unpack('<II', header)
        if offset & 0x80000000:
            offset = ((offset ^ 0xffffffff) << 8) + 0x100
        if offset < 8 or size < 32 or offset + size > path.stat().st_size:
            raise ValueError('CC8 index lies outside archive')
        stream.seek(offset)
        return parse_index(stream.read(size), archive_limit=offset)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output filename')
    rows = index(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(rows, stream, indent=2)
    print(f'{len(rows)} verified file entries; {sum(r["path"].endswith(".CU3") for r in rows)} CU3 files')

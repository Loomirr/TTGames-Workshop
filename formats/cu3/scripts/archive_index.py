"""Read-only Batman 3 DAT index inventory; observed -6 layout from ttgames.bms."""
from pathlib import Path
import struct, json, argparse, zlib

def index(path):
    path = Path(path)
    with path.open('rb') as f:
        off, size = struct.unpack('<II', f.read(8))
        if off & 0x80000000:
            off = ((off ^ 0xffffffff) << 8) + 0x100
        f.seek(off)
        data = f.read(size)
    ver, count = struct.unpack_from('<iI', data)
    if ver != -6:
        raise ValueError(f'Unsupported DAT index {ver}')
    names_at = 8 + count * 16
    names_count, = struct.unpack_from('<I', data, names_at)
    entries_at = names_at + 4
    strings_at = entries_at + names_count * 12 + 4
    crc_at = strings_at + struct.unpack_from('<I', data, strings_at - 4)[0]
    hashes = dict((struct.unpack_from('<I', data, crc_at + i * 4)[0], i) for i in range(count))
    result, paths = [], {}
    current = ''
    for n in range(names_count):
        next_, prev, no, unk = struct.unpack_from('<hhiI', data, entries_at + n * 12)
        name = '' if no < 0 else data[strings_at + no:data.index(0, strings_at + no)].decode('ascii')
        current = paths.get(unk, '')
        paths[n] = current
        if next_ > 0:
            # Stored prev references the containing path, before this name.
            paths[n] = current + name + '\\'
            continue
        if not name:
            continue
        full = (current + name).lstrip('\\').upper()
        h = 0x811c9dc5
        for b in full.encode('ascii'):
            h = ((h ^ b) * 0x199933) & 0xffffffff
        if h not in hashes:
            raise ValueError(f'Unmatched DAT path hash: {full}')
        i = hashes[h]
        lo, packed_size, raw_size, flagword = struct.unpack_from('<4I', data, 8 + i * 16)
        result.append(dict(path=full.replace('\\','/'), offset=(lo << 8) + (flagword >> 24), size=raw_size, packed_size=packed_size, flags=flagword & 0xffffff))
    return result

def extract(path, entry, dest):
    with Path(path).open('rb') as f:
        f.seek(entry['offset'])
        data = f.read(entry['packed_size'])
    out = bytearray()
    if data[:4] in (b'DFLT', b'ZLIB'):
        pos = 0
        while pos < len(data):
            magic, compressed, raw = struct.unpack_from('<4sII', data, pos)
            chunk = data[pos + 12:pos + 12 + compressed]
            if compressed == raw:
                decoded = chunk
            elif magic == b'DFLT':
                decoded = zlib.decompress(chunk, -15)
            elif magic == b'ZLIB':
                decoded = zlib.decompress(chunk)
            else:
                raise ValueError(f'Unsupported chunk {magic}')
            if len(decoded) != raw:
                raise ValueError('DAT chunk size mismatch')
            out.extend(decoded)
            pos += 12 + compressed
        data = bytes(out)
    elif data[:4] in (b'LZ2K', b'LZMA', b'ZIPX', b'RFPK', b'RNC_'):
        raise ValueError(f'Compression requires QuickBMS: {data[:4]!r}')
    if len(data) != entry['size']:
        raise ValueError('DAT extracted size mismatch')
    target = Path(dest) / entry['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('archive', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--extract-cutscenes', action='store_true')
    args = ap.parse_args()
    entries = index(args.archive)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / (args.archive.stem + '-index.json')).write_text(json.dumps(entries, indent=2))
    cuts = [e for e in entries if e['path'].endswith('.CU3')]
    print(args.archive.name, 'entries', len(entries), 'CU3', len(cuts), flush=True)
    if args.extract_cutscenes:
        for e in cuts:
            extract(args.archive, e, args.output / 'Extracted')
        for e in entries:
            if e['path'].startswith('CUT/') and e['path'].endswith(('.TXT','.SUB','.LED')):
                extract(args.archive, e, args.output / 'Extracted')
        print('Extracted CU3 and CUT text companions', flush=True)

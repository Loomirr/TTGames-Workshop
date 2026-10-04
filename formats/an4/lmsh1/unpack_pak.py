"""Read TT 0x1234567a PAKs; unpack Deflate_v1.0 members without changing input.

Container layout reference: Luigi Auriemma's ttgames.bms, EXTRACT_1234567a.
This tool deliberately supports only the format observed in the local PC copy.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import subprocess


def unpack(source: Path, destination: Path, quickbms: Path, bms: Path):
    data = source.read_bytes()
    magic, count, total, archive_crc, zero1, zero2 = struct.unpack_from('<6I', data)
    if magic != 0x1234567A or total != len(data) or 24 + count * 28 > total:
        raise ValueError(f'Invalid or unsupported PAK: {source}')
    destination.mkdir(parents=True, exist_ok=True)
    # TT's DFLT codec is not interchangeable with Python's raw DEFLATE.
    # Keep its proven decoder external until its bitstream is independently understood.
    if count:
        subprocess.run([str(quickbms.resolve()), '-k', str(bms.resolve()),
                        str(source.resolve()), str(destination.resolve())],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    records = []
    for i in range(count):
        name_off, offset, size, kind, reserved1, crc, reserved2 = struct.unpack_from('<7I', data, 24 + i * 28)
        if name_off >= total or offset + size > total:
            raise ValueError(f'Entry {i} is out of bounds')
        name = data[name_off:data.index(b'\0', name_off)].decode('ascii')
        relative = PurePosixPath(name.replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts or ':' in name:
            raise ValueError(f'Unsafe entry name: {name}')
        payload = data[offset:offset + size]
        compression = None
        if payload[:32].rstrip(b'\0') == b'Deflate_v1.0':
            expected, = struct.unpack_from('<I', payload, 32)
            payload = destination.joinpath(*relative.parts).read_bytes()
            if len(payload) != expected:
                raise ValueError(f'Decompressed size mismatch: {name}')
            compression = 'TT DFLT (QuickBMS)'
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(payload)
        if target.read_bytes() != payload:
            raise ValueError(f'Existing output differs: {target}')
        records.append(dict(name=name, offset=offset, stored_bytes=size,
                            extracted_bytes=len(payload), compression=compression,
                            kind=kind, crc=f'{crc:08x}',
                            sha256=hashlib.sha256(payload).hexdigest()))
    return dict(source=str(source.resolve()), source_sha256=hashlib.sha256(data).hexdigest(),
                destination=str(destination.resolve()), count=count, entries=records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path, help='PAK file or tree of extracted files')
    parser.add_argument('destination', type=Path)
    refs = Path(__file__).resolve().parent.parent / 'references'
    parser.add_argument('--quickbms', type=Path, default=refs / 'quickbms.exe')
    parser.add_argument('--bms', type=Path, default=refs / 'ttgames.bms')
    args = parser.parse_args()
    sources = [args.source] if args.source.is_file() else sorted(args.source.rglob('*.PAK'))
    manifests = []
    for source in sources:
        relative = Path(source.stem) if args.source.is_file() else source.relative_to(args.source).with_suffix('')
        manifest = unpack(source, args.destination / relative, args.quickbms, args.bms)
        manifests.append(manifest)
        if manifest['count']:
            print(f"{source.name}: {manifest['count']} members")
    args.destination.mkdir(parents=True, exist_ok=True)
    (args.destination / 'pak-manifest.json').write_text(json.dumps(manifests, indent=2), encoding='utf-8')
    print(f"Total: {sum(m['count'] for m in manifests)} members in {len(manifests)} PAKs")

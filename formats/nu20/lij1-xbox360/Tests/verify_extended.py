"""Check exported extended resources against their supplied source allocations.

Requires Pillow. No game data is bundled. Point --exports at selected exports
and --sources at the corresponding extracted game tree. Writes a new report.
The address equations are independently evaluated in Python, with Xenia's
BSD-3-Clause attribution in ../THIRD_PARTY_NOTICES.txt.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
from PIL import Image


def address(x, y, pitch, size):
    # Separate bank/pipe selection from the micro/macro tile offset.
    macro = ((y // 32) * (pitch // 32) + x // 32) * 64
    micro = ((y // 2) % 8) * 8 + x % 8
    offset = (macro + micro) * size
    pipe = (x // 8 % 4) ^ (y // 8 % 2 * 2)
    return ((y % 2) * 16 + pipe * 64 + (y // 16 % 2) * 2048
            + offset % 16 + (offset // 16 % 2) * 32
            + (offset // 32 % 8) * 256 + (offset // 256) * 4096)


def linear_mips(source, t):
    w, h, size = t['Width'], t['Height'], t['BlockBytes']
    unit = 1 if t['FormatCode'] == 9 else 4
    count, faces = t['MipCount'], t.get('Faces', 1)
    packed = t.get('PackedMips', True) and count > 1
    tail = max(0, min(w.bit_length(), h.bit_length()) - 5)
    face_size = t['PayloadBytes'] // faces
    units = lambda n: max(1, (n + unit - 1) // unit)
    align = lambda n: (n + 31) // 32 * 32
    swap = 4 if unit == 1 else 2
    for face in range(faces):
        storage = 0
        for level in range(count):
            mw, mh = max(1, w >> level), max(1, h >> level)
            bw, bh = units(mw), units(mh)
            pitch, x0, y0 = align(bw), 0, 0
            if packed and level >= tail:
                pitch = align(units(max(1, w >> tail)))
                p = level - tail
                if p < 3:
                    if w > h:
                        y0 = (16 >> p) // unit
                    else:
                        x0 = (16 >> p) // unit
                else:
                    delta = ((max(w, h) >> tail) >> (p - 2)) // unit
                    if w > h:
                        x0 = delta
                    else:
                        y0 = delta
            result = bytearray(bw * bh * size)
            for y in range(bh):
                for x in range(bw):
                    relative = storage + address(x + x0, y + y0, pitch, size)
                    assert relative + size <= face_size
                    at = t['PayloadOffset'] + face * face_size + relative
                    data = source[at:at + size]
                    reordered = b''.join(data[j:j + swap][::-1] for j in range(0, size, swap))
                    dest = (y * bw + x) * size
                    result[dest:dest + size] = reordered
            yield face, level, mw, mh, bytes(result)
            if not packed or level < tail:
                storage += pitch * align(bh) * size


def verify(sources, exports, report):
    candidates = {}
    for p in sources.rglob('*'):
        if p.is_file():
            candidates.setdefault(p.name.lower(), []).append(p)
    records, formats = [], set()
    compared = decoded = float_pixels = raw = passthrough = 0
    previews = report.parent / (report.stem + '_previews')
    previews.mkdir(exist_ok=False)
    for manifest_path in sorted(exports.rglob('Extraction.json')):
        manifest = json.loads(manifest_path.read_text())
        possible = candidates.get(manifest['source'].lower(), [])
        matches = [p for p in possible if hashlib.sha256(p.read_bytes()).hexdigest() == manifest['sourceSha256']]
        assert matches, manifest['source']
        source = matches[0].read_bytes()
        for item in manifest['outputs']:
            t = item['texture']
            data = (manifest_path.parent / item['file']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == item['sha256']
            if t.get('RawOnly', False):
                assert data == source[t['PayloadOffset']:t['PayloadOffset'] + t['PayloadBytes']]
                raw += 1
                continue
            if t['FormatCode'] == -1:
                assert data == source
                passthrough += 1
                continue
            fmt = t['FormatCode']; formats.add(fmt)
            assert data[:4] == b'DDS '
            header = list(struct.unpack('<31I', data[4:128]))
            assert (header[3], header[2], header[6]) == (t['Width'], t['Height'], t['MipCount'])
            assert header[27] == (0xfe00 if t.get('Faces', 1) == 6 else 0)
            if fmt in (4, 9):
                assert data[84:88] == b'DX10'
                assert struct.unpack_from('<5I', data, 128) == (83 if fmt == 4 else 2, 3, 0, 1, 0)
                pos = 148
            else:
                assert data[84:88].decode() == {1: 'DXT1', 3: 'DXT3', 6: 'DXT5'}[fmt]
                pos = 128
            for face, level, mw, mh, linear in linear_mips(source, t):
                assert data[pos:pos + len(linear)] == linear, (item['file'], face, level)
                compared += 1
                if fmt == 9:
                    assert len(linear) == mw * mh * 16
                    # Preserve all IEEE-754 bit patterns, including any NaNs.
                    float_pixels += mw * mh
                else:
                    one = header.copy()
                    one[1], one[2], one[3], one[4], one[6], one[26], one[27] = 0x81007, mh, mw, len(linear), 1, 0x1000, 0
                    image_data = b'DDS ' + struct.pack('<31I', *one)
                    if fmt == 4:
                        image_data += data[128:148]
                    image = Image.open(io.BytesIO(image_data + linear)).convert('RGBA')
                    image.load(); decoded += 1
                    if level == 0:
                        image.thumbnail((256, 256))
                        image.save(previews / f'{manifest_path.parent.name}_{t["Index"]:03d}_face{face}.png')
                pos += len(linear)
            assert pos == len(data), item['file']
            records.append(dict(source=manifest['source'], output=item['file'], format=fmt,
                                faces=t.get('Faces', 1), mips=t['MipCount']))
        assert hashlib.sha256(matches[0].read_bytes()).hexdigest() == manifest['sourceSha256']
    result = dict(resources=len(records), compared_face_mips=compared, pillow_decoded_mips=decoded,
                  float_pixels_checked=float_pixels, raw_allocations_checked=raw,
                  unchanged_dds_checked=passthrough, formats=sorted(formats), records=records)
    report.write_text(json.dumps(result, indent=2))
    print({k: v for k, v in result.items() if k != 'records'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--exports', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Use a new report path.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    verify(args.sources, args.exports, args.report)

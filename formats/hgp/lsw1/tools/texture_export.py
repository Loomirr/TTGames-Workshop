"""Extract or replace an existing LSW1 PC embedded DDS without rebuilding HGP."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from material_export import MAX_BYTES, material_slots, write_new


def texture_slots(data):
    material_slots(data)  # Reviewed PC header/material layout, not another HGP family.
    at = 0x30 + struct.unpack_from('<I', data, 8)[0]
    if not 0x30 <= at <= len(data) - 12:
        raise ValueError('Invalid texture table range')
    relative, size, count = struct.unpack_from('<3I', data, at)
    if not 0 <= count <= 4096 or at + 12 + count * 20 > len(data):
        raise ValueError('Invalid texture table count')
    base = at + 12 + relative
    if relative < count * 20 or base + size > len(data):
        raise ValueError('Invalid texture data range')
    if count == 0:
        return []
    offsets = [struct.unpack_from('<I', data, at + 28 + i * 20)[0]
               for i in range(count)] + [size]
    if offsets[0] != 0 or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError('Unsupported texture offsets')
    slots = [(base + a, base + b) for a, b in zip(offsets, offsets[1:])]
    for start, end in slots:
        dds_layout(data[start:end], allow_padding=True)
    return slots


def dds_layout(data, *, allow_padding=False):
    """Accept complete 2D DXT1/3/5 mip chains, with no extra surfaces or padding."""
    if len(data) < 128 or data[:4] != b'DDS ':
        raise ValueError('Expected a complete DDS texture')
    header = struct.unpack_from('<31I', data, 4)
    size, flags, height, width, pitch, depth, mips = header[:7]
    pf_size, pf_flags = header[18:20]
    fourcc = data[84:88]
    if size != 124 or pf_size != 32 or pf_flags != 4 or fourcc not in (b'DXT1', b'DXT3', b'DXT5'):
        raise ValueError('Only the reviewed DXT1/DXT3/DXT5 DDS layouts are writable')
    if depth not in (0, 1) or header[27] != 0:
        raise ValueError('Cubemap, volume and additional DDS surfaces are unsupported')
    if not 1 <= width <= 16384 or not 1 <= height <= 16384:
        raise ValueError('Invalid DDS dimensions')
    levels = mips or 1
    if not 1 <= levels <= max(width, height).bit_length():
        raise ValueError('Invalid DDS mip count')
    block = 8 if fourcc == b'DXT1' else 16
    payload = sum(((max(1, width >> level) + 3) // 4)
                  * ((max(1, height >> level) + 3) // 4) * block
                  for level in range(levels))
    length = 128 + payload
    padding = data[length:]
    # Original exports pad each DDS to 128 bytes, then may start another
    # padding run at the end of the texture allocation. Preserve both runs.
    first = min(len(padding), (-length) % 128)
    pad = lambda size: (b'padding' * ((size + 6) // 7))[:size]
    expected_padding = pad(first) + pad(len(padding) - first)
    if len(data) < length or (padding and (not allow_padding or padding != expected_padding)):
        raise ValueError('DDS payload does not match its dimensions and mip count')
    return dict(width=width, height=height, mips=levels, format=fourcc.decode('ascii'), bytes=length)


def replace_texture(data, source_sha256, index, replacement):
    if hashlib.sha256(data).hexdigest() != source_sha256:
        raise ValueError('Source SHA-256 does not match')
    slots = texture_slots(data)
    if type(index) is not int or not 0 <= index < len(slots):
        raise ValueError('Texture ID is unavailable')
    start, end = slots[index]
    original = dds_layout(data[start:end], allow_padding=True)
    dds_layout(replacement)
    if len(replacement) != original['bytes'] or replacement[:128] != data[start:start + 128]:
        raise ValueError('Replacement must preserve the original DDS header, format, dimensions and mip count')
    return data[:start] + replacement + data[start + len(replacement):]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'extract', 'replace'))
    parser.add_argument('input', type=Path)
    parser.add_argument('--texture', type=int)
    parser.add_argument('--source-sha256')
    parser.add_argument('--dds', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        slots = texture_slots(data)
        digest = hashlib.sha256(data).hexdigest()
        if args.operation == 'inspect':
            if any(x is not None for x in (args.texture, args.source_sha256, args.dds, args.output)):
                parser.error('inspect does not take edit/extract options')
            result = dict(source_sha256=digest, textures=[dict(id=i, **dds_layout(data[a:b], allow_padding=True))
                          for i, (a, b) in enumerate(slots)])
        else:
            if args.output is None or args.texture is None or not 0 <= args.texture < len(slots):
                parser.error('Choose --texture from inspect and a new --output path')
            start, end = slots[args.texture]
            if args.operation == 'extract':
                if args.dds is not None or args.source_sha256 is not None:
                    parser.error('--dds and --source-sha256 belong to replace')
                output = data[start:start + dds_layout(data[start:end], allow_padding=True)['bytes']]
            else:
                if args.dds is None or args.source_sha256 is None:
                    parser.error('replace requires --dds and --source-sha256')
                with args.dds.open('rb') as stream:
                    replacement = stream.read(MAX_BYTES + 1)
                output = replace_texture(data, args.source_sha256, args.texture, replacement)
            write_new(args.output, output)
            result = dict(operation=args.operation, source_sha256=digest,
                          output_sha256=hashlib.sha256(output).hexdigest(), bytes=len(output))
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, struct.error) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()

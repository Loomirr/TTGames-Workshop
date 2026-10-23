"""Source-preserving LSW1 PC material recoloring; no model rebuilding."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


MAX_BYTES = 128 * 1024 * 1024


def material_slots(data):
    """Accept the contiguous 0xb4-byte material records observed in PC originals."""
    if not 0xb0 <= len(data) <= MAX_BYTES:
        raise ValueError('Unsupported HGP file size')
    header = struct.unpack_from('<12I', data)
    if header[0] != 0 or header[1] not in (0x14, 0x28, 0x30, 0x36):
        raise ValueError('Expected an original LSW1 PC HGP')
    start, end = header[3:5]
    body_size = len(data) - 0x30
    if not 0x40 <= start < end <= body_size or start + 4 > end:
        raise ValueError('Invalid material block range')
    count = struct.unpack_from('<I', data, 0x30 + start)[0]
    if not 1 <= count <= 4096 or start + 4 + count * (4 + 0xb4) != end:
        raise ValueError('Unsupported material block layout')
    slots = []
    for index in range(count):
        pointer = struct.unpack_from('<I', data, 0x30 + start + 4 + index * 4)[0]
        expected = start + 4 + count * 4 + index * 0xb4
        if pointer != expected:
            raise ValueError('Unsupported material pointer layout')
        slots.append(0x30 + pointer + 0x54)
    return slots


def recolor(data, source_sha256, edits):
    """Patch only native RGB float fields; all other source bytes remain identical.

    edits maps zero-based material IDs to three native palette values in [0, 1].
    This does not read Blender nodes or convert Blender linear colors.
    """
    if hashlib.sha256(data).hexdigest() != source_sha256:
        raise ValueError('Source SHA-256 does not match')
    slots = material_slots(data)
    result = bytearray(data)
    for index, color in edits.items():
        if type(index) is not int or not 0 <= index < len(slots):
            raise ValueError('Material ID is unavailable')
        if not isinstance(color, (list, tuple)) or len(color) != 3 or any(
            type(value) not in (int, float) or not math.isfinite(value)
            or not 0 <= value <= 1 for value in color
        ):
            raise ValueError('RGB must contain three finite native values from 0 to 1')
        struct.pack_into('<3f', result, slots[index], *color)
    return bytes(result)


def write_new(path, data):
    # Exclusive creation also refuses existing sources, symlinks and hard links.
    with Path(path).open('xb') as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'recolor'))
    parser.add_argument('input', type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--material', type=int)
    parser.add_argument('--rgb', nargs=3, type=float)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        slots = material_slots(data)
        digest = hashlib.sha256(data).hexdigest()
        if args.operation == 'inspect':
            if any(value is not None for value in (
                args.source_sha256, args.material, args.rgb, args.output
            )):
                parser.error('Edit options require recolor')
            report = dict(source_sha256=digest, materials=[
                dict(id=i, rgb=struct.unpack_from('<3f', data, offset))
                for i, offset in enumerate(slots)])
        else:
            if any(value is None for value in (
                args.source_sha256, args.material, args.rgb, args.output
            )):
                parser.error('recolor requires --source-sha256, --material, --rgb and --output')
            edited = recolor(data, args.source_sha256, {args.material: args.rgb})
            write_new(args.output, edited)
            report = dict(source_sha256=digest,
                          output_sha256=hashlib.sha256(edited).hexdigest(),
                          changed_bytes=sum(a != b for a, b in zip(data, edited)),
                          material=args.material, rgb=args.rgb,
                          scope='Native material RGB only; in-game validation required')
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, struct.error) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()

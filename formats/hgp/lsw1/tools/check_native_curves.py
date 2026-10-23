"""Compare scalar curves with original LSW1 PC instructions in isolation.

Optional research dependencies: pefile and unicorn. Supply your own original
EXE and extracted ANI/BSA folder. Never launches or patches an installed game.
The time context is synthesized; this checks the curve evaluator, not its
caller, skeleton mapping, scene playback, or gameplay.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct

from animation_records import AnimationRecords, AnimationError


EXE_SHA256 = '49f74d802596b72b8da24b76f98f249dfdb370d5607fa7e65e3a19beb833d473'


def compare(executable, inputs):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP

    raw = executable.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXE_SHA256:
        raise ValueError('This native comparison requires the documented original PC executable hash')
    pe = pefile.PE(data=raw)
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(base, (len(image) + 4095) & ~4095)
    machine.mem_write(base, image)
    scratch = 0x20000000
    machine.mem_map(scratch, 0x200000)
    # Runtime popcount lookup used by the original curve routine.
    machine.mem_write(0x3384c80, bytes(i.bit_count() for i in range(256)))
    stop, trampoline, result = scratch, scratch + 0x100, scratch + 0x200
    context, slot, data_at, stack = scratch + 0x300, scratch + 0x400, scratch + 0x1000, scratch + 0x1ff000
    # Store the x87 return as float32, as the game's callers do.
    machine.mem_write(trampoline, b'\xd9\x1d' + struct.pack('<I', result) +
                      b'\xe9' + struct.pack('<i', stop - (trampoline + 11)))
    counts = Counter()
    mismatches, refused = [], []
    maximum = 0.
    for path in sorted(inputs.rglob('*')):
        family = path.suffix.upper()[1:]
        if not path.is_file() or family not in ('ANI', 'BSA'):
            continue
        relative = str(path.relative_to(inputs))
        try:
            with path.open('rb') as stream:
                data = stream.read(0x1e0000 + 1)
            if len(data) > 0x1e0000:
                raise ValueError('Input exceeds isolated native comparison buffer')
            clip = AnimationRecords(data, family)
        except (OSError, ValueError) as error:
            refused.append(dict(file=relative, error=str(error)))
            continue
        patched = bytearray(data)
        for curve in clip._curves.values():
            for offset in (curve['address'], curve['address'] + 4, curve['address'] + 8):
                struct.pack_into('<I', patched, offset, clip.pointer(offset) + data_at)
        machine.mem_write(data_at, bytes(patched))
        seen = set()
        for channel, curve in enumerate(clip.records):
            if not curve['kind'] or curve['address'] in seen:
                continue
            seen.add(curve['address'])
            machine.mem_write(slot, struct.pack('<I', data_at + curve['address']))
            times = {1., clip.duration - .01, clip.duration / 2 + .25}
            for frame in curve['mask_frames'][:2] + curve['mask_frames'][-2:]:
                times.update((float(frame + 1), frame + 1.375))
            for time in sorted(times):
                if not 1 <= time < clip.duration:
                    continue
                try:
                    expected = clip.evaluate_channel(channel // clip.components, channel % clip.components, time)
                except AnimationError as error:
                    refused.append(dict(file=relative, channel=channel, time=time, error=str(error)))
                    continue
                t = struct.unpack('<f', struct.pack('<f', time))[0]
                if t >= clip.duration:
                    t = struct.unpack('<f', struct.pack('<f', clip.duration - .01))[0]
                frame = int(t) - 1
                block, bit = min(frame // 32, clip.blocks - 1), frame % 32
                machine.mem_write(context, struct.pack('<ff4I', t, t - block * 32, block,
                                                       (1 << (bit % 8 + 1)) - 1, bit // 8, bit))
                machine.mem_write(stack, struct.pack('<4I', trampoline, slot, context, curve['kind']))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.emu_start(0x4fa090, stop, count=10000)
                if machine.reg_read(UC_X86_REG_EIP) != stop:
                    raise RuntimeError('Native curve execution did not return within its instruction limit')
                native = struct.unpack('<f', machine.mem_read(result, 4))[0]
                difference = abs(expected - native)
                maximum = max(maximum, difference)
                counts['samples'] += 1
                counts[f'type_{curve["kind"]}'] += 1
                if not math.isfinite(native) or difference > max(2e-5, abs(native) * 2e-6):
                    counts['mismatches'] += 1
                    if len(mismatches) < 100:
                        mismatches.append(dict(file=relative, channel=channel, time=time,
                                               python=expected, native=native))
        counts['files'] += 1
    return dict(counts=dict(counts), max_absolute_error=maximum, mismatches=mismatches,
                refused=refused, executable_sha256=EXE_SHA256,
                scope='Isolated scalar evaluator; synthesized time context; no game startup or rig playback')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    if not args.inputs.is_dir():
        parser.error('inputs must be an extracted ANI/BSA directory')
    if args.report.exists():
        parser.error('Choose a new report path')
    report = compare(args.executable, args.inputs)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report['counts']))
    if not report['counts'].get('samples') or report['counts'].get('mismatches'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

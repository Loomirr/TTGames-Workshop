"""Compare sampled ANI local transforms with isolated original PC instructions.

Requires pefile/unicorn. Uses pre-sampled constant channels, a synthesized sine
table and no gameplay overrides. This checks transform math, not clip ownership.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import sys

from animation_pose import IDENTITY, local_transform
from animation_records import AnimationRecords
from check_native_curves import EXE_SHA256


def compare(executable, model_path, animation_path):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from hgp import HGP
    raw = executable.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXE_SHA256:
        raise ValueError('Unsupported executable hash')
    pe = pefile.PE(data=raw); image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(base, (len(image)+4095)&~4095); machine.mem_write(base, image)
    scratch = 0x20000000; machine.mem_map(scratch, 0x200000)
    machine.mem_write(0x33fe500, struct.pack('<32768f', *[
        math.sin(i*math.tau/32768) for i in range(32768)]))
    values, types, context, joint_at, scales, parent_scale, output = [scratch+i*256 for i in range(1,8)]
    stack = scratch + 0x1ff000
    machine.mem_write(parent_scale, struct.pack('<3f', 1, 1, 1))
    maximum = 0.; cases = 0

    def check(sample, flags, joint, pivot, joint_flags, parent=(1.,1.,1.)):
        nonlocal maximum, cases
        sample = struct.unpack('<9f', struct.pack('<9f', *sample))
        parent = struct.unpack('<3f', struct.pack('<3f', *parent))
        machine.mem_write(parent_scale, struct.pack('<3f', *parent))
        machine.mem_write(values, struct.pack('<9f', *sample))
        machine.mem_write(joint_at, struct.pack('<16f', *joint))
        machine.mem_write(joint_at+64, struct.pack('<3f', *pivot))
        machine.mem_write(joint_at+81, bytes([joint_flags]))
        args = [values, types, flags, context, joint_at, scales, parent_scale, output, 0, 0, 0]
        machine.mem_write(stack, struct.pack('<12I', scratch, *args))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.emu_start(0x3b67505, scratch, count=10000)
        if machine.reg_read(UC_X86_REG_EIP) != scratch:
            raise RuntimeError('Native pose evaluator exceeded the instruction limit')
        native = struct.unpack('<16f', machine.mem_read(output, 64))
        native_scale = struct.unpack('<3f', machine.mem_read(scales, 12))
        expected, expected_scale = local_transform(sample, flags, joint, pivot, joint_flags, parent)
        error = max(abs(a-b) for a,b in zip((*native,*native_scale), (*expected,*expected_scale)))
        if not all(math.isfinite(v) for v in native) or error > 2e-6:
            raise AssertionError((flags, joint_flags, error, native, expected))
        maximum = max(maximum, error); cases += 1
        return native_scale

    rng = random.Random(81)
    joint = list(IDENTITY); joint[:3] = (0,1,0); joint[4:7] = (-1,0,0)
    for _ in range(1000):
        check([rng.uniform(-2,2) for _ in range(9)], rng.choice((0,1,8,9,0x23,0x2b,0x10,0x19,0x3b)),
              joint, (.2,-.1,.3), rng.choice((0,8)),
              tuple(rng.choice((-1,1))*rng.uniform(.5,4) for _ in range(3)))
    model = HGP(model_path)
    clip = AnimationRecords(animation_path.read_bytes(), 'ANI')
    if clip.tracks != model.count:
        raise ValueError('Supply an explicit research pair with matching track/bone tables')
    for time in (1., 1.5, clip.duration*.25, clip.duration*.5, clip.duration-1.01):
        inherited = []
        for i in range(clip.tracks):
            at = model.joints_at+i*96
            parent = model.bones[i]['parent']
            inherited.append(check([clip.evaluate_channel(i,c,time) for c in range(9)], clip.flags[i],
                  model.floats(at,16), model.floats(at+64,3), model.body[at+81],
                  inherited[parent] if parent >= 0 else (1.,1.,1.)))
    return dict(cases=cases, maximum_error=maximum, model=model_path.name,
                animation=animation_path.name, model_sha256=hashlib.sha256(model.data).hexdigest(),
                animation_sha256=clip.sha256, executable_sha256=EXE_SHA256,
                scope='Original local-transform and inherited-scale code with pre-sampled constants; synthesized sine table; no gameplay overrides, ownership or in-game validation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('executable','model','animation','output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Choose a new output report')
    report = compare(args.executable, args.model, args.animation)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

"""Check ordinary and special-material fallback selection against original x86 code.

Requires pefile and unicorn. Uses synthetic draw/geometry/material structures;
does not load game assets, initialize Direct3D, or run the executable as a game.
Runtime overrides, lighting-mode-2 shadow helpers and MRT are outside this check.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct

from check_native_curves import EXE_SHA256


def observe(path):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP

    with path.open('rb') as stream:
        raw = stream.read(128 * 1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != EXE_SHA256:
        raise ValueError('Unsupported executable hash for native effect comparison')
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(base, (len(image) + 4095) & ~4095)
    machine.mem_write(base, image)
    scratch = 0x20000000
    machine.mem_map(scratch, 0x10000)
    sentinel = scratch + 0xff00

    def put(address, value):
        machine.mem_write(address, struct.pack('<I', value))

    # Explicit ordinary-render scenario, rather than relying on PE BSS zeros.
    for address in (0x3008990, 0x30089b0, 0x30089d0, 0x2bff0d4,
                    0x2bff0d8, 0x3008980, 0x3008984):
        put(address, 0)

    def restrict_execution(machine, address, size, data):
        if not (0x52f300 <= address < 0x52fa30 or address == 0x405e20):
            raise ValueError(f'Effect selection left the checked function at {address:#x}')

    machine.hook_add(UC_HOOK_CODE, restrict_execution)
    cases = []
    # Lighting modes 0, 1 and 3 follow the observed dynamic-lighting branch.
    # Mode 2 calls runtime shadow/capability helpers and is deliberately absent.
    inputs = itertools.product((0x59, 0x5d), (False, True), (False, True),
                               (False, True), (0, 1, 3), range(16),
                               ((0, False, False, 0.), (129, False, False, 0.), (135, False, False, 0.), (145, False, False, 0.), (135, True, False, 0.), (145, False, True, 0.), (135, True, True, 0.), (135, True, True, .5)))
    for vertex_type, skin_data, morph_data, morph_weights, lighting, blend, (effect_byte, bump_enabled, reflections, reflection_scalar) in inputs:
        put(0x3008984, int(bump_enabled))
        put(0x3008980, int(reflections))
        machine.mem_write(scratch, b'\0' * 0x1000)
        item, geometry, material = scratch, scratch + 0x100, scratch + 0x200
        put(item + 0x20, geometry)
        put(item + 0x28, scratch + 0x400 if morph_weights else 0)
        put(geometry + 4, material)
        put(geometry + 0xc, vertex_type)
        put(geometry + 0x38, scratch + 0x500 if skin_data else 0)
        put(geometry + 0x3c, scratch + 0x600 if morph_data else 0)
        put(material + 0x40, lighting << 16 | blend)
        machine.mem_write(material+0x60,struct.pack('<f',reflection_scalar))
        machine.mem_write(material + 0x9d, bytes([effect_byte]))
        put(scratch + 0xf000, sentinel)
        put(scratch + 0xf004, item)
        machine.reg_write(UC_X86_REG_ESP, scratch + 0xf000)
        machine.emu_start(0x52f300, sentinel, count=1000)
        if machine.reg_read(UC_X86_REG_EIP) != sentinel:
            raise AssertionError('Native selector did not return within the instruction limit')
        observed = machine.reg_read(UC_X86_REG_EAX)
        # Separate behavioral assertion: a dormant facial target must keep the
        # skinning path; merely having target data does not activate deformation.
        skinned = skin_data or vertex_type == 0x5d
        expected = (19 if morph_data and morph_weights else 15) if skinned else (11 if blend == 6 else 9)
        if effect_byte == 129:
            expected = (0 if morph_data and morph_weights else 17) if skinned else 2
        if bump_enabled:
            expected = (47 if morph_data and morph_weights else 43) if skinned else 27
        if reflections and effect_byte == 145:
            expected = (48 if morph_data and morph_weights else 44) if skinned else 35
        if reflections and bump_enabled and reflection_scalar:
            expected = (49 if morph_data and morph_weights else 45) if skinned else 31
        case = dict(material_effect=effect_byte, vertex_type=hex(vertex_type), skin_data=skin_data,
                    bump_enabled=bump_enabled,advanced_reflections=reflections,reflection_scalar=reflection_scalar,
                    morph_data=morph_data, morph_weights=morph_weights,
                    lighting_mode=lighting, blend_mode=blend, effect_id=observed)
        if observed != expected:
            raise AssertionError(dict(case=case, expected=expected))
        cases.append(case)
    return dict(executable_sha256=EXE_SHA256, cases=len(cases),
                selected_effects=dict(Counter(case['effect_id'] for case in cases)),
                scope='Original selector, material effect bytes 0/129/135/145, lighting modes 0/1/3; effect 135 also checked with bump enabled and effects 145/135 with advanced reflections, including zero/nonzero material strength; synthetic inputs; overrides and MRT disabled; no graphics calls',
                observations=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a new report path')
    report = observe(args.executable)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({key: value for key, value in report.items() if key != 'observations'}))


if __name__ == '__main__':
    main()

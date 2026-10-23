"""Compare the arithmetic reference with interpreted original ps_2_0 assembly.

Requires the shader inventory dependencies. This executes a deliberately small
instruction subset on the CPU, not a GPU; partial precision, texture filtering,
interpolation, render states and runtime program selection are not simulated.
"""
import argparse
import json
import math
from pathlib import Path
import random
import struct
import re

from inspect_native_shaders import inspect
from shader_reference import ordinary_pixel, specular_pixel, specular_uv, bump_pixel, tangent_light_vectors


PROGRAMS = {
    0x67c614: False, 0x67cb10: True,  # ordinary rigid candidate
    0x6a0c90: False, 0x6a169c: True,  # ordinary skin candidate
    0x6a2b58: False, 0x6a3598: True,  # ordinary morph/skin candidate
}


SPECULAR_PROGRAMS = {0x6a4c5c: False, 0x6a57d4: True, 0x6ab218: True}
BUMP_PROGRAMS = {0x681880: False, 0x681fc0: True, 0x69519c: False,
                 0x695f40: True, 0x68c1cc: False, 0x68cf70: True}

def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def interpret(assembly, registers, texture, output='oC0'):
    registers = {key: list(map(f32, value)) for key, value in registers.items()}

    def read(token):
        if token.startswith('-'):
            return [-v for v in read(token[1:])]
        relative=re.fullmatch(r'c(\d+)\[a0\.([xyz])\](?:\.([xyzw]+))?',token)
        if relative:
            offset=registers.get('a0')
            if offset is None:raise ValueError('Uninitialized shader address register')
            name='c'+str(int(relative[1])+int(offset['xyz'.index(relative[2])]))
            swizzle=relative[3] or ''
        else:
            name, _, swizzle = token.partition('.')
        if name not in registers:
            raise ValueError(f'Uninitialized shader input: {name}')
        swizzle = swizzle or 'xyzw'
        if len(swizzle) == 1:
            swizzle *= 4
        if len(swizzle) != 4:
            raise ValueError(f'Unsupported source swizzle: {token}')
        return [registers[name]['xyzw'.index(component)] for component in swizzle]

    for line in assembly.splitlines():
        line = line.split('//', 1)[0].strip()
        if not line or line in ('ps_2_0', 'vs_2_0') or line.startswith('dcl'):
            continue
        instruction, operands = line.split(None, 1)
        args = [part.strip() for part in operands.split(',')]
        modifiers = instruction.split('_'); operation = modifiers[0]
        if any(modifier not in ('sat', 'pp') for modifier in modifiers[1:]):
            raise ValueError(f'Unsupported instruction modifier: {instruction}')
        if operation == 'def':
            registers[args[0]] = [f32(float(value)) for value in args[1:]]
            continue
        target, _, mask = args[0].partition('.')
        mask = mask or 'xyzw'
        if operation in ('texld','texldp'):
            bindings = texture if isinstance(texture, dict) else {('t0', 's0'): texture}
            sample = bindings.get(tuple(args[1:]))
            if sample is None:
                raise ValueError('Texture instruction has no supplied coordinate/sampler binding')
            if callable(sample):
                coordinates=read(args[1])
                if operation=='texldp':
                    if coordinates[3]==0:raise ValueError('Undefined projected texture coordinate')
                    coordinates=[v/coordinates[3] for v in coordinates]
                sample = sample(coordinates)
            value = list(map(f32, sample))
        else:
            sources = [read(arg) for arg in args[1:]]
            if operation in ('dp3', 'dp4'):
                size = 3 if operation == 'dp3' else 4
                value = [f32(sum(a * b for a, b in zip(sources[0][:size], sources[1][:size])))] * 4
            elif operation == 'rsq':
                value = [f32(1 / math.sqrt(abs(sources[0][0])))] * 4
            elif operation == 'nrm':
                length = math.sqrt(sum(v*v for v in sources[0][:3]))
                value = [f32(v/length) for v in sources[0][:3]] + [0.]
            elif operation == 'abs':
                value = [abs(v) for v in sources[0]]
            elif operation == 'max':
                value = [max(a, b) for a, b in zip(*sources)]
            elif operation == 'mul':
                value = [f32(a * b) for a, b in zip(*sources)]
            elif operation == 'add':
                value = [f32(a + b) for a, b in zip(*sources)]
            elif operation == 'mad':
                value = [f32(a * b + c) for a, b, c in zip(*sources)]
            elif operation == 'mov':
                value = sources[0]
            elif operation == 'mova':
                value = [round(v) for v in sources[0]]
            elif operation == 'frc':
                value = [f32(v-math.floor(v)) for v in sources[0]]
            elif operation == 'cmp':
                value = [b if a>=0 else c for a,b,c in zip(*sources)]
            else:
                raise ValueError(f'Unsupported shader instruction: {operation}')
        if 'sat' in modifiers:
            value = [min(1., max(0., channel)) for channel in value]
        registers.setdefault(target, [0.] * 4)
        for component in mask:
            index = 'xyzw'.index(component)
            registers[target][index] = value[index]
    return tuple(registers[output])


def compare(executable, output):
    output.mkdir(parents=True, exist_ok=False)
    inventory = inspect(executable, output / 'programs', include_assembly=True)
    found = {int(row['address'], 16): row for row in inventory['shaders']}
    randomizer = random.Random(2005)
    samples = []
    for _ in range(512):
        samples.append(dict(material=[randomizer.uniform(0, 1) for _ in range(3)],
                            alpha=randomizer.random(), normal=[randomizer.uniform(-1, 1) for _ in range(3)],
                            ambient=[randomizer.uniform(0, .5) for _ in range(3)],
                            lights=[([randomizer.uniform(-1, 1) for _ in range(3)],
                                     [randomizer.uniform(0, 2) for _ in range(3)]) for _ in range(3)],
                            texture=[randomizer.random() for _ in range(4)],
                            specular=[randomizer.random() for _ in range(4)],
                            strength=randomizer.uniform(0, 2)))
    results = []
    for address, textured in (PROGRAMS | SPECULAR_PROGRAMS | BUMP_PROGRAMS).items():
        specular = address in SPECULAR_PROGRAMS
        bump = address in BUMP_PROGRAMS
        if found[address]['profile'] != 'ps_2_0':
            raise ValueError('Unexpected original pixel-program profile')
        assembly = (output / 'programs' / f'{address:08x}.txt').read_text(encoding='utf-8')
        maximum = 0.
        for sample in samples:
            material, alpha, normal = sample['material'], sample['alpha'], sample['normal']
            ambient, lights = sample['ambient'], sample['lights']
            texture = sample['texture'] if textured else None
            registers = dict(v0=[v * (.5 if textured else 1.) for v in material] + [alpha],
                             t1=normal + [0.])
            shift = int(specular)
            registers[f'c{shift}'] = ambient + [1.]
            if specular:
                registers['c0'] = [sample['strength']] * 4
            for index, (direction, color) in enumerate(lights):
                registers[f'c{shift + 1 + 2 * index}'] = direction + [0.]
                registers[f'c{shift + 2 + 2 * index}'] = color + [0.]
            bindings = {('t0', 's0'): texture}
            if specular:
                bindings[('t2', 's1' if textured else 's0')] = sample['specular']
            if bump:
                for index,(direction,color) in enumerate(lights):
                    registers[f't{index+2}'] = direction + [0.]
                    registers[f'c{index+1}'] = color + [0.]
                # Rigid and skinned compilations bind these samplers in
                # opposite orders despite sharing the same pixel equation.
                bump_sampler = 's1' if textured and address != 0x681fc0 else 's0'
                bindings = {('t0',bump_sampler): sample['specular']}
                if textured:
                    bindings[('t0','s0' if bump_sampler == 's1' else 's1')] = texture
            actual = interpret(assembly, registers, bindings)
            expected = (specular_pixel(material, alpha, normal, ambient, lights,
                                        sample['specular'], sample['strength'], texture) if specular else
                        ordinary_pixel(material, alpha, normal, ambient, lights, texture))
            if bump:
                expected = bump_pixel(material,alpha,sample['specular'],ambient,lights,texture)
            error = max(abs(a - b) for a, b in zip(actual, expected))
            if error > 2e-6:
                raise AssertionError((hex(address), sample, actual, expected, error))
            maximum = max(maximum, error)
        results.append(dict(address=hex(address), sha256=found[address]['sha256'],
                            textured=textured, specular=specular, bump=bump, samples=len(samples), maximum_error=maximum))
    # The rigid texture-specular vertex program transforms normals, forms a
    # four-component lookup vector, normalizes it, and emits UVs per vertex.
    # Testing this separately catches a tempting but incorrect per-pixel normal
    # mapping implementation and the loss of its fourth length component.
    address = 0x6ab5dc
    if found[address]['profile'] != 'vs_2_0':
        raise ValueError('Unexpected original specular vertex-program profile')
    assembly = (output / 'programs' / f'{address:08x}.txt').read_text(encoding='utf-8')
    uv_maximum = 0.
    for _ in range(512):
        normal = [randomizer.uniform(-1, 1) for _ in range(3)]
        world = [[randomizer.uniform(-1, 1) for _ in range(4)] for _ in range(4)]
        rows = [[randomizer.uniform(-1, 1) for _ in range(4)] for _ in range(4)]
        registers = dict(v0=[.3, .4, .5, 1.], v1=normal+[0.], v2=[1., 1., 1., .5],
                         v3=[.2, .8, 0., 0.], c12=[1., 1., 1., 1.])
        for i in range(4):
            registers[f'c{i}'] = rows[i]
            registers[f'c{4+i}'] = [float(i == j) for j in range(4)]
            registers[f'c{8+i}'] = world[i]
        actual = interpret(assembly, registers, None, output='oT2')[:2]
        world_normal = [sum(a*b for a, b in zip(normal, row[:3])) for row in world[:3]]
        expected = specular_uv(world_normal, rows)
        error = max(abs(a-b) for a, b in zip(actual, expected))
        if error > 2e-6:
            raise AssertionError((hex(address), actual, expected, error))
        uv_maximum = max(uv_maximum, error)
    vertex_result = dict(address=hex(address), sha256=found[address]['sha256'], samples=512, maximum_error=uv_maximum)
    address = 0x681b4c
    assembly = (output/'programs'/f'{address:08x}.txt').read_text(encoding='utf-8')
    bump_maximum = 0.
    for _ in range(512):
        tangent, normal = [[randomizer.uniform(-1,1) for _ in range(3)] for _ in range(2)]
        world = [[randomizer.uniform(-1,1) for _ in range(4)] for _ in range(4)]
        lights = [([randomizer.uniform(-1,1) for _ in range(3)],(1,1,1)) for _ in range(3)]
        registers = dict(v0=[.3,.4,.5,1], v1=normal+[0], v2=[1,1,1,.5],
                         v3=[.2,.8,0,0], v4=tangent+[0], c11=[1,1,1,1], c12=[0,0,0,1])
        for i in range(4):
            registers[f'c{i}'] = [float(i==j) for j in range(4)]
            registers[f'c{i+4}'] = world[i]
        for i,(direction,_) in enumerate(lights):
            registers[f'c{i+8}'] = direction+[0]
        bitangent = [tangent[1]*normal[2]-tangent[2]*normal[1],
                     tangent[2]*normal[0]-tangent[0]*normal[2], tangent[0]*normal[1]-tangent[1]*normal[0]]
        transform = lambda v: [sum(a*b for a,b in zip(v,row[:3])) for row in world[:3]]
        expected = tangent_light_vectors(transform(tangent),transform(bitangent),transform(normal),lights)
        for i,wanted in enumerate(expected):
            actual = interpret(assembly,registers,None,output=f'oT{i+2}')[:3]
            error = max(abs(a-b) for a,b in zip(actual,wanted))
            if error > 2e-5:
                raise AssertionError((hex(address),actual,wanted,error))
            bump_maximum = max(bump_maximum,error)
    bump_vertex = dict(address=hex(address),samples=512,maximum_error=bump_maximum)
    report = dict(programs=results, samples=len(samples) * len(results), vertex_lookup=vertex_result,
                  bump_vertex=bump_vertex,
                  scope='CPU interpretation of original assembly; full-float arithmetic; not GPU or game-frame validation')
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.executable, args.output)))

"""Check reflection arithmetic against twelve original LSW1 PC pixel programs.

Supply the inventory created by inspect_native_shaders.py --disassembly.
This checks full-float shader instructions, with explicit preshader constants
and a direction-sensitive synthetic cube sample. It does not capture a game.
"""
import argparse
import json
from pathlib import Path
import random

from check_native_curves import EXE_SHA256
from check_pixel_programs import interpret
from shader_reference import reflection_pixel, reflection_terms, reflection_vertex, unit_vector, bump_reflection_pixel, tangent_light_vectors


PROGRAMS = {0x67f7e8:(False,False), 0x680414:(True,False),
            0x6979c4:(False,True), 0x698b50:(True,True),
            0x68e9f4:(False,True), 0x68fbc8:(True,True)}


BUMP_PROGRAMS={0x6898dc:(False,False),0x68a784:(True,False),
               0x69aa80:(False,True),0x69bf9c:(True,True),
               0x691b40:(False,False),0x69309c:(True,False)}


def compare(folder):
    inventory = json.loads((folder/'inventory.json').read_text(encoding='utf-8'))
    if inventory['executable_sha256'] != EXE_SHA256:
        raise ValueError('Unsupported executable inventory')
    found = {int(r['address'],16):r for r in inventory['shaders']}
    results = []
    for address,(textured,skinned) in (PROGRAMS | BUMP_PROGRAMS).items():
        bump=address in BUMP_PROGRAMS
        variant='morph' if address in (0x68e9f4,0x68fbc8,0x691b40,0x69309c) else 'skin' if skinned else 'rigid'
        skinned=variant!='rigid'
        if found[address]['profile'] != 'ps_2_0':
            raise ValueError('Unexpected reflection shader profile')
        assembly = (folder/f'{address:08x}.txt').read_text(encoding='utf-8')
        # D3DX evaluates these two scalar preshader outputs before GPU execution.
        # Supply them explicitly; this interpreter does not execute preshaders.
        assembly = 'ps_2_0' + assembly.split('    ps_2_0',1)[1]
        rng = random.Random(145)
        maximum = direction_error = 0.
        for _ in range(512):
            normal,probe,camera = [[rng.uniform(-1,1) for _ in range(3)] for _ in range(3)]
            material = [rng.random() for _ in range(3)]
            alpha = rng.random()
            ambient = [rng.uniform(0,.5) for _ in range(3)]
            lights = [([rng.uniform(-1,1) for _ in range(3)],
                       [rng.uniform(0,2) for _ in range(3)]) for _ in range(3)]
            bump_texel=[rng.random() for _ in range(4)]
            texel = [rng.random() for _ in range(4)] if textured else None
            parameters = [rng.uniform(0,1),rng.uniform(0,2),.2,.8]
            registers = dict(v0=[v*(.5 if textured else 1) for v in material]+[alpha],
                             t1=normal+[0],t2=probe+[0],t3=camera+[0],
                             c1=[1/(parameters[3]-parameters[2])]*4,
                             c2=[parameters[1]-parameters[0]]*4,
                             c3=parameters,c4=ambient+[1])
            for i,(direction,color) in enumerate(lights):
                registers[f'c{5+2*i}']=direction+[0]
                registers[f'c{6+2*i}']=color+[0]
            if bump:
                for i,(direction,color) in enumerate(lights):
                    registers[f't{i+4}']=direction+[0]
                    registers[f'c{i+5}']=color+[0]
            sampled=[]
            def cube(direction):
                sampled.append(tuple(direction[:3]))
                return tuple(.5+.5*v for v in direction[:3])+(0.,)
            bindings = {('r0','s1' if textured else 's0'):cube}
            if bump:
                bindings={('r0','s2' if textured else 's1'):cube,('t0','s1' if textured else 's0'):bump_texel}
            if textured:
                bindings[('t0','s0')]=texel
            actual = interpret(assembly,registers,bindings)
            reflected,_ = reflection_terms(normal,probe,camera,parameters)
            if bump and variant=='skin':reflected=tuple(-v for v in reflected)
            wanted_sample=tuple(.5+.5*v for v in reflected)+(0.,)
            expected = reflection_pixel(material,alpha,normal,ambient,lights,
                                        probe,camera,parameters,wanted_sample,texel,skinned=skinned)
            if bump:
                expected=bump_reflection_pixel(material,alpha,normal,ambient,lights,probe,camera,parameters,wanted_sample,bump_texel,texel)
            if len(sampled)!=1:
                raise AssertionError('Expected exactly one cube lookup')
            error = max(abs(a-b) for a,b in zip(actual,expected))
            coordinate_error = max(abs(a-b) for a,b in zip(sampled[0],reflected))
            if error>4e-6 or coordinate_error>2e-6:
                raise AssertionError((hex(address),actual,expected,error,coordinate_error))
            maximum=max(maximum,error);direction_error=max(direction_error,coordinate_error)
        results.append(dict(address=hex(address),sha256=found[address]['sha256'],
                            textured=textured,variant=variant,skinned=skinned,bump=bump,samples=512,
                            maximum_error=maximum,maximum_direction_error=direction_error))
    address=0x680a74
    assembly=(folder/f'{address:08x}.txt').read_text(encoding='utf-8')
    assembly='vs_2_0'+assembly.split('    vs_2_0',1)[1]
    rng=random.Random(35);vertex_error=0.
    for _ in range(512):
        position,normal,camera,player=[[rng.uniform(-2,2) for _ in range(3)] for _ in range(4)]
        world=[[rng.uniform(-1,1) for _ in range(4)] for _ in range(3)]+[[0,0,0,1]]
        world_position=[sum(a*b for a,b in zip(position+[1],row)) for row in world[:3]]
        world_normal=[sum(a*b for a,b in zip(normal,row[:3])) for row in world[:3]]
        delta=unit_vector((player[0]-camera[0],player[1]-camera[1]+.5,player[2]-camera[2]),'Preshader direction')
        probe=[p-.5*d for p,d in zip(player,delta)]
        registers=dict(v0=position+[1],v1=normal+[0],v2=[1,1,1,1],v3=[0,0,0,0],
                       c11=probe+[0],c12=camera+[1],c13=[1,1,1,1],c14=[0,0,0,1])
        for i in range(4):
            registers[f'c{i}']=[float(i==j) for j in range(4)]
            registers[f'c{i+4}']=world[i]
        probe_vector,camera_vector=reflection_vertex(world_position,camera,player)
        for output,wanted in (('oT1',unit_vector(world_normal,'Normal')),('oT2',probe_vector),('oT3',camera_vector)):
            actual=interpret(assembly,registers,None,output=output)[:3]
            error=max(abs(a-b) for a,b in zip(actual,wanted))
            if error>3e-6:raise AssertionError((output,actual,wanted,error))
            vertex_error=max(vertex_error,error)
    bump_address=0x68ae2c
    assembly=(folder/f'{bump_address:08x}.txt').read_text(encoding='utf-8')
    assembly='vs_2_0'+assembly.split('    vs_2_0',1)[1]
    bump_vertex_error=0.
    for _ in range(512):
        tangent,normal=[[rng.uniform(-1,1) for _ in range(3)] for _ in range(2)]
        world=[[rng.uniform(-1,1) for _ in range(4)] for _ in range(3)]+[[0,0,0,1]]
        lights=[([rng.uniform(-1,1) for _ in range(3)],(1,1,1)) for _ in range(3)]
        registers=dict(v0=[.3,.4,.5,1],v1=normal+[0],v2=[1,1,1,1],v3=[0,0,0,0],v4=tangent+[0],
                       c11=[0,0,0,0],c12=[4,5,6,1],c16=[1,1,1,1],c17=[0,0,0,1])
        for i in range(4):
            registers[f'c{i}']=[float(i==j) for j in range(4)]
            registers[f'c{i+4}']=world[i]
        for i,(light,_) in enumerate(lights):registers[f'c{i+13}']=light+[0]
        bitangent=(tangent[1]*normal[2]-tangent[2]*normal[1],
                   tangent[2]*normal[0]-tangent[0]*normal[2],tangent[0]*normal[1]-tangent[1]*normal[0])
        transform=lambda v:[sum(a*b for a,b in zip(v,row[:3])) for row in world[:3]]
        expected=tangent_light_vectors(transform(tangent),transform(bitangent),unit_vector(transform(normal),'Normal'),lights)
        for i,wanted in enumerate(expected):
            actual=interpret(assembly,registers,None,output=f'oT{i+4}')[:3]
            error=max(abs(a-b) for a,b in zip(actual,wanted))
            if error>3e-6:raise AssertionError((i,actual,wanted,error))
            bump_vertex_error=max(bump_vertex_error,error)
    return dict(programs=results,samples=512*len(results),
                bump_rigid_vertex=dict(address=hex(bump_address),samples=512,maximum_error=bump_vertex_error),
                rigid_vertex=dict(address=hex(address),samples=512,maximum_error=vertex_error,preshader='Explicit supplied constants; preshader bytecode not executed'),
                scope='Interpreted original pixel arithmetic; explicit preshader constants; synthetic direction-sensitive cube; no texture filtering, GPU partial precision or game-frame proof')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path);parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=compare(args.inventory)
    with args.report.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report))

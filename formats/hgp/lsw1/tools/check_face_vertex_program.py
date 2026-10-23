"""Compare active-face bump/reflection vertex inputs against original assembly.

Explicit synthetic morph deltas and skin matrices; no native face-clip decoding.
Preshader camera/probe constants are supplied, not executed here.
"""
import argparse
import json
import math
from pathlib import Path
import random
from check_pixel_programs import interpret
from check_native_curves import EXE_SHA256
from shader_reference import unit_vector,tangent_light_vectors


def compare(folder):
    metadata=json.loads((folder/'inventory.json').read_text(encoding='utf-8'))
    if metadata['executable_sha256']!=EXE_SHA256:raise ValueError('Unknown face shader inventory')
    assembly=(folder/'00693738.txt').read_text(encoding='utf-8')
    assembly='vs_2_0'+assembly.split('    vs_2_0',1)[1]
    ordinary=(folder/'006a389c.txt').read_text(encoding='utf-8')
    rng=random.Random(49);maximum=0.
    for sample in range(256):
        positions=[rng.uniform(-1,1) for _ in range(3)]
        delta=[rng.uniform(-.4,.4) for _ in range(3)]
        normal=unit_vector([rng.uniform(-1,1) for _ in range(3)],'normal')
        tangent=unit_vector([rng.uniform(-1,1) for _ in range(3)],'tangent')
        weights=[rng.random() for _ in range(3)];total=sum(weights);weights=[w/total for w in weights]
        matrices=[[[rng.uniform(-1,1) for _ in range(4)] for _ in range(3)] for _ in range(3)]
        lights=[([rng.uniform(-1,1) for _ in range(3)],(1,1,1)) for _ in range(3)]
        camera=(3.,4.,5.);probe=(-3.,2.,4.)
        registers={'v0':positions+[1.],'v1':weights[:2]+[0,0],'v2':[.125,1.25,2.75,0],'v3':list(normal)+[0],
                   'v4':[1,1,1,.4],'v5':[.2,.3,0,0],'v6':delta+[0],'v7':list(tangent)+[0],
                   'c49':[0,0,0,0],'c53':list(probe)+[1],'c58':list(camera)+[1],'c62':[.5,.5,.5,1]}
        for i,matrix in enumerate(matrices):
            for j,row in enumerate(matrix):registers[f'c{i*3+j}']=row
        for i in range(4):registers[f'c{54+i}']=[float(i==j) for j in range(4)]
        for i,(direction,_) in enumerate(lights):registers[f'c{59+i}']=list(direction)+[0]
        def skin(value,w):
            return tuple(sum(weights[k]*sum(a*b for a,b in zip(matrices[k][j],list(value)+[w])) for k in range(3)) for j in range(3))
        world=skin([a+b for a,b in zip(positions,delta)],1)
        n=unit_vector(skin(normal,0),'posed normal');t=skin(tangent,0)
        bitangent=(tangent[1]*normal[2]-tangent[2]*normal[1],tangent[2]*normal[0]-tangent[0]*normal[2],tangent[0]*normal[1]-tangent[1]*normal[0])
        b=skin(bitangent,0)
        expected={'oPos':world+(1.,),'oT1':n,'oT2':unit_vector([a-b for a,b in zip(probe,world)],'probe'),
                  'oT3':unit_vector([a-b for a,b in zip(world,camera)],'camera')}
        expected.update({f'oT{4+i}':v for i,v in enumerate(tangent_light_vectors(t,b,n,lights))})
        for output,wanted in expected.items():
            actual=interpret(assembly,registers,{},output=output)
            error=max(abs(a-b) for a,b in zip(actual,wanted));maximum=max(maximum,error)
            if error>2e-5:raise AssertionError((sample,output,actual,wanted,error))
        for i in range(4):registers[f'c{48+i}']=[float(i==j) for j in range(4)]
        registers['c52']=[.5,.5,.5,1]
        for output,wanted in {'oPos':world+(1.,),'oT1':skin(normal,0)}.items():
            actual=interpret(ordinary,registers,{},output=output)
            error=max(abs(a-b) for a,b in zip(actual,wanted));maximum=max(maximum,error)
            if error>2e-5:raise AssertionError(('ordinary',sample,output,error))
    return dict(samples=256,outputs_per_sample=9,maximum_error=maximum,
                scope='Active face ordinary and combined bump/reflection vertex shaders; explicit delta and preshader constants. No clip decoding, GPU precision or native delta accumulation proof')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('inventory',type=Path);parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=compare(args.inventory);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(report)

"""Check original shadow-receiver pixel equations with explicit map samples."""
import argparse
import json
from pathlib import Path
import random
from check_pixel_programs import interpret
from check_native_curves import EXE_SHA256
from shader_reference import shadow_receiver_pixel


def compare(inventory):
    metadata=json.loads((inventory/'inventory.json').read_text(encoding='utf-8'))
    if metadata['executable_sha256']!=EXE_SHA256:raise ValueError('Unknown shader inventory')
    rng=random.Random(2005);results=[]
    for address,textured,secondary in ((0x69e168,True,False),(0x69e6a4,False,False),
            (0x69f7e0,True,False),(0x69fd1c,False,False),(0x6d8540,True,True),
            (0x6d8b08,False,True),(0x6d9d30,True,True),(0x6da2f8,False,True)):
        assembly=(inventory/f'{address:08x}.txt').read_text(encoding='utf-8');maximum=0.
        for case in range(512):
            vertex=[rng.uniform(0,2) for _ in range(4)];texture=[rng.random() for _ in range(4)]
            shadow=[rng.random() for _ in range(4)];attenuation=[rng.random() for _ in range(4)]
            w=rng.choice((-2.,-.1,.1,2.));incidence=rng.uniform(0,2)
            coordinate=(.4,-.7,.3,w);seen=[]
            def sampler(value,sample):
                if max(abs(a-b/w) for a,b in zip(value,coordinate))>1e-6:raise AssertionError('Projection division mismatch')
                seen.append(value);return sample
            registers={'v0':vertex,'t3':(.37,0,0,0)}
            if textured:
                registers.update(t0=(.1,.2,0,1),t1=coordinate,t2=(incidence,0,0,0))
                bindings={('t0','s0'):texture,('t1','s1'):lambda uv:sampler(uv,shadow),('t1','s2'):lambda uv:sampler(uv,attenuation)}
            else:
                registers.update(t0=coordinate,t1=(incidence,0,0,0))
                bindings={('t0','s0'):lambda uv:sampler(uv,shadow),('t0','s1'):lambda uv:sampler(uv,attenuation)}
            actual=interpret(assembly,registers,bindings)
            expected=shadow_receiver_pixel(vertex,w,incidence,shadow,attenuation,texture if textured else None)
            error=max(abs(a-b) for a,b in zip(actual,expected));maximum=max(maximum,error)
            if error>1e-6 or len(seen)!=2:raise AssertionError((hex(address),case,error))
            if secondary:
                extra=interpret(assembly,registers,bindings,output='oC1')
                if max(abs(v-.37) for v in extra)>1e-7:raise AssertionError('Secondary output mismatch')
        results.append(dict(address=hex(address),samples=512,maximum_error=maximum,secondary_target=secondary))
    return dict(programs=results,scope='CPU interpretation of original pixel programs; no shadow-map generation, filtering, runtime pass choice or game comparison')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory',type=Path);parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=compare(args.inventory);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Passed 4096 original shadow receiver pixel comparisons')

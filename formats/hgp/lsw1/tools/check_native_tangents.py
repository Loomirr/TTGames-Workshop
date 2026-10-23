"""Compare triangle UV derivatives with the reviewed original LSW1 PC executable.

Requires pefile and Unicorn. Executes the two math routines and reviewed strip
assignment loop, intercepting external vector normalization. Does not launch
the game, load Direct3D or execute its buffer creation and draw calls.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct

from check_native_curves import EXE_SHA256
from shader_tangents import triangle_basis, strip_tangents


def observe(path, models=()):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_EAX
    with path.open('rb') as stream:
        raw=stream.read(128*1024*1024+1)
    if hashlib.sha256(raw).hexdigest()!=EXE_SHA256:
        raise ValueError('Unsupported executable hash for tangent comparison')
    pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase
    image=pe.get_memory_mapped_image()
    machine=Uc(UC_ARCH_X86,UC_MODE_32)
    machine.mem_map(base,(len(image)+4095)&~4095);machine.mem_write(base,image)
    scratch=0x20000000;machine.mem_map(scratch,0x10000)
    assembly=False
    def guard(machine,address,size,data):
        if assembly and address==0x54fa3d:
            # External lazy-linked normalization is represented by its vector
            # contract; this check proves native assignment, not DLL arithmetic.
            import math
            stack=machine.reg_read(UC_X86_REG_ESP)
            target,out,source=struct.unpack('<3I',machine.mem_read(stack,12))
            value=struct.unpack('<3f',machine.mem_read(source,12));length=math.sqrt(sum(v*v for v in value))
            machine.mem_write(out,struct.pack('<3f',*(v/length for v in value)) if length else bytes(12))
            machine.reg_write(UC_X86_REG_EAX,out);machine.reg_write(UC_X86_REG_ESP,stack+12);machine.reg_write(UC_X86_REG_EIP,target)
            return
        if not (0x3b38e13<=address<=0x3b38f99 or 0x3b5ad3c<=address<=0x3b5aec2
                or assembly and (0x547a4e<=address<0x547c08 or address in (0x547050,0x5471e0))):
            raise ValueError(f'Tangent execution left reviewed math at {address:#x}')
    machine.hook_add(UC_HOOK_CODE,guard)
    rng=random.Random(20261022)
    f32=lambda value:struct.unpack('<f',struct.pack('<f',value))[0]
    cases=[];triangles=[];originals=[]
    for index in range(512):
        positions=[tuple(f32(rng.uniform(-4,4)) for _ in range(3)) for _ in range(3)]
        # Orthogonal, mirrored, collapsed, nearly singular and general UVs.
        uvs=(((0,0),(1,0),(0,1)),((0,0),(-1,0),(0,1)),
             ((0,0),)*3,((0,0),(1,0),(0,1e-6)),
             ((0,0),(1,0),(0,1e-4)),((0,0),(1,0),(0,1.001e-4)))[index%6] if index<96 else [tuple(rng.uniform(-2,2) for _ in range(2)) for _ in range(3)]
        uvs=[tuple(f32(v) for v in uv) for uv in uvs]
        triangles.append((positions,uvs))
    if models:
        import importlib.util
        spec=importlib.util.spec_from_file_location('lsw1_tangent_hgp',Path(__file__).parents[1]/'hgp.py')
        hgp=importlib.util.module_from_spec(spec);spec.loader.exec_module(hgp)
        for model in models:
            source=hgp.HGP(model);count=0;seen=set()
            for layer in range(source.layer_count):
                for part in source.layer_meshes(layer):
                    identity=(part['geometry'],part['primitive'])
                    if identity in seen:continue
                    seen.add(identity)
                    for face in part['faces']:
                        if count>=2048:break
                        triangles.append(([part['vertices'][i] for i in face],[part['uvs'][i] for i in face]))
                        count+=1
            originals.append(dict(model=model.name,sha256=hashlib.sha256(model.read_bytes()).hexdigest(),triangles=count))
    for index,(positions,uvs) in enumerate(triangles):
        wanted=triangle_basis(positions,uvs)
        for vertex_type,begin,end,uv_offset in ((0x59,0x3b38e13,0x3b38f99,28),(0x5d,0x3b5ad3c,0x3b5aec2,48)):
            for i,(position,uv) in enumerate(zip(positions,uvs)):
                machine.mem_write(scratch+i*0x100,struct.pack('<3f',*position))
                machine.mem_write(scratch+i*0x100+uv_offset,struct.pack('<2f',*uv))
            machine.mem_write(scratch+0xf000,struct.pack('<6I',scratch+0xff00,scratch,scratch+0x100,scratch+0x200,scratch+0x400,scratch+0x410))
            machine.reg_write(UC_X86_REG_ESP,scratch+0xf000)
            machine.emu_start(begin,end,count=1000)
            if machine.reg_read(UC_X86_REG_EIP)!=end:
                raise AssertionError('Native tangent routine did not reach return')
            actual=[struct.unpack('<3f',machine.mem_read(scratch+offset,12)) for offset in (0x400,0x410)]
            error=max(abs(a-b)/max(1.,abs(b)) for row,want in zip(actual,wanted) for a,b in zip(row,want))
            if error>2e-4:
                raise AssertionError((index,vertex_type,error,actual,wanted))
            cases.append(dict(case=index,vertex_type=hex(vertex_type),relative_error=error))
    assembly=True;assembly_cases=[]
    for case in range(64):
        positions=[tuple(f32(rng.uniform(-2,2)) for _ in range(3)) for _ in range(12)]
        uvs=[tuple(f32(rng.uniform(-1,1)) for _ in range(2)) for _ in range(12)]
        indices=[rng.randrange(12) for _ in range(24)]
        wanted=strip_tangents(positions,uvs,indices)
        for rigid in (True,False):
            frame=scratch+0xe000;geometry=scratch+0x3000;primitive=scratch+0x3200;vertices=scratch+0x4000;index_at=scratch+0x5000
            machine.mem_write(frame,bytes(0x100))
            for offset,value in ((0x18,index_at),(0x20,vertices),(0x24,vertices),(0x54,geometry),(0x58,int(rigid))):
                machine.mem_write(frame+offset,struct.pack('<I',value))
            machine.mem_write(geometry+0x30,struct.pack('<I',primitive));machine.mem_write(primitive+0x4c,struct.pack('<I',len(indices)-2))
            machine.mem_write(index_at,struct.pack('<24H',*indices))
            for i,(position,uv) in enumerate(zip(positions,uvs)):
                at=vertices+i*(36 if rigid else 56)
                machine.mem_write(at,struct.pack('<3f',*position));machine.mem_write(at+(28 if rigid else 48),struct.pack('<2f',*uv))
            sentinel=(17.,19.,23.);machine.mem_write(0x329fc18,struct.pack('<3f',*sentinel)*12)
            machine.reg_write(UC_X86_REG_ESP,frame);machine.reg_write(UC_X86_REG_EDI,geometry);machine.reg_write(UC_X86_REG_EBP,0)
            machine.emu_start(0x547a4e,0x547c08,count=20000)
            if machine.reg_read(UC_X86_REG_EIP)!=0x547c08:raise AssertionError('Tangent assembly did not finish')
            actual=list(struct.iter_unpack('<3f',machine.mem_read(0x329fc18,12*12)))
            error=max(abs(a-b) for row,want in zip(actual,wanted) for a,b in zip(row,want if want is not None else sentinel))
            if error>2e-5:raise AssertionError(('assembly',case,rigid,error))
            assembly_cases.append(dict(case=case,rigid=rigid,error=error))
    return dict(executable_sha256=EXE_SHA256,cases=len(cases),maximum_relative_error=max(c['relative_error'] for c in cases),
                strip_assignment_cases=assembly_cases,normalizer='intercepted external vector normalization contract',
                originals=originals,samples=cases,scope='Triangle derivatives and strip slot assignment; external normalization contract intercepted. Buffer creation, GPU upload and game-frame fidelity remain separate')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable',type=Path);parser.add_argument('report',type=Path)
    parser.add_argument('--model',type=Path,action='append',default=[],help='Original HGP; compare up to 2048 triangles per model in both routines')
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=observe(args.executable,args.model)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"Compared {report['cases']} native triangle derivatives; maximum relative error {report['maximum_relative_error']:.8g}")


if __name__=='__main__':
    main()

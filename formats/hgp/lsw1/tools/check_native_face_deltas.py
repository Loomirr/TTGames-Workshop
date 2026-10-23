"""Compare original HGP+BSA weighted deltas with the native accumulation loop.

Explicit research pairing only. Does not establish gameplay clip ownership.
Requires pefile/unicorn; supplies the output buffer instead of locking a GPU
buffer. Original target-ID lookup and XYZ accumulation instructions execute.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hgp import HGP
from animation_records import AnimationRecords
from check_native_curves import EXE_SHA256
from face_channels import sample_layers


def compare(executable, model, animation):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_EIP, UC_X86_REG_ESP
    raw=executable.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXE_SHA256:raise ValueError('Unknown executable')
    h=HGP(model)
    with animation.open('rb') as stream:clip=AnimationRecords(stream.read(AnimationRecords.MAX_BYTES+1),'BSA')
    pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
    m=Uc(UC_ARCH_X86,UC_MODE_32);m.mem_map(base,(len(image)+4095)&~4095);m.mem_write(base,image)
    scratch=0x20000000;m.mem_map(scratch,0x200000)
    put=lambda at,v:m.mem_write(at,struct.pack('<I',v))
    f32=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
    frame=scratch+0x1000;item=scratch+0x2000;geometry=scratch+0x2100;record=scratch+0x2200
    table=scratch+0x3000;ids=scratch+0x4000;weights=scratch+0x5000;output=scratch+0x6000
    put(frame+8,item);put(item+0x20,geometry);put(item+0x28,weights);put(geometry+0x3c,record)
    reports=[];maximum=0.
    for layer in h.selected_layers('AUTO'):
        for part in h.layer_meshes(layer):
            if not part['morph']:continue
            targets=part['morph']['targets'];count=len(part['vertices'])
            if count>2000:raise ValueError('Part exceeds reviewed native scratch capacity')
            if layer>=clip.tracks or max(t['id'] for t in targets)>=clip.components:
                raise ValueError('Clip lacks explicit channels for every requested target; padding is unverified')
            put(record,len(targets));put(record+4,table);put(record+8,ids);put(geometry+0x14,count)
            cursor=scratch+0x10000
            for index,target in enumerate(targets):
                put(ids+index*4,target['id']);put(table+index*4,cursor if target['deltas'] is not None else 0)
                if target['deltas'] is not None:
                    data=b''.join(struct.pack('<3f',*v) for v in target['deltas'])
                    if cursor+len(data)>scratch+0x1f0000:raise ValueError('Delta data exceeds comparison buffer')
                    m.mem_write(cursor,data);cursor+=len(data)
            for time in (1.,clip.duration*.25,clip.duration*.5,clip.duration*.75,clip.duration-.01):
                values=sample_layers(clip,time,[layer])[0]
                m.mem_write(weights+8,struct.pack('<'+'f'*len(values),*values))
                put(frame-8,record);put(frame-12,output);put(frame-0x44,2000)
                m.reg_write(UC_X86_REG_EBP,frame);m.reg_write(UC_X86_REG_ESP,frame-0x100)
                m.emu_start(0x52c397,0x52c4c4,count=2000000)
                if m.reg_read(UC_X86_REG_EIP)!=0x52c4c4:raise AssertionError('Native accumulator did not complete')
                native=list(struct.iter_unpack('<3f',m.mem_read(output,count*12)))
                expected=[[0.,0.,0.] for _ in range(count)]
                for target in targets:
                    weight=values[target['id']]
                    if target['deltas'] is None or weight==0:continue
                    for row,delta in zip(expected,target['deltas']):
                        for axis in range(3):row[axis]=f32(row[axis]+delta[axis]*weight)
                error=max(abs(a-b) for row,wanted in zip(native,expected) for a,b in zip(row,wanted))
                maximum=max(maximum,error)
                if error>2e-6:raise AssertionError((layer,time,error))
                reports.append(dict(layer=layer,geometry=hex(part['geometry']),vertices=count,time=time,weights=values,max_error=error))
    if not reports:raise ValueError('No supported facial geometry')
    return dict(model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),animation_sha256=clip.sha256,
        executable_sha256=EXE_SHA256,cases=reports,max_error=maximum,
        scope='Explicit original-file pairing; native target-ID lookup and accumulation; supplied GPU scratch buffer, no runtime ownership or draw validation')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('executable','model','animation','report'):parser.add_argument(name,type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report')
    report=compare(args.executable,args.model,args.animation)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Native face delta cases',len(report['cases']),'maximum error',report['max_error'])

"""Observe original shadow resource allocation with intercepted graphics calls.

Requires pefile and Unicorn. Never creates GPU resources or starts the game.
The executable hash gates all offsets. Numeric format/usage values are recorded
verbatim; successful allocation does not establish shadow rendering fidelity.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
from check_native_curves import EXE_SHA256


def observe(path):
    import pefile
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_ESI,UC_X86_REG_EBX
    with path.open('rb') as stream:raw=stream.read(128*1024*1024+1)
    if hashlib.sha256(raw).hexdigest()!=EXE_SHA256:raise ValueError('Unknown shadow executable')
    pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
    machine=Uc(UC_ARCH_X86,UC_MODE_32);machine.mem_map(base,(len(image)+4095)&~4095);machine.mem_write(base,image)
    scratch=0x20000000;machine.mem_map(scratch,0x10000);sentinel=scratch+0xff00
    put=lambda at,value:machine.mem_write(at,struct.pack('<I',value))
    texture_slots=(0x2ee0cc8,0x2ee0c54);surface_slots=(0x2ee0ccc,0x2ee0c58)
    calls=[];phase='allocation'
    def hook(machine,address,size,data):
        stack=machine.reg_read(UC_X86_REG_ESP)
        if phase=='end':
            counts={0x4b3050:1,0x531a80:2,0x531900:1,0x531a30:2,scratch+0xa00:1}
            if address in counts:
                ret,*args=struct.unpack('<'+str(counts[address]+1)+'I',machine.mem_read(stack,4*(counts[address]+1)))
                calls.append(dict(function=hex(address),args=args))
                machine.reg_write(UC_X86_REG_EAX,0)
                machine.reg_write(UC_X86_REG_ESP,stack+(8 if address==scratch+0xa00 else 4))
                machine.reg_write(UC_X86_REG_EIP,ret)
            elif not (0x4f7500<=address<0x4f75b8 or 0x401391<=address<=0x4013a1):
                raise ValueError(f'Shadow restoration left reviewed function at {address:#x}')
            return
        if phase=='begin':
            counts={0x531780:2,0x531600:1,0x531a80:2,0x531900:1,0x4b7550:3,0x531730:2,0x531a30:2}
            if address in counts:
                values=struct.unpack('<'+str(counts[address]+1)+'I',machine.mem_read(stack,4*(counts[address]+1)))
                ret,*args=values;calls.append(dict(function=hex(address),args=args))
                if address==0x531780:put(args[1],scratch+0x6000)
                if address==0x531600:put(args[0],scratch+0x6100)
                if address==0x531730:put(args[1],15 if args[0]==168 else 0)
                machine.reg_write(UC_X86_REG_EAX,0);machine.reg_write(UC_X86_REG_ESP,stack+4);machine.reg_write(UC_X86_REG_EIP,ret)
            elif not 0x3b62371<=address<0x3b623fa:
                raise ValueError(f'Shadow setup left reviewed function at {address:#x}')
            return
        if address==0x531350:
            ret,width,height,levels,usage,fmt,pool,out=struct.unpack('<8I',machine.mem_read(stack,32))
            if out not in texture_slots:raise AssertionError('Unexpected allocation destination')
            index=texture_slots.index(out);handle=scratch+0x100+index*0x100
            put(out,handle);put(handle,scratch+0x800);put(scratch+0x848,scratch+0x900)
            calls.append(dict(kind='texture',width=width,height=height,levels=levels,usage=usage,format=fmt,pool=pool,slot=hex(out)))
            machine.reg_write(UC_X86_REG_ESP,stack+4);machine.reg_write(UC_X86_REG_EIP,ret)
        elif address==scratch+0x900:
            ret,instance,level,out=struct.unpack('<4I',machine.mem_read(stack,16))
            if out not in surface_slots or level!=0:raise AssertionError('Unexpected surface request')
            if instance!=scratch+0x100+surface_slots.index(out)*0x100:raise AssertionError('Surface requested from wrong texture')
            put(out,scratch+0x1000+surface_slots.index(out)*0x100)
            calls.append(dict(kind='surface',level=level,slot=hex(out)))
            machine.reg_write(UC_X86_REG_EAX,0);machine.reg_write(UC_X86_REG_ESP,stack+16);machine.reg_write(UC_X86_REG_EIP,ret)
        elif not 0x4f7da0<=address<=0x4f7e36:
            raise ValueError(f'Allocation left reviewed function at {address:#x}')
    machine.hook_add(UC_HOOK_CODE,hook);cases=[]
    for enabled,have_depth,have_depth_surface,have_color,have_color_surface in itertools.product((0,1),repeat=5):
        # A cached surface cannot exist without its owning texture.
        if have_depth_surface>have_depth or have_color_surface>have_color:continue
        for width,height in ((512,512),(256,128)):
            calls.clear();put(0x778388,enabled);put(0x2ee0c68,width);put(0x2ee0c6c,height)
            for index,(slot,present) in enumerate(zip(texture_slots,(have_depth,have_color))):
                handle=scratch+0x100+index*0x100;put(slot,handle if present else 0);put(handle,scratch+0x800)
            put(scratch+0x848,scratch+0x900)
            for slot,present in zip(surface_slots,(have_depth_surface,have_color_surface)):put(slot,scratch+0x2000 if present else 0)
            put(scratch+0xf000,sentinel);machine.reg_write(UC_X86_REG_ESP,scratch+0xf000)
            machine.emu_start(0x4f7da0,sentinel,count=500)
            if machine.reg_read(UC_X86_REG_EIP)!=sentinel:raise AssertionError('Allocation did not return')
            expected=[]
            if enabled:
                if not have_depth:expected.append(dict(kind='texture',width=width,height=height,levels=1,usage=2,format=75,pool=0,slot=hex(texture_slots[0])))
                if not have_depth_surface:expected.append(dict(kind='surface',level=0,slot=hex(surface_slots[0])))
                if not have_color:expected.append(dict(kind='texture',width=512,height=512,levels=1,usage=1,format=21,pool=0,slot=hex(texture_slots[1])))
                if not have_color_surface:expected.append(dict(kind='surface',level=0,slot=hex(surface_slots[1])))
            if calls!=expected:raise AssertionError((calls,expected))
            cases.append(dict(enabled=enabled,requested_size=[width,height],cached=[have_depth,have_depth_surface,have_color,have_color_surface],calls=list(calls)))
    phase='begin';calls.clear();light=scratch+0x3000;config=scratch+0x4000
    put(light+0xc8,config);put(config+0x64,scratch+0x5000);put(0x2ee0c58,scratch+0x5100)
    machine.reg_write(UC_X86_REG_ESP,scratch+0xe000);machine.reg_write(UC_X86_REG_ESI,0);machine.reg_write(UC_X86_REG_EBX,light)
    machine.emu_start(0x3b62371,0x3b623fa,count=500)
    expected=[(0x531780,[0,0x2ee0c44]),(0x531600,[0x2ee0c48]),
              (0x531a80,[0,scratch+0x5100]),(0x531900,[scratch+0x5000]),
              (0x4b7550,[2,0,0x3f800000]),(0x531730,[168,0x2ee0c4c]),
              (0x531730,[14,0x2ee0c50]),(0x531a30,[168,0]),(0x531a30,[14,1])]
    if [(int(c['function'],16),c['args']) for c in calls]!=expected:raise AssertionError(calls)
    if machine.reg_read(UC_X86_REG_EIP)!=0x3b623fa:raise AssertionError('Shadow setup did not reach boundary')
    begin_calls=list(calls)
    phase='end';end_cases=[]
    for enabled,active,index,mask,zwrite,have_surfaces in itertools.product((0,1),(0,1),(-1,0,1),(0,15),(0,1),(0,1)):
        calls.clear();put(0x778388,enabled);put(0x2ee0c38,active);put(0x2ee0c3c,light)
        put(0x2ee0c4c,mask);put(0x2ee0c50,zwrite)
        for slot,handle in ((0x2ee0c44,scratch+0x6000),(0x2ee0c48,scratch+0x6100)):
            put(slot,handle if have_surfaces else 0);put(handle,scratch+0x7000)
        put(scratch+0x7008,scratch+0xa00)
        put(scratch+0xf000,sentinel);put(scratch+0xf004,index&0xffffffff)
        machine.reg_write(UC_X86_REG_ESP,scratch+0xf000)
        machine.emu_start(0x4f7500,sentinel,count=500)
        if machine.reg_read(UC_X86_REG_EIP)!=sentinel:raise AssertionError('Shadow restoration did not return')
        valid=bool(enabled and active and index==0)
        expected=[]
        if valid:
            expected=[(0x4b3050,[0x2ee0bd0])]
            if have_surfaces:expected += [(scratch+0xa00,[scratch+0x6000]),(scratch+0xa00,[scratch+0x6100])]
            expected += [(0x531a80,[0,scratch+0x6000 if have_surfaces else 0]),
                         (0x531900,[scratch+0x6100 if have_surfaces else 0]),
                         (0x531a30,[168,mask]),(0x531a30,[14,zwrite])]
        if [(int(c['function'],16),c['args']) for c in calls]!=expected:raise AssertionError(calls)
        if machine.reg_read(UC_X86_REG_EAX)!=(0 if valid else 0xffffffff):raise AssertionError('Wrong end-pass status')
        flags=struct.unpack('<2I',machine.mem_read(0x2ee0c38,8))
        if flags!=((0,0) if valid else (active,light)):raise AssertionError('Wrong active-pass restoration')
        end_cases.append(dict(enabled=enabled,active=active,index=index,color_mask=mask,zwrite=zwrite,surfaces=have_surfaces,calls=list(calls)))
    return dict(executable_sha256=EXE_SHA256,cases=cases,begin_pass_calls=begin_calls,end_pass_cases=end_cases,
                scope='Native allocation, caching, begin-pass setup and end-pass restoration; graphics calls intercepted. No caster geometry or actual GPU writes')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('executable',type=Path);parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=observe(args.executable);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print('Passed',len(report['cases']),'resource cases,',len(report['begin_pass_calls']),'begin calls and',len(report['end_pass_cases']),'restoration cases')

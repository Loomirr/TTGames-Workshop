"""Compare decoded BSA layer/blend samples with the original PC evaluator.

Requires pefile and unicorn, the documented executable and two extracted BSA
files. Allocators and time-context preparation are intercepted; original track
selection, scalar curves and blending execute. No game or Blender playback.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from animation_records import AnimationRecords
from check_native_curves import EXE_SHA256
from face_channels import sample_layers


def compare(executable, paths):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EAX
    raw = executable.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXE_SHA256:
        raise ValueError('Unknown executable; refusing unreviewed offsets')
    pe = pefile.PE(data=raw)
    image = pe.get_memory_mapped_image()
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    base = pe.OPTIONAL_HEADER.ImageBase
    machine.mem_map(base, (len(image)+4095)&~4095)
    machine.mem_write(base, image)
    scratch = 0x20000000
    machine.mem_map(scratch, 0x600000)
    machine.mem_write(0x3384c80, bytes(i.bit_count() for i in range(256)))
    clips = []
    roots = []
    for index, path in enumerate(paths):
        with path.open('rb') as stream:
            data = stream.read(0x100000)
        if len(data) >= 0x100000:
            raise ValueError('BSA exceeds isolated comparison buffer')
        clip = AnimationRecords(data, 'BSA')
        at = scratch + 0x10000 + index * 0x100000
        patched = bytearray(data)
        for offset in (8, 28, 32, 36):
            struct.pack_into('<I', patched, offset, at + clip.pointer(offset))
        for curve in clip._curves.values():
            for offset in (curve['address'], curve['address']+4, curve['address']+8):
                struct.pack_into('<I', patched, offset, at + clip.pointer(offset))
        for channel, record in enumerate(clip.records):
            if record['kind']:
                struct.pack_into('<I', patched, 48+4*channel, at+record['address'])
        machine.mem_write(at, bytes(patched))
        clips.append(clip)
        roots.append(at+16)
    heap = scratch+0x300000
    allocations = []
    def hook(machine, address, size, _):
        nonlocal heap
        if address not in (0x4b7cd0, 0x4b7d30, 0x4f9ca0):
            return
        sp = machine.reg_read(UC_X86_REG_ESP)
        ret, arg = struct.unpack('<2I', machine.mem_read(sp,8))
        if address == 0x4f9ca0:
            _, _, time, out = struct.unpack('<IIfI', machine.mem_read(sp,16))
            clip = clips[roots.index(arg)]
            t = max(1., min(time, struct.unpack('<f',struct.pack('<f',clip.duration-.01))[0]))
            frame = int(t)-1
            block, bit = min(frame//32, clip.blocks-1), frame%32
            machine.mem_write(out, struct.pack('<ff4I',t,t-block*32,block,(1<<(bit%8+1))-1,bit//8,bit))
        else:
            if arg > 65536:
                raise AssertionError('Unbounded native allocation')
            length = 4*arg + (8 if address==0x4b7cd0 else 0)
            machine.mem_write(heap, bytes(max(16,length)))
            machine.reg_write(UC_X86_REG_EAX,heap)
            allocations.append((heap,length))
            heap += (max(16,length)+15)&~15
        machine.reg_write(UC_X86_REG_ESP,sp+4)
        machine.reg_write(UC_X86_REG_EIP,ret)
    machine.hook_add(UC_HOOK_CODE,hook)
    layers = list(range(max(c.tracks for c in clips))) + [-1, max(c.tracks for c in clips)]
    layer_at, stack, stop = scratch+0x100, scratch+0x5ff000, scratch
    machine.mem_write(layer_at, struct.pack('<'+'h'*len(layers),*layers))
    cases = []
    maximum = 0.
    for mode in ('both','first','second'):
        for fraction in (0.,.17,.5,.93):
            times = [1+(c.duration-1.01)*fraction for c in clips]
            times = [struct.unpack('<f',struct.pack('<f',t))[0] for t in times]
            for blend in (0.,.25,1.):
                heap=scratch+0x300000;allocations.clear()
                a,b = (clips[0] if mode!='second' else None),(clips[1] if mode!='first' else None)
                expected=sample_layers(a,times[0],layers,second=b,second_time=times[1],blend=blend)
                machine.mem_write(stack,struct.pack('<IIIIfIff',stop,len(layers),layer_at,roots[0] if a else 0,times[0],roots[1] if b else 0,times[1],blend))
                machine.reg_write(UC_X86_REG_ESP,stack)
                machine.emu_start(0x3af9075,stop,count=200000)
                if machine.reg_read(UC_X86_REG_EIP)!=stop:
                    raise AssertionError('Native face evaluator did not return')
                table=machine.reg_read(UC_X86_REG_EAX)
                for index,values in enumerate(expected):
                    ptr=struct.unpack('<I',machine.mem_read(table+4*index,4))[0]
                    if values is None:
                        if ptr:raise AssertionError('Skipped layer was populated')
                        continue
                    if not ptr:raise AssertionError('Selected layer has no output')
                    native=struct.unpack('<'+'f'*len(values),machine.mem_read(ptr+8,4*len(values))) if values else ()
                    for left,right in zip(values,native):
                        error=abs(left-right);maximum=max(maximum,error)
                        if not error<=max(2e-5,abs(right)*2e-6):raise AssertionError((mode,index,left,right))
                cases.append(dict(mode=mode,times=times,blend=blend,decoded_layers=expected))
    return dict(executable_sha256=EXE_SHA256,clips=[c.summary() for c in clips],layers=layers,cases=cases,max_error=maximum,
        scope='Original BSA selection, curves and blending; intercepted allocation and time context. No target ownership or game playback')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable',type=Path)
    parser.add_argument('first',type=Path)
    parser.add_argument('second',type=Path)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=compare(args.executable,(args.first,args.second))
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Native BSA layer/blend cases:',len(report['cases']),'maximum error:',report['max_error'])

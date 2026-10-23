"""Observe original PC blend states and material-color uploads without Direct3D.

Requires pefile and unicorn, and the executable hash used by check_native_curves.
Intercepts the state wrapper and effect SetVector; never starts or patches a game.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from check_native_curves import EXE_SHA256
from alpha_passes import helper_states


def observe(path):
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EIP, UC_X86_REG_EBP
    with path.open('rb') as stream:raw=stream.read(128*1024*1024+1)
    if hashlib.sha256(raw).hexdigest()!=EXE_SHA256:
        raise ValueError('Unsupported executable hash for native blend-state comparison')
    pe=pefile.PE(data=raw);base=pe.OPTIONAL_HEADER.ImageBase
    image=pe.get_memory_mapped_image()
    machine=Uc(UC_ARCH_X86,UC_MODE_32)
    machine.mem_map(base,(len(image)+4095)&~4095);machine.mem_write(base,image)
    scratch=0x20000000;machine.mem_map(scratch,0x10000)
    states=[]

    def intercept(machine,address,size,data):
        stack=machine.reg_read(UC_X86_REG_ESP)
        target,state,value=struct.unpack('<3I',machine.mem_read(stack,12))
        states.append((state,value))
        machine.reg_write(UC_X86_REG_ESP,stack+4)
        machine.reg_write(UC_X86_REG_EIP,target)

    machine.hook_add(UC_HOOK_CODE,intercept,begin=0x531a30,end=0x531a30)
    expected={0:[(27,0),(19,2),(20,1)],1:[(27,1),(171,1),(19,5),(20,6)],
              2:[(27,1),(171,1),(19,5),(20,2)],3:[(27,1),(171,3),(19,5),(20,2)],
              4:[(27,1),(171,1),(19,5),(20,2)],5:[(27,1),(171,3),(19,1),(20,6)],
              6:[(27,1),(171,1),(19,9),(20,5)],10:[(27,0),(19,2),(20,1)]}
    result={}
    for mode,wanted in expected.items():
        states.clear();machine.mem_write(scratch+0x40,struct.pack('<I',mode))
        machine.reg_write(UC_X86_REG_ESI,scratch);machine.reg_write(UC_X86_REG_ESP,scratch+0xf000)
        machine.emu_start(0x520f29,0x521094,count=200)
        if machine.reg_read(UC_X86_REG_EIP)!=0x521094 or states!=wanted:
            raise AssertionError((mode,states,wanted))
        result[str(mode)]=list(states)
    # The queued renderer calls these AFTER the general material setter.
    # Its first alpha pass and complementary pass must not be inferred from
    # the general setter's temporary alpha-test-disable state alone.
    alpha_passes=[]
    for alpha_mode in range(8):
        for secondary in range(4):
            for reference in (0,125,255):
                attributes=1 | alpha_mode<<20 | reference<<23
                machine.mem_write(scratch+0x40,struct.pack('<II',attributes,secondary))
                observed=[]
                for entry in (0x521610,0x521720):
                    machine.mem_write(scratch+0xf000,struct.pack('<II',scratch+0xff00,scratch))
                    machine.reg_write(UC_X86_REG_ESP,scratch+0xf000);states.clear()
                    machine.emu_start(entry,scratch+0xff00,count=500)
                    if machine.reg_read(UC_X86_REG_EIP)!=scratch+0xff00:raise AssertionError('Alpha pass did not return')
                    observed.append(list(states))
                first,second=helper_states(attributes,secondary)
                if observed!=[first,second]:raise AssertionError((alpha_mode,secondary,observed))
                alpha_passes.append(dict(attributes=hex(attributes),secondary_mode=secondary,first=first,second=second))
    # Check the complete material-state routine, not just its blend branch.
    # Depth overrides are explicitly absent. Alpha fields are cached but this
    # routine disables fixed-function alpha testing; no invented cutout threshold.
    for address in (0x2fc7fa0,0x2fc7fa4,0x2fc7fa8):
        machine.mem_write(address,struct.pack('<I',0))
    full_states=[]
    depth_states=(((7,1),(14,1),(23,4)),((7,1),(14,0),(23,4)),
                  ((7,1),(14,1),(23,8)),((7,0),(14,0),(23,8)))
    for mode in expected:
        for cull in range(4):
            for depth in range(4):
                attributes=mode | cull<<12 | depth<<14 | 5<<20 | 125<<23
                machine.mem_write(scratch+0x40,struct.pack('<II',attributes,2))
                machine.mem_write(scratch+0xf000,struct.pack('<II',scratch+0xff00,scratch))
                machine.reg_write(UC_X86_REG_ESP,scratch+0xf000)
                states.clear()
                machine.emu_start(0x520ef0,scratch+0xff00,count=1000)
                wanted=expected[mode]+[(15,0),(22,(3,2,1,1)[cull])]+list(depth_states[depth])
                cached=tuple(struct.unpack('<I',machine.mem_read(at,4))[0]
                             for at in (0x334a584,0x3351a64,0x3358b00))
                if machine.reg_read(UC_X86_REG_EIP)!=scratch+0xff00 or states!=wanted or cached!=(5,250,2):
                    raise AssertionError((hex(attributes),states,wanted,cached))
                full_states.append(dict(attributes=hex(attributes),states=list(states),cached_alpha=cached))
    # Effect construction maps SEMANTIC_MATERIALCOLOR to object +0x78. Supply a
    # synthetic COM vtable so the original upload branch can call SetVector.
    # Runtime texture handle 0 means absent; it is NOT serialized HGP index 0.
    item,geometry,material,effect,com,vtable=(scratch+offset for offset in
                                           (0,0x100,0x200,0x400,0x600,0x700))
    def put(address,value):machine.mem_write(address,struct.pack('<I',value))
    machine.mem_write(scratch,b'\0'*0x1000)
    put(item+0x20,geometry);put(geometry+4,material)
    put(effect,com);put(effect+0x78,123);put(com,vtable);put(vtable+0x88,scratch+0x900)
    frame=scratch+0xe000;put(frame+8,item);put(frame-4,effect)
    uploads=[]
    vector_handle=123

    def capture_vector(machine,address,size,data):
        stack=machine.reg_read(UC_X86_REG_ESP)
        target,instance,handle,pointer=struct.unpack('<4I',machine.mem_read(stack,16))
        if instance!=com or handle!=vector_handle:
            raise AssertionError(('Unexpected effect parameter upload',hex(instance),handle,vector_handle,hex(target)))
        uploads.append(struct.unpack('<4f',machine.mem_read(pointer,16)))
        machine.reg_write(UC_X86_REG_ESP,stack+16)  # COM stdcall, three arguments.
        machine.reg_write(UC_X86_REG_EIP,target)

    machine.hook_add(UC_HOOK_CODE,capture_vector,begin=scratch+0x900,end=scratch+0x900)
    colors=[]
    for color in ((0.,0.,0.),(1.,1.,1.),(.25,.5,.75),(-.25,2.,.125)):
        for texture_handle in (0,1,7):
            uploads.clear()
            machine.mem_write(material+0x54,struct.pack('<3f',*color))
            machine.mem_write(material+0x78,struct.pack('<h',texture_handle))
            machine.reg_write(UC_X86_REG_EBP,frame)
            machine.reg_write(UC_X86_REG_ESP,frame-0x300)
            machine.emu_start(0x52ac00,0x52acd2,count=2000)
            expected_color=tuple(value/(2 if texture_handle else 1) for value in color)+(1.,)
            if machine.reg_read(UC_X86_REG_EIP)!=0x52acd2 or uploads!=[expected_color]:
                raise AssertionError((color,texture_handle,uploads,expected_color))
            colors.append(dict(diffuse=color,runtime_texture_handle=texture_handle,uploaded=uploads[0]))
    # Texture-specular strength is auxiliary material red * 0.1, not the
    # primary material's +0x60 scalar or Blender roughness.
    auxiliary = scratch + 0xa00
    put(material + 0x30, auxiliary); put(effect + 0xc0, 456)
    put(vtable + 0x78, scratch + 0x980)
    strengths = []

    def capture_float(machine, address, size, data):
        stack = machine.reg_read(UC_X86_REG_ESP)
        target, instance, handle = struct.unpack('<3I', machine.mem_read(stack, 12))
        value = struct.unpack('<f', machine.mem_read(stack + 12, 4))[0]
        if instance != com or handle != 456:
            raise AssertionError('Unexpected specular parameter upload')
        strengths.append(value)
        machine.reg_write(UC_X86_REG_ESP, stack + 16)
        machine.reg_write(UC_X86_REG_EIP, target)

    machine.hook_add(UC_HOOK_CODE, capture_float, begin=scratch+0x980, end=scratch+0x980)
    specular_cases = []
    for red in (0., .25, .5, 1., 2., 10.):
        strengths.clear()
        machine.mem_write(auxiliary+0x54, struct.pack('<3f', red, 7., 9.))
        machine.reg_write(UC_X86_REG_EBP, frame)
        machine.reg_write(UC_X86_REG_ESP, frame-0x300)
        machine.emu_start(0x52b0b4, 0x52b0f3, count=200)
        if machine.reg_read(UC_X86_REG_EIP) != 0x52b0f3 or len(strengths) != 1 or abs(strengths[0]-red*.1) > 1e-7:
            raise AssertionError((red, strengths))
        specular_cases.append(dict(auxiliary_red=red, uploaded=strengths[0]))
    from shader_reference import reflection_parameters
    vector_handle=789; put(effect+0xa0,vector_handle)
    reflection_cases=[]
    for scalar in (0.,.25,.5,1.,2.,10.):
        for low_scale,high_scale in ((0.,.32),(.1,.32),(.4,.8)):
            uploads.clear()
            machine.mem_write(material+0x60,struct.pack('<f',scalar))
            machine.mem_write(0x304379c,struct.pack('<f',low_scale))
            machine.mem_write(0x77af94,struct.pack('<f',high_scale))
            machine.reg_write(UC_X86_REG_EBP,frame)
            machine.reg_write(UC_X86_REG_ESP,frame-0x300)
            machine.emu_start(0x52ad2a,0x52ada1,count=500)
            wanted=reflection_parameters(scalar,low_scale,high_scale)
            if machine.reg_read(UC_X86_REG_EIP)!=0x52ada1 or len(uploads)!=1 or max(abs(a-b) for a,b in zip(uploads[0],wanted))>1e-6:
                raise AssertionError((scalar,low_scale,high_scale,uploads,wanted))
            reflection_cases.append(dict(material_scalar=scalar,minimum_scale=low_scale,maximum_scale=high_scale,uploaded=uploads[0]))
    view_cases=[]
    stop_address=None
    def stop_at_boundary(machine,address,size,data):
        if address==stop_address:machine.emu_stop()
    machine.hook_add(UC_HOOK_CODE,stop_at_boundary)
    transform=scratch+0x1100;put(item+0x1c,transform)
    for semantic,offset,begin,end,source_address in (
            ('PlayerPosition',0x98,0x52acd2,0x52ad2a,transform+0x30),
            ('CameraPosition',0xb0,0x52ada1,0x52adec,0x33fe0f0)):
        vector_handle=790+offset;put(effect+offset,vector_handle)
        for xyz in ((0.,0.,0.),(.5,-2.,3.),(40.,50.,-60.)):
            uploads.clear();machine.mem_write(source_address,struct.pack('<3f',*xyz))
            machine.reg_write(UC_X86_REG_EBP,frame);machine.reg_write(UC_X86_REG_ESP,frame-0x300)
            stop_address=end
            machine.emu_start(begin,end,count=500)
            if machine.reg_read(UC_X86_REG_EIP)!=end or uploads!=[xyz+(1.,)]:
                raise AssertionError((semantic,xyz,uploads))
            view_cases.append(dict(semantic=semantic,xyz=xyz,uploaded=uploads[0]))
    # Original directional/ambient uploads use item+0x34, not material RGB.
    # Execute all seven setters, including the original vector constructor and
    # reviewed trampoline at 0x405903. Colors are halved; directions are copied.
    from shader_reference import native_lighting
    import random
    rng=random.Random(20261022)
    light_block=scratch+0x1800;put(item+0x34,light_block)
    lighting_cases=[]
    branches=((0x48,0x52a936,0x52a988),(0x50,0x52a988,0x52a9fd),
              (0x58,0x52a9fd,0x52aa4f),(0x60,0x52aa4f,0x52aac4),
              (0x68,0x52aac4,0x52ab16),(0x70,0x52ab16,0x52ab8b),
              (0x40,0x52ab8b,0x52ac00))
    for case in range(64):
        directions=[tuple(rng.uniform(-2,2) for _ in range(3)) for _ in range(3)]
        colors_native=[tuple(rng.uniform(-1,4) for _ in range(4)) for _ in range(4)]
        for index,direction in enumerate(directions):
            machine.mem_write(light_block+0x104+12*index,struct.pack('<3f',*direction))
        for index,color in enumerate(colors_native):
            machine.mem_write(light_block+0x128+16*index,struct.pack('<4f',*color))
        ambient,lights=native_lighting(colors_native[3],directions,colors_native[:3])
        wanted=[]
        for index,(direction,color) in enumerate(lights):
            wanted.extend((direction+(1.,),color+(colors_native[index][3],)))
        wanted.append(ambient+(colors_native[3][3],))
        observed=[]
        for (offset,begin,end),value in zip(branches,wanted):
            vector_handle=1000+offset;put(effect+offset,vector_handle)
            uploads.clear();stop_address=end
            machine.reg_write(UC_X86_REG_EBP,frame);machine.reg_write(UC_X86_REG_ESP,frame-0x300)
            machine.emu_start(begin,end,count=500)
            if machine.reg_read(UC_X86_REG_EIP)!=end or len(uploads)!=1 or max(abs(a-b) for a,b in zip(uploads[0],value))>3e-7:
                raise AssertionError(('lighting',case,hex(offset),uploads,value))
            observed.append(uploads[0])
        lighting_cases.append(dict(directions=directions,colors=colors_native,uploaded=observed))
    return dict(executable_sha256=EXE_SHA256,states=result,full_material_states=full_states,material_color_uploads=colors,
                lighting_uploads=lighting_cases,alpha_passes=alpha_passes,
                specular_strength_uploads=specular_cases,reflection_parameter_uploads=reflection_cases,view_position_uploads=view_cases,
                scope='Original blend and material-color branches; intercepted setters with synthetic inputs; no pixel shader, texture loading or draw call')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable',type=Path);parser.add_argument('report',type=Path)
    args=parser.parse_args()
    if args.report.exists():parser.error('Choose a new report path')
    report=observe(args.executable)
    with args.report.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()

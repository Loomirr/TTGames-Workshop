"""Bounded DDS face extraction for the optional LSW1 shader experiment.

Only the observed complete, square, single-level legacy DDS cube layouts are
accepted. Faces stay in Direct3D order (+X,-X,+Y,-Y,+Z,-Z); pixel blocks are
copied unchanged, with a 2D header for Blender. No panorama resampling.
"""
import struct


def split_faces(raw):
    if len(raw)<128 or raw[:4]!=b'DDS ':
        raise ValueError('Reflection cube needs a legacy DDS header')
    u32=lambda offset:struct.unpack_from('<I',raw,offset)[0]
    if u32(4)!=124 or u32(76)!=32 or u32(112)!=0xfe00:
        raise ValueError('Reflection DDS must contain all six cube faces')
    height,width=u32(12),u32(16)
    if not 1<=width<=2048 or width&(width-1) or height!=width or u32(24)!=0 or u32(28) not in (0,1):
        raise ValueError('Reflection lab supports square single-level cubes up to 2048 pixels')
    flags=u32(80);fourcc=raw[84:88]
    if flags&4 and fourcc in (b'DXT1',b'DXT3',b'DXT5'):
        face_size=((width+3)//4)**2*(8 if fourcc==b'DXT1' else 16)
    elif flags&0x40 and not flags&4 and u32(88) in (24,32):
        masks=tuple(u32(i) for i in (92,96,100,104))
        if masks[:3]!=(0xff0000,0xff00,0xff) or masks[3] not in (0,0xff000000):
            raise ValueError('Unverified reflection DDS color masks')
        if u32(88)==24 and masks[3]:
            raise ValueError('24-bit reflection DDS cannot contain an alpha mask')
        row_size=width*(u32(88)//8)
        if u32(20) not in (0,row_size):
            raise ValueError('Padded DDS cube rows are outside this experiment')
        face_size=row_size*height
    else:
        raise ValueError('Unsupported reflection DDS pixel layout')
    if len(raw)!=128+6*face_size:
        raise ValueError('Reflection DDS payload does not match six complete faces')
    header=bytearray(raw[:128])
    struct.pack_into('<I',header,108,0x1000)  # DDSCAPS_TEXTURE, 2D face.
    struct.pack_into('<I',header,112,0)
    return tuple(bytes(header)+raw[128+i*face_size:128+(i+1)*face_size] for i in range(6))


def load_faces(path, output):
    """Load and pack unchanged face payloads into a background Blender scene."""
    import bpy
    with path.open('rb') as stream:
        raw=stream.read(128*1024*1024+1)
    if len(raw)>128*1024*1024:raise ValueError('Reflection cube exceeds the 128 MiB input limit')
    faces=split_faces(raw)
    output.mkdir(parents=True,exist_ok=False)
    images=[]
    for i,raw in enumerate(faces):
        face=output/f'face-{i}.dds'
        face.write_bytes(raw)
        image=bpy.data.images.load(str(face),check_existing=False)
        image.colorspace_settings.name='Non-Color'
        image.pack();images.append(image)
    return images


def sample_nodes(nodes, links, math, vec, direction, images):
    """Direct3D major-axis lookup; input is the lab's Blender Z-up direction.

    Image nodes use bottom-up V; native cube faces use top-down V. Filtering is
    per-face bilinear with edge extension; seamless/mip filtering is unverified.
    """
    if len(images)!=6:raise ValueError('A reflection cube needs six face images')
    split=nodes.new('ShaderNodeSeparateXYZ');links.new(direction,split.inputs[0])
    x,z,y=split.outputs  # Blender to original game coordinates.
    ax,ay,az=[math('ABSOLUTE',v) for v in (x,y,z)]
    ge=lambda a,b:math('SUBTRACT',1.,math('LESS_THAN',a,b))
    mx=math('MULTIPLY',ge(ax,ay),ge(ax,az))
    my=math('MULTIPLY',math('SUBTRACT',1.,mx),ge(ay,az))
    mz=math('SUBTRACT',1.,math('ADD',mx,my))
    neg=lambda v:math('MULTIPLY',v,-1.)
    axes=((x,ax,mx,neg(z),neg(y)),(x,ax,mx,z,neg(y)),
          (y,ay,my,x,z),(y,ay,my,x,neg(z)),
          (z,az,mz,x,neg(y)),(z,az,mz,neg(x),neg(y)))
    result=(0.,0.,0.)
    for i,(axis,major,mask,s,t) in enumerate(axes):
        positive=ge(axis,0.)
        weight=math('MULTIPLY',mask,positive if i%2==0 else math('SUBTRACT',1.,positive))
        uv=nodes.new('ShaderNodeCombineXYZ')
        # Non-selected faces still evaluate: avoid division by zero and bound
        # their unused UVs before image sampling (huge UVs can crash Cycles).
        denominator=math('MAXIMUM',major,1e-12)
        links.new(math('MULTIPLY',.5,math('ADD',1.,math('DIVIDE',s,denominator)),clamp=True),uv.inputs[0])
        links.new(math('MULTIPLY',.5,math('SUBTRACT',1.,math('DIVIDE',t,denominator)),clamp=True),uv.inputs[1])
        texture=nodes.new('ShaderNodeTexImage');texture.image=images[i]
        texture.interpolation='Linear';texture.extension='EXTEND'
        links.new(uv.outputs[0],texture.inputs['Vector'])
        result=vec('ADD',result,vec('SCALE',texture.outputs['Color'],weight))
    return result

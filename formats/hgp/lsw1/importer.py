"""Convert validated original LSW1 character data into Blender objects."""
import math
from pathlib import Path
import tempfile
import uuid
from contextlib import contextmanager

import bpy
from mathutils import Matrix, Vector

from .hgp import HGP
from .colour import diffuse_to_linear

C=Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
DATA_TYPES=('objects','meshes','armatures','materials','images','collections')


@contextmanager
def texture_temp_directory():
    # Default inherited permissions also work with Windows restricted tokens;
    # Python's TemporaryDirectory uses a private ACL for mode 0o700 there.
    base=Path(tempfile.gettempdir()).resolve()
    path=base/f'lsw1_hgp_{uuid.uuid4().hex}'
    path.mkdir()
    try:
        yield path
    finally:
        # Only this unique flat directory's generated texture files are removed.
        if path.parent.resolve()==base and path.name.startswith('lsw1_hgp_'):
            for file in path.iterdir():file.unlink()
            path.rmdir()


def snapshot_data():
    return {name:set(getattr(bpy.data,name)) for name in DATA_TYPES}


def remove_created_data(context, before):
    """Roll back a failed file without touching objects from the user's scene."""
    if context.object and context.object.mode!='OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for name in DATA_TYPES:
        data=getattr(bpy.data,name)
        for item in set(data)-before[name]:data.remove(item,do_unlink=True)


def matrix(values):
    return Matrix([values[i:i+4] for i in range(0,16,4)]).transposed()


def make_materials(h, label, load_textures):
    textures=[]
    if load_textures:
        with texture_temp_directory() as temp:
            for i,raw in enumerate(h.textures()):
                path=Path(temp)/f'texture_{i:02d}.dds';path.write_bytes(raw)
                image=bpy.data.images.load(str(path),check_existing=False)
                image.name=f'{label} texture {i:02d}'
                image.colorspace_settings.name='sRGB'
                if not len(image.pixels):raise ValueError(f'Blender cannot decode texture {i}')
                image.filepath_raw=str(path.with_suffix('.png'))
                image.file_format='PNG';image.save();image.pack()
                image.filepath=f'//lsw1_textures/{h.path.stem}_texture_{i:02d}.png'
                textures.append(image)
    result=[]
    sources=h.materials()
    normal_indices={s['normal_texture'] for s in sources if s['normal_texture'] is not None}
    # Share images only within the same colour-space role. A texture can also
    # appear as an auxiliary material's base texture, so retain sRGB separately.
    normal_images={}
    if load_textures:
        for index in normal_indices:
            if index>=len(textures):raise ValueError(f'Missing normal texture {index}')
            image=textures[index].copy();image.name=f'{label} normal {index:02d}'
            image.colorspace_settings.name='Non-Color';image.pack();normal_images[index]=image
    for i,source in enumerate(sources):
        material=bpy.data.materials.new(f'{label} material {i:02d}');material.use_nodes=True
        # Native palette floats are display RGB, matching the byte texture colors.
        # Image nodes already convert sRGB to linear; constant sockets must do so
        # explicitly, otherwise solid plastic becomes much paler than the printing.
        linear=diffuse_to_linear(source['diffuse'])
        material.diffuse_color=(*linear,1)
        material['lsw1_diffuse_srgb']=list(source['diffuse'])
        material['lsw1_diffuse_linear']=list(linear)
        material['lsw1_colour_version']=1
        material['lsw1_effect_id']=source['effect'];material['lsw1_attributes']=source['attributes']
        bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.38
        texture=source['texture']
        if load_textures and texture is not None:
            if texture>=len(textures):raise ValueError(f'Material {i} references missing texture {texture}')
            node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=textures[texture]
            material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
            if source['attributes'] & 15 in (1,10):
                material.node_tree.links.new(node.outputs['Alpha'],bsdf.inputs['Alpha'])
                if hasattr(material,'surface_render_method'):material.surface_render_method='DITHERED'
        else:bsdf.inputs['Base Color'].default_value=(*linear,1)
        normal=source['normal_texture']
        material['lsw1_linked_material']=source['linked_material']
        material['lsw1_normal_texture']=normal if normal is not None else -1
        if load_textures and normal is not None:
            node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=normal_images[normal];node.label='Original LSW1 normal map'
            normal_node=material.node_tree.nodes.new('ShaderNodeNormalMap');normal_node.uv_map='Original LSW1 UV';normal_node.space='TANGENT'
            material.node_tree.links.new(node.outputs['Color'],normal_node.inputs['Color'])
            material.node_tree.links.new(normal_node.outputs['Normal'],bsdf.inputs['Normal'])
        result.append(material)
    return result


def import_character(context,path,location=(0,0,0),scale=1.0,armature=True,textures=True,
                     custom_normals=True,detail='AUTO',correct_preview_pose=True,variant_layers=()):
    h=HGP(path);parts=h.meshes(lod=detail);label=h.path.stem.replace('_',' ').title()
    # Optional scene-builder variants retain the same native skeleton/weights.
    seen={(p['geometry'],p['primitive'],p['rigid_bone']) for p in parts}
    for layer in variant_layers:
        for part in h.meshes(lod=layer):
            identity=(part['geometry'],part['primitive'],part['rigid_bone'])
            if identity not in seen:parts.append(part);seen.add(identity)
    # Check native transforms before creating scene data.
    worlds=[];max_error=0
    for bone in h.bones:
        local=matrix(bone['local'])
        world=worlds[bone['parent']]@local if bone['parent']>=0 else local
        inverse=matrix(bone['inverse'])
        error=max(abs(x-y) for row1,row2 in zip(world.inverted(),inverse) for x,y in zip(row1,row2))
        if not math.isfinite(error) or error>2e-5:raise ValueError('Unsupported or inconsistent native bind transforms')
        max_error=max(max_error,error);worlds.append(world)
    worlds=[C@m@C for m in worlds]
    mats=make_materials(h,label,textures)
    if any(p['material']>=len(mats) for p in parts):raise ValueError('Invalid material reference')
    collection=bpy.data.collections.new(f'LSW1 {label}');context.scene.collection.children.link(collection)
    data=bpy.data.armatures.new(f'{label} native skeleton') if armature else None
    root=bpy.data.objects.new(f'{label} RIG' if armature else f'{label} ROOT',data)
    collection.objects.link(root);root.location=location;root.scale=(scale,)*3
    root['source_game']='LEGO Star Wars: The Video Game (2005 PC)'
    root['lsw1_source_file']=str(h.path);root['lsw1_bind_inverse_max_error']=max_error
    root['lsw1_layers']=', '.join(h.layers)
    root['lsw1_imported_detail']=str(detail)
    root['lsw1_native_weights']=bool(armature)
    root['lsw1_animation_status']='No game animations imported'
    names=[]
    if armature:
        bpy.ops.object.select_all(action='DESELECT');root.select_set(True)
        context.view_layer.objects.active=root;root.show_in_front=True;data.display_type='STICK'
        bpy.ops.object.mode_set(mode='EDIT')
        for native,world in zip(h.bones,worlds):
            bone=data.edit_bones.new(native['name']);names.append(bone.name)
            bone.head=world.translation;bone.tail=bone.head+world.to_3x3()@Vector((0,.028,0))
            bone.matrix=world;bone.length=.028
            if native['parent']>=0:bone.parent=data.edit_bones[names[native['parent']]]
            bone.use_connect=False
        bpy.ops.object.mode_set(mode='OBJECT')
        for native,name in zip(h.bones,names):
            data.bones[name]['lsw1_joint_index']=native['index']
            data.bones[name]['lsw1_original_name']=native['name']
    else:root.empty_display_type='PLAIN_AXES';root.empty_display_size=.1
    for index,part in enumerate(parts):
        bind=worlds[part['rigid_bone']] if part['rigid_bone'] is not None else Matrix.Identity(4)
        vertices=[bind@Vector((v[0],v[2],v[1])) for v in part['vertices']]
        # The mesh-only path bakes the optional preview-facing correction.
        if not armature and correct_preview_pose and h.path.stem.lower()=='jangofett' and part['rigid_bone'] is not None and h.bones[part['rigid_bone']]['name']=='helmet':
            correction=bind@Matrix.Rotation(math.pi,4,'X')@bind.inverted()
            vertices=[correction@v for v in vertices]
            normal_matrix=correction.to_3x3()@bind.to_3x3()
        else:normal_matrix=bind.to_3x3()
        mesh=bpy.data.meshes.new(f'{label} mesh {index:02d}')
        mesh.from_pydata(vertices,[],part['faces']);mesh.update()
        obj=bpy.data.objects.new(f'{label} part {index:02d}',mesh);collection.objects.link(obj)
        obj.parent=root;mesh.materials.append(mats[part['material']])
        obj['lsw1_geometry_offset']=hex(part['geometry']);obj['lsw1_vertex_buffer']=part['buffer']
        obj['lsw1_attachment_bone']=part['rigid_bone'] if part['rigid_bone'] is not None else -1
        uv=mesh.uv_layers.new(name='Original LSW1 UV')
        normals=[]
        for polygon in mesh.polygons:
            polygon.use_smooth=custom_normals
            for li in polygon.loop_indices:
                vi=mesh.loops[li].vertex_index;u,v=part['uvs'][vi];uv.data[li].uv=(u,1-v)
                if custom_normals:
                    n=part['normals'][vi];normals.append((normal_matrix@Vector((n[0],n[2],n[1]))).normalized())
        if custom_normals:mesh.normals_split_custom_set(normals)
        if armature:
            groups={}
            for vi,weights in enumerate(part['weights']):
                for bi,weight in weights.items():
                    if bi not in groups:groups[bi]=obj.vertex_groups.new(name=names[bi])
                    groups[bi].add([vi],weight,'REPLACE')
            modifier=obj.modifiers.new('Native LSW1 skinning','ARMATURE');modifier.object=root
    if armature and correct_preview_pose and h.path.stem.lower()=='jangofett':
        helmet=root.pose.bones.get('helmet')
        if helmet:
            helmet.rotation_mode='XYZ';helmet.rotation_euler=(math.pi,0,0)
            root['lsw1_preview_pose_correction']='Jango helmet faces forward; clear pose transforms for native bind pose'
    return root

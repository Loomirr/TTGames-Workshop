"""Build a Blender scene from a LEGO Star Wars II model (.hgp).

The game is left-handed with Y up and characters facing -Z. Blender is right-handed with Z up, so
game (x, y, z) becomes Blender (x, z, y): characters face -Y, and triangle winding is reversed.

What is created, under one armature object named after the file:
- one bone per game bone, at its bind pose;
- one mesh object per geometry part, in a collection per detail layer. A skinned part sits in model
  space with an Armature modifier; a rigid part sits in its bone's space, parented to that bone;
- one material per game material, with its embedded texture packed into the .blend;
- an empty per attachment point (weapon hands, look-at target and so on), parented to its bone.
Each object carries `lsw2_*` custom properties that the exporter uses to find the original part.
"""
import os
import re
import tempfile

import bpy
from mathutils import Matrix, Vector

from . import hgp
from .exporter_support import pixel_hash

# game -> Blender basis change (a mirror: swaps Y and Z)
SWAP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def to_blender_point(v):
    return (v[0], v[2], v[1])


def to_blender_matrix(m16):
    """Game row-major matrix (row vectors, translation in the last row) -> Blender Matrix."""
    rows = [m16[0:4], m16[4:8], m16[8:12], m16[12:16]]
    column_form = Matrix(rows).transposed()
    return SWAP @ column_form @ SWAP


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


# detail-level layer names: TT1_Special, TT2_HiRes, TT3_MedRes, TT4_VeryLoRes, TT1_High_res, TT3_VLoRes ...
DETAIL_LEVEL = re.compile(r'^tt\d+_(special|hi(gh)?(_?res)?|med(ium)?(_?res)?|lo(w)?(_?res)?|v(ery)?_?lo(w)?(_?res)?)$',
                          re.IGNORECASE)


def pick_layers(model):
    """Layers shown after import: defaultLayer, the most detailed detail level (by vertex count), and
    every other layer (hair, helmets, capes, vehicle pieces) except death variants."""
    verts = {}
    for p in model.parts:
        verts[p.layer] = verts.get(p.layer, 0) + len(p.positions)
    shown = set()
    levels = []
    for layer in model.layers:
        i, name = layer['index'], layer['name']
        if i not in verts:
            continue
        if i == 0:
            shown.add(i)
        elif DETAIL_LEVEL.match(name):
            levels.append(i)
        elif 'die' not in name.lower():
            shown.add(i)
    if levels:
        shown.add(max(levels, key=lambda i: verts[i]))
    return shown or set(verts)


def load_textures(model, name):
    images = []
    tmp = tempfile.mkdtemp(prefix='lsw2_hgp_')
    for i, t in enumerate(model.textures):
        path = os.path.join(tmp, f'{name}_{i}.dds')
        with open(path, 'wb') as f:
            f.write(t['dds'])
        img = bpy.data.images.load(path)
        img.name = f'{name}_tex{i}'
        img.pack()
        img.filepath_raw = ''
        img['lsw2_texture'] = i
        img['lsw2_pixels'] = pixel_hash(img)        # the exporter re-encodes the image only if this changes
        images.append(img)
        os.remove(path)
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    return images


def build_material(name, index, m, images):
    mat = bpy.data.materials.new(f'{name}_mat{index}')
    mat['lsw2_material'] = index
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    colour = [srgb_to_linear(max(0.0, min(1.0, c))) for c in m['colour']] + [1.0]
    bsdf.inputs['Base Color'].default_value = colour
    bsdf.inputs['Roughness'].default_value = 0.35
    mat.diffuse_color = colour
    if m['alpha'] < 1.0:
        bsdf.inputs['Alpha'].default_value = max(0.0, m['alpha'])
        mat.diffuse_color[3] = max(0.0, m['alpha'])
        if hasattr(mat, 'surface_render_method'):
            mat.surface_render_method = 'BLENDED'
    if m['texture'] is not None and m['texture'] < len(images):
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = images[m['texture']]
        tex.location = (-600, 200)
        # texture colour times the material colour; texture alpha times the material opacity (decals such
        # as faces are see-through where their texture is)
        mix = nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.location = (-300, 200)
        mix.inputs['Factor'].default_value = 1.0
        mix.inputs['A'].default_value = colour
        links.new(tex.outputs['Color'], mix.inputs['B'])
        links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
        opacity = nodes.new('ShaderNodeMath')
        opacity.operation = 'MULTIPLY'
        opacity.location = (-300, -100)
        opacity.inputs[1].default_value = max(0.0, min(1.0, m['alpha']))
        links.new(tex.outputs['Alpha'], opacity.inputs[0])
        links.new(opacity.outputs['Value'], bsdf.inputs['Alpha'])
        if hasattr(mat, 'surface_render_method'):
            mat.surface_render_method = 'DITHERED'
        elif hasattr(mat, 'blend_method'):
            mat.blend_method = 'HASHED'
    return mat


def import_hgp(context, filepath, show_all_layers=False, animations=True, animation_folder='', report=print,
               unproven_animations=False):
    with open(filepath, 'rb') as f:
        data = f.read()
    model = hgp.Model(data)
    name = os.path.splitext(os.path.basename(filepath))[0]

    root = bpy.data.collections.new(name)
    context.scene.collection.children.link(root)

    # armature
    arm_data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, arm_data)
    arm['lsw2_source'] = os.path.abspath(filepath)
    arm['lsw2_size'] = len(data)
    root.objects.link(arm)
    context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    worlds = [to_blender_matrix(b['world']) for b in model.bones]
    edit = []
    for i, b in enumerate(model.bones):
        eb = arm_data.edit_bones.new(b['name'] or f'bone{i}')
        eb.head = (0, 0, 0)
        eb.tail = (0, 0.02, 0)
        if b['parent'] >= 0:
            eb.parent = edit[b['parent']]
        m = worlds[i].normalized()
        eb.matrix = m
        edit.append(eb)
    bone_names = [eb.name for eb in edit]
    bpy.ops.object.mode_set(mode='OBJECT')
    for i, bname in enumerate(bone_names):
        arm_data.bones[bname]['lsw2_bone'] = i

    images = load_textures(model, name)
    materials = [build_material(name, i, m, images) for i, m in enumerate(model.materials)]

    shown = set(range(len(model.layers))) if show_all_layers else pick_layers(model)
    layer_cols = []
    for layer in model.layers:
        col = bpy.data.collections.new(f'{name} {layer["index"]} {layer["name"]}')
        col['lsw2_layer'] = layer['index']        # new meshes put here are exported into this layer
        root.children.link(col)
        layer_cols.append(col)
        if layer['index'] not in shown:
            col.hide_viewport = True
            col.hide_render = True

    for index, part in enumerate(model.parts):
        obj = build_part(name, index, part, model, materials, arm, bone_names, worlds)
        layer_cols[part.layer].objects.link(obj)

    for p in model.points:
        empty = bpy.data.objects.new(f'{name} {p["name"]}', None)
        empty.empty_display_type = 'ARROWS'
        empty.empty_display_size = 0.02
        empty['lsw2_point'] = p['name']
        root.objects.link(empty)
        if 0 <= p['bone'] < len(bone_names):
            local = to_blender_matrix(p['matrix'])
            empty.parent = arm
            empty.parent_type = 'BONE'
            empty.parent_bone = bone_names[p['bone']]
            empty.matrix_world = arm.matrix_world @ worlds[p['bone']] @ local
    if animations:
        from . import anim_import
        made, refused = anim_import.import_clips(context, arm, model, filepath, animation_folder, report,
                                                 unproven_animations)
        arm['lsw2_clips'] = len(made)
    return arm, model


def build_part(name, index, part, model, materials, arm, bone_names, worlds):
    mesh = bpy.data.meshes.new(f'{name}_part{index}')
    verts = [to_blender_point(v) for v in part.positions]
    faces = [(a, c, b) for a, b, c in part.triangles()]     # mirror: reverse the winding
    mesh.from_pydata(verts, [], faces)
    uv = mesh.uv_layers.new(name='UVMap')
    loops = [li for poly in mesh.polygons for li in poly.loop_indices]
    for li in loops:
        vi = mesh.loops[li].vertex_index
        u, v = part.uvs[vi]
        uv.data[li].uv = (u, 1.0 - v)
    colour = mesh.attributes.new('lsw2_colour', 'INT', 'POINT')
    for i, c in enumerate(part.colours):
        colour.data[i].value = c - (1 << 32) if c >= 1 << 31 else c
    mesh.update()
    mesh.normals_split_custom_set_from_vertices([to_blender_point(n) for n in part.normals])
    mesh.materials.append(materials[part.material])

    obj = bpy.data.objects.new(f'{name} L{part.layer} {part.slot} {index}', mesh)
    obj['lsw2_part'] = index
    obj['lsw2_layer'] = part.layer
    obj['lsw2_slot'] = part.slot
    obj['lsw2_buffer'] = part.buffer
    if part.shapes:
        obj['lsw2_morph_ids'] = [sid for sid, _ in part.shapes]
        basis = obj.shape_key_add(name='Basis', from_mix=False)
        for k, (sid, deltas) in enumerate(part.shapes):
            if deltas is None:
                continue                  # an empty slot in the file: no key; it stays empty on export
            key = obj.shape_key_add(name=f'morph {k}', from_mix=False)
            key.value = 0.0                   # new keys start at 1.0 in recent Blender: show the basis
            for i, d in enumerate(deltas):
                key.data[i].co = basis.data[i].co + Vector(to_blender_point(d))
    if part.slot == 'rigid':
        obj['lsw2_bone'] = part.bone
        bname = bone_names[part.bone]
        obj.parent = arm
        obj.parent_type = 'BONE'
        obj.parent_bone = bname
        obj.matrix_world = arm.matrix_world @ worlds[part.bone]
        group = obj.vertex_groups.new(name=bname)
        group.add(range(len(verts)), 1.0, 'REPLACE')
    else:
        obj.parent = arm
        groups = {}
        for vi, slots in enumerate(part.weights):
            for b, w in slots:
                g = groups.get(b)
                if g is None:
                    g = groups[b] = obj.vertex_groups.new(name=bone_names[b])
                g.add([vi], w, 'ADD')
        mod = obj.modifiers.new('Armature', 'ARMATURE')
        mod.object = arm
    return obj

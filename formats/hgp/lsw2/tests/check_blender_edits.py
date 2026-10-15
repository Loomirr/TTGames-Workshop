"""Edit-path checks for the LEGO Star Wars II add-on, in Blender's background mode (no window):

    blender -b --factory-startup --python formats/hgp/lsw2/tests/check_blender_edits.py -- <out folder> <model.hgp> [...]

Per model, each from a fresh import, through the add-on's own operators:
  duplicate  a part's object (skinned if any) is duplicated: one more part, a copy of its vertices
  delete     a part's object is deleted: one part fewer, the rest unchanged
  bones      a skinned part is weighted to every bone in turn: it is split into parts of at most 8 bones,
             same triangle count, every vertex on exactly one bone of its part
  morph      a face part with facial shapes gets an extra vertex and an edited shape key: the shapes follow
Every written file must read back.
"""
import importlib
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

PACKAGE = Path(__file__).resolve().parents[1]           # this add-on's folder
sys.path.insert(0, str(PACKAGE.parent))
io_lsw2_hgp = importlib.import_module(PACKAGE.name)
exporter, hgp = (importlib.import_module(f'{PACKAGE.name}.{m}') for m in ('exporter', 'hgp'))

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0])
out.mkdir(parents=True, exist_ok=True)
io_lsw2_hgp.register()
fails = []


def fresh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)     # the add-on's classes stay registered
    bpy.ops.import_scene.lsw2_hgp(filepath=path)
    arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    return arm, hgp.Model(Path(path).read_bytes())


def export(arm, name):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = arm
    target = out / f'{name}.hgp'
    result = bpy.ops.export_scene.lsw2_hgp(filepath=str(target))
    if result != {'FINISHED'}:
        raise RuntimeError(f'export cancelled: {result}')
    return hgp.Model(target.read_bytes())


def check(label, ok, detail=''):
    print(f'CHECK {label}: {"ok" if ok else "FAILED"} {detail}')
    if not ok:
        fails.append(label)


def tri_count(m):
    return sum(len(p.triangles()) for p in m.parts)


for path in argv[1:]:
    name = Path(path).stem

    # duplicate
    arm, orig = fresh(path)
    src = next((o for o in exporter.collect(arm) if o['lsw2_slot'] != 'rigid'), None) or exporter.collect(arm)[0]
    if src is not None:
        dup = src.copy()
        dup.data = src.data.copy()
        for col in src.users_collection:
            col.objects.link(dup)
        del dup['lsw2_part']
        m = export(arm, f'{name}_dup')
        before = orig.parts[int(src['lsw2_part'])]
        new = [p for p in m.parts if p.offset is not None and p.offset >= orig.texture_block]
        same = bool(new) and sorted(new[0].positions) == sorted(before.positions)
        check(f'{name} duplicate', len(m.parts) == len(orig.parts) + 1 and same,
              f'parts {len(orig.parts)} -> {len(m.parts)}')

    # delete
    arm, orig = fresh(path)
    victim = exporter.collect(arm)[0]
    gone = int(victim['lsw2_part'])
    bpy.data.objects.remove(victim)
    m = export(arm, f'{name}_del')
    kept = [p for i, p in enumerate(orig.parts) if i != gone]
    check(f'{name} delete', len(m.parts) == len(orig.parts) - 1 and
          [(p.positions, p.strip) for p in m.parts] == [(p.positions, p.strip) for p in kept],
          f'parts {len(orig.parts)} -> {len(m.parts)}')

    # bones: weight a skinned part to every bone in turn
    arm, orig = fresh(path)
    src = next((o for o in exporter.collect(arm) if o['lsw2_slot'] != 'rigid'), None)
    if src is not None and len(arm.data.bones) > 8:
        src.vertex_groups.clear()
        groups = [src.vertex_groups.new(name=b.name) for b in arm.data.bones]
        for v in src.data.vertices:
            groups[v.index % len(groups)].add([v.index], 1.0, 'REPLACE')
        m = export(arm, f'{name}_bones')
        edited = orig.parts[int(src['lsw2_part'])].offset
        rebuilt = [p for p in m.parts if p.offset == edited or p.offset >= orig.texture_block]
        ok = tri_count(m) == tri_count(orig) and all(len(p.palette) <= 8 for p in m.parts) and \
            all(len(w) == 1 for p in rebuilt for w in p.weights) and len(rebuilt) > 1
        check(f'{name} bones', ok, f'parts {len(orig.parts)} -> {len(m.parts)}, the edited one became '
                                   f'{len(rebuilt)}, triangles {tri_count(orig)} -> {tri_count(m)}')

    # morph: a face with facial shapes gets an extra vertex and one shape key is changed; the shapes
    # follow the edit (the record moves to fit its larger morph block)
    arm, orig = fresh(path)
    face = next((o for o in exporter.collect(arm) if o.get('lsw2_morph_ids')), None)
    if face is not None:
        index = int(face['lsw2_part'])
        before = orig.parts[index]
        keys = face.data.shape_keys.key_blocks
        moved_key = next(k for k in keys if k.name.startswith('morph '))
        slot = int(moved_key.name[6:])
        for d in moved_key.data:
            d.co.x += 0.001
        bm = bmesh.new()
        bm.from_mesh(face.data)
        bm.edges.ensure_lookup_table()
        bmesh.ops.subdivide_edges(bm, edges=[bm.edges[0]], cuts=1)
        bm.to_mesh(face.data)
        bm.free()
        m = export(arm, f'{name}_morph')
        got = [p for p in m.parts if p.shapes and p.layer == before.layer and p.slot == before.slot
               and p.material == before.material and len(p.positions) > len(before.positions)]
        ok = len(got) == 1 and len(got[0].shapes) == len(before.shapes) and             [s_ is None for _, s_ in got[0].shapes] == [s_ is None for _, s_ in before.shapes] and             [i for i, _ in got[0].shapes] == [i for i, _ in before.shapes]
        if ok:
            # the moved slot changed by +0.001 in game X on the vertices that existed before
            mx = [abs(d[0]) for d in got[0].shapes[slot][1]]
            ok = max(mx) > 0.0005
        check(f'{name} morph', ok, f'shapes {len(before.shapes)}; part grew to '
                                   f'{len(got[0].positions) if got else "?"} vertices')

    # new bone, a new mesh on it, a new material with a new image, an original material recoloured
    arm, orig = fresh(path)
    parent_name = next((b.name for b in arm.data.bones if b.name == 'head'), arm.data.bones[0].name)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    pe = arm.data.edit_bones[parent_name]
    eb = arm.data.edit_bones.new('added_bone')
    eb.head = pe.head + Vector((0, 0, 0.05))
    eb.tail = eb.head + Vector((0, 0.02, 0))
    eb.parent = pe
    bpy.ops.object.mode_set(mode='OBJECT')
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.02)
    me = bpy.data.meshes.new('added_cube')
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new(name='UVMap')
    cube = bpy.data.objects.new('added_cube', me)
    layer_col = next(c for c in bpy.data.collections if 'lsw2_layer' in c and not c.hide_viewport
                     and c['lsw2_layer'] != 0) if any('lsw2_layer' in c and c['lsw2_layer'] != 0
                                                       and not c.hide_viewport for c in bpy.data.collections) \
        else next(c for c in bpy.data.collections if 'lsw2_layer' in c)
    layer_col.objects.link(cube)
    arm.data.pose_position = 'REST'          # rig the new part against the rest pose (imports arrive posed)
    bpy.context.view_layer.update()
    cube.matrix_world = arm.matrix_world @ arm.data.bones['added_bone'].matrix_local
    world_before = cube.matrix_world.copy()
    cube.parent = arm
    cube.parent_type = 'BONE'
    cube.parent_bone = 'added_bone'
    cube.matrix_world = world_before
    img = bpy.data.images.new('added_image', 64, 48, alpha=True)
    grid = [((x // 8 + y // 8) % 2, x / 64, y / 48, 0.5 + 0.5 * ((x // 16) % 2)) for y in range(48) for x in range(64)]
    img.pixels = [c for cell in grid for c in (cell[0], cell[1], cell[2], cell[3])]
    mat = bpy.data.materials.new('added_material')
    mat.use_nodes = True
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex_node.image = img
    bsdf = mat.node_tree.nodes['Principled BSDF']
    mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Alpha'].default_value = 0.6
    me.materials.append(mat)
    m0 = next(m for m in bpy.data.materials if m.get('lsw2_material') == 0)
    if m0.node_tree.nodes.get('Mix'):
        m0.node_tree.nodes['Mix'].inputs['A'].default_value = (1.0, 0.0, 0.0, 1.0)
    else:
        m0.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1.0, 0.0, 0.0, 1.0)
    cube_world_game = [(v.x, v.z, v.y) for v in ((arm.matrix_world.inverted() @ cube.matrix_world) @ vt.co
                                                for vt in me.vertices)]
    arm.data.pose_position = 'POSE'
    bpy.context.view_layer.update()
    m = export(arm, f'{name}_added')
    nb = len(orig.bones)
    ok_bone = len(m.bones) == nb + 1 and m.bones[-1]['name'] == 'added_bone' and \
        m.bones[m.bones[-1]['parent']]['name'] == parent_name
    got = [p for p in m.parts if p.bone == nb]
    ok_part = False
    if len(got) == 1:
        w = m.bones[-1]['world']
        placed = [tuple(sum(p_[k] * w[k * 4 + c] for k in range(3)) + w[12 + c] for c in range(3))
                  for p_ in got[0].positions]
        ok_part = all(min(max(abs(a - b) for a, b in zip(q, r)) for r in cube_world_game) < 1e-4 for q in placed)
    new_mat = m.materials[got[0].material] if got else None
    ok_mat = new_mat is not None and got[0].material == len(orig.materials) and \
        abs(new_mat['alpha'] - 0.6) < 1e-4 and new_mat['texture'] == len(orig.textures)
    ok_recolour = max(abs(a - b) for a, b in zip(m.materials[0]['colour'], (1.0, 0.0, 0.0))) < 1e-3
    ok_tex = False
    if ok_mat:
        import numpy as np
        _dxt = importlib.import_module(f'{PACKAGE.name}.dxt')
        t = m.textures[new_mat['texture']]
        dec = _dxt.decode_dxt5(t['dds'][128:128 + (t['width'] // 4) * (t['height'] // 4) * 16], t['width'], t['height'])
        want = np.array(grid, dtype=np.float64).reshape(48, 64, 4)[::-1]
        small = dec[::1, :, :].astype(np.float64) / 255.0
        ok_tex = (t['width'], t['height']) == (64, 64) and all(
            abs(small[..., c].mean() - want[..., c].mean()) < 0.02 for c in range(4))
    check(f'{name} new bone, part, material, texture', ok_bone and ok_part and ok_mat and ok_recolour and ok_tex,
          f'bone {ok_bone} part {ok_part} material {ok_mat} recolour {ok_recolour} texture {ok_tex}')

    # paint on an original texture: it is re-encoded in place, the others stay as they were
    arm, orig = fresh(path)
    tex_img = next((i for i in bpy.data.images if i.get('lsw2_texture') == 0), None)
    if tex_img is not None:
        px = list(tex_img.pixels)
        for k in range(0, min(len(px), 4 * 64), 4):
            px[k:k + 4] = [1.0, 0.0, 0.0, 1.0]
        tex_img.pixels = px
        m = export(arm, f'{name}_paint')
        check(f'{name} paint', m.textures[0]['dds'] != orig.textures[0]['dds'] and
              [t['dds'] for t in m.textures[1:]] == [t['dds'] for t in orig.textures[1:]] and
              len(m.textures) == len(orig.textures), f'textures {len(orig.textures)} -> {len(m.textures)}')

print(f'SUMMARY {"all passed" if not fails else "FAILED: " + ", ".join(fails)}')
sys.exit(1 if fails else 0)

"""Edit-path checks for the LEGO Star Wars II add-on, in Blender's background mode (no window):

    blender -b --factory-startup --python formats/hgp/lsw2/tests/check_blender_edits.py -- <out folder> <model.hgp> [...]

Per model, each from a fresh import, through the add-on's own operators:
  duplicate  a part's object (skinned if any) is duplicated: one more part, a copy of its vertices
  delete     a part's object is deleted: one part fewer, the rest unchanged
  bones      a skinned part is weighted to every bone in turn: it is split into parts of at most 8 bones,
             same triangle count, every vertex on exactly one bone of its part
  morph      a face part with facial shapes gets an extra vertex: its shapes are dropped, the file reads
Every written file must read back.
"""
import importlib
import sys
from pathlib import Path

import bmesh
import bpy

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

    # morph: add a vertex to a part with facial shapes
    arm, orig = fresh(path)
    face = next((o for o in exporter.collect(arm) if o.get('lsw2_has_morphs')), None)
    if face is not None:
        bm = bmesh.new()
        bm.from_mesh(face.data)
        bm.edges.ensure_lookup_table()
        bmesh.ops.subdivide_edges(bm, edges=[bm.edges[0]], cuts=1)
        bm.to_mesh(face.data)
        bm.free()
        with_morph = sum(p.morph is not None for p in orig.parts)
        m = export(arm, f'{name}_morph')
        check(f'{name} morph', sum(p.morph is not None for p in m.parts) == with_morph - 1,
              f'parts with shapes {with_morph} -> {sum(p.morph is not None for p in m.parts)}')

print(f'SUMMARY {"all passed" if not fails else "FAILED: " + ", ".join(fails)}')
sys.exit(1 if fails else 0)

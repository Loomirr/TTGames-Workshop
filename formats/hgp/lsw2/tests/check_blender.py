"""Blender checks for the LEGO Star Wars II add-on. Runs in Blender's background mode (no window):

    blender -b --factory-startup --python formats/hgp/lsw2/tests/check_blender.py -- <out folder> <model.hgp | @list.txt> [...]

For each model: import; export unchanged and compare with the original byte for byte; move one
skinned part's vertices, export, read back and check the move arrived and nothing else changed;
render a front view (Workbench, textured) to <out>/<name>.png.
"""
import importlib
import sys
from pathlib import Path

import bpy
from mathutils import Vector

PACKAGE = Path(__file__).resolve().parents[1]           # this add-on's folder
sys.path.insert(0, str(PACKAGE.parent))
io_lsw2_hgp = importlib.import_module(PACKAGE.name)
exporter, hgp, importer = (importlib.import_module(f'{PACKAGE.name}.{m}') for m in ('exporter', 'hgp', 'importer'))

argv = sys.argv[sys.argv.index('--') + 1:]
out_dir = Path(argv[0])
out_dir.mkdir(parents=True, exist_ok=True)
io_lsw2_hgp.register()
results = []


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)     # the add-on's classes stay registered


def render(name, arm):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.render.resolution_x, scene.render.resolution_y = 600, 800
    scene.render.film_transparent = False
    shown = [o for o in scene.objects if o.type == 'MESH' and o.visible_get()]
    pts = [o.matrix_world @ Vector(c) for o in shown for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre, size = (lo + hi) / 2, max(hi - lo)
    cam_data = bpy.data.cameras.new('cam')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size * 1.15
    cam = bpy.data.objects.new('cam', cam_data)
    scene.collection.objects.link(cam)
    cam.location = centre + Vector((0, -size * 3, 0))
    cam.rotation_euler = (1.5707963, 0, 0)        # looking along +Y: the front of a character facing -Y
    scene.camera = cam
    scene.render.filepath = str(out_dir / f'{name}.png')
    bpy.ops.render.render(write_still=True)


paths = []
for arg in argv[1:]:
    if arg.startswith('@'):                 # @list.txt: one model path per line
        paths += [line.strip() for line in Path(arg[1:]).read_text().splitlines() if line.strip()]
    else:
        paths.append(arg)
for path in paths:
    name = Path(path).stem
    reset()
    original = Path(path).read_bytes()
    arm, model = importer.import_hgp(bpy.context, path)
    n_obj = sum(1 for o in bpy.data.objects if o.type == 'MESH')
    same_path = out_dir / f'{name}_same.hgp'
    data, notes = exporter.export_hgp(bpy.context, str(same_path), arm)
    identical = data == original
    # an edit: lift the first part by 1 cm (game Y; a rigid part in its bone's space) and export
    target = next(iter(exporter.collect(arm)), None)      # rigid parts move in their bone's space
    moved_ok = None
    if target is not None:
        for v in target.data.vertices:
            v.co.z += 0.01
        edit_path = out_dir / f'{name}_edit.hgp'
        data2, notes2 = exporter.export_hgp(bpy.context, str(edit_path), arm)
        m2 = hgp.Model(data2)
        idx = int(target['lsw2_part'])
        before = model.parts[idx]
        after = next(p for p in m2.parts if p.layer == before.layer and p.slot == before.slot and
                     p.material == before.material and len(p.positions) == len(before.positions)
                     and p.offset == before.offset)
        lifted = all(abs(a[1] + 0.01 - b[1]) < 1e-5 and abs(a[0] - b[0]) < 1e-6 and abs(a[2] - b[2]) < 1e-6
                     for a, b in zip(before.positions, after.positions))
        others = [p for p in m2.parts if p.offset != before.offset]
        orig_others = [p for p in model.parts if p.offset != before.offset]
        rest_same = [(p.positions, p.strip) for p in others] == [(p.positions, p.strip) for p in orig_others]
        moved_ok = lifted and rest_same
        if not moved_ok:
            dev = max(max(abs(a[0] - b[0]), abs(a[1] + 0.01 - b[1]), abs(a[2] - b[2]))
                      for a, b in zip(before.positions, after.positions))
            changed = [i for i, (p, q) in enumerate(zip(others, orig_others)) if (p.positions, p.strip) != (q.positions, q.strip)]
            print(f'EDIT DETAIL {name}: part {idx} max deviation {dev:.2e}; other parts changed {changed[:8]} '
                  f'of {len(others)} vs {len(orig_others)}; notes {notes2}')
        for v in target.data.vertices:
            v.co.z -= 0.01
    render(name, arm)
    results.append((name, len(model.parts), n_obj, identical, moved_ok, notes))
    print(f'RESULT {name}: parts {len(model.parts)} objects {n_obj} unchanged-export-identical {identical} '
          f'edit-arrives {moved_ok} notes {notes}')

bad = [r for r in results if not r[3] or r[4] is False]
print(f'SUMMARY {len(results) - len(bad)} of {len(results)} passed')
sys.exit(1 if bad else 0)

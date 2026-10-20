"""Animation checks for the LEGO Star Wars II add-on, in Blender's background mode (no window):

    blender -b --factory-startup --python formats/hgp/lsw2/tests/check_blender_anim.py -- <out folder> <model.hgp> [clip ... | --all]

Imports the model with its animations, then for each named clip (default: walk, jump; --all: every
imported clip, without renders) checks at several
frames that every posed bone in Blender equals the game's own transform computed from the file; exports
with an action assigned (must still equal the original); renders four frames per clip to <out>.
"""
import importlib
import sys
from pathlib import Path

import bpy
from mathutils import Vector

PACKAGE = Path(__file__).resolve().parents[1]           # this add-on's folder
sys.path.insert(0, str(PACKAGE.parent))
anim, anim_import, exporter, importer = (importlib.import_module(f'{PACKAGE.name}.{m}') for m in ('anim', 'anim_import', 'exporter', 'importer'))

argv = sys.argv[sys.argv.index('--') + 1:]
out = Path(argv[0])
out.mkdir(parents=True, exist_ok=True)
path = argv[1]
clips = argv[2:] or ['walk', 'jump']
every = clips == ['--all']
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
arm, model = importer.import_hgp(bpy.context, path)
actions = {a.name.lower(): a for a in bpy.data.actions}
print(f'CLIPS imported {len(actions)}: {sorted(actions)[:12]}')
fails = []
if every:
    clips = sorted(actions)
for name in clips:
    act = actions.get(name)
    if act is None:
        print(f'CHECK {name}: no such clip')
        continue
    with open(act['lsw2_source'], 'rb') as f:
        clip = anim.Clip(f.read(), name)
    arm.animation_data.action = act
    if hasattr(act, 'slots'):
        arm.animation_data.action_slot = act.slots[0]
    step = (scene.render.fps / scene.render.fps_base) / act['lsw2_fps']
    worst = 0.0
    for frame in (0, clip.frames // 3, 2 * clip.frames // 3, clip.frames - 1):
        t = frame * step + 1
        scene.frame_set(int(t), subframe=t - int(t))
        bpy.context.view_layer.update()
        driven = model.bones[:clip.nodes]            # a clip may drive only the first bones
        want = [importer.to_blender_matrix(w) for w in anim_import._world(clip.local_matrices(frame, driven), driven)]
        for b in arm.data.bones:
            j = int(b['lsw2_bone'])
            if j >= clip.nodes:
                continue
            got = arm.pose.bones[b.name].matrix
            worst = max(worst, max(abs(got[r][c] - want[j][r][c]) for r in range(3) for c in range(4)))
    ok = worst < 1e-3
    print(f'CHECK {name} pose equals the file: {"ok" if ok else "FAILED"} (worst {worst:.2e}, fps {act["lsw2_fps"]}'
          f'{" assumed" if act["lsw2_fps_assumed"] else ""})')
    if not ok:
        fails.append(name)
    if every:
        continue
    # renders
    scene.render.engine = 'BLENDER_EEVEE'
    world = bpy.data.worlds.get('w') or bpy.data.worlds.new('w')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (0.8, 0.8, 0.85, 1)
    scene.world = world
    if 'sun' not in bpy.data.objects:
        sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
        sun.data.energy = 3
        sun.rotation_euler = (0.9, 0.2, -0.4)
        scene.collection.objects.link(sun)
        cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = 0.7
        scene.collection.objects.link(cam)
        cam.location = Vector((0.9, -1.4, 0.45))
        cam.rotation_euler = (Vector((0, 0, 0.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 320, 360
    for k, frame in enumerate((0, clip.frames // 4, clip.frames // 2, 3 * clip.frames // 4)):
        scene.frame_set(int(round(frame * step + 1)))
        scene.render.filepath = str(out / f'{name}_{k}.png')
        bpy.ops.render.render(write_still=True)

# export with an action assigned: the file holds the rest pose, so it must equal the original
data, notes = exporter.export_hgp(bpy.context, str(out / 'posed_export.hgp'), arm)
same = data == Path(path).read_bytes()
print(f'CHECK export while animated equals the original: {"ok" if same else "FAILED"}')
if not same:
    fails.append('export')
print(f'SUMMARY {"all passed" if not fails else "FAILED: " + ", ".join(fails)}')
sys.exit(1 if fails else 0)

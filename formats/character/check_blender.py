"""Manual installed-package check: Blender --background --python this.py -- cases.json output."""
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
cases_path, output = Path(args[0]), Path(args[1])
output.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
bundle = output / 'addon'
with ZipFile(root / 'builds/blender/TT_Character_Importer_0.3.0.zip') as archive:
    archive.extractall(bundle)
sys.path.insert(0, str(bundle))
import io_scene_tt_character as addon
addon.register()
from io_scene_tt_character.importer import import_character, import_animations

results = []
for case in json.loads(cases_path.read_text()):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig, report = import_character(bpy.context, Path(case['source']), Path(case['assets']), case['game'],
                                  cache=output / 'cache')
    assert rig.type == 'ARMATURE' and len(rig.data.bones) > 0
    assert report['models']
    assert all(len(o.data.vertices) for o in bpy.context.scene.objects if o.type == 'MESH')
    actions = import_animations(bpy.context, rig, [Path(p) for p in case.get('animations', [])])
    if case.get('animations'):
        assert actions['imported'], actions
        for index in range(len(rig.tt_clips)):
            rig.tt_clip_index = index
            clip = rig.tt_clips[index]
            assert rig.animation_data.action == clip.action
            assert bpy.context.scene.frame_end == clip.frames
            for frame in (1, max(1, clip.frames // 2), clip.frames):
                bpy.context.scene.frame_set(frame)
                assert all(math.isfinite(v) for b in rig.pose.bones for row in b.matrix for v in row)
        rig.tt_clip_index = 0
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = [o.matrix_world @ Vector(corner) for obj in meshes for o in [obj.evaluated_get(depsgraph)] for corner in o.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (low + high) / 2
    extent = max(high - low)
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new('Inspection lighting')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.25, .25, .25, 1)
    data = bpy.data.cameras.new('Preview camera')
    camera = bpy.data.objects.new('Preview camera', data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((.9, 2.5, .7)) * extent
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = extent * 1.4
    scene.camera = camera
    light_data = bpy.data.lights.new('Inspection sun', 'SUN')
    light_data.energy = 2.5
    light = bpy.data.objects.new('Inspection sun', light_data)
    scene.collection.objects.link(light)
    light.rotation_euler = (.4, -.7, -.5)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = scene.render.resolution_y = 650
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.type = 'MATERIAL'
                area.spaces.active.region_3d.view_location = center
                area.spaces.active.region_3d.view_distance = extent * 2
    label = case['game'] + '_' + Path(case['source']).stem
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (label + '.blend')))
    scene.render.filepath = str(output / (label + '.png'))
    bpy.ops.render.render(write_still=True)
    results.append(dict(name=label, report=report, animation=actions,
                        meshes=len(meshes), bones=len(rig.data.bones), bounds=list(high-low)))
(output / 'validation.json').write_text(json.dumps(results, indent=2))
print('CHARACTER_PACKAGE_CHECK_PASSED', len(results))

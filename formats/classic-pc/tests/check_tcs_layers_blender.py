"""Check TCS rigid-piece binding in Blender, from repository source (not a built ZIP).

blender -b --factory-startup --python-exit-code 1 --python formats/classic-pc/tests/check_tcs_layers_blender.py -- CHARACTER_PC.GHG new-output-folder [--render]

Supply your own TCS PC character GHG. The output folder must not exist yet and
will contain game-derived data, so put it under the ignored local/ folder.
Checks: rigid pieces named by the layer table are bound (vertex group of their
joint, weight 1, armature modifier) and sit near that joint; posing the joint on
two frames moves them exactly with it. --render also writes Workbench images of
both frames. Also checks layers_high visibility when a matching sibling TXT
exists, without deleting the alternative layers. This is not a check of native
shaders, runtime costume switches or AN3 playback.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    render = '--render' in args
    args = [a for a in args if a != '--render']
    if len(args) != 2:
        raise ValueError('Usage: -- CHARACTER_PC.GHG new-output-folder [--render]')
    source, output = Path(args[0]).resolve(), Path(args[1]).resolve()
    if not source.is_file() or source.suffix.lower() != '.ghg':
        raise ValueError('Supply one TCS PC character GHG')
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(root / 'formats/classic-pc'), str(root / 'formats/cu3/Addon')]
    from tools.blender_inspect import inspect_model
    from io_scene_lego_cu3.dds import read_dds
    from io_scene_lego_cu3.geometry_normals import apply_authored_normals

    # The documented --factory-startup invocation includes a cube and camera.
    # They would obscure the sample and prevent the fixed test camera being made.
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    collection, report = inspect_model(bpy.context, source, read_dds, apply_authored_normals, profile='TCS')
    from tools.nu20 import NU20
    native_layers = NU20(source).character_layers()['layers']
    children = [c for c in collection.children if 'tt_native_layer' in c]
    if sorted(c['tt_native_layer'] for c in children) != list(range(len(native_layers))):
        raise AssertionError('Native layer collections were dropped or duplicated')
    selected = report['layer_selection']['selected']
    initial_hidden = {}
    for child in children:
        expected_hidden = selected is not None and child['tt_native_layer'] not in selected
        if child.hide_viewport != expected_hidden or child.hide_render != expected_hidden:
            raise AssertionError('Layer visibility disagrees with the reported native selection')
        initial_hidden[child.name] = expected_hidden
        # Hidden collections intentionally skip dependency-graph evaluation.
        # Enable all for the separate deformation check, then restore for renders.
        child.hide_viewport = False
    rig = next(o for o in collection.all_objects if o.type == 'ARMATURE')
    rigid = [o for o in collection.all_objects if 'tt_classic_rigid_joint' in o]
    if not rigid or report['rigid_bound_meshes'] != len(rigid):
        raise AssertionError(f'Expected bound rigid pieces, report says {report["rigid_bound_meshes"]}')
    result = dict(source=source.name, layers=report.get('character_layers'), rigid=len(rigid),
                  unbound=report['unbound_rigid_meshes'], issues=report['issues'], pieces=[],
                  layer_selection=report['layer_selection'], initial_hidden=initial_hidden)
    for obj in rigid:
        joint = obj['tt_classic_rigid_joint']
        group = obj.vertex_groups.get(joint)
        if group is None or not any(m.type == 'ARMATURE' and m.object == rig for m in obj.modifiers):
            raise AssertionError(f'{obj.name}: not deformed by its joint {joint}')
        for v in obj.data.vertices:
            weights = [(obj.vertex_groups[g.group].name, g.weight) for g in v.groups if g.weight > 0]
            if weights != [(joint, 1.0)]:
                raise AssertionError(f'{obj.name}: vertex {v.index} weights {weights}')
        centre = sum((v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
        distance = (centre - rig.data.bones[joint].head_local).length
        result['pieces'].append(dict(object=obj.name, joint=joint, distance_to_joint=round(distance, 4)))

    # Pose every joint that owns a rigid piece on two frames and compare the
    # evaluated vertices with the bone's own deformation matrix.
    scene = bpy.context.scene
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    joints = sorted({o['tt_classic_rigid_joint'] for o in rigid})
    for frame, angle in ((1, 0.0), (10, 0.6)):
        for name in joints:
            bone = rig.pose.bones[name]
            bone.rotation_mode = 'XYZ'
            bone.rotation_euler = (angle, 0.0, angle / 2)
            bone.keyframe_insert('rotation_euler', frame=frame)
    bpy.ops.object.mode_set(mode='OBJECT')
    worst = {}
    for frame in (1, 10):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        error = 0.0
        for obj in rigid:
            bone = rig.pose.bones[obj['tt_classic_rigid_joint']]
            deform = rig.matrix_world @ bone.matrix @ bone.bone.matrix_local.inverted() @ rig.matrix_world.inverted()
            evaluated = obj.evaluated_get(depsgraph).to_mesh()
            for rest, moved in zip(obj.data.vertices, evaluated.vertices):
                expected = obj.matrix_world.inverted() @ deform @ obj.matrix_world @ rest.co
                error = max(error, (moved.co - expected).length)
            obj.evaluated_get(depsgraph).to_mesh_clear()
        worst[frame] = error
        if render:
            for child in children:
                child.hide_viewport = initial_hidden[child.name]
            scene.render.engine = 'BLENDER_WORKBENCH'
            scene.render.resolution_x, scene.render.resolution_y = 640, 800
            if scene.camera is None:
                camera = bpy.data.objects.new('TCS check camera', bpy.data.cameras.new('TCS check camera'))
                scene.collection.objects.link(camera)
                camera.data.type = 'ORTHO'
                camera.data.ortho_scale = 0.6
                camera.location = (0.0, -2.0, 0.2)
                camera.rotation_euler = (math.radians(90), 0.0, 0.0)
                scene.camera = camera
            scene.render.filepath = str(output / f'frame_{frame:03d}.png')
            bpy.ops.render.render(write_still=True)
            for child in children:
                child.hide_viewport = False
    result['max_pose_error'] = worst
    if max(worst.values()) > 1e-4:
        raise AssertionError(f'Rigid pieces do not follow their joints: {worst}')
    for child in children:
        child.hide_viewport = initial_hidden[child.name]
    (output / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


main()

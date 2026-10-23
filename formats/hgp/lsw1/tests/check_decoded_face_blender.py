"""Reopen a decoded facial shader scene and compare all integer BSA samples.

Background Blender: -- scene.blend original.bsa new-report.json
The renderer's fixed native body pose is required for the evaluated XYZ check.
"""
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from animation_records import AnimationRecords
from face_channels import sample_layers


def main():
    if not bpy.app.background:
        raise ValueError('Use background Blender to preserve open projects')
    scene_path, clip_path, report_path = sys.argv[sys.argv.index('--') + 1:]
    report_path = Path(report_path)
    if report_path.exists():
        raise ValueError('Choose a new report path')
    clip = AnimationRecords(Path(clip_path).read_bytes(), 'BSA')
    bpy.ops.wm.open_mainfile(filepath=str(Path(scene_path).resolve()))
    scene = bpy.context.scene
    objects = [o for o in scene.objects if o.type == 'MESH' and o.data.shape_keys]
    assert objects
    count = 0; maximum = 0.; movement = 0.; normals = {}
    for obj in objects:
        action = obj.data.shape_keys.animation_data.action
        binding = json.loads(action['lsw1_binding'])
        assert binding['animation_sha256'] == clip.sha256
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    assert all(point.interpolation == 'LINEAR'
                               for curve in bag.fcurves for point in curve.keyframe_points)
        normals[obj.name] = [tuple(p.vector) for p in obj.data.attributes['LSW1 shader test normal'].data]
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            values = sample_layers(clip, frame, [int(obj['lsw1_layer_index'])])[0]
            keys = obj.data.shape_keys.key_blocks
            for key in keys[1:]:
                target = int(key.name.split()[-1])
                assert abs(key.value - values[target]) < 2e-6
                count += 1
            evaluated = obj.evaluated_get(graph)
            assert len(evaluated.data.vertices) == len(keys[0].data)
            assert [tuple(p.vector) for p in evaluated.data.attributes['LSW1 shader test normal'].data] == normals[obj.name]
            for i, vertex in enumerate(evaluated.data.vertices):
                basis = keys[0].data[i].co
                expected = basis.copy()
                for key in keys[1:]:
                    expected += (key.data[i].co - basis) * values[int(key.name.split()[-1])]
                maximum = max(maximum, (vertex.co - expected).length)
                movement = max(movement, (expected - basis).length)
    assert maximum < 2e-5, maximum
    assert movement > 1e-6, movement
    report = dict(meshes=len(objects), frames=scene.frame_end, weight_checks=count,
                  maximum_xyz_error=maximum, maximum_displacement=movement,
                  authored_normals_unchanged=True, interpolation='LINEAR',
                  scope='Decoded BSA integer weights and evaluated Blender deformation; fixed body')
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()

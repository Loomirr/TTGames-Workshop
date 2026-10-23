"""Reopen a shader-lab face preview and verify deformation and shading inputs.

Run in background Blender with -- scene.blend target-id new-report.json.
Requires an example made with render_shader_comparison --face-preview-animation.
This tests manual target playback, not native facial clip decoding.
"""
import json
from pathlib import Path
import sys

import bpy


def main():
    if not bpy.app.background:
        raise ValueError('Use background Blender to preserve open projects')
    scene_path, target, output = sys.argv[sys.argv.index('--') + 1:]
    output = Path(output)
    if output.exists():
        raise ValueError('Choose a new report path')
    bpy.ops.wm.open_mainfile(filepath=str(Path(scene_path).resolve()))
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH' and o.data.shape_keys
              and o.data.shape_keys.key_blocks.get(f'morph {int(target)}')]
    assert meshes, 'No requested face target'
    samples = {}
    for frame, weight in ((1, 0.), (9, 1.), (17, 0.)):
        scene.frame_set(frame)
        graph = bpy.context.evaluated_depsgraph_get()
        samples[frame] = {}
        for obj in meshes:
            key = obj.data.shape_keys.key_blocks[f'morph {int(target)}']
            assert abs(key.value - weight) < 1e-6, (obj.name, frame, key.value)
            evaluated = obj.evaluated_get(graph)
            attr = evaluated.data.attributes.get('LSW1 shader test normal')
            assert attr and len(attr.data) == len(evaluated.data.vertices)
            samples[frame][obj.name] = (
                [tuple(evaluated.matrix_world @ v.co) for v in evaluated.data.vertices],
                [tuple(p.vector) for p in attr.data])
    movement = 0.
    for obj in meshes:
        basis, normals = samples[1][obj.name]
        displaced, middle_normals = samples[9][obj.name]
        returned, final_normals = samples[17][obj.name]
        assert normals == middle_normals == final_normals, 'Authored shading vectors changed'
        assert len(basis) == len(displaced) == len(returned), 'Topology changed'
        assert max(abs(a-b) for p,q in zip(basis, returned) for a,b in zip(p,q)) < 1e-6
        movement = max(movement, max(abs(a-b) for p,q in zip(basis, displaced) for a,b in zip(p,q)))
    assert movement > 1e-6, 'Playback did not deform any face vertices'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(meshes=len(meshes), maximum_displacement=movement,
        frames=[1,9,17], scope='Saved-scene manual face playback; fixed body and authored normals'), indent=2))
    print('FACE_SHADER_PLAYBACK', len(meshes), 'meshes; maximum displacement', movement)


if __name__ == '__main__':
    main()

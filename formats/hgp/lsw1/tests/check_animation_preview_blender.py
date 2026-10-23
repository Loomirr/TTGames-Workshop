"""Check an explicitly supplied ANI research pair and its saved Blender action."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

component = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(component/'tools'))
from bake_animation_preview import load_binding, bake
from animation_pose import sample_pose


def main():
    model_path, animation, binding_path, output = map(Path, sys.argv[sys.argv.index('--')+1:])
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('lsw1_pose_test', component/'__init__.py',
                                                submodule_search_locations=[str(component)])
    addon = importlib.util.module_from_spec(spec); sys.modules[spec.name] = addon; spec.loader.exec_module(addon)
    from lsw1_pose_test.hgp import HGP
    from lsw1_pose_test.importer import import_character
    bpy.ops.wm.read_factory_settings(use_empty=True)
    model = HGP(model_path)
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (model_path,animation)]
    clip, binding = load_binding(model, animation, binding_path)
    rig = import_character(bpy.context, model_path, correct_preview_pose=False)
    rest = [b.matrix_local.copy() for b in rig.data.bones]
    geometry = {o.name: [tuple(v.co) for v in o.data.vertices] for o in rig.children if o.type=='MESH'}
    report = bake(rig, model, clip, binding, bpy.context.scene)
    for bone, before in zip(rig.data.bones, rest):
        assert bone.matrix_local == before, 'Native rest matrix changed'
    for bone, flags in zip(rig.data.bones, clip.flags):
        assert bone.inherit_scale == ('NONE' if flags & 0x10 else 'FULL')
    for name, coords in geometry.items():
        assert coords == [tuple(v.co) for v in bpy.data.objects[name].data.vertices]
    for key, value in (('model_sha256','0'*64),('animation_sha256','0'*64),
                       ('track_bones',list(reversed(binding['track_bones']))),('fps',float('nan'))):
        bad = dict(binding); bad[key] = value
        file = output/(key+'.json'); file.write_text(json.dumps(bad), encoding='utf-8')
        try:
            load_binding(model, animation, file)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid binding accepted: '+key)
    name = rig.name
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'playback.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(output/'playback.blend'))
    rig = bpy.data.objects[name]
    conversion = Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
    maximum = 0.
    for frame in range(1, report['frames']+1):
        bpy.context.scene.frame_set(frame)
        for bone, native in zip(rig.pose.bones, sample_pose(model,clip,frame,binding['track_bones'])):
            expected = conversion @ Matrix([native[i:i+4] for i in range(0,16,4)]).transposed() @ conversion
            maximum = max(maximum, max(abs(bone.matrix[r][c]-expected[r][c]) for r in range(4) for c in range(4)))
    assert maximum < 2e-4, maximum
    assert hashes == [hashlib.sha256(p.read_bytes()).hexdigest() for p in (model_path,animation)]
    report['reopened_maximum_error'] = maximum
    (output/'report.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
    print('ANIMATION_PREVIEW_PASSED', json.dumps(report))


if __name__ == '__main__':
    main()

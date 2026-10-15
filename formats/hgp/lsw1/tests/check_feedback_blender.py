"""Original-file naming, placement and native bone-axis regression checks.

blender -b --factory-startup --python-exit-code 1 --python this.py -- extracted-folder new-output
Requires yoda.hgp, _yoda.hgp, watto.hgp and speeder_dooku.hgp. No game data is
bundled. Run with an isolated Blender user profile; output should be ignored.
"""
import importlib.util
import json
from pathlib import Path
import sys

import bpy


def main():
    source, output = [Path(p).resolve() for p in sys.argv[sys.argv.index('--') + 1:]]
    output.mkdir(parents=True, exist_ok=False)
    component = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        'lsw1_feedback_test', component / '__init__.py',
        submodule_search_locations=[str(component)])
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    from lsw1_feedback_test.hgp import HGP
    from lsw1_feedback_test.importer import C, matrix

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon.register()
    reports = []
    try:
        assert bpy.ops.import_scene.lsw1_hgp.get_rna_type().properties['spacing'].default == 0
        files = ['_yoda.hgp', 'yoda.hgp', 'watto.hgp', 'speeder_dooku.hgp']
        for name in files:
            if not (source / name).is_file():
                raise FileNotFoundError(source / name)
        result = bpy.ops.import_scene.lsw1_hgp(
            directory=str(source), files=[{'name': n} for n in files],
            placement='ORIGIN', import_textures=False, correct_preview_pose=False)
        assert result == {'FINISHED'}, result
        rigs = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
        assert len(rigs) == len(files)
        for name in files:
            rig = next(r for r in rigs if Path(r['lsw1_source_file']).name == name)
            assert rig.name == Path(name).stem + ' RIG', rig.name
            assert rig.location.length == 0, rig.location
            h = HGP(source / name)
            assert len(rig.data.bones) == len(h.bones)
            worlds, errors = [], []
            for native in h.bones:
                local = matrix(native['local'])
                world = worlds[native['parent']] @ local if native['parent'] >= 0 else local
                worlds.append(world)
                expected = C @ world @ C
                bone = next(b for b in rig.data.bones if b['lsw1_joint_index'] == native['index'])
                assert bone['lsw1_original_name'] == native['name']
                if native['parent'] >= 0:
                    assert bone.parent['lsw1_joint_index'] == native['parent']
                else:
                    assert bone.parent is None
                error = max(abs(expected[i][j] - bone.matrix_local[i][j])
                            for i in range(4) for j in range(4))
                assert error < 2e-5, (name, bone.name, error)
                expected_direction = expected.col[1].to_3d().normalized()
                actual_direction = (bone.tail_local - bone.head_local).normalized()
                assert (expected_direction - actual_direction).length < 2e-5, (name, bone.name)
                errors.append(error)
            reports.append(dict(file=name, root=rig.name, bones=len(h.bones),
                                maximum_bind_matrix_error=max(errors)))
        report = dict(blender=bpy.app.version_string, checks=reports,
                      scope='Source addon: batch naming/placement and original bind axes; no game animation or visual fidelity claim')
        (output / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('HGP_FEEDBACK_CHECK_PASSED', json.dumps(report))
    finally:
        addon.unregister()


if __name__ == '__main__':
    main()

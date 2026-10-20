"""Original-file bind/skin checks and scaled rigid custom-normal regression.

blender -b --factory-startup --python-exit-code 1 --python this.py -- extracted-folder new-output
Inputs and optional rendered outputs belong in an ignored private directory.
No assets are bundled. This checks source import, not in-game animation playback.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector


def load_component():
    component = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        'lsw1_assembly_test', component / '__init__.py',
        submodule_search_locations=[str(component)])
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    return sys.modules['lsw1_assembly_test.importer']


def maximum_error(first, second):
    return max(abs(first[i][j] - second[i][j])
               for i in range(4) for j in range(4))


def scaled_normal_regression(importer, output):
    """A source normal must stay perpendicular to both transformed tangents."""
    native = Matrix.Diagonal((2.0, 3.0, .5, 1.0))
    native.translation = (1.0, -.25, .5)
    values = lambda m: tuple(value for row in m.transposed() for value in row)
    first, second = Vector((1, 0, 1)), Vector((0, 1, 1))
    normal = first.cross(second).normalized()

    class ScaledRigidHGP:
        def __init__(self, path):
            self.path = Path(path)
            self.layers = ['defaultLayer']
            self.bones = [dict(index=0, name='attachment', parent=-1,
                               local=values(native), inverse=values(native.inverted()))]

        def meshes(self, lod='AUTO'):
            return [dict(geometry=1, primitive=2, material=0, buffer=1,
                         rigid_bone=0, vertices=[(0, 0, 0), tuple(first), tuple(second)],
                         faces=[(0, 2, 1)], normals=[tuple(normal)] * 3,
                         uvs=[(0, 0), (1, 0), (0, 1)], weights=[{0: 1.0}] * 3)]

    with patch.object(importer, 'HGP', ScaledRigidHGP), patch.object(
            importer, 'make_materials', lambda *args: [bpy.data.materials.new('Synthetic')]):
        rig = importer.import_character(bpy.context, output / 'synthetic.hgp',
                                        armature=False, textures=False, correct_preview_pose=False)
    mesh = next(o.data for o in rig.children if o.type == 'MESH')
    a, b, c = [v.co for v in mesh.vertices]
    tangent1, tangent2 = (b - a).normalized(), (c - a).normalized()
    expected = (tangent1.cross(tangent2) * -1).normalized()
    actual = mesh.corner_normals[0].vector
    assert abs(actual.dot(tangent1)) < 1e-5, (actual, tangent1)
    assert abs(actual.dot(tangent2)) < 1e-5, (actual, tangent2)
    assert (expected - actual).length < 1e-4, (expected, actual)
    assert mesh.has_custom_normals


def normal_fan_regression(importer):
    """A lower failure count may still damage a previously valid corner."""
    good=Vector((0,0,1));bad=Vector((0,0,0))
    class FanMesh:
        def __init__(self,frames):
            self.frames=frames;self.call=-1
            self.polygons=[SimpleNamespace(area=1.,loop_indices=(0,1,2),use_smooth=True)]
        def normals_split_custom_set(self,values):
            self.call+=1
        @property
        def corner_normals(self):
            return [SimpleNamespace(vector=n) for n in self.frames[self.call]]
    original=[good.copy() for _ in range(3)]
    baseline=[bad,bad,good]
    mesh=FanMesh([baseline,[good,good,bad],baseline])
    result=importer.preserve_authored_normals(mesh,original)
    assert result['rejected'] and result['remaining']==2
    assert mesh.polygons[0].use_smooth
    mesh=FanMesh([baseline,[good,bad,good]])
    result=importer.preserve_authored_normals(mesh,original)
    assert not result['rejected'] and result['remaining']==1 and result['isolated_faces']==1
    assert not mesh.polygons[0].use_smooth
    assert original==[good,good,good]


def main():
    source, output = [Path(p).resolve() for p in sys.argv[sys.argv.index('--') + 1:]]
    output.mkdir(parents=True, exist_ok=False)
    importer = load_component()
    from lsw1_assembly_test.hgp import HGP
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scaled_normal_regression(importer, output)
    normal_fan_regression(importer)
    reports = []
    names = ['clonewalker', 'clone', 'stormtrooper', 'clone_ep3_walker',
             'clone_ep3_swamp', 'clone_ep3_pilot', 'clone_ep3', 'clone_ep3_sand',
             'imperialofficer', 'bob', 'walk', 'kaminoandroid', 'captainpanaka',
             'dookusspeeder', 'speeder_dooku','kiadimundi','kitfisto','obiwankenobi_ep3']
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path = source / (name + '.hgp')
        h = HGP(path)
        rig = importer.import_character(bpy.context, path, textures=False,
                                        correct_preview_pose=False)
        bpy.context.view_layer.update()
        worlds, rest_errors = [], []
        for native, bone in zip(h.bones, rig.data.bones):
            local = importer.matrix(native['local'])
            world = worlds[native['parent']] @ local if native['parent'] >= 0 else local
            worlds.append(world)
            expected = importer.C @ world @ importer.C
            assert bone['lsw1_original_name'] == native['name']
            assert bone['lsw1_joint_index'] == native['index']
            assert ((bone.parent['lsw1_joint_index'] if bone.parent else -1)
                    == native['parent'])
            error = maximum_error(expected, bone.matrix_local)
            assert error < 2e-5, (name, native['name'], error)
            rest_errors.append(error)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        deform_error, vertex_count, computed_fallbacks, degenerate_faces = 0.0, 0, 0, 0
        source_parts = h.meshes()
        children = sorted(rig.children, key=lambda obj: int(obj.name.rsplit(' ', 1)[1]))
        for obj, part in zip(children, source_parts):
            assert obj.type == 'MESH'
            assert obj.data.has_custom_normals
            assert len(obj.data.vertices) == len(part['vertices'])
            assert [tuple(p.vertices) for p in obj.data.polygons] == part['faces']
            bind = (importer.C @ worlds[part['rigid_bone']] @ importer.C
                    if part['rigid_bone'] is not None else Matrix.Identity(4))
            normal_matrix = bind.to_3x3().inverted().transposed()
            for vertex, source_position, source_weights in zip(
                    obj.data.vertices, part['vertices'], part['weights']):
                expected_position = bind @ Vector((source_position[0], source_position[2],
                                                    source_position[1]))
                assert (vertex.co - expected_position).length < 1e-6
                weights = {obj.vertex_groups[g.group].name: g.weight for g in vertex.groups}
                assert all(math.isfinite(w) and w > 0 for w in weights.values())
                assert abs(sum(weights.values()) - 1) < 1e-5
                assert len(weights) == len(source_weights)
                for index, weight in source_weights.items():
                    assert abs(weights[rig.data.bones[index].name] - weight) < 1e-6
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            for actual, original in zip(mesh.vertices, obj.data.vertices):
                deform_error = max(deform_error, (actual.co - original.co).length)
                assert all(math.isfinite(v) for v in actual.co)
            # Zero authored normals are Blender's documented request for a
            # calculated split normal. Valid authored directions remain custom.
            final_normals = [n.vector.copy() for n in obj.data.corner_normals]
            for loop in obj.data.loops:
                u, v = part['uvs'][loop.vertex_index]
                uv = obj.data.uv_layers.active.data[loop.index].uv
                assert abs(uv.x - u) < 1e-6 and abs(uv.y - (1 - v)) < 1e-6
            for polygon in obj.data.polygons:
                if polygon.area == 0:
                    degenerate_faces += 1
                    assert not polygon.use_smooth
                    continue
                for li in polygon.loop_indices:
                    loop = obj.data.loops[li]
                    native_normal = Vector(part['normals'][loop.vertex_index])
                    final_normal = final_normals[li]
                    assert all(math.isfinite(v) for v in final_normal)
                    assert abs(final_normal.length - 1) < 1e-4, (name, obj.name, li)
                    if native_normal.length == 0:
                        computed_fallbacks += 1
                    else:
                        expected = (normal_matrix @ Vector((native_normal.x, native_normal.z,
                                                            native_normal.y))).normalized()
                        assert (expected - final_normal).length < .005, (name, obj.name, li)
            vertex_count += len(mesh.vertices)
            evaluated.to_mesh_clear()
        assert len(rig.children) == len(source_parts)
        assert deform_error < 2e-5, (name, deform_error)
        reports.append(dict(file=path.name, bones=len(h.bones), vertices=vertex_count,
                            maximum_rest_error=max(rest_errors), neutral_deform_error=deform_error,
                            zero_source_normal_corners=computed_fallbacks,
                            preserved_degenerate_faces=degenerate_faces))
    report = dict(blender=bpy.app.version_string, originals=reports,
                  synthetic='Nonuniform rigid normal stays perpendicular to transformed tangents',
                  scope='Source import; exact native rigid rest and weights; no native animation claim')
    (output / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('LSW1_ASSEMBLY_CHECK_PASSED', json.dumps(report))


if __name__ == '__main__':
    main()

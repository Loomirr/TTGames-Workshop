"""Independent structural fixtures; no game files, Blender or character names."""
import copy
import sys
import types
import unittest
from pathlib import Path

pkg = types.ModuleType('validation_fixture')
pkg.__path__ = [str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
from validation_fixture.model_validation import validate_model, validate_draw, matrix
from validation_fixture.cu3 import FormatError


def fixture():
    identity = [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    return dict(mesh_version=175, display=dict(version=32),
                skeleton=dict(version=15, joints=[dict(index=0, name='native_root', parent=None,
                    local_bind_row_major=identity[:], inverse_world_bind_row_major=identity[:])]),
                materials=[dict(table_version=232)],
                parts=[dict(index=0, attribute_types=dict(position=3, uv=5), morphs=None,
                    vertices=[dict(position=p, uv=[0,0], weights=[(0,1)]) for p in ([0,0,0],[1,0,0],[0,1,0])],
                    triangles=[[0,1,2]])])


class ValidationTests(unittest.TestCase):
    def test_report_preserves_input(self):
        model=fixture(); original=copy.deepcopy(model)
        result=validate_model(model)
        self.assertEqual(model, original)
        self.assertEqual(result['material_versions'], [232])
        self.assertEqual(result['warnings'], [])

    def test_nonfinite_attributes(self):
        for field in ('position','uv'):
            model=fixture(); model['parts'][0]['vertices'][0][field][0]=float('nan')
            with self.assertRaisesRegex(FormatError, 'mesh validation.*non-finite'):
                validate_model(model)

    def test_bad_triangles(self):
        for triangle in ([-1,0,1],[0,1,3],[0,1]):
            model=fixture();model['parts'][0]['triangles']=[triangle]
            with self.assertRaisesRegex(FormatError, 'triangle 0'):validate_model(model)

    def test_skin_values(self):
        for influence in ((-1,1),(0,-.1),(0,float('inf'))):
            model=fixture();model['parts'][0]['vertices'][0]['weights']=[influence]
            with self.assertRaisesRegex(FormatError, 'skin validation'):validate_model(model)

    def test_selected_skin_bounds_and_zero(self):
        for influence in ((1,1),(0,0)):
            model=fixture();model['parts'][0]['vertices'][0]['weights']=[influence]
            with self.assertRaisesRegex(FormatError, 'skin association'):
                validate_draw(model,dict(part=0,material=0),None)

    def test_negative_draw_references(self):
        for binding,joint in ((dict(part=-1,material=0),None),(dict(part=0,material=-1),None),(dict(part=0,material=0),-1)):
            with self.assertRaises(FormatError):validate_draw(fixture(),binding,joint)

    def test_rigid_skin_does_not_require_vertex_weights(self):
        model=fixture()
        for vertex in model['parts'][0]['vertices']:del vertex['weights']
        validate_model(model);validate_draw(model,dict(part=0,material=0),0)

    def test_quality_warning_does_not_rewrite_weights(self):
        model=fixture();model['parts'][0]['vertices'][0]['weights']=[(0,.5)]
        result=validate_model(model)
        self.assertEqual(result['warnings'][0]['code'],'non_unit_weight_sums')
        self.assertEqual(model['parts'][0]['vertices'][0]['weights'],[(0,.5)])

    def test_singular_and_nonfinite_matrices(self):
        for values in ([0]*16,[float('inf')]*16):
            with self.assertRaisesRegex(FormatError,'coordinate conversion'):matrix(values,'coordinate conversion','instance')

    def test_bad_parents(self):
        model=fixture();model['skeleton']['joints'][0]['parent']=0
        with self.assertRaisesRegex(FormatError,'skeleton association'):validate_model(model)

    def test_uv_widths(self):
        model=fixture();model['parts'][0]['vertices'][0]['uv']=[0]
        with self.assertRaisesRegex(FormatError,'incomplete uv'):validate_model(model)


if __name__=='__main__':unittest.main()

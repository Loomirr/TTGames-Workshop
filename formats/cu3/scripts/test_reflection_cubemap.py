"""Reflection-cubemap binding gate and face resampling, without proprietary assets."""
import sys, types, unittest
from pathlib import Path
R = Path(__file__).resolve().parents[1]
p = types.ModuleType('io_scene_lego_cu3'); p.__path__ = [str(R/'Addon/io_scene_lego_cu3')]; sys.modules[p.__name__] = p
from io_scene_lego_cu3.native_materials import reflection_cubemap_binding
from io_scene_lego_cu3.material_preview import cubemap_to_equirect

try:
    import numpy as np
except ImportError:  # numpy ships with Blender; plain Python checks may lack it
    np = None


def entry(table=177, reflection=1, textures=None):
    ids = [-1]*18
    for slot, value in (textures or {8: 4}).items():
        ids[slot] = value
    return dict(table_version=table, texture_ids=ids, fields=dict(reflection=reflection))


class ReflectionBindingTests(unittest.TestCase):
    def test_only_texture_in_slot_8(self):
        for table in (172, 174, 176, 177):
            self.assertEqual(reflection_cubemap_binding(entry(table), 169), dict(texture=4))

    def test_other_textures_are_not_combined(self):
        for extra in ({0: 1, 8: 4}, {6: 2, 8: 4}, {0: 1, 6: 2, 8: 4}):
            self.assertIsNone(reflection_cubemap_binding(entry(textures=extra), 169))

    def test_reflection_flag_and_slot_required(self):
        self.assertIsNone(reflection_cubemap_binding(entry(reflection=0), 169))
        self.assertIsNone(reflection_cubemap_binding(entry(reflection=2), 169))
        self.assertIsNone(reflection_cubemap_binding(entry(textures={0: 1}), 169))

    def test_version_gate(self):
        for mesh, table in ((175, 202), (170, 191), (169, 175), (169, 228)):
            self.assertIsNone(reflection_cubemap_binding(entry(table), mesh))


@unittest.skipIf(np is None, 'numpy unavailable')
class EquirectTests(unittest.TestCase):
    def setUp(self):
        # One flat colour per D3D face: +X, -X, +Y, -Y, +Z, -Z.
        self.faces = [np.full((8, 8, 4), (i/10, 0, 0, 1), dtype=np.float32) for i in range(6)]
        self.out = cubemap_to_equirect(self.faces, width=64)

    def face_at(self, u, v):
        h, w = self.out.shape[:2]
        return round(float(self.out[min(h-1, int(v*h)), min(w-1, int(u*w)), 0])*10)

    def test_layout(self):
        self.assertEqual(self.out.shape, (32, 64, 4))
        self.assertTrue(np.all(self.out[..., 3] == 1))

    def test_axis_convention(self):
        # Blender equirect: u = atan2(y, -x)/2pi + 0.5, v = elevation/pi + 0.5 (bottom row first).
        # Game direction = (Blender x, Blender z, -Blender y).
        self.assertEqual(self.face_at(0.5, 0.99), 2)    # Blender up (+Z) -> game +Y
        self.assertEqual(self.face_at(0.5, 0.01), 3)    # Blender down -> game -Y
        self.assertEqual(self.face_at(0.5, 0.5), 1)     # Blender -X -> game -X
        self.assertEqual(self.face_at(0.0, 0.5), 0)     # Blender +X -> game +X
        self.assertEqual(self.face_at(0.75, 0.5), 5)    # Blender +Y -> game -Z
        self.assertEqual(self.face_at(0.25, 0.5), 4)    # Blender -Y -> game +Z


if __name__ == '__main__':
    unittest.main()

"""Asset-free regressions for PC component-layer selection and bounds.

Run directly with Python. Original-file and Blender/render evidence is separate.
"""
import importlib.util
from pathlib import Path
import struct
import unittest


spec = importlib.util.spec_from_file_location('lsw1_layer_reader', Path(__file__).parents[1] / 'hgp.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def part(identity, bones, triangles=20):
    return dict(geometry=identity, primitive=identity + 1, rigid_bone=None,
                weights=[{bone: 1.0} for bone in bones], faces=[(0, 1, 2)] * triangles)


def layers(names, contents):
    h = reader.HGP.__new__(reader.HGP)
    h.path = Path('fixture.hgp')
    h.layers = names
    h.layer_count = len(names)
    h.bones = [dict(parent=i - 1) for i in range(8)]
    h.layer_meshes = lambda index: contents[index]
    return h


class LayerAssemblyTests(unittest.TestCase):
    def test_independent_hair_family_is_not_replaced_by_goggles_or_low_hair(self):
        h = layers(['defaultLayer', 'TT1_HighRes', 'TT2_MediumRes',
                    'TT5_HairHi', 'TT6_HairLo', 'TT9_GogglesHi'],
                   [[], [part(10, [1, 2])], [part(20, [1, 2])],
                    [part(30, [3])], [part(40, [3])], [part(50, [4])]])
        self.assertEqual(h.selected_layers(), [1, 3])
        self.assertEqual([p['geometry'] for p in h.meshes()], [10, 30])

    def test_independent_head_is_added_without_second_body(self):
        h = layers(['defaultLayer', 'TT1_HiRes', 'TT2_MediumRes', 'TT4_Head'],
                   [[part(1, [7])], [part(10, [1, 2])], [part(20, [1, 2])],
                    [part(30, [3])]])
        self.assertEqual(h.selected_layers(), [0, 1, 3])

    def test_empty_high_detail_falls_back_to_nonempty_lower_body(self):
        h = layers(['defaultLayer', 'TT1_Hi', 'TT2_Lo'],
                   [[part(1, [1, 2], 4)], [], [part(20, [1, 2], 60)]])
        self.assertEqual(h.selected_layers(), [0, 2])

    def test_complete_default_high_body_does_not_overlay_lower_detail(self):
        h = layers(['defaultLayer', 'TT1_MediumRes', 'TT2_LoRes'],
                   [[part(1, [1, 3, 5], 100)], [part(20, [1, 2, 4], 60)],
                    [part(30, [1, 2, 4], 20)]])
        self.assertEqual(h.selected_layers(), [0])

    def test_default_head_is_combined_with_lower_body(self):
        h = layers(['defaultLayer', 'TT1_MediumRes'],
                   [[part(1, [2], 100)], [part(20, [1, 2, 4, 5], 60)]])
        self.assertEqual(h.selected_layers(), [0, 1])

    def test_broken_and_cutscene_alternates_stay_out_of_automatic_assembly(self):
        h = layers(['defaultLayer', 'TT1_BrokenBits', 'TT2_BrokenBits',
                    'TT4_Hoses', 'TT5_CutSceneHoses', 'TT6_EnergyBinders'],
                   [[part(1, [1])], [part(10, [1])], [part(20, [1])],
                    [part(30, [1])], [part(40, [1])], [part(50, [1])]])
        self.assertEqual(h.selected_layers(), [0, 3, 5])

    def test_vehicle_common_layers_complement_high_body(self):
        h = layers(['defaultLayer', 'TT1_Hi', 'TT2_NotUsed',
                    'TT3_HiMed_Common', 'TT4_Lo', 'TT5_CommonHose'],
                   [[part(1, [1])], [part(10, [1, 2])], [],
                    [part(30, [3])], [part(40, [1, 2])], [part(50, [1, 2])]])
        self.assertEqual(h.selected_layers(), [0, 1, 3, 5])

    def test_explicit_selection_does_not_add_automatic_accessories(self):
        h = layers(['defaultLayer', 'TT1_HighRes', 'TT4_Head'],
                   [[part(1, [1])], [part(10, [1])], [part(20, [2])]])
        self.assertEqual(h.selected_layers(1), [0, 1])
        self.assertEqual(h.selected_layers(2), [0, 2])
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            h.selected_layers(3)

    def test_duplicated_primitive_pointer_is_emitted_once(self):
        shared = part(1, [1])
        h = layers(['defaultLayer', 'TT1_HighRes'], [[shared], [shared]])
        self.assertEqual(len(h.meshes()), 1)

    def test_empty_assembly_has_useful_diagnostic(self):
        h = layers(['defaultLayer', 'TT1_HighRes'], [[], []])
        with self.assertRaisesRegex(ValueError, 'no geometry'):
            h.meshes()

    def test_corrupt_rigid_object_table_is_rejected_before_iteration(self):
        h = reader.HGP.__new__(reader.HGP)
        h.layers = ['defaultLayer']
        h.layer_count = 1
        h.count = 2
        h.lods_at = 0
        h.body = bytearray(20)
        struct.pack_into('<I', h.body, 4, 0xfffffff0)
        with self.assertRaisesRegex(ValueError, 'rigid object table range'):
            h.layer_meshes(0)


if __name__ == '__main__':
    unittest.main()

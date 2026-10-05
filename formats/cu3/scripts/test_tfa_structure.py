"""Synthetic TFA envelope/tree tests. These do not validate animated poses."""
import struct
import sys
import types
import unittest
from pathlib import Path

package = types.ModuleType('tt_tfa_check')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_tfa_check.cu3 import Cutscene, FormatError


def fixture(version=27, tree_version=20, resource=b'ScoutTrooper\0'):
    header = bytearray(32)
    struct.pack_into('>3IIf3I', header, 0, 0, 1, version, 30, 30.0, 0xffffffff, 4, 1)
    metadata = bytearray(48)
    struct.pack_into('>I', metadata, 6, 76)  # Blob-relative AN4 actor node.
    struct.pack_into('>Hff', metadata, 12, 1, 1.0, 1.0)
    struct.pack_into('>I', metadata, 44, len(resource))
    tree = bytearray(144)
    actor_name = b'Instance1_ScoutTrooper\0'
    struct.pack_into('<2I', tree, 0, tree_version, len(tree) + len(actor_name))
    struct.pack_into('<H', tree, 8, 1)
    struct.pack_into('<2I', tree, 16, len(tree), 72)
    struct.pack_into('<I', tree, 72 + 28, 1)
    blob = bytes(4) + tree + actor_name
    name = b'SAMPLE\0'
    matrix = [float(i % 5 == 0) for i in range(16)]
    data = header + metadata + resource + struct.pack('>I', len(blob)) + blob
    data += struct.pack('>I', len(name)) + name + struct.pack('>I16f', 1, *matrix)
    data += bytes(4)
    struct.pack_into('>I', data, 0, len(data)-4)
    return data


class TfaStructureTests(unittest.TestCase):
    def test_all_observed_version_pairs(self):
        for version, tree in ((22,17), (23,18), (24,18), (25,18), (26,19), (27,20)):
            with self.subTest(version=version):
                cut = Cutscene('synthetic.CU3', fixture(version, tree))
                self.assertEqual(cut.tree_version, tree)
                self.assertEqual(cut.actors[0]['metadata']['resource_name'], 'ScoutTrooper')
                self.assertEqual(cut.actors[0]['name'], 'Instance1_ScoutTrooper')

    def test_empty_resource_field(self):
        self.assertNotIn('resource_name', Cutscene('synthetic.CU3', fixture(resource=b'')).actor_metadata[0])

    def test_wrong_tree_pair_rejected(self):
        with self.assertRaisesRegex(FormatError, 'tree header'):
            Cutscene('synthetic.CU3', fixture(25,20))

    def test_unknown_envelope_rejected(self):
        with self.assertRaisesRegex(FormatError, 'envelope/version'):
            Cutscene('synthetic.CU3', fixture(28,20))

    def test_unterminated_resource_rejected(self):
        with self.assertRaisesRegex(FormatError, 'Unterminated'):
            Cutscene('synthetic.CU3', fixture(resource=b'ScoutTrooper'))

    def test_resource_trailing_bytes_rejected(self):
        with self.assertRaisesRegex(FormatError, 'trailing bytes'):
            Cutscene('synthetic.CU3', fixture(resource=b'Scout\0Trooper\0'))

    def test_resource_length_bounds_rejected(self):
        data = fixture()
        struct.pack_into('>I', data, 32+44, 8192)
        with self.assertRaisesRegex(FormatError, 'exceeds bounds'):
            Cutscene('synthetic.CU3', data)


if __name__ == '__main__':
    unittest.main()

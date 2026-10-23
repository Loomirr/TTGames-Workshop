"""Standalone LOTR/Dimensions tree profiles; no original assets required."""
import struct
import unittest

from test_an4_standalone import tree
from tt_an4_test.an4 import AnimationFile
from tt_an4_test.cu3 import FormatError


class TreeProfiles(unittest.TestCase):
    def fixture(self, version):
        raw = tree()
        struct.pack_into('>I', raw, 0, version)
        return raw

    def test_observed_tree_profiles_keep_native_records(self):
        for version in (8, 11, 17):
            with self.subTest(version=version):
                source = AnimationFile('clip.an4', data=self.fixture(version))
                self.assertEqual((source.version, source.endian, source.header_size),
                                 (version, '>', 72))
                actor = source.choose_actor(1)
                self.assertEqual((actor['offset'], actor['name']), (72, 'Actor'))
                record = actor['records'][0]
                self.assertEqual((record['offset'], record['name']), (144, 'Clip'))
                self.assertEqual(record['animation'].sample(.5),
                                 [[16, 17, 18, 19, 20, 21]])

    def test_unobserved_versions_stay_rejected(self):
        for version in (3, 9, 10, 12, 21, 22, 99):
            with self.subTest(version=version), self.assertRaises(FormatError):
                AnimationFile('clip.an4', data=self.fixture(version))

    def test_new_profiles_keep_hierarchy_record_and_string_guards(self):
        for version in (8, 11, 17):
            for offset, fmt, value in ((4, 'I', 0), (16, 'I', 0),
                                       (20, 'I', 0), (80, 'H', 4097),
                                       (96, 'I', 0), (100, 'I', 0),
                                       (208, 'I', 0), (212, 'I', 999999)):
                with self.subTest(version=version, offset=offset):
                    raw = self.fixture(version)
                    struct.pack_into('>' + fmt, raw, offset, value)
                    with self.assertRaises(FormatError):
                        AnimationFile('clip.an4', data=raw)
            raw = self.fixture(version)
            struct.pack_into('>H', raw, 80, 1)
            struct.pack_into('>I', raw, 92, 72)
            with self.assertRaisesRegex(FormatError, 'cyclic'):
                AnimationFile('clip.an4', data=raw)

    def test_ani_e_inventory_does_not_enable_sampling(self):
        raw = self.fixture(17)
        raw[224:228] = b'ANIE'
        source = AnimationFile('clip.an4', data=raw)
        animation = source.actors[0]['records'][0]['animation']
        self.assertEqual(animation.header()['format'], 'ANIE')
        with self.assertRaisesRegex(FormatError, 'ANI-E sampling'):
            animation.prepare(scene_channels=True)

if __name__ == '__main__':
    unittest.main()

"""Asset-free PC morph tests: full-buffer indexing, empty slots and bad layouts."""
import struct
import unittest

from check_vertex_opacity import primitive


def fixture():
    h = primitive(0x5d)
    h.body.extend(bytes(512))
    # Two primitives share four source vertices, but use different subsets.
    h.buffers = [h.buffers[0] + h.buffers[0][:56]]
    struct.pack_into('<3H', h.body, 224, 3, 1, 2)
    struct.pack_into('<I', h.body, 144, 256)
    struct.pack_into('<IIHHI', h.body, 256, 0, 5, 3, 0, 300)
    struct.pack_into('<2H', h.body, 276, 1, 0)
    struct.pack_into('<3H', h.body, 300, 0, 2, 3)
    # Target 0 has distinctive XYZ deltas; target 1 is empty.
    for i in range(4):
        struct.pack_into('<3f', h.body, 512 + i * 12, i + .25, i + .5, i + .75)
    struct.pack_into('<2I', h.body, 560, 512, 0)
    struct.pack_into('<2I', h.body, 568, 0, 1)
    struct.pack_into('<5I', h.body, 576, 2, 560, 568, 512, 0x1234)
    struct.pack_into('<I', h.body, 64 + 0x3c, 576)
    return h


class MorphTests(unittest.TestCase):
    def test_each_primitive_uses_its_original_vertex_indices(self):
        h = fixture()
        before = bytes(h.body), list(h.buffers)
        a, b = list(h.object_meshes(0, None))
        self.assertEqual(a['source_vertex_indices'], [1, 2, 3])
        self.assertEqual(b['source_vertex_indices'], [0, 2, 3])
        self.assertEqual(a['morph']['targets'][0]['deltas'],
                         ((1.25, 1.5, 1.75), (2.25, 2.5, 2.75), (3.25, 3.5, 3.75)))
        self.assertEqual(b['morph']['targets'][0]['deltas'][0], (.25, .5, .75))
        self.assertEqual(a['morph']['targets'][1], {'id': 1, 'deltas': None})
        self.assertEqual(a['morph']['unknown_word'], 0x1234)
        self.assertEqual((bytes(h.body), h.buffers), before)

    def test_absent_morph_keeps_geometry(self):
        h = fixture()
        original = list(h.object_meshes(0, None))
        struct.pack_into('<I', h.body, 64 + 0x3c, 0)
        for a, b in zip(original, h.object_meshes(0, None)):
            self.assertIsNone(b['morph'])
            for field in ('vertices', 'faces', 'normals', 'weights', 'uvs', 'colors'):
                self.assertEqual(a[field], b[field])

    def test_all_empty_slots(self):
        h = fixture()
        struct.pack_into('<I', h.body, 560, 0)
        struct.pack_into('<I', h.body, 588, 560)
        self.assertTrue(all(t['deltas'] is None for t in h.morph_targets(64, 0x5d, 4)['targets']))

    def test_corrupt_layouts_are_rejected(self):
        for at, value, message in (
            (124, 1010, 'morph record'), (576, 0xffffffff, 'count'),
            (580, 1020, 'pointer table'), (584, 1020, 'ID table'),
            (568, 9, 'target IDs'), (560, 516, 'delta layout'),
            (564, 512, 'delta layout'), (588, 0, 'delta layout'),
            (588, 1020, 'delta layout'),
        ):
            with self.subTest(at=at, value=value):
                h = fixture()
                struct.pack_into('<I', h.body, at, value)
                with self.assertRaisesRegex(ValueError, message):
                    list(h.object_meshes(0, None))

    def test_nonfinite_deltas_and_wrong_vertex_layout_are_rejected(self):
        for bad in (float('nan'), float('inf'), -float('inf')):
            h = fixture()
            struct.pack_into('<f', h.body, 524, bad)
            with self.assertRaisesRegex(ValueError, 'Non-finite'):
                h.morph_targets(64, 0x5d, 4)
        with self.assertRaisesRegex(ValueError, 'vertex layout'):
            fixture().morph_targets(64, 0x59, 4)

    def test_buffer_size_mismatch_and_resource_limit_are_rejected(self):
        for size in (0, 3, 5, 600000):
            with self.subTest(size=size), self.assertRaises(ValueError):
                fixture().morph_targets(64, 0x5d, size)


if __name__ == '__main__':
    unittest.main()

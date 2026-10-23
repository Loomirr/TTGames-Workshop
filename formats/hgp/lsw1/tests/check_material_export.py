"""Asset-free material writer round trips and refusal checks."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from material_export import recolor, material_slots, write_new


def fixture():
    data = bytearray(0x400)
    struct.pack_into('<12I', data, 0, 0, 0x30, 0, 0x80, 0x1f4, 0, 0, 0, 0, 0, 0, 0)
    struct.pack_into('<3I', data, 0xb0, 2, 0x8c, 0x140)
    struct.pack_into('<3f', data, 0x110, .25, .5, .75)
    return bytes(data)


class MaterialExportTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.digest = hashlib.sha256(self.data).hexdigest()

    def test_noop_and_exact_patch(self):
        self.assertEqual(recolor(self.data, self.digest, {}), self.data)
        self.assertEqual(recolor(self.data, self.digest, {0: [.25, .5, .75]}), self.data)
        output = recolor(self.data, self.digest, {0: [1, 0, .125]})
        self.assertEqual(output[:0x110], self.data[:0x110])
        self.assertEqual(output[0x11c:], self.data[0x11c:])
        self.assertEqual(struct.unpack_from('<3f', output, 0x110), (1, 0, .125))

    def test_bad_identity_and_colors(self):
        with self.assertRaises(ValueError):
            recolor(self.data, '0' * 64, {})
        for edits in ({-1: [0, 0, 0]}, {2: [0, 0, 0]}, {True: [0, 0, 0]},
                      {0: [float('nan'), 0, 0]}, {0: [float('inf'), 0, 0]},
                      {0: [2, 0, 0]}, {0: [0, 0]}, {0: [True, 0, 0]}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                recolor(self.data, self.digest, edits)

    def test_corrupt_layouts(self):
        for offset, value in ((4, 0x29), (12, 0xffffffff), (16, 0xffffffff),
                              (0xb0, 4097), (0xb4, 0x80), (0xb8, 0x8c)):
            data = bytearray(self.data)
            struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                material_slots(data)
        with self.assertRaises(ValueError):
            material_slots(self.data[:0x180])

    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model.hgp'
            write_new(path, self.data)
            with self.assertRaises(FileExistsError):
                write_new(path, b'bad')
            self.assertEqual(path.read_bytes(), self.data)


if __name__ == '__main__':
    unittest.main()

"""Asset-free checks for original PC signature gates and corrupt table bounds.

Run with Python directly. Original-file decoding/visual tests remain separate.
"""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('lsw1_hgp_reader', Path(__file__).parents[1] / 'hgp.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def fixture(signature):
    body = bytearray(0x220)
    body[signature:signature + 5] = b'Root\0'
    body[0x50:0x56] = b'Layer\0'
    root = 0x80
    for offset, value in ((0x14, 0x100), (0x18, 0x160), (0x1c, 0x1a0), (0x24, 0x1e0)):
        struct.pack_into('<I', body, root + offset, value)
    body[root + 0x7c] = 1
    body[root + 0x7e] = 1
    struct.pack_into('<I', body, 0x100 + 0x4c, 0x30)
    struct.pack_into('<I', body, 0x100 + 0x50, 255)
    identity = tuple(float(i % 5 == 0) for i in range(16))
    for at in (0x160, 0x1a0):
        struct.pack_into('<16f', body, at, *identity)
    struct.pack_into('<I', body, 0x1e0, 0x50)
    header = (0, signature, 0, 0x60, 0, 0x200, root, 0, 0, 0, 0, 0)
    return bytearray(struct.pack('<12I', *header)) + body


class HeaderTests(unittest.TestCase):
    def decode(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.hgp'
            path.write_bytes(data)
            return reader.HGP(path)

    def test_observed_signatures_preserve_joint_data(self):
        for signature in (0x14, 0x28, 0x30, 0x36):
            with self.subTest(signature=signature):
                model = self.decode(fixture(signature))
                self.assertEqual(model.bones[0]['name'], 'Root')
                self.assertEqual(model.bones[0]['parent'], -1)
                self.assertEqual(model.layers, ['Layer'])

    def test_unknown_signature_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'original LSW1 PC'):
            self.decode(fixture(0x29))

    def test_new_signatures_do_not_bypass_table_validation(self):
        for signature in (0x28, 0x36):
            for field, label in ((0x14, 'joint'), (0x18, 'local bind'), (0x1c, 'inverse bind'), (0x24, 'layer')):
                with self.subTest(signature=signature, field=field):
                    data = fixture(signature)
                    struct.pack_into('<I', data, 0x30 + 0x80 + field, 0xfffffff0)
                    with self.assertRaisesRegex(ValueError, label):
                        self.decode(data)

    def test_out_of_bounds_root(self):
        data = fixture(0x28)
        struct.pack_into('<I', data, 24, 0xffffffff)
        with self.assertRaisesRegex(ValueError, 'root range'):
            self.decode(data)

    def test_nonfinite_bind_is_rejected(self):
        data = fixture(0x28)
        struct.pack_into('<f', data, 0x30 + 0x160, float('nan'))
        with self.assertRaisesRegex(ValueError, 'Non-finite'):
            self.decode(data)

    def test_vertex_count_is_bounded(self):
        data = fixture(0x28)
        struct.pack_into('<I', data, 0x30 + 0x200, 0xffffffff)
        with self.assertRaisesRegex(ValueError, 'vertex table range'):
            self.decode(data)


if __name__ == '__main__':
    unittest.main()

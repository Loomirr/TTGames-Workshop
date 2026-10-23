"""Asset-free same-layout DDS replacement and malformed-input tests."""
import hashlib
import struct
import unittest

from check_material_export import fixture
from texture_export import dds_layout, replace_texture, texture_slots


def dds(fourcc=b'DXT1', mips=1):
    data = bytearray(128)
    data[:4] = b'DDS '
    struct.pack_into('<7I', data, 4, 124, 0x81007, 4, 4, 8, 0, mips)
    struct.pack_into('<2I', data, 76, 32, 4)
    data[84:88] = fourcc
    struct.pack_into('<I', data, 108, 0x1000)
    return bytes(data) + bytes((8 if fourcc == b'DXT1' else 16) * mips)


def model():
    data = bytearray(fixture())
    struct.pack_into('<I', data, 8, 0x200)
    texture = dds()
    struct.pack_into('<3I', data, 0x230, 20, len(texture), 1)
    struct.pack_into('<I', data, 0x24c, 0)
    data[0x250:0x250 + len(texture)] = texture
    return bytes(data)


class TextureTests(unittest.TestCase):
    def test_unchanged_and_edit_preservation(self):
        data = model(); digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(texture_slots(data), [(0x250, 0x2d8)])
        self.assertEqual(replace_texture(data, digest, 0, dds()), data)
        replacement = dds()[:-1] + b'\xff'
        edited = replace_texture(data, digest, 0, replacement)
        self.assertEqual(edited[:0x250], data[:0x250])
        self.assertEqual(edited[0x2d8:], data[0x2d8:])
        self.assertEqual(edited[0x250:0x2d8], replacement)

    def test_formats_and_mips(self):
        for fmt in (b'DXT1', b'DXT3', b'DXT5'):
            self.assertEqual(dds_layout(dds(fmt, 3))['mips'], 3)

    def test_native_padding_is_preserved(self):
        data = bytearray(model())
        struct.pack_into('<I', data, 0x234, len(dds()) + 10)
        data[0x2d8:0x2e2] = b'paddingpad'
        data = bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(replace_texture(data, digest, 0, dds()), data)
        edited = replace_texture(data, digest, 0, dds()[:-1] + b'\xff')
        self.assertEqual(edited[0x2d8:], data[0x2d8:])
        broken = data[:0x2d8] + b'X' + data[0x2d9:]
        with self.assertRaises(ValueError):
            texture_slots(broken)
        raw = dds()
        first = (-len(raw)) % 128
        pad = lambda n: (b'padding' * ((n + 6) // 7))[:n]
        self.assertEqual(dds_layout(raw + pad(first) + pad(250), allow_padding=True)['bytes'], len(raw))

    def test_replacement_guards(self):
        data = model(); digest = hashlib.sha256(data).hexdigest()
        for index, sha, replacement in ((1, digest, dds()), (True, digest, dds()),
                (0, '0' * 64, dds()), (0, digest, dds(b'DXT5')),
                (0, digest, dds()[:-1]), (0, digest, dds() + b'X')):
            with self.subTest(index=index, sha=sha), self.assertRaises(ValueError):
                replace_texture(data, sha, index, replacement)
        modified_header = bytearray(dds()); modified_header[32] = 1
        with self.assertRaisesRegex(ValueError, 'header'):
            replace_texture(data, digest, 0, bytes(modified_header))

    def test_malformed_layouts(self):
        empty = bytearray(model()); struct.pack_into('<I', empty, 0x238, 0)
        self.assertEqual(texture_slots(empty), [])
        for offset, value in ((8, 0xffffffff), (0x230, 0), (0x234, 0xffffffff),
                              (0x238, 4097), (0x24c, 1)):
            data = bytearray(model()); struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                texture_slots(data)
        for offset, value in ((12, 0), (16, 20000), (24, 2), (28, 4), (112, 512)):
            data = bytearray(dds()); struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                dds_layout(data)


if __name__ == '__main__':
    unittest.main()

"""LEGO Batman 2 facial (BSA) blocks: 37 channels, little-endian trees with the pointer at node +40 and file
offsets in the BSA header, and the reserved word (synthetic fixtures, no game files)."""
import struct
import sys
import types
import unittest
from pathlib import Path
pkg = types.ModuleType('lb2_face_test')
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lb2_face_test.cu3 import FormatError
from lb2_face_test.an4 import AnimationFile
from test_lb2_an4 import tree


def facial(endian, curves=37):
    """One node, `curves` constant channels: type 16+i gives i/100 (flags 0xA4, scale 0.01)."""
    raw = bytearray(80 + curves * 2 + 1)
    raw[:4] = b'ANIB' if endian == '>' else b'BINA'
    struct.pack_into(endian + '6H', raw, 4, 1, 1, 0, 2, curves, 0)
    raw[19] = 0xa4
    struct.pack_into(endian + 'H', raw, 22, 2)
    struct.pack_into(endian + '2f', raw, 28, -0.16, 0.01)
    struct.pack_into(endian + '9I', raw, 36, 80, 80, 80, 80, 80 + curves * 2, 0, 0, 0, 0)
    struct.pack_into(endian + '2f', raw, 72, 1, 0)
    struct.pack_into(endian + f'{curves}H', raw, 80, *range(16, 16 + curves))
    return raw


def with_face(endian='>', version=7, reserved=0, curves=37):
    """`tree()` with a BSA block appended and pointed at from the second actor's node."""
    raw = bytearray(tree(endian, version))
    at = len(raw)
    block = facial(endian, curves)
    size = 20 + len(block)
    words = (20, size, size, reserved) if endian == '>' else (at + 20, at + size, at + size, reserved)
    raw += (b'BSA\0' if endian == '>' else b'\0ASB') + struct.pack(endian + '4I', *words) + block
    head = 72 if endian == '>' else 44
    struct.pack_into(endian + 'I', raw, head + head + (36 if endian == '>' else 40), at)
    struct.pack_into(endian + 'I', raw, 4, len(raw))
    return bytes(raw)


class LB2Faces(unittest.TestCase):
    def test_37_channel_blocks_in_both_tree_orders(self):
        for endian, version in (('>', 7), ('>', 2), ('<', 1), ('<', 2)):
            source = AnimationFile('f.an4', data=with_face(endian, version))
            self.assertIsNone(source.morph_animation(source.actors[0]))
            face = source.morph_animation(source.actors[1])
            self.assertEqual((face.curves, face.variant, face.endian), (37, 'ANIB', endian))
            row = face.sample(0)[0]
            self.assertEqual(len(row), 37)
            for channel, value in enumerate(row):
                self.assertAlmostEqual(value, channel / 100, places=5)

    def test_reserved_word_is_kept_for_lb2_trees_only(self):
        for endian, reserved in (('>', 0x01010000), ('<', 0x101)):
            source = AnimationFile('f.an4', data=with_face(endian, 2, reserved))
            self.assertEqual(source.morph_animation(source.actors[1]).bsa_reserved, reserved)
        source = AnimationFile('f.an4', data=with_face('>', 13, 0x01010000))
        with self.assertRaisesRegex(FormatError, 'BSA header'):
            source.morph_animation(source.actors[1])

    def test_other_channel_counts_stay_refused(self):
        for curves in (36, 38):
            source = AnimationFile('f.an4', data=with_face(curves=curves))
            with self.assertRaisesRegex(FormatError, 'Facial scalar layout'):
                source.morph_animation(source.actors[1])

    def test_unobserved_reserved_flags_remain_refused(self):
        for endian, reserved in (('>', 1), ('>', 0x101), ('<', 0x01010000), ('<', 0xffffffff)):
            source = AnimationFile('f.an4', data=with_face(endian, 2, reserved))
            with self.subTest(endian=endian, reserved=reserved), self.assertRaisesRegex(FormatError, 'BSA header'):
                source.morph_animation(source.actors[1])

    def test_little_endian_block_needs_its_own_magic(self):
        raw = bytearray(with_face('<', 2))
        at = raw.rfind(b'\0ASB')
        raw[at:at + 4] = b'BSA\0'
        source = AnimationFile('f.an4', data=bytes(raw))
        with self.assertRaisesRegex(FormatError, 'facial-control block'):
            source.morph_animation(source.actors[1])


if __name__ == '__main__':
    unittest.main()

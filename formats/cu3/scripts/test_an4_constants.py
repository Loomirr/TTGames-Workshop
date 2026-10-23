"""Native ANI-D constant/step layouts, built independently of the writer.

The LMSH1 decoder distinguishes embedded words (0x20), indexed float32
constants (0x10), and indexed quantized uint16 constants (neither bit).
External step bytes are required whenever 0x20 is clear.
"""
import struct
import unittest

from test_an4_standalone import Animation, Reader, FormatError


def fixture(flags=0xd0, step=False, integer_count=0):
    embedded = bool(flags & 0x20)
    floating = bool(flags & 0x10)
    constants = bytearray(struct.pack('>h', -7) * integer_count)
    if not embedded:
        if floating:
            constants.extend(bytes((-len(constants)) % 4))
            constants.extend(struct.pack('>3f', -1.25, 2.5, 3.5))
        else:
            constants.extend(struct.pack('>3H', 10, 20, 30))
    type_at = 88 + len(constants)
    control_at = type_at + 12
    key_at = (control_at + (0 if embedded else 6) + 3) & ~3
    flags_at = key_at + 24
    raw = bytearray(flags_at + 1)
    raw[:4] = b'ANID'
    struct.pack_into('>6H', raw, 4, 1, 5, 8, 2, 6, 0)
    raw[17], raw[19] = integer_count, flags
    struct.pack_into('>H', raw, 22, 2)
    struct.pack_into('>2f', raw, 28, -3, .25)
    struct.pack_into('>9I', raw, 36, 80, 88, type_at, key_at, flags_at, 0, 0, 0, 0)
    struct.pack_into('>2f', raw, 72, 4, 0)
    struct.pack_into('>2f', raw, 80, 1, 2)
    raw[88:type_at] = constants
    struct.pack_into('>6H', raw, type_at, 0x8007 if embedded and step else 7,
                     16, 17, 14, 15, 18)
    if not embedded:raw[control_at] = int(step)
    for index, value in enumerate((0, 4, 4)):
        struct.pack_into('>4H', raw, key_at + index * 8, value, 0xf000, 0xf400, 0xb800)
    raw[flags_at] = 3
    return raw


def read(raw):
    anim = Animation(Reader(raw), 0, len(raw))
    anim.prepare(scene_channels=True)
    return anim


class NativeConstants(unittest.TestCase):
    def test_three_native_constant_encodings(self):
        for flags, expected in ((0xe0, [1, 1.25, 0, 1, 1.5]),
                                (0xd0, [-1.25, 2.5, 0, 1, 3.5]),
                                (0xc0, [-.5, 2, 0, 1, 4.5])):
            with self.subTest(flags=hex(flags)):
                anim = read(fixture(flags))
                self.assertEqual(anim.sample(0)[0], [2] + expected)
                self.assertEqual(anim.sample(1)[0], [6] + expected)

    def test_float_alignment_after_odd_integer_pool(self):
        self.assertEqual(read(fixture(integer_count=1)).sample(0)[0],
                         [2, -1.25, 2.5, 0, 1, 3.5])

    def test_embedded_and_external_step_controls(self):
        for flags in (0xe0, 0xd0, 0xc0):
            with self.subTest(flags=hex(flags)):
                self.assertAlmostEqual(read(fixture(flags)).sample(.125)[0][0],
                                       2 + 2 * 1024 / 4095, places=6)
                self.assertEqual(read(fixture(flags, step=True)).sample(.125)[0][0], 2)

    def test_float_flag_is_required_not_inferred_from_pool_bytes(self):
        raw = fixture()
        raw[19] &= ~0x10
        # 0xbfa0 is the first half of float32(-1.25), interpreted as uint16.
        self.assertEqual(read(raw).sample(0)[0][1], 0xbfa0 * .25 - 3)

    def test_missing_controls_and_out_of_bounds_constants_refused(self):
        raw = fixture()
        type_at = struct.unpack_from('>I', raw, 44)[0]
        struct.pack_into('>I', raw, 48, type_at + 12)
        with self.assertRaisesRegex(FormatError, 'channel-control'):
            read(raw)
        raw = fixture()
        struct.pack_into('>H', raw, type_at + 2, 0x7fff)
        with self.assertRaisesRegex(FormatError, 'constant index'):
            read(raw)


if __name__ == '__main__':
    unittest.main()

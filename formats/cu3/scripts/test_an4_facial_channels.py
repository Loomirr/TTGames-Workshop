"""54-channel facial scalars observed in Hobbit and Avengers PC ANI-D.

Synthetic data exercises the last channel, including its packed animation,
without borrowing a writer's output or distributing game data.
"""
import struct
import unittest

from test_an4_standalone import Animation, Reader, FormatError


def fixture(curves=54):
    type_at = 80
    scale_at = (type_at + curves * 2 + 3) & ~3
    key_at = scale_at + 8
    flags_at = key_at + 12
    raw = bytearray(flags_at + 1)
    raw[:4] = b'ANID'
    struct.pack_into('>6H', raw, 4, 1, 5, 4, 2, curves, 0)
    raw[19] = 0xa4
    struct.pack_into('>H', raw, 22, 2)
    struct.pack_into('>2f', raw, 28, 0, 1)
    struct.pack_into('>9I', raw, 36, scale_at, type_at, type_at,
                     key_at, flags_at, 0, 0, 0, 0)
    struct.pack_into('>2f', raw, 72, 4, 0)
    struct.pack_into('>' + str(curves) + 'H', raw, type_at,
                     15, *([14] * (curves - 2)), 6)
    struct.pack_into('>2f', raw, scale_at, 1 / 255, 0)
    tangents = (21 << 14) | (42 << 20) | (63 << 26)
    struct.pack_into('>3I', raw, key_at, tangents, 255 | tangents, 255 | tangents)
    return raw


def read(raw, limit=None):
    animation = Animation(Reader(raw), 0, len(raw) if limit is None else limit)
    animation.prepare(morph_channels=True)
    return animation


class FacialChannels(unittest.TestCase):
    def test_54th_channel_is_an_independent_animated_scalar(self):
        animation = read(fixture())
        for frame, value in ((0, 0), (.125, 1 / 6), (.25, 1 / 3),
                             (.5, 2 / 3), (.75, 1), (1, 1)):
            row = animation.sample(frame)[0]
            self.assertEqual(len(row), 54)
            self.assertEqual(row[:-1], [1] + [0] * 52)
            self.assertAlmostEqual(row[-1], value, places=6)

    def test_existing_37_and_53_channel_sampling_is_unchanged(self):
        for count in (37, 53):
            with self.subTest(count=count):
                row = read(fixture(count)).sample(.25)[0]
                self.assertEqual(len(row), count)
                self.assertAlmostEqual(row[-1], 1 / 3, places=6)

    def test_unknown_count_and_new_profile_flags_remain_refused(self):
        for count in (36, 38, 52, 55, 64):
            with self.subTest(count=count), self.assertRaisesRegex(FormatError, 'Facial scalar layout'):
                read(fixture(count))
        for flag in (0xac, 0xe4, 0xa5):
            raw = fixture()
            raw[19] = flag
            with self.subTest(flag=flag), self.assertRaisesRegex(FormatError, 'Facial scalar layout'):
                read(raw)
        raw = fixture()
        raw[:4] = b'ANIB'
        with self.assertRaisesRegex(FormatError, 'Facial scalar layout'):
            read(raw)

    def test_malformed_last_channel_and_truncated_keys_are_refused(self):
        raw = fixture()
        struct.pack_into('>H', raw, 80 + 53 * 2, 5)
        with self.assertRaisesRegex(FormatError, 'curve type'):
            read(raw)
        raw = fixture()
        flags_at = struct.unpack_from('>I', raw, 52)[0]
        struct.pack_into('>I', raw, 52, flags_at - 4)
        raw[flags_at - 4] = 0
        with self.assertRaisesRegex(FormatError, 'key groups overlap'):
            read(raw)
        raw = fixture()
        with self.assertRaisesRegex(FormatError, 'node flags outside'):
            read(raw, len(raw) - 1)


if __name__ == '__main__':
    unittest.main()

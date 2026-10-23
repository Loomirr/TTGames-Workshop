"""Asset-free malformed/ambiguous effect-registration checks."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from native_effects import registrations

BASE = 0x400000


def fixture():
    image = bytearray(0x1000)
    for start, blob, size in ((0x20, 0x400, 0x100), (0x50, 0x600, 0x100)):
        code = b'\x50\x6a\x09\x68' + struct.pack('<I', size)
        code += b'\x68' + struct.pack('<I', BASE + blob)
        code += b'\xb9' + struct.pack('<I', 0x30437b0 + 9 * 0x194)
        code += b'\xe8' + struct.pack('<i', 0x52a290 - (BASE + start + 23))
        assert len(code) == 23
        image[start:start + len(code)] = code
        image[blob:blob + 4] = b'\x01\x09\xff\xfe'
    return image


class EffectRegistrations(unittest.TestCase):
    def test_keeps_alternative_blobs_for_the_same_effect_id(self):
        image = fixture()
        shaders = [dict(address=hex(BASE + 0x440), bytes=0x20),
                   dict(address=hex(BASE + 0x640), bytes=0x20)]
        found = registrations(image, BASE, 0, 0x100, shaders)
        self.assertEqual([r['effect_id'] for r in found], [9, 9])
        self.assertEqual([r['shader_candidates'] for r in found], [['0x400440'], ['0x400640']])

    def test_exact_boundary_is_valid_but_crossing_is_rejected(self):
        shaders = [dict(address=hex(BASE + 0x4e0), bytes=0x20)]
        self.assertEqual(len(registrations(fixture(), BASE, 0, 0x100, shaders)), 2)
        shaders[0]['bytes'] += 4
        with self.assertRaisesRegex(ValueError, 'boundary'):
            registrations(fixture(), BASE, 0, 0x100, shaders)

    def test_rejects_invalid_blob_ranges_signatures_and_object_ids(self):
        for offset, value in ((0x24, 0xffffffff), (0x29, BASE - 4),
                              (0x2e, 0x30437b0), (0x400, 0)):
            with self.subTest(offset=offset):
                image = fixture()
                struct.pack_into('<I', image, offset, value)
                with self.assertRaises(ValueError):
                    registrations(image, BASE, 0, 0x100)

    def test_other_call_targets_and_outside_code_do_not_count(self):
        image = fixture()
        image[0x33] ^= 1  # Change the first call's displacement.
        self.assertEqual(len(registrations(image, BASE, 0, 0x100)), 1)
        self.assertEqual(registrations(fixture(), BASE, 0x100, 0x300), [])

    def test_invalid_code_and_shader_ranges(self):
        for start, end in ((-1, 10), (0, 0x1001), (10, 9)):
            with self.assertRaisesRegex(ValueError, 'code range'):
                registrations(fixture(), BASE, start, end)
        for address, size in ((BASE - 4, 4), (BASE + 0xff0, 32), (BASE, 0)):
            with self.assertRaisesRegex(ValueError, 'shader range'):
                registrations(fixture(), BASE, 0, 0x100, [dict(address=hex(address), bytes=size)])


if __name__ == '__main__':
    unittest.main()

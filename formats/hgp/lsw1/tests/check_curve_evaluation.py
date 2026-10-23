"""Scalar evaluation without game data: masks, stored times and cubic tangents."""
import math
import struct
import unittest

from check_animation_records import AnimationRecords, AnimationError, fixture


class EvaluationTests(unittest.TestCase):
    def test_float_cubic_uses_derivatives_and_interval(self):
        clip = AnimationRecords(fixture(), 'ANI')
        # Endpoint values 2,4; derivatives .25,-.5; interval 32.
        self.assertEqual(clip.evaluate_channel(0, 0, 1), 2)
        self.assertEqual(clip.evaluate_channel(0, 0, 17), 6)
        self.assertEqual(clip.evaluate_channel(0, 0, 33), 4)

    def test_compressed_cubic_and_constant(self):
        clip = AnimationRecords(fixture('BSA'), 'BSA')
        # Values 25,-50, derivatives -.02,.03 and interval 32.
        self.assertAlmostEqual(clip.evaluate_channel(0, 1, 17), -12.7, places=5)
        self.assertEqual(clip.evaluate_channel(0, 1, 1), 25)
        self.assertEqual(clip.evaluate_channel(0, 2, 17), 1)

    def test_masks_select_pair_even_when_stored_time_disagrees(self):
        clip = AnimationRecords(fixture(), 'ANI')
        data = bytearray(clip.data)
        struct.pack_into('<f', data, clip.records[0]['keys'][1]['at'], 5)
        edited = AnimationRecords(data, 'ANI')
        # Time 17 still uses first pair (mask's next key is frame 33).
        self.assertEqual(edited.evaluate_channel(0, 0, 17), 3.375)
        self.assertEqual(edited.data, bytes(data))

    def test_compressed_zero_interval_is_not_division_by_zero(self):
        clip = AnimationRecords(fixture(), 'ANI')
        data = bytearray(clip.data)
        data[clip.records[1]['keys'][1]['at'] + 3] = 0
        self.assertEqual(AnimationRecords(data, 'ANI').evaluate_channel(0, 1, 17), 25)

    def test_native_time_clamp_and_extra_terminal_key(self):
        clip = AnimationRecords(fixture(), 'ANI')
        self.assertEqual(clip.evaluate_channel(0, 0, -10), clip.evaluate_channel(0, 0, 1))
        self.assertEqual(clip.evaluate_channel(0, 0, 100), clip.evaluate_channel(0, 0, 33.99))
        self.assertTrue(math.isfinite(clip.evaluate_channel(0, 0, 33.5)))
        self.assertEqual(clip.records[0]['extra_keys'], 1)

    def test_missing_pair_is_refused_instead_of_reading_unowned_bytes(self):
        clip = AnimationRecords(fixture(), 'ANI')
        data = bytearray(clip.data)
        masks = clip.pointer(clip.records[0]['address'])
        struct.pack_into('<IIHH', data, masks, 3, 1, 0, 2)
        edited = AnimationRecords(data, 'ANI')
        with self.assertRaisesRegex(AnimationError, 'bounded interpolation pair'):
            edited.evaluate_channel(0, 0, 33.5)

    def test_invalid_time_and_indices(self):
        clip = AnimationRecords(fixture(), 'ANI')
        for time in (float('nan'), float('inf'), 1e300, 'one'):
            with self.subTest(time=time), self.assertRaises(AnimationError):
                clip.evaluate_channel(0, 0, time)
        for track, component in ((-1, 0), (1, 0), (0, 9)):
            with self.assertRaises(AnimationError):
                clip.evaluate_channel(track, component, 1)


if __name__ == '__main__':
    unittest.main()

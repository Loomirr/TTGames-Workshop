"""Asset-free validation of decoded BSA layer sampling and refusal boundaries."""
import unittest
from check_animation_records import fixture, AnimationRecords, AnimationError
from face_channels import sample_layers


class FaceChannelsTests(unittest.TestCase):
    def setUp(self):
        self.clip = AnimationRecords(fixture('BSA'), 'BSA')

    def test_missing_and_skipped_layers_stay_distinct(self):
        values = sample_layers(self.clip, 1, [-1, 0, 1])
        self.assertEqual(values, [None, [2., 25., 1.], []])

    def test_missing_clip_contributes_zero_without_clamping_channels(self):
        self.assertEqual(sample_layers(None, None, [0], second=self.clip,
            second_time=1, blend=.25), [[.5, 6.25, .25]])

    def test_invalid_inputs(self):
        for layers in ([], [32768], [-32769], [1.5], [True], '0'):
            with self.assertRaises(AnimationError):sample_layers(self.clip,1,layers)
        for blend in (float('nan'),float('inf'),-1,2):
            with self.assertRaises(AnimationError):sample_layers(self.clip,1,[0],blend=blend)
        with self.assertRaises(AnimationError):sample_layers(self.clip,float('nan'),[0])
        with self.assertRaises(AnimationError):sample_layers(None,1,[0])
        with self.assertRaises(AnimationError):sample_layers(AnimationRecords(fixture(),'ANI'),1,[0])


if __name__ == '__main__':
    unittest.main()

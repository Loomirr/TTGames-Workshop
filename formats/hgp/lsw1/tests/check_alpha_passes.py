"""Behavioral checks for ordered alpha/depth interactions, not a GPU comparison."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from alpha_passes import helper_states, alpha_test, fragment

ATTRIBUTES = 1 | 5 << 20 | 125 << 23


class AlphaTests(unittest.TestCase):
    def draw(self, alpha, secondary, color=(0., 0., 0., 0.), depth=1.):
        return fragment(color, depth, source=(1., 0., 0., alpha / 255), source_depth=.2,
                        alpha_byte=alpha, attributes=ATTRIBUTES, secondary=secondary)

    def test_low_alpha_colors_without_occluding_later_draw(self):
        color, depth, trace = self.draw(128, 1)
        self.assertGreater(color[0], .5)
        self.assertEqual(depth, 1.)
        self.assertEqual([p['passed'] for p in trace], [False, True])
        later, depth, _ = fragment(color, depth, source=(0., 1., 0., 1.), source_depth=.5,
            alpha_byte=255, attributes=ATTRIBUTES, secondary=1)
        self.assertEqual(later, (0., 1., 0., 1.))
        self.assertEqual(depth, .5)

    def test_high_alpha_does_occlude(self):
        color, depth, trace = self.draw(255, 1)
        self.assertEqual(color, (1., 0., 0., 1.))
        self.assertEqual(depth, .2)
        self.assertEqual([p['passed'] for p in trace], [True, False])

    def test_complement_depth_only_and_color_masks(self):
        color, depth, _ = self.draw(0, 2)
        self.assertEqual(color, (0., 0., 0., 0.))
        self.assertEqual(depth, .2)  # Native secondary mode can write invisible depth.
        color, depth, _ = self.draw(128, 3, color=(0., 0., 0., .75))
        self.assertGreater(color[0], 0.)
        self.assertEqual(color[3], .75)
        self.assertEqual(depth, 1.)

    def test_comparisons_partition_alpha_domain(self):
        for mode in (0, 2, 3, 4, 5, 6, 7):
            first, second = helper_states(1 | mode << 20 | 125 << 23, 1)
            a = dict(first); b = dict(second)
            for alpha in range(256):
                self.assertNotEqual(alpha_test(a[25], alpha, a[24]), alpha_test(b[25], alpha, a[24]))

    def test_unknown_device_behavior_refused(self):
        with self.assertRaises(ValueError):
            alpha_test(7, 255, 510)
        with self.assertRaises(ValueError):
            helper_states(-1, 0)
        with self.assertRaises(ValueError):
            fragment((0, 0, 0, 0), 1, source=(1, 0, 0, 1), source_depth=.2,
                     alpha_byte=255, attributes=10, secondary=1)


if __name__ == '__main__':
    unittest.main()

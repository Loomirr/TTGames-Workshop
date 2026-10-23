"""Asset-free checks for the deliberately limited ANI transform preview."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from animation_pose import IDENTITY, local_transform


class PoseTests(unittest.TestCase):
    def test_disabled_channels_do_not_collapse_scale(self):
        result, scale = local_transform((2,3,4,99,99,99,0,0,0), 2)
        self.assertEqual(result[:12], IDENTITY[:12])
        self.assertEqual(result[12:], (2,3,-4,1))
        self.assertEqual(scale, (1,1,1))

    def test_rotation_and_nonuniform_scale(self):
        result, scale = local_transform((0,0,0,0,0,math.pi/2,2,3,4), 9)
        self.assertAlmostEqual(result[1], 2, places=5)
        self.assertAlmostEqual(result[4], -3, places=5)
        self.assertAlmostEqual(result[10], 4, places=5)
        self.assertEqual(scale, (2,3,4))

    def test_pivot_stays_fixed(self):
        pivot = (1.,2.,3.)
        result, _ = local_transform((0,0,0,.2,.4,.6,1,1,1), 1, pivot=pivot, joint_flags=8)
        # Row-space pivot formula before handedness conversion: -p maps to -p.
        p = (-1.,-2.,3.,1.)
        for column in range(3):
            self.assertAlmostEqual(sum(p[k]*result[k*4+column] for k in range(4)), p[column], places=6)

    def test_refuses_unimplemented_or_invalid_inputs(self):
        for flags in (0x80, 4):
            with self.assertRaises(ValueError):
                local_transform((0,0,0,0,0,0,1,1,1), flags)
        for bad in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                local_transform((bad,0,0,0,0,0,1,1,1), 1)
        with self.assertRaises(ValueError):
            local_transform((0,)*8, 0)
        with self.assertRaises(ValueError):
            local_transform((0,0,0,1e20,0,0,1,1,1), 1)

    def test_parent_scale_compensation(self):
        values = (2,3,4,0,0,math.pi/2,2,3,4)
        matrix, inherited = local_transform(values, 0x19, parent_scale=(2,3,4))
        # Column division follows row scaling: these axes intentionally differ.
        self.assertAlmostEqual(matrix[1], 2/3, places=5)
        self.assertAlmostEqual(matrix[4], -3/2, places=5)
        self.assertEqual(matrix[12:15], (2,3,-4))
        self.assertEqual(inherited, (2,3,4))
        _, propagated = local_transform(values, 9, parent_scale=(2,3,4))
        self.assertEqual(propagated, (4,9,16))
        for parent in ((0,1,1),(1,1e-15,1)):
            with self.assertRaises(ValueError):
                local_transform(values, 0x19, parent_scale=parent)


if __name__ == '__main__':
    unittest.main()

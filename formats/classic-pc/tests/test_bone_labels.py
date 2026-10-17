"""Unique labels for repeated or empty native bone names (constructed names, no game data)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nu20 import bone_labels


class BoneLabels(unittest.TestCase):
    def test_unique_names_are_unchanged(self):
        self.assertEqual(bone_labels(['root','head']),(['root','head'],[]))

    def test_repeated_names_take_their_index(self):
        # Shape of Dexter's rig: two bones per arm name.
        labels,repeated=bone_labels(['root','leftArm','rightArm','leftArm','rightArm'])
        self.assertEqual(labels,['root','leftArm#1','rightArm#2','leftArm#3','rightArm#4'])
        self.assertEqual(repeated,['leftArm','rightArm'])

    def test_empty_names_are_labelled(self):
        self.assertEqual(bone_labels(['root','','']),(['root','bone#1','bone#2'],['']))

    def test_label_that_meets_a_real_name_is_refused(self):
        with self.assertRaisesRegex(ValueError,'unique'):bone_labels(['leg','leg','leg#1'])


if __name__=='__main__':unittest.main()

"""Portable checks for mapping refusal, rest rotation and output protection."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from plan import bone_plan
from rotation import IDENTITY, transfer_local_rotation


def joint(index, name, parent=None):
    return dict(index=index, name=name, parent=parent, flags=8,
                local_bind_row_major=IDENTITY[:], inverse_world_bind_row_major=IDENTITY[:])


def rotate_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    return [c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


class TransferTests(unittest.TestCase):
    def assertMatrixNear(self, a, b):
        self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 1e-9)

    def test_rest_pose_keeps_target_offsets_and_scale(self):
        source = rotate_z(0.7)
        source[12:15] = [3, 4, 5]
        target = rotate_z(-0.4)
        for row in range(3):
            target[row * 4:row * 4 + 3] = [v * (row + 1) for v in target[row * 4:row * 4 + 3]]
        target[12:15] = [8, 9, 10]
        self.assertMatrixNear(transfer_local_rotation(source, target, source, IDENTITY), target)

    def test_rest_relative_rotation_and_explicit_bridge(self):
        source, pose = rotate_z(0.7), rotate_z(1.0)
        target = rotate_z(-0.4)
        target[12:15] = [8, 9, 10]
        result = transfer_local_rotation(source, target, pose, IDENTITY)
        wanted = rotate_z(-0.1)
        wanted[12:15] = target[12:15]
        self.assertMatrixNear(result, wanted)
        # Proper bridge: source X -> target Z, source Z -> target -X.
        bridge = [0, 0, 1, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 0, 1]
        transformed = transfer_local_rotation(IDENTITY, IDENTITY, rotate_z(math.pi / 2), bridge)
        # Source Z maps to target -X: expect precisely a -90 degree X turn.
        self.assertMatrixNear(transformed, [1,0,0,0, 0,0,-1,0, 0,1,0,0, 0,0,0,1])

    def test_refuse_scaled_delta_and_reflected_bridge(self):
        scaled = IDENTITY[:]
        scaled[0] = 2
        with self.assertRaisesRegex(ValueError, "scale/shear/reflection"):
            transfer_local_rotation(IDENTITY, IDENTITY, scaled, IDENTITY)
        reflected = IDENTITY[:]
        reflected[0] = -1
        with self.assertRaisesRegex(ValueError, "proper rotation"):
            transfer_local_rotation(IDENTITY, IDENTITY, IDENTITY, reflected)
        translated = IDENTITY[:]
        translated[12] = 1
        with self.assertRaisesRegex(ValueError, "translation"):
            transfer_local_rotation(IDENTITY, IDENTITY, IDENTITY, translated)

    def test_bone_count_does_not_create_mapping(self):
        donor = dict(joints=[joint(0, "donor_root"), joint(1, "donor_grip", 0)])
        target = dict(joints=[joint(0, "target_root"), joint(1, "target_grip", 0)])
        result = bone_plan(donor, target)
        self.assertEqual(result["mappings"], [])
        self.assertEqual(len(result["unmapped_target"]), 2)

    def test_named_mapping_detects_parent_change(self):
        donor = dict(joints=[joint(0, "root"), joint(1, "arm", 0), joint(2, "grip", 1)])
        target = dict(joints=[joint(0, "root"), joint(1, "arm", 0), joint(2, "grip", 0)])
        result = bone_plan(donor, target)
        self.assertFalse(result["mappings"][-1]["mapped_parent_matches"])
        self.assertFalse(result["explicit_mapping"])

    def test_duplicate_mapping_rejected(self):
        rig = dict(joints=[joint(0, "root"), joint(1, "arm", 0)])
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            bone_plan(rig, rig, {"bones": [dict(source="root", target="root"),
                                         dict(source="root", target="arm")]})

    def test_cli_sources_and_outputs_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            donor, recipient, report = (root / name for name in ("donor.json", "recipient.json", "report.json"))
            rig = dict(version=16, byte_order="big", joints=[joint(0, "root")])
            original = json.dumps(rig).encode()
            donor.write_bytes(original)
            recipient.write_bytes(original)
            command = [sys.executable, str(Path(__file__).with_name("plan.py")),
                       "--donor", str(donor), "--recipient", str(recipient), "--output", str(report)]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr.decode())
            decoded = json.loads(report.read_text())
            self.assertFalse(decoded["export_enabled"])
            self.assertFalse(decoded["bone_plan"]["explicit_mapping"])
            self.assertIn("native byte ownership not proven", decoded["donor"]["evidence"])
            saved = report.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(saved, report.read_bytes())
            self.assertNotEqual(subprocess.run(command[:-1] + [str(donor)], capture_output=True).returncode, 0)
            self.assertEqual(donor.read_bytes(), original)
            self.assertEqual(recipient.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

"""Independent native-envelope fixtures for transfer audit regressions."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from animation_audit import AnimationFile, compare_files, main


def tree(*, endian=">", first=2.0, flags=0xe6, node_flags=3, ratio=1.0):
    # A five-key native compressed curve, with three complete key groups.
    block = bytearray(135)
    block[:4] = b"ANID" if endian == ">" else b"DINA"
    struct.pack_into(endian + "6H", block, 4, 1, 5, 8, 0, 6, int(first))
    block[19] = flags
    struct.pack_into(endian + "H", block, 22, 7)
    struct.pack_into(endian + "9I", block, 36, 80, 88, 88, 100, 124, 0, 0, 0, 0)
    struct.pack_into(endian + "2f", block, 72, ratio, first)
    struct.pack_into(endian + "2f", block, 80, 1 / 65535, 0)
    struct.pack_into(endian + "6H", block, 88, 7, 14, 14, 14, 14, 14)
    for group, value in enumerate((0, 65535, 65535)):
        tangent = round(.75 * 4095)
        words = [round(t * 4095) | (((tangent >> (4 * i)) & 15) << 12)
                 for i, t in enumerate((0, .25, .5))]
        struct.pack_into(endian + "4H", block, 100 + group * 8, value, *words)
    block[124] = node_flags
    raw = bytearray(240) + block
    struct.pack_into(">2I", raw, 0, 16, len(raw))
    struct.pack_into(">H", raw, 8, 1)
    struct.pack_into(">2I", raw, 16, 144, 72)
    raw[84] = 1
    struct.pack_into(">2I", raw, 96, 160, 1)
    raw[144:155] = b"Actor\0Clip\0"
    struct.pack_into(">16f", raw, 160, *(1 if i % 5 == 0 else 0 for i in range(16)))
    struct.pack_into(">2I", raw, 224, 7, 240)
    return bytes(raw)


def parsed(**kwargs):
    return AnimationFile("fixture.AN4", data=tree(**kwargs))


class AuditTests(unittest.TestCase):
    def test_identical_native_motion_and_metadata(self):
        result = compare_files(parsed(), parsed())
        row = result["records"][0]
        self.assertEqual(row["metadata_changes"], {})
        self.assertEqual(row["maximum_undeclared_channel_error"], 0)
        self.assertFalse(result["native_export_certified"])

    def test_equal_samples_do_not_hide_endian_and_flags(self):
        row = compare_files(parsed(), parsed(endian="<", flags=0xc0))["records"][0]
        self.assertEqual(row["maximum_undeclared_channel_error"], 0)
        self.assertIn("byte_order", row["metadata_changes"])
        self.assertIn("flags", row["metadata_changes"])

    def test_combo_start_is_not_reset_silently(self):
        row = compare_files(parsed(), parsed(first=0))["records"][0]
        self.assertIn("first", row["metadata_changes"])
        self.assertIn("old_first", row["metadata_changes"])
        self.assertGreater(row["maximum_undeclared_channel_error"], .4)

    def test_changed_bone_does_not_excuse_native_contract(self):
        row = compare_files(parsed(), parsed(first=0, node_flags=2), actor_name="Actor", changed_bones=[0])["records"][0]
        self.assertEqual(row["maximum_undeclared_channel_error"], 0)
        self.assertIn("first", row["metadata_changes"])
        self.assertEqual(len(row["node_flag_changes"]), 1)
        self.assertTrue(row["node_flag_changes"][0]["declared_changed"])
        with self.assertRaises(ValueError):
            compare_files(parsed(), parsed(), changed_bones=[0])

    def test_subframe_sampling_and_bounds(self):
        row = compare_files(parsed(), parsed(ratio=.9))["records"][0]
        self.assertEqual(row["sampled_times"], 25)
        self.assertGreater(row["maximum_undeclared_channel_error"], .05)
        for step in (float("nan"), 0, 2):
            with self.assertRaises(ValueError):
                compare_files(parsed(), parsed(), sample_step=step)
        for indices in ([True], [-1], [1]):
            with self.assertRaises(ValueError):
                compare_files(parsed(), parsed(), changed_bones=indices)

    def test_cli_new_output_unknown_version_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); src = root / "source.AN4"; new = root / "new.AN4"; out = root / "audit.json"
            src.write_bytes(tree()); new.write_bytes(tree())
            args = ["--source", str(src), "--candidate", str(new), "--actor", "Actor", "--output", str(out)]
            main(args)
            self.assertEqual(json.loads(out.read_text())["records"][0]["maximum_undeclared_channel_error"], 0)
            with self.assertRaises(SystemExit):
                main(args)
            raw = bytearray(tree());struct.pack_into(">I", raw, 0, 17);new.write_bytes(raw)
            with self.assertRaises(SystemExit):
                main(args[:-1] + [str(root / "refused.json")])
            self.assertFalse((root / "refused.json").exists())
            self.assertEqual(src.read_bytes(), tree())


if __name__ == "__main__":
    unittest.main()

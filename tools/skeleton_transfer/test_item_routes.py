"""Observed item syntax and ownership checks, independent of game assets."""
import json
from pathlib import Path
import tempfile
import unittest
from item_routes import declarations, inspect_items, main, MAX_DEPTH


class ItemRouteTests(unittest.TestCase):
    def test_literal_paths_and_comments_have_correct_ownership(self):
        text = 'item_type "Tool"\n{\n scn "Items\\" // path, not an escaped quote\n obj "a//b"\n act_fight1 "Swing"\n}\n'
        items, notices = declarations(text)
        self.assertEqual(notices, [])
        self.assertEqual(items[0]["fields"][0]["args"], ["Items\\"])
        self.assertEqual(items[0]["fields"][1]["args"], ["a//b"])
        result = inspect_items(text, "Tool")
        self.assertEqual({x["code"] for x in result["notices"]},
                         {"fight_routes_without_combo", "fight_routes_without_damage"})
        self.assertFalse(result["runtime_binding_certified"])

    def test_nested_and_commented_flags_do_not_activate_combat(self):
        text = 'item_type "Tool" {\n // combo\n hold_locator\n {\n combo\n damage 50\n }\n act_fight1 "Swing"\n}\n'
        result = inspect_items(text, "Tool")
        self.assertEqual(result["combat_flags"]["combo"], "absent")
        self.assertIsNone(result["damage"])

    def test_known_reference_supplies_combat_and_local_actions(self):
        text = 'item_type "Base" {\n combo\n sword\n damage 50\n act_fight1 "BaseSwing"\n}\nitem_type "Tool" {\n reference "Base"\n act_fight1 "ToolSwing"\n}\n'
        result = inspect_items(text, "Tool")
        self.assertTrue(result["references_resolved"])
        self.assertEqual(result["reference_chain"], ["Base", "Tool"])
        self.assertEqual(result["combat_flags"]["combo"], "declared")
        self.assertEqual(result["damage"], 50)
        self.assertEqual(result["actions"]["act_fight1"], [["ToolSwing"]])
        self.assertEqual(result["notices"], [])

    def test_external_and_cyclic_inheritance_are_not_guessed(self):
        external = 'item_type "Tool" {\n reference "NotSupplied"\n act_fight1 "Swing"\n}\n'
        result = inspect_items(external, "Tool")
        self.assertFalse(result["references_resolved"])
        self.assertEqual(result["combat_flags"]["combo"], "unknown")
        self.assertEqual([x["code"] for x in result["notices"]], ["unresolved_reference"])
        cycle = 'item_type "Tool" {\n reference "Base"\n}\nitem_type "Base" {\n reference "Tool"\n}\n'
        result = inspect_items(cycle, "Tool")
        self.assertFalse(result["references_resolved"])
        self.assertEqual([x["code"] for x in result["notices"]], ["reference_cycle_or_depth"])

    def test_orphan_and_duplicate_blocks_are_not_override_evidence(self):
        text = '//item_type "Tool"\n{\n combo\n}\nitem_type "Tool" {\n act_fight1 "Swing"\n}\n'
        result = inspect_items(text, "Tool")
        self.assertEqual(result["declarations"], 1)
        self.assertEqual(result["combat_flags"]["combo"], "absent")
        self.assertIn("orphan_top_level_block", {x["code"] for x in result["notices"]})
        for names in ('"Tool"', '"tool"'):
            with self.assertRaises(ValueError):
                inspect_items(text + f'item_type {names} {{\n combo\n}}\n', "Tool")

    def test_bad_framing_and_values_are_bounded(self):
        for text in ('item_type "Tool" {', 'item_type "Tool"\n',
                     'item_type "Tool" {\n /* combo */\n}', 'item_type "Tool" {\n\0\n}',
                     'item_type "Tool" {\n obj "bad\nquote"\n}',
                     'item_type "Tool" {\n' + '{' * MAX_DEPTH + '}' * MAX_DEPTH + '}'):
            with self.assertRaises(ValueError):
                declarations(text)
        result = inspect_items('item_type "Tool" {\n combo false\n damage nan\n}\n', "Tool")
        self.assertEqual(result["combat_flags"]["combo"], "unknown")
        self.assertIsNone(result["damage"])
        self.assertIn("uninspected_damage", {x["code"] for x in result["notices"]})

    def test_cli_preserves_source_and_existing_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root / "items.txt"; report = root / "report.json"
            raw = b'item_type "Tool" {\n combo\n damage 50\n}\n'
            source.write_bytes(raw)
            args = ["--items", str(source), "--item", "Tool", "--output", str(report)]
            main(args)
            self.assertEqual(json.loads(report.read_text())["damage"], 50)
            original_report = report.read_bytes()
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(report.read_bytes(), original_report)
            with self.assertRaises(SystemExit):
                main(args[:-1] + [str(source)])
            self.assertEqual(source.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()

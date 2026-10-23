"""Synthetic custom-clip and batch discovery regressions; run in Blender 4.4+."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import bpy

ROOT = Path(__file__).resolve().parents[2]
core = types.ModuleType('io_scene_tt_character._core')
core.__path__ = [str(ROOT / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules[core.__name__] = core
sys.path.insert(0, str(ROOT / 'formats/character/Addon'))
sys.path.insert(0, str(ROOT / 'formats/cu3/scripts'))
import io_scene_tt_character as addon
from io_scene_tt_character import importer
from io_scene_tt_character.animation_export import export_action, action_fingerprint
from io_scene_tt_character.custom_animation import create_custom_clip, load_custom_clip
from io_scene_tt_character._core.blender_import import create_rig
from io_scene_tt_character._core.an4_edit import patch_record
from io_scene_tt_character._core.source_provenance import SourceProvenance
from io_scene_tt_character._core.cu3 import FormatError
from test_an4_standalone import tree
from test_animation_bank_edit import fixture as make_bank

addon.register()


class CustomAnimationTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        temp = tempfile.TemporaryDirectory(prefix='tt-custom-animation-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        identity = [1 if i % 5 == 0 else 0 for i in range(16)]
        skeleton = {'joints': [{'name': 'root', 'index': 0, 'parent': None,
            'inverse_world_bind_row_major': identity, 'orient_row_major': identity}]}
        self.rig = create_rig(skeleton, 'Actor', bpy.context.scene.collection)
        self.rig['tt_character_skeleton'] = json.dumps(skeleton)
        self.rig['tt_character_assets_root'] = str(self.assets)
        self.rig['tt_character_game'] = 'LMSH1'
        self.rig['tt_native_source_provenance'] = SourceProvenance().dumps()
        raw = bytes(tree())
        self.raw, _ = patch_record(raw, 'Actor', 0, [[[0]*6]]*2,
                                   hashlib.sha256(raw).hexdigest())
        self.source = self.assets / 'source.pak'
        self.source.write_bytes(make_bank([self.raw, b'walking', b'running']))
        self.entry = dict(game='LMSH1', source=str(self.source), member='clip0.an4',
                          actor='Actor', clip='Clip')
        report = importer.import_catalog_entry(bpy.context, self.rig, self.entry)
        self.assertEqual(report['imported'], 1, report)

    def test_custom_copy_edit_and_bank_reload(self):
        original = self.rig.animation_data.action
        fingerprint = action_fingerprint(original)
        custom = create_custom_clip(self.rig, 'My animation')
        self.assertNotEqual(custom, original)
        self.assertEqual(self.rig.animation_data.action, custom)
        self.assertEqual(action_fingerprint(custom), fingerprint)
        bone = self.rig.pose.bones['root']
        bone.location.x = .25
        bone.keyframe_insert(data_path='location', frame=2)
        self.assertEqual(action_fingerprint(original), fingerprint)
        output = self.root / 'output' / 'custom.pak'
        report = export_action(bpy.context, self.rig, output, rebuild_bank=True)
        self.assertTrue(report['bank']['other_members_unchanged'])
        loaded = load_custom_clip(bpy.context, self.rig, output, self.entry)
        self.assertEqual(loaded['imported'], 1, loaded)
        bpy.context.scene.frame_set(2)
        self.assertAlmostEqual(bone.location.x, .25, places=4)
        reexport = self.root / 'reload' / 'custom.pak'
        export_action(bpy.context, self.rig, reexport, rebuild_bank=True)
        self.assertEqual(reexport.read_bytes(), output.read_bytes())
        self.assertEqual(self.source.read_bytes(), make_bank([self.raw, b'walking', b'running']))

    def test_custom_loose_clip_and_wrong_route(self):
        source = self.root / 'external.an4'
        source.write_bytes(self.raw)
        count = len(self.rig.tt_clips)
        for field, value in (('actor', 'Other'), ('clip', 'Other')):
            with self.assertRaisesRegex(FormatError, 'actor and clip name'):
                load_custom_clip(bpy.context, self.rig, source, dict(self.entry, **{field: value}))
        self.assertEqual(len(self.rig.tt_clips), count)
        loaded = load_custom_clip(bpy.context, self.rig, source, self.entry)
        self.assertEqual(loaded['imported'], 1, loaded)
        self.assertEqual(json.loads(self.rig.animation_data.action['tt_authored_action'])['member'], '')
        output = self.root / 'exports' / 'copy.an4'
        # A loose source must live in its own folder to keep export separate.
        moved = self.assets / 'external.an4'
        moved.write_bytes(self.raw)
        load_custom_clip(bpy.context, self.rig, moved, self.entry)
        export_action(bpy.context, self.rig, output)
        self.assertEqual(output.read_bytes(), self.raw)

    def test_standalone_batch_builds_one_asset_index(self):
        paths = [self.assets / name for name in ('first.an4', 'second.an4')]
        for path in paths:
            path.write_bytes(self.raw)
        with patch.object(importer, 'open_assets', wraps=importer.open_assets) as opened:
            report = importer.import_animations(bpy.context, self.rig, paths, 'Actor')
        self.assertEqual(report['imported'], 2, report)
        self.assertEqual(opened.call_count, 1)
        self.assertTrue(all(bpy.data.actions[c['action']].get('tt_native_bone_fingerprints')
                            for c in report['clips']))


if __name__ == '__main__':
    unittest.main(argv=[__file__])

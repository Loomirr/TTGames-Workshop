"""Asset-free Blender test for actual Character AN4 export storage handling.

Run with Blender 4.4+:
  blender --background --factory-startup --python-exit-code 1 --python \
    formats/character/test_animation_export_storage.py

Loads working source directly, not a previously built addon ZIP. All AN4 and
PAK inputs are synthetic, and output goes to a temporary directory.
"""
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

import bpy


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'tt_character_storage_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'formats/character/Addon/io_scene_tt_character')]
sys.modules[PACKAGE] = package
core = types.ModuleType(PACKAGE + '._core')
core.__path__ = [str(ROOT / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules[core.__name__] = core
exporter = importlib.import_module(PACKAGE + '.animation_export')
blender_import = importlib.import_module(PACKAGE + '._core.blender_import')
codec = importlib.import_module(PACKAGE + '._core.tt_deflate')
sys.path.insert(0, str(ROOT / 'formats/cu3/scripts'))
from test_an4_standalone import tree
from test_animation_bank_edit import fixture as make_bank


def digest(data):
    return hashlib.sha256(data).hexdigest()


class AnimationStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tt-an4-export-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        bpy.ops.wm.read_factory_settings(use_empty=True)
        identity = [1 if i % 5 == 0 else 0 for i in range(16)]
        skeleton = {'joints': [{'name': 'root', 'index': 0, 'parent': None,
                               'inverse_world_bind_row_major': identity,
                               'orient_row_major': identity}]}
        self.rig = blender_import.create_rig(skeleton, 'Fixture', bpy.context.scene.collection)
        self.rig['tt_character_assets_root'] = str(self.assets)
        self.rig['tt_character_skeleton'] = json.dumps(skeleton)
        bone = self.rig.pose.bones['root']
        for frame in (1, 2):
            bone.location = (0, 0, 0)
            bone.keyframe_insert(data_path='location', frame=frame)
        self.action = self.rig.animation_data.action
        self.action.use_frame_range = True
        self.action.frame_start, self.action.frame_end = 1, 2
        self.action['cu3_actor'], self.action['cu3_record'] = 'Actor', 0
        self.action['tt_native_pose_fingerprint'] = exporter.action_fingerprint(self.action)
        raw = bytes(tree())
        self.raw, _ = exporter.patch_record(raw, 'Actor', 0, [[[0]*6]]*2, digest(raw))

    def source(self, route, compressed):
        stored = codec.compress(self.raw) if compressed else self.raw
        path = self.assets / ('animations.pak' if route == 'bank' else 'clip.an4')
        path.write_bytes(make_bank([stored, b'walking', b'running']) if route == 'bank' else stored)
        for prop in ('tt_authored_action', 'tt_native_animation_source'):
            if prop in self.action:
                del self.action[prop]
        if route == 'legacy-loose':
            self.action['tt_native_animation_source'] = str(path)
        else:
            self.action['tt_authored_action'] = json.dumps({
                'source': str(path), 'member': 'clip0.an4' if route == 'bank' else ''})
        if route == 'bank':self.action['tt_animation_bank_sha256'] = digest(path.read_bytes())
        # Bank imports fingerprint decoded members; loose imports fingerprint
        # the standalone file, including its wrapper when present.
        self.action['cu3_sha256'] = digest(self.raw if route == 'bank' else stored)
        return path, stored

    def edit_pose(self):
        bone = self.rig.pose.bones['root']
        bone.location.x = .25
        bone.keyframe_insert(data_path='location', frame=2)
        bpy.context.scene.frame_set(7, subframe=.5)

    def test_unchanged_bytes_preserved_for_all_source_routes(self):
        for route in ('bank', 'authored-loose', 'legacy-loose'):
            for compressed in (False, True):
                with self.subTest(route=route, compressed=compressed):
                    path, stored = self.source(route, compressed)
                    before = path.read_bytes()
                    output = self.root / 'output' / f'{route}-{compressed}.an4'
                    report = exporter.export_action(bpy.context, self.rig, output)
                    self.assertEqual(output.read_bytes(), stored)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertFalse(report['changed'])
                    self.assertEqual(report['output_sha256'], digest(stored))
                    self.assertEqual(report['storage']['output'], 'Deflate_v1.0' if compressed else 'raw')
                    self.assertTrue(output.with_suffix('.AN4.json').is_file())

    def test_edited_wrapped_and_raw_outputs_preserve_storage_and_source(self):
        self.edit_pose()
        for route in ('bank', 'authored-loose', 'legacy-loose'):
            for compressed in (False, True):
                with self.subTest(route=route, compressed=compressed):
                    path, stored = self.source(route, compressed)
                    before = path.read_bytes()
                    output = self.root / 'output' / f'edited-{route}-{compressed}.an4'
                    report = exporter.export_action(bpy.context, self.rig, output)
                    result = output.read_bytes()
                    self.assertNotEqual(result, stored)
                    self.assertEqual(result.startswith(b'Deflate_v1.0'), compressed)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertTrue(report['changed'])
                    self.assertEqual(report['storage']['source'], report['storage']['output'])
                    self.assertEqual(report['imported_source_sha256'], self.action['cu3_sha256'])
                    parsed = exporter.AnimationFile(output)
                    animation = parsed.actors[0]['records'][0]['animation']
                    animation.prepare(scene_channels=True)
                    self.assertAlmostEqual(animation.sample(0)[0][0], 0, places=4)
                    self.assertAlmostEqual(animation.sample(1)[0][0], .25, places=4)
                    self.assertEqual((bpy.context.scene.frame_current, bpy.context.scene.frame_subframe), (7, .5))

    def test_stale_imported_source_refused_without_output(self):
        for route in ('bank', 'authored-loose', 'legacy-loose'):
            for compressed in (False, True):
                with self.subTest(route=route, compressed=compressed):
                    path, _ = self.source(route, compressed)
                    changed, _ = exporter.patch_record(
                        self.raw, 'Actor', 0, [[[0]*6], [[.5, 0, 0, 0, 0, 0]]], digest(self.raw))
                    stored = codec.compress(changed) if compressed else changed
                    path.write_bytes(make_bank([stored, b'walking', b'running']) if route == 'bank' else stored)
                    before = path.read_bytes()
                    output = self.root / 'output' / f'stale-{route}-{compressed}.an4'
                    with self.assertRaisesRegex(exporter.FormatError, 'changed since import'):
                        exporter.export_action(bpy.context, self.rig, output)
                    self.assertFalse(output.exists())
                    self.assertFalse(output.with_suffix('.AN4.json').exists())
                    self.assertEqual(path.read_bytes(), before)

    def test_rebuilt_bank_export_keeps_other_members(self):
        for edited in (False, True):
            if edited:self.edit_pose()
            for compressed in (False, True):
                with self.subTest(edited=edited, compressed=compressed):
                    path, stored = self.source('bank', compressed)
                    before = path.read_bytes()
                    output = self.root / 'output' / f'bank-{edited}-{compressed}.pak'
                    report = exporter.export_action(bpy.context, self.rig, output, rebuild_bank=True)
                    bank = exporter.AnimationBank(output)
                    self.assertEqual(bank.read_stored('clip1.an4'), b'walking')
                    self.assertEqual(bank.read_stored('clip2.an4'), b'running')
                    self.assertEqual(path.read_bytes(), before)
                    if not edited:self.assertEqual(output.read_bytes(), before)
                    clip = exporter.AnimationFile('clip.an4', data=bank.read_stored('clip0.an4'))
                    anim = clip.actors[0]['records'][0]['animation']
                    anim.prepare(scene_channels=True)
                    self.assertAlmostEqual(anim.sample(1)[0][0], .25 if edited else 0, places=4)
                    self.assertEqual(report['bank']['output_sha256'], digest(output.read_bytes()))
                    self.assertTrue(output.with_suffix('.PAK.json').is_file())

    def test_bank_export_refuses_old_import_loose_source_and_other_member_changes(self):
        for mode in ('old-import', 'loose', 'other-member'):
            path, _ = self.source('authored-loose' if mode == 'loose' else 'bank', False)
            if mode == 'old-import':del self.action['tt_animation_bank_sha256']
            if mode == 'other-member':
                bank = exporter.AnimationBank(path)
                path.write_bytes(bank.replace_members({'clip1.an4': b'other edit'}, digest(bank.data)))
            before = path.read_bytes()
            output = self.root / 'output' / f'{mode}.pak'
            with self.assertRaises(exporter.FormatError):
                exporter.export_action(bpy.context, self.rig, output, rebuild_bank=True)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix('.PAK.json').exists())
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(argv=[__file__])

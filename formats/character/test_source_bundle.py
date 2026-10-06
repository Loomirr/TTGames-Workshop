"""Shared-instance export integration with synthetic native meshes, without bpy.

Blender collection/rig/material adapters are replaced by small test adapters;
the exporter, consumed-revision ledger, native vertex/face writers, decoders and
filesystem publication are real. This does not establish Blender or game fidelity.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
package = ModuleType('character_bundle_fixture')
package.__path__ = [str(Path(__file__).parent / 'Addon/io_scene_tt_character')]
sys.modules[package.__name__] = package
core = ModuleType(package.__name__ + '._core')
core.__path__ = [str(root / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules[core.__name__] = core


def adapter(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    sys.modules[name] = module


def collect_vertices(objects, model, source_hash):
    request = next((obj.requested for obj in objects if obj.type == 'MESH'), {})
    return dict(schema='tt.native-vertex-edits.v1', sha256=source_hash,
                mesh_version=model['mesh_version'], parts={'0': request})


def collect_faces(objects, companion):
    result = copy.deepcopy(companion)
    delta = next((obj.face_delta for obj in objects), None)
    if delta is not None:
        result['parts']['0']['targets'][0]['offsets'][0] = delta
    return result


adapter(core.__name__ + '.native_model_blender', load_model=None)
adapter(core.__name__ + '.mesh_edit_blender', vertex_edits=collect_vertices)
adapter(core.__name__ + '.face_edit_blender', edited_companion=collect_faces)
adapter(core.__name__ + '.blender_import', check_rig=lambda *_: None)
adapter(core.__name__ + '.material_edit_guard', check_materials=lambda *_: None)
adapter(core.__name__ + '.asset_index', open_assets=lambda path, *_: SimpleNamespace(root=path))
adapter(package.__name__ + '.animation_export', action_fingerprint=lambda action: '',
        check_linked_actions=lambda action: None)

from character_bundle_fixture import exporter
from character_bundle_fixture.source_bundle import canonical_source, group_source_instances, SourceProposals
from character_bundle_fixture._core.cu3 import FormatError
from character_bundle_fixture._core.native_mesh import read_mesh_bytes
from character_bundle_fixture._core.source_provenance import SourceProvenance

spec = importlib.util.spec_from_file_location('native_mesh_fixture_cases', root / 'formats/cu3/scripts/test_mesh_edit.py')
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)


class Object(dict):
    def __init__(self, name, kind='ARMATURE', **properties):
        super().__init__(properties)
        self.name, self.type, self.children, self.tt_clips = name, kind, [], []
        self.requested, self.face_delta = {}, None

    @property
    def children_recursive(self):
        return [item for child in self.children for item in [child] + child.children_recursive]


class SourceBundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assets = self.root / 'sources'
        self.assets.mkdir()
        self.destination = self.root / 'export'

    def character(self, version=175, face=False):
        raw = fixture_module.face_fixture(version) if face else fixture_module.fixture(version)
        path = self.assets / ('Hero.GHG' if face else 'Hero.GSC')
        path.write_bytes(raw)
        source_hash = hashlib.sha256(raw).hexdigest()
        ledger = SourceProvenance(SimpleNamespace(root=self.assets, files={}, profile='synthetic'))
        ledger.record(path, 'model', data=raw)
        rig = Object('Hero', tt_native_source=str(path), tt_native_source_sha256=source_hash,
                     tt_character_assets_root=str(self.assets), tt_character_game='synthetic',
                     tt_native_source_provenance=ledger.dumps())
        mesh = Object('Hero mesh', 'MESH', tt_vertex_transform='test-adapter')
        if face:
            mesh['tt_face_source_sha256'] = source_hash
        rig.children.append(mesh)
        return rig, mesh, path, raw, ledger

    def duplicate(self, rig, mesh, path=None):
        duplicate = Object('Second instance', **dict(rig))
        if path is not None:
            duplicate['tt_native_source'] = str(path)
        second_mesh = Object('Second mesh', 'MESH', **dict(mesh))
        duplicate.children.append(second_mesh)
        rig.children.append(duplicate)
        return duplicate, second_mesh

    def export(self, rig, **kwargs):
        def load(path):
            raw = path.read_bytes()
            return dict(read_mesh_bytes(raw), source_sha256=hashlib.sha256(raw).hexdigest())
        with mock.patch.object(exporter, 'load_model', side_effect=load) as load_model:
            report = exporter.export_sources(rig, self.destination, **kwargs)
        return report, load_model

    def assert_no_output(self):
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob('.export.tt-stage-*')), [])

    def test_canonical_groups_include_relative_segments_and_symlink_aliases(self):
        path = self.assets / 'Hero.GHG'
        path.write_bytes(b'synthetic')
        (self.assets / 'folder').mkdir()
        alias = self.assets / 'folder/../Hero.GHG'
        rows = [(path, 'first'), (alias, 'second')]
        link = self.assets / 'alias.GHG'
        try:
            link.symlink_to(path)
        except OSError:
            pass
        else:
            rows.append((link, 'symlink'))
        groups = group_source_instances(rows)
        self.assertEqual(list(groups), [canonical_source(path)])
        self.assertEqual(groups[canonical_source(path)], [label for _, label in rows])

    def test_proposals_compare_complete_bytes_including_noop_and_empty_payloads(self):
        for first, second in ((b'original', b'edited'), (b'edited', b'original'),
                              (b'edit-one', b'edit-two'), (b'', b'edited')):
            with self.subTest(first=first, second=second):
                proposals = SourceProposals(self.assets / 'Hero.GHG')
                self.assertTrue(proposals.add('First actor', first))
                with self.assertRaisesRegex(FormatError, 'First actor / Second actor'):
                    proposals.add('Second actor', second)
        same = SourceProposals(self.assets / 'Hero.GHG')
        self.assertTrue(same.add('First', b''))
        self.assertFalse(same.add('Second', b''))
        self.assertEqual(same.instances, ['First', 'Second'])

    def test_duplicate_noop_roundtrips_preserve_original_bytes(self):
        for version in (169, 170, 175):
            with self.subTest(version=version):
                self.destination = self.root / str(version)
                rig, mesh, path, raw, _ = self.character(version)
                self.duplicate(rig, mesh)
                report, load = self.export(rig)
                self.assertEqual(load.call_count, 1)
                self.assertEqual(len(report['files']), 1)
                self.assertEqual((self.destination / path.name).read_bytes(), raw)
                self.assertEqual(report['vertex_patches'][str(canonical_source(path))]['changed_bytes'], 0)
                self.assertEqual(report['source_instances'][str(canonical_source(path))]['instances'], ['Hero', 'Second instance'])

    def test_identical_edited_instances_deduplicate_and_decode_the_intentional_edit(self):
        rig, mesh, path, raw, _ = self.character()
        (self.assets / 'alias-folder').mkdir()
        _, second = self.duplicate(rig, mesh, self.assets / 'alias-folder/../Hero.GSC')
        mesh.requested = {'uv': [[.25, .75], [1, 0], [0, 1]]}
        second.requested = copy.deepcopy(mesh.requested)
        # A repeated dependency role must not later reset the edited model bytes.
        rig['tt_native_texture_sources'] = json.dumps([str(path), str(path)])
        report, load = self.export(rig)
        output = (self.destination / path.name).read_bytes()
        self.assertEqual(load.call_count, 1)
        self.assertEqual(len(report['files']), 1)
        self.assertNotEqual(output, raw)
        before, after = read_mesh_bytes(raw), read_mesh_bytes(output)
        self.assertEqual(after['parts'][0]['vertices'][0]['uv'], [.25, .75])
        self.assertEqual(after['parts'][0]['triangles'], before['parts'][0]['triangles'])
        self.assertEqual(len(output), len(raw))
        self.assertGreater(report['vertex_patches'][str(canonical_source(path))]['changed_bytes'], 0)

    def test_edited_unchanged_and_divergent_instances_fail_in_both_orders(self):
        changes = [{'uv': [[.25, .75], [1, 0], [0, 1]]},
                   {'uv': [[.75, .25], [1, 0], [0, 1]]}]
        for left, right in ((changes[0], {}), ({}, changes[0]),
                            (changes[0], changes[1]), (changes[1], changes[0])):
            with self.subTest(left=left, right=right):
                rig, mesh, _, _, _ = self.character()
                _, second = self.duplicate(rig, mesh)
                mesh.requested, second.requested = left, right
                with self.assertRaisesRegex(FormatError, 'Conflicting native source instances'):
                    self.export(rig)
                self.assert_no_output()

    def test_native_face_and_vertex_proposals_combine_then_compare(self):
        rig, mesh, path, raw, _ = self.character(face=True)
        _, second = self.duplicate(rig, mesh)
        for instance in (mesh, second):
            instance.requested = {'uv': [[.25, .75], [1, 0], [0, 1]]}
            instance.face_delta = [.25, .5, .75]
        report, _ = self.export(rig)
        output = (self.destination / path.name).read_bytes()
        part = read_mesh_bytes(output)['parts'][0]
        self.assertNotEqual(output, raw)
        self.assertEqual(part['vertices'][0]['uv'], [.25, .75])
        self.assertEqual(part['morphs']['targets'][0]['offsets'][0], [.25, .5, .75])
        self.assertTrue(report['face_patches'])
        self.assertTrue(report['vertex_patches'])

    def test_edited_and_unchanged_face_instances_conflict(self):
        rig, mesh, _, _, _ = self.character(face=True)
        self.duplicate(rig, mesh)
        mesh.face_delta = [.25, .5, .75]
        with self.assertRaisesRegex(FormatError, 'Conflicting native source instances'):
            self.export(rig, mesh_edits=False)
        self.assert_no_output()

    def test_duplicate_logical_targets_are_rejected_even_when_bytes_agree(self):
        rig, _, path, raw, ledger = self.character()
        other = self.assets / 'other.GSC'
        other.write_bytes(raw)
        record = ledger.record(other, 'other-model', data=raw)
        record['logical_path'] = path.name
        rig['tt_native_source_provenance'] = ledger.dumps()
        with self.assertRaisesRegex(FormatError, 'Duplicate or conflicting'):
            self.export(rig)
        self.assert_no_output()

    def test_changed_consumed_companion_still_fails_before_output(self):
        rig, _, _, _, ledger = self.character()
        companion = self.assets / 'Hero.TEX'
        companion.write_bytes(b'imported-revision')
        ledger.record(companion, 'texture')
        rig['tt_native_source_provenance'] = ledger.dumps()
        companion.write_bytes(b'changed-revision')
        with self.assertRaisesRegex(FormatError, 'changed since import'):
            self.export(rig)
        self.assert_no_output()

    def test_copied_source_hash_and_material_guards_still_run_for_each_instance(self):
        rig, mesh, _, _, _ = self.character()
        duplicate, second = self.duplicate(rig, mesh)
        duplicate['tt_native_source_sha256'] = 'stale'
        with self.assertRaisesRegex(FormatError, 'changed since import'):
            self.export(rig)
        self.assert_no_output()
        duplicate['tt_native_source_sha256'] = rig['tt_native_source_sha256']
        def check(instance):
            if instance is second:
                raise FormatError('edited material')
        with mock.patch.object(exporter, 'check_materials', side_effect=check) as guard:
            with self.assertRaisesRegex(FormatError, 'edited material'):
                self.export(rig)
            self.assertEqual(guard.call_count, 2)
        self.assert_no_output()


if __name__ == '__main__':
    unittest.main()

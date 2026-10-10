"""Asset-free declaration inspector, byte-reader parity and refusal tests.

Synthetic material/CD framing tests tool behavior only. No fixture proves the
appearance or resource ownership of Tony, Mark 6, Hulkbuster or Alfred assets.
"""
from contextlib import redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import inspect_material_declarations as cli
from material_declaration_inspection.native_materials import read_materials, read_materials_bytes
from material_declaration_inspection.definitions import read_definition, read_definition_bytes


def model_fixture(*, count=1, version=232, mesh_version=175):
    # Independent scalar framing for the already gated UMTL 232 prefix.
    records = []
    for index in range(count):
        raw = bytearray(0x480)
        struct.pack_into('>I', raw, 0, 2)
        struct.pack_into('>2I', raw, 12, 9, 7)  # Retained enum values, no invented meanings.
        struct.pack_into('>2I', raw, 36, 1, 5)
        struct.pack_into('>I', raw, 0x88, 2)
        raw[0x99] = 4
        for i in range(17):
            struct.pack_into('>2I', raw, 0x9a + i * 8, 1 if i in (0, 4) else 0,
                             2 if i == 4 else 0 if i == 0 else 0xffffffff)
        raw[0x130] = 0xaa  # Opaque shader flags remain opaque.
        struct.pack_into('>4I', raw, 0x180, 4, 10, 2, 0)
        ids = [2] + [-1] * 5 + [5] + [-1] * 11
        struct.pack_into('>18iI', raw, 0x1a9, *ids, 17)
        raw[0x1a9 + 76:0x1a9 + 93] = bytes([4] * 17)
        name = f'NativeMaterial{index}'.encode('ascii') + b'\0'
        struct.pack_into('>H', raw, 0x3fd, len(name))
        raw[0x3ff:0x3ff + len(name)] = name
        flags = bytearray(76)
        flags[3], flags[15], flags[44] = 125, 15, 3
        struct.pack_into('>2I', flags, 47, 0xffffffff, 0xffffffff)
        struct.pack_into('>I', flags, 72, 2)
        records.append(bytes(raw + flags))
    # Only the MESH header is valid. Deliberately undecodable geometry and
    # skeleton bytes establish that this command does not call those readers.
    header = b'HSEM' + struct.pack('>I', mesh_version) + b'not mesh buffers; HGOL ownership unknown'
    return header + b'LTMU' + struct.pack('>2I', version, count) + b''.join(records) + b'ROTV' + bytes(17) + b'TDML'


def block(name, payload):
    name = name.encode('ascii') + b'\0'
    return struct.pack('<2I', 8 + len(name) + len(payload), len(name)) + name + payload


def string(value):
    raw = value.encode('ascii') + b'\0'
    return struct.pack('<I', len(raw)) + raw


def definition_fixture(*, version=27, selector=3, count=1, unknown_tail=False, texture='../not-opened.TEX'):
    fields = [(2, 'Material'), (5, 'Texture'), (4, 'Roughness')]
    if unknown_tail:
        fields.append((99, 'UndecodedControl'))
    schemas = b''.join(struct.pack('<I', typ) + string(name) + bytes(20 if version >= 27 else 16)
                       for typ, name in fields)
    cls = block('Class', string('Material Remap') + block('Types', struct.pack('<I', len(fields)) + schemas))
    values = struct.pack('<i', selector) + string(texture) + struct.pack('<f', 0.5)
    if unknown_tail:
        values += b'unknown native fields'
    objects = b''.join(block('MOBJ', bytes(4 if version >= 28 else 3) + values) for _ in range(count))
    return (block('StreamInfo', struct.pack('<I', version)) + block('ClassList', cls) +
            block('OLST', struct.pack('<HI', 0, count) + objects))


def compressed_definition(data):
    return b'Deflate_v1.0'.ljust(32, b'\0') + struct.pack('<I', len(data)) + b'\x05' + struct.pack('<H', len(data)) + data


class Declarations(unittest.TestCase):
    def test_remap_requires_definition(self):
        with self.assertRaisesRegex(ValueError, 'requires an explicit'):
            cli.inspect('not-opened.GHG', remap_library='not-opened.GSC')

    def test_candidate_differences_retain_shader_and_texture_distinctions(self):
        entries = [dict(fields={'skinned': value, 'numBones': value*4},
                        render_flags={'nextVariantIdx': 1-value}, table_version=176,
                        texture_ids=[3, value+4], texture_formats=[]) for value in (0, 1)]
        differences = {row['field']: row['values'] for row in cli._candidate_differences(entries)}
        self.assertEqual(differences['fields.numBones'], [0, 4])
        self.assertEqual(differences['fields.skinned'], [0, 1])
        self.assertEqual(differences['render_flags.nextVariantIdx'], [1, 0])
        self.assertEqual(differences['texture_ids'], [[3, 4], [3, 5]])
        self.assertNotIn('table_version', differences)
        self.assertEqual(cli._candidate_differences(entries[:1]), [])

    def test_remap_reports_duplicates_missing_names_and_does_not_follow_paths(self):
        # Both same-named records must survive; name equality does not prove
        # renderer/LOD ownership. The missing path in the CD is never opened.
        raw = model_fixture(count=2).replace(b'NativeMaterial1', b'NativeMaterial0')
        self.model.write_bytes(raw)
        parsed = {'objects': [dict(complete=True, fields={
            'Source Material': name, 'Source Material Type': 1, 'Material': 3,
            'Source Material Resource File': '../not-opened'})
            for name in ('NativeMaterial0', 'Missing', 'nativematerial0')]}
        report = cli.remap_comparison(parsed, self.model, max_objects=256, max_text=128)
        rows = report['declarations']
        self.assertEqual([row['status'] for row in rows],
                         ['multiple_name_candidates', 'name_not_found', 'name_not_found'])
        self.assertEqual([row['index'] for row in rows[0]['candidates']], [0, 1])
        self.assertEqual(report['source']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.model.read_bytes(), raw)
        limited = cli.remap_comparison(parsed, self.model, max_objects=1, max_text=128)
        self.assertEqual(limited['omitted_declarations'], 2)

    def test_remap_unknown_table_rejected(self):
        self.model.write_bytes(model_fixture(version=233))
        with self.assertRaises(ValueError):
            cli.remap_comparison({'objects': []}, self.model, max_objects=1, max_text=128)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.model = self.root / 'SharedBody.GHG'
        self.cd = self.root / 'Selected.CD'
        self.output = self.root / 'report.json'
        self.model.write_bytes(model_fixture())
        self.cd.write_bytes(definition_fixture())

    def test_native_material_path_and_bytes_apis_agree(self):
        self.assertEqual(read_materials(self.model), read_materials_bytes(self.model.read_bytes()))

    def test_definition_path_and_bytes_apis_preserve_fields_and_provenance(self):
        for version in (25, 26, 27, 28, 29, 30, 31):
            for compressed in (False, True):
                with self.subTest(version=version, compressed=compressed):
                    data = definition_fixture(version=version, unknown_tail=True)
                    if compressed:
                        data = compressed_definition(data)
                    self.cd.write_bytes(data)
                    actual = read_definition_bytes(data, source=self.cd)
                    self.assertEqual(actual, read_definition(self.cd))
                    self.assertEqual(actual['source'], str(self.cd.resolve()))
                    self.assertEqual(actual['source_sha256'], hashlib.sha256(data).hexdigest())
                    self.assertFalse(actual['objects'][0]['complete'])
        self.assertIsNone(read_definition_bytes(definition_fixture())['source'])

    def test_native_declarations_survive_unreadable_geometry_and_skeleton(self):
        report = cli.inspect(self.model, self.cd)
        self.assertEqual(report['source']['sha256'], hashlib.sha256(self.model.read_bytes()).hexdigest())
        self.assertEqual(report['mesh_header']['version'], 175)
        self.assertEqual(report['material_table']['version'], 232)
        self.assertIn('name placement remains inferred', report['material_table']['layout_validation'])
        material = report['materials'][0]
        self.assertEqual(material['native_special_id'], 3)
        self.assertEqual(material['costume_role'], 3)
        self.assertEqual(material['texture_ids'][6], 5)
        self.assertEqual(len(material['texture_ids']), 18)
        self.assertEqual(len(material['texture_formats']), 17)
        self.assertEqual(material['raw_uv_pairs'][4], (1, 2))
        self.assertEqual(material['surface_fields']['surfaceMapFormat0'], 5)
        self.assertEqual(material['shader_fields']['substanceMode'], 9)
        self.assertEqual(material['shader_fields']['roughnessMode'], 7)
        self.assertIsNone(material['shader_fields']['vertAlbedo'])
        self.assertEqual(material['render_flags']['colourWriteMask'], 15)
        self.assertIn('Opaque', material['opaque_shader_flags']['interpretation'])
        self.assertLessEqual(len(material['opaque_shader_flags']['first_bytes_hex']), 128)
        self.assertEqual(report['renderer_evaluation']['status'], 'not_evaluated')
        for module in ('bpy', 'material_declaration_inspection.native_mesh',
                       'material_declaration_inspection.skeleton', 'material_declaration_inspection.costume_materials'):
            self.assertNotIn(module, sys.modules)
        serialized = cli._render(report)
        for key in ('"vertices"', '"triangles"', '"pixels"', '"unapplied_fields"', '"normal_applied"'):
            self.assertNotIn(key, serialized)

    def test_cd_selectors_are_numeric_observations_without_remap_claims(self):
        report = cli.inspect(self.model, self.cd)
        definition = report['definition']
        row = definition['objects'][0]
        self.assertEqual(row['class_name'], 'Material Remap')
        self.assertEqual(row['material_selector'], 3)
        self.assertEqual(row['same_numeric_role']['material_indices'], [0])
        self.assertEqual({field['name']: field['value'] for field in row['fields']}['Texture'], '../not-opened.TEX')
        self.assertIn('not a material-remap implementation', definition['role_comparison'])
        self.assertIn('ownership and renderer branch are not verified', definition['pairing'])
        self.cd.write_bytes(definition_fixture(selector=999))
        row = cli.inspect(self.model, self.cd)['definition']['objects'][0]
        self.assertEqual(row['same_numeric_role']['total_matches'], 0)
        self.assertEqual(row['material_selector'], 999)

    def test_optional_definition_and_partial_fields_are_explicit(self):
        self.assertIsNone(cli.inspect(self.model)['definition'])
        self.cd.write_bytes(definition_fixture(unknown_tail=True))
        report = cli.inspect(self.model, self.cd)['definition']
        self.assertFalse(report['objects'][0]['complete'])
        self.assertLess(report['objects'][0]['decoded_end'], report['objects'][0]['offset'] + report['objects'][0]['size'])
        self.assertIn('remain undecoded', report['unparsed_scope'])

    def test_report_detail_caps_are_explicit(self):
        self.model.write_bytes(model_fixture(count=3))
        self.cd.write_bytes(definition_fixture(count=3, texture='x' * 200))
        report = cli.inspect(self.model, self.cd, max_materials=1, max_objects=2, max_fields=2, max_text=64)
        self.assertTrue(report['declaration_lists_truncated'])
        self.assertEqual(report['omitted_materials'], 2)
        self.assertEqual(report['definition']['omitted_objects'], 1)
        self.assertEqual(report['definition']['omitted_fields'], 5)
        field = report['definition']['objects'][0]['fields'][1]
        self.assertEqual(field['value']['prefix'], 'x' * 64)
        self.assertEqual(field['value']['chars'], 200)
        self.assertTrue(field['value']['truncated'])
        self.assertEqual(field['value']['sha256'], hashlib.sha256(b'x' * 200).hexdigest())

    def test_global_cd_field_budget_is_not_multiplied_per_object(self):
        self.cd.write_bytes(definition_fixture(count=3))
        with patch.object(cli, 'MAX_TOTAL_CD_FIELDS', 4):
            report = cli.inspect(self.model, self.cd)
        self.assertEqual(report['definition']['reported_fields'], 4)
        self.assertEqual(report['definition']['omitted_fields'], 5)

    def test_unknown_mesh_material_and_cd_versions_stay_rejected(self):
        self.model.write_bytes(model_fixture(mesh_version=176))
        with self.assertRaisesRegex(ValueError, 'supported native MESH'):
            cli.inspect(self.model)
        self.model.write_bytes(model_fixture(version=233))
        with self.assertRaisesRegex(ValueError, 'material table version'):
            cli.inspect(self.model)
        self.model.write_bytes(model_fixture())
        self.cd.write_bytes(definition_fixture(version=32))
        with self.assertRaisesRegex(ValueError, 'not verified'):
            cli.inspect(self.model, self.cd)

    def test_ambiguous_mesh_headers_and_corrupt_material_boundary_refuse(self):
        self.model.write_bytes(model_fixture() + b'HSEM' + struct.pack('>I', 169))
        with self.assertRaisesRegex(ValueError, 'multiple candidates'):
            cli.inspect(self.model)
        self.model.write_bytes(model_fixture()[:-4] + b'FAKE')
        with self.assertRaisesRegex(ValueError, 'boundary missing'):
            cli.inspect(self.model)

    def test_file_and_material_count_bounds_precede_material_decoder(self):
        with patch.object(cli, 'MAX_MODEL_BYTES', 32), patch.object(cli, 'read_materials_bytes') as decode:
            with self.assertRaisesRegex(ValueError, 'at most 32'):
                cli.inspect(self.model)
        decode.assert_not_called()
        data = bytearray(model_fixture())
        struct.pack_into('>I', data, data.index(b'LTMU') + 8, cli.MAX_DECODED_MATERIALS + 1)
        self.model.write_bytes(data)
        with patch.object(cli, 'read_materials_bytes') as decode:
            with self.assertRaisesRegex(ValueError, 'count exceeds inspection limit'):
                cli.inspect(self.model)
        decode.assert_not_called()

    def test_cd_stored_and_declared_decoded_bounds_precede_definition_decoder(self):
        with patch.object(cli, 'MAX_CD_BYTES', 32), patch.object(cli, 'read_definition_bytes') as decode:
            with self.assertRaisesRegex(ValueError, 'at most 32'):
                cli.inspect(self.model, self.cd)
        decode.assert_not_called()
        self.cd.write_bytes(b'Deflate_v1.0'.ljust(32, b'\0') + struct.pack('<I', cli.MAX_CD_BYTES + 1))
        with patch.object(cli, 'read_definition_bytes') as decode:
            with self.assertRaisesRegex(ValueError, 'declared decoded size'):
                cli.inspect(self.model, self.cd)
        decode.assert_not_called()

    def test_compressed_definition_hash_is_stored_source_hash(self):
        self.cd.write_bytes(compressed_definition(definition_fixture()))
        report = cli.inspect(self.model, self.cd)['definition']
        self.assertEqual(report['source']['compression'], 'Deflate_v1.0')
        self.assertEqual(report['source']['sha256'], hashlib.sha256(self.cd.read_bytes()).hexdigest())
        self.assertIn('decompressed', report['offset_basis'])

    def test_snapshot_does_not_use_directory_metadata(self):
        with patch.object(Path, 'stat', side_effect=AssertionError('Use the open handle')):
            data, info = cli._snapshot(self.model, cli.MAX_MODEL_BYTES)
        self.assertEqual(info['sha256'], hashlib.sha256(data).hexdigest())

    def test_source_growth_during_snapshot_is_rejected(self):
        source = self.model
        stream = source.open('rb')
        class GrowingFile:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return stream.__exit__(*args)
            def fileno(self):
                return stream.fileno()
            def read(self, size):
                result = stream.read(size)
                with open(source, 'ab') as writer:
                    writer.write(b'changed')
                return result
        with patch.object(Path, 'open', return_value=GrowingFile()), patch.object(cli, 'read_materials_bytes') as decode:
            with self.assertRaisesRegex(ValueError, 'source changed'):
                cli.inspect(self.model)
        decode.assert_not_called()

    def test_unknown_inputs_and_excess_report_values_are_refused(self):
        for source, definition in ((self.root / 'GAME.DAT', None), (self.model, self.root / 'index.hdr')):
            with self.assertRaises(ValueError):
                cli.inspect(source, definition)
        for limits in (dict(max_objects=0), dict(max_materials=1025), dict(max_fields=257), dict(max_text=1)):
            with self.assertRaises(ValueError):
                cli.inspect(self.model, **limits)
        with self.assertRaisesRegex(ValueError, 'bounded primitive'):
            cli._value(list(range(17)), 64)
        with self.assertRaises(ValueError):
            cli._render({'invalid': float('nan')})

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_material_declarations.py')),
                               *map(str, args)], capture_output=True, text=True)

    def test_help_runs_without_blender(self):
        result = self.run_cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('without loading a mesh, skeleton or Blender', ' '.join(result.stdout.split()))

    def test_cli_saves_declarations_and_preserves_selected_sources(self):
        before_model, before_cd = self.model.read_bytes(), self.cd.read_bytes()
        result = self.run_cli(self.model, '--definition', self.cd, '--output', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Renderer application was not evaluated', result.stdout)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(report['schema'], 'tt.material-declarations.v1')
        self.assertEqual(report['renderer_evaluation']['status'], 'not_evaluated')
        self.assertEqual(report['definition']['objects'][0]['material_selector'], 3)
        self.assertEqual(self.model.read_bytes(), before_model)
        self.assertEqual(self.cd.read_bytes(), before_cd)
        self.assertEqual(len(list(self.root.iterdir())), 3)

    def test_cli_existing_file_and_dangling_link_are_preserved(self):
        self.output.write_bytes(b'keep existing report')
        result = self.run_cli(self.root / 'missing.GHG', '--output', self.output)
        self.assertEqual(result.returncode, 2)
        self.assertIn('new diagnostic report filename', result.stderr)
        self.assertEqual(self.output.read_bytes(), b'keep existing report')
        self.output.unlink()
        try:
            self.output.symlink_to(self.root / 'missing-target')
        except OSError:
            self.skipTest('Symbolic links unavailable')
        result = self.run_cli(self.model, '--output', self.output)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse((self.root / 'missing-target').exists())

    def test_cli_competing_creation_is_not_replaced(self):
        report = cli.inspect(self.model)
        def compete(*args, **kwargs):
            self.output.write_bytes(b'competing report')
            return report
        with patch.object(cli, 'inspect', side_effect=compete), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main([str(self.model), '--output', str(self.output)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.output.read_bytes(), b'competing report')

    def test_failed_parse_or_report_size_does_not_create_output(self):
        self.model.write_bytes(model_fixture(version=233))
        result = self.run_cli(self.model, '--output', self.output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())
        self.model.write_bytes(model_fixture())
        with patch.object(cli, 'MAX_REPORT_BYTES', 128), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main([str(self.model), '--output', str(self.output)])
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()

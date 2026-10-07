"""Constructed HGOL diagnostics and validity regressions; no original assets."""
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


package = types.ModuleType('skeleton_diagnostics_fixture')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from skeleton_diagnostics_fixture.cu3 import FormatError
from skeleton_diagnostics_fixture.skeleton import read_skeleton, scan_skeleton_candidates, select_skeleton
from skeleton_diagnostics_fixture.skeleton_diagnostics import skeleton_candidate_report

I4 = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
CLI = Path(__file__).with_name('inspect_skeleton_candidates.py')


def native(*, opaque=b'', local=I4, inverse=I4, special=0, flags=0, pre=b'', post=b'', layers=True):
    """One explicit HGOL16 fixture using the already supported ROTV layout."""
    data = b'LOGH' + struct.pack('>I', 16)
    data += b'ROTV' + struct.pack('>IH', 1, 5) + b'Root\0'
    data += struct.pack('>16f3f2B', *I4, 0, 0, 0, 255, flags)
    data += b'ROTV' + struct.pack('>I16f', 1, *local)
    data += b'ROTV' + struct.pack('>I16f', 1, *inverse)
    data += b'ROTV' + struct.pack('>I', len(pre)) + pre
    data += b'ROTV' + struct.pack('>I', 0)
    data += b'ROTV' + struct.pack('>I', len(post)) + post
    data += struct.pack('>I', len(opaque)) + opaque
    data += b'ROTV' + struct.pack('>IBBHB', 1, 0, 0, special, 0)
    data += b'ROTV' + struct.pack('>I', int(layers))
    if layers:
        data += struct.pack('>H', 6) + b'Layer\0' + struct.pack('>3H', 0, 1, 0)
    return data


def native_v10():
    names = b'Root\0Layer\0'
    data = b'LBTN' + struct.pack('>2I', 1, len(names)) + names
    data += b'LOGH' + struct.pack('>3I', 10, 1, 0)
    data += struct.pack('>16f3f2B', *I4, 0, 0, 0, 255, 0)
    data += struct.pack('>I16f', 1, *I4) * 2
    data += struct.pack('>4I', 0, 0, 0, 0)
    data += struct.pack('>IBBHB', 1, 0, 0, 0, 0)
    return data + struct.pack('>2I3H', 1, 5, 0, 1, 0)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'fixture.GHG'

    def tearDown(self):
        self.temp.cleanup()

    def scan(self, raw):
        self.source.write_bytes(raw)
        return scan_skeleton_candidates(self.source)

    def report(self, raw, **options):
        return skeleton_candidate_report(self.scan(raw), **options)


class CandidateValidityTests(Fixture):
    def test_singular_bind_candidate_is_rejected_before_ownership_arbitration(self):
        singular = list(I4)
        singular[4:8] = singular[0:4]  # finite but linearly dependent rows
        for field in ('local', 'inverse'):
            with self.subTest(field=field):
                invalid = native(**{field: singular})
                self.scan(invalid + native())
                rig = read_skeleton(self.source)
                self.assertEqual(rig['hgol_offset'], len(invalid))
                rejected = rig['selection']['rejected_candidates']
                self.assertEqual(rejected[0]['offset'], 0)
                self.assertIn('singular matrix', rejected[0]['issue'])

    def test_only_singular_candidate_cannot_be_imported(self):
        self.scan(native(inverse=(0,) * 16))
        with self.assertRaisesRegex(FormatError, 'singular matrix'):
            read_skeleton(self.source)

    def test_json_skeleton_uses_the_same_bind_validity_gate(self):
        rig = self.scan(native())['candidates'][0]
        rig['joints'][0]['local_bind_row_major'] = [0] * 16
        path = self.folder / 'rig.json'
        path.write_text(json.dumps(rig), encoding='utf-8')
        with self.assertRaisesRegex(FormatError, 'singular matrix'):
            read_skeleton(path)

    def test_different_valid_bind_tables_still_refuse_equal_joint_count(self):
        translated = list(I4)
        translated[12] = 4
        scan = self.scan(native() + native(local=translated))
        with self.assertRaisesRegex(FormatError, 'conflicting native bind tables'):
            select_skeleton(scan['candidates'], expected_nodes=1)

    def test_invalid_candidate_report_is_json_serializable_without_native_nan(self):
        invalid = list(I4)
        invalid[0] = float('nan')
        report = self.report(native(local=invalid))
        self.assertFalse(report['candidates'][0]['validation']['valid'])
        self.assertIsNone(report['candidates'][0]['identity'])
        self.assertEqual(report['selection']['outcome'], 'rejected')
        json.dumps(report, allow_nan=False)


class CandidateDiagnosticsTests(Fixture):
    def test_adjacent_candidates_have_separate_exact_consumed_spans(self):
        first, second = native(), native(opaque=b'Uninterpreted')
        scan = self.scan(first + second)
        self.assertEqual([(r['hgol_offset'], r['end_offset']) for r in scan['candidates']],
                         [(0, len(first)), (len(first), len(first) + len(second))])
        for candidate in scan['candidates']:
            spans = candidate['decoded_section_spans']
            self.assertEqual(spans[0]['start'], candidate['hgol_offset'])
            self.assertEqual(spans[-1]['end'], candidate['end_offset'])
            for left, right in zip(spans, spans[1:]):
                self.assertEqual(left['end'], right['start'])
            for span in spans:
                raw = (first + second)[span['start']:span['end']]
                self.assertEqual(span['bytes'], len(raw))
                self.assertEqual(span['sha256'], hashlib.sha256(raw).hexdigest())
        report = skeleton_candidate_report(scan)
        self.assertIn('adjacent_decoded_spans', [r['kind'] for r in report['relationships']['items']])

    def test_separated_candidates_do_not_acquire_an_overlap_relationship(self):
        raw = native()
        report = self.report(raw + b'Padding' + raw)
        self.assertEqual(report['relationships']['observations_total'], 0)
        self.assertEqual(report['candidates'][0]['end_offset'], len(raw))
        self.assertEqual(report['candidates'][1]['hgol_offset'], len(raw) + 7)

    def test_nested_hgol_in_opaque_payload_is_reported_and_remains_ambiguous(self):
        child = native()
        raw = native(opaque=child)
        scan = self.scan(raw)
        self.assertEqual(len(scan['candidates']), 2)
        with self.assertRaisesRegex(FormatError, 'conflicting resource/layer ownership'):
            read_skeleton(self.source)
        report = skeleton_candidate_report(scan)
        relation = next(r for r in report['relationships']['items'] if r['kind'] == 'contained_decoded_span')
        self.assertEqual((relation['outer_candidate'], relation['inner_candidate']), (0, 1))
        self.assertEqual(relation['containing_field'], 'opaque_payload')
        self.assertTrue(relation['inner_end_within_field'])
        self.assertEqual(report['selection']['outcome'], 'ambiguous')
        self.assertEqual(report['binding_groups']['groups_total'], 1)
        self.assertEqual(report['ownership_groups']['groups_total'], 2)
        self.assertIn('opaque_tail_hex', report['candidates'][1]['differences_from_baseline']['paths'])

    def test_opaque_bytes_remain_identity_evidence_but_are_not_exported(self):
        opaque = b'Private native payload remains in the source'
        report = self.report(native(opaque=opaque) + native(opaque=opaque + b'!'))
        rendered = json.dumps(report)
        self.assertNotIn(opaque.decode('ascii'), rendered)
        self.assertNotIn(opaque.hex(), rendered)
        self.assertNotIn('Root', rendered)
        self.assertNotIn('local_bind_row_major": [', rendered)
        self.assertEqual(report['binding_groups']['groups_total'], 1)
        self.assertEqual(report['selection']['outcome'], 'ambiguous')
        self.assertEqual(report['candidates'][0]['counts']['opaque_payload_bytes'], len(opaque))

    def test_conflicting_name_tables_keep_both_interpretations_and_offsets(self):
        raw = native_v10()
        names = b'Else\0Layer\0'
        report = self.report(raw + b'LBTN' + struct.pack('>2I', 1, len(names)) + names)
        self.assertEqual(report['scan']['parsed_candidates'], 2)
        self.assertEqual(report['selection']['outcome'], 'ambiguous')
        self.assertEqual([r['name_table_offset'] for r in report['candidates']], [0, len(raw)])
        self.assertEqual(report['name_tables'][1]['sha256'], hashlib.sha256(names).hexdigest())
        self.assertEqual(report['relationships']['items'][0]['kind'], 'same_marker_interpretations')
        self.assertIn('joints[0].name', report['candidates'][1]['differences_from_baseline']['paths'])

    def test_marker_inside_name_table_is_observed_without_suppressing_candidate(self):
        child = native()
        report = self.report(b'LBTN' + struct.pack('>2I', 1, len(child)) + child)
        self.assertEqual(report['scan']['parsed_candidates'], 1)
        self.assertEqual(report['relationships']['items'][0]['kind'], 'marker_inside_name_table_data')
        self.assertEqual(report['candidates'][0]['hgol_offset'], 12)

    def test_report_limit_cannot_hide_a_conflicting_omitted_identity(self):
        translated = list(I4)
        translated[12] = 5
        report = self.report(native() * 5 + native(local=translated), max_candidates=1)
        self.assertEqual(len(report['candidates']), 1)
        self.assertEqual(report['omitted_candidates'], 5)
        self.assertEqual(report['selection']['candidates_considered'], 6)
        self.assertEqual(report['selection']['outcome'], 'ambiguous')
        self.assertEqual(report['ownership_groups']['groups_total'], 2)
        self.assertEqual(report['ownership_groups']['omitted_groups'], 1)

    def test_relationship_and_error_detail_limits_are_explicit(self):
        bad = (b'LOGH' + struct.pack('>I', 99)) * 4
        report = self.report(native() * 3 + bad, max_relationships=1, max_errors=2)
        self.assertEqual(len(report['relationships']['items']), 1)
        self.assertEqual(report['relationships']['omitted_observations'], 1)
        self.assertEqual(report['scan']['parse_errors'], 4)
        self.assertEqual(len(report['parse_errors']), 2)
        self.assertEqual(report['omitted_parse_errors'], 2)

    def test_difference_paths_are_bounded_without_weakening_identity(self):
        report = self.report(native() + native(pre=b'a', post=b'b', opaque=b'c', flags=1), max_differences=1)
        changes = report['candidates'][1]['differences_from_baseline']
        self.assertEqual(len(changes['paths']), 1)
        self.assertTrue(changes['truncated'])
        self.assertEqual(report['selection']['outcome'], 'ambiguous')

    def test_display_compatibility_reports_rejection_and_not_ownership_proof(self):
        report = self.report(native(special=9) + native(), display={'specials': [{}]})
        self.assertTrue(report['candidates'][0]['validation']['valid'])
        self.assertFalse(report['candidates'][0]['display_compatibility']['compatible'])
        references = report['candidates'][1]['display_compatibility']['references']
        self.assertEqual(references['special_indices'], [0])
        self.assertIn('structural evidence only', references['note'])
        self.assertEqual(report['selection']['outcome'], 'selected')

    def test_empty_layers_are_explicitly_no_ownership_evidence(self):
        report = self.report(native(layers=False), display={'specials': [{}]})
        references = report['candidates'][0]['display_compatibility']['references']
        self.assertEqual(references['entries'], 0)
        self.assertEqual(references['layers'], 0)
        self.assertIn('no ownership evidence', references['note'])

    def test_report_limits_have_strict_positive_caps(self):
        scan = self.scan(native())
        for key, value in (('max_candidates', 0), ('max_candidates', 257), ('max_errors', True),
                           ('max_relationships', 2049), ('max_differences', 129)):
            with self.subTest(option=key, value=value), self.assertRaises(ValueError):
                skeleton_candidate_report(scan, **{key: value})

    def test_expected_count_is_only_checked_after_unique_identity(self):
        report = self.report(native(), expected_nodes=2)
        self.assertEqual(report['selection']['outcome'], 'rejected')
        self.assertFalse(report['selection']['count_used_to_select'])
        self.assertIn('animation has 2', report['selection']['detail'])


class CandidateCliTests(Fixture):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-I', str(CLI), *map(str, args)], cwd=self.folder,
                              capture_output=True, text=True, timeout=30)

    def load_cli(self):
        spec = importlib.util.spec_from_file_location('candidate_cli_test', CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_help_imports_headlessly_from_an_unrelated_working_directory(self):
        result = self.run_cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--with-display', result.stdout)

    def test_cli_writes_ambiguous_report_when_optional_display_is_unavailable(self):
        raw = native() + native(opaque=b'Unknown')
        self.source.write_bytes(raw)
        target = self.folder / 'report.json'
        result = self.run_cli(self.source, '--output', target, '--with-display')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual(report['selection']['outcome'], 'ambiguous')
        self.assertEqual(report['display_check']['status'], 'unavailable')
        self.assertFalse(report['selection']['display_compatibility_checked'])
        self.assertTrue(report['source']['sha256_rechecked'])
        self.assertEqual(self.source.read_bytes(), raw)

    def test_cli_protects_source_and_existing_output(self):
        raw = native()
        self.source.write_bytes(raw)
        target = self.folder / 'existing.json'
        target.write_text('Preserved', encoding='utf-8')
        for output in (self.source, target):
            result = self.run_cli(self.source, '--output', output)
            self.assertEqual(result.returncode, 2)
            self.assertIn('protected', result.stderr)
        self.assertEqual(self.source.read_bytes(), raw)
        self.assertEqual(target.read_text(encoding='utf-8'), 'Preserved')

    def test_cli_protects_a_dangling_output_symlink(self):
        self.source.write_bytes(native())
        target = self.folder / 'report.json'
        try:
            target.symlink_to(self.folder / 'absent.json')
        except (OSError, NotImplementedError):
            self.skipTest('Symlink fixture is not permitted on this platform')
        result = self.run_cli(self.source, '--output', target)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(target.is_symlink())
        self.assertFalse((self.folder / 'absent.json').exists())

    def test_source_digest_change_prevents_report_write(self):
        self.source.write_bytes(native())
        target = self.folder / 'report.json'
        cli = self.load_cli()
        with patch.object(cli, '_source_digest', return_value='f' * 64), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main([str(self.source), '--output', str(target)])
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(target.exists())

    def test_exclusive_creation_protects_a_file_created_during_inspection(self):
        raw = native()
        self.source.write_bytes(raw)
        target = self.folder / 'report.json'
        cli = self.load_cli()

        def concurrent_writer(path):
            target.write_text('Concurrent output must survive', encoding='utf-8')
            return hashlib.sha256(raw).hexdigest()

        with patch.object(cli, '_source_digest', side_effect=concurrent_writer), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main([str(self.source), '--output', str(target)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(target.read_text(encoding='utf-8'), 'Concurrent output must survive')


if __name__ == '__main__':
    unittest.main()

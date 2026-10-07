"""Synthetic CC prefix, unknown-suffix and inspection-only CLI regressions.

These deliberately invented suffixes exercise refusal and bounded reporting;
they are not specimens or evidence for an Avengers/ROTV record grammar.
"""
from pathlib import Path
from contextlib import redirect_stderr
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3 import archive_cc as cc
import inspect_archive_cc as cli


def fixture(*, kind=-8, version=2, suffix=b''):
    """One synthetic file in an explicitly selected, already gated layout."""
    name = b'Scene.CU3\0'
    header = struct.pack('>I8si4I', 0, b'.CC40TAD', kind, version, 1, 1, len(name))
    record = (struct.pack('>IHhH', 0, 65535, 0, 1) if version == 1 else
              struct.pack('>IHHhH', 0, 65535, 0, 0, 1))
    if kind == -12:
        table = struct.pack('>iIQII', kind, 1, 8, 20, 20)
        value = 0xcbf29ce484222325
        for byte in b'SCENE.CU3':
            value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
        tail = struct.pack('>Q', value)
    else:
        table = struct.pack('>iI4I', kind, 1, 0, 20, 20, 8)
        tail = struct.pack('>I2I', cc.path_hash('Scene.CU3'), 0, 0)
    data = header + name + bytes(4) + record + table + tail + suffix
    return struct.pack('>I', len(data) - 4) + data[4:]


def write_dat(path, data, *, index_offset=512):
    # Filler represents unrelated asset bytes that the inspector must not read.
    path.write_bytes(struct.pack('<II', index_offset, len(data)) +
                     b'x' * (index_offset - 8) + data + b'unrelated archive trailer')
    return index_offset


class TrackedFile:
    def __init__(self, stream, *, short_read=False):
        self.stream = stream
        self.reads = []
        self.seeks = []
        self.short_read = short_read

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def fileno(self):
        return self.stream.fileno()

    def read(self, size):
        self.reads.append(size)
        data = self.stream.read(size)
        return data[:-1] if self.short_read and size != 8 else data

    def seek(self, offset):
        self.seeks.append(offset)
        return self.stream.seek(offset)


class CCIndexDiagnostics(unittest.TestCase):
    def assert_inspection_only(self, report):
        self.assertFalse(report['extraction_allowed'])
        text = json.dumps(report)
        for forbidden in ('"entries"', '"files"', '"packed_size"', '"flags"', 'Scene.CU3'):
            self.assertNotIn(forbidden, text)
        self.assertLess(len(text), 16000)

    def test_all_existing_layouts_retain_exact_table_spans(self):
        for kind, version, width in ((-8, 1, 10), (-8, 2, 12), (-12, 2, 12)):
            with self.subTest(kind=kind, version=version):
                data = fixture(kind=kind, version=version)
                rows = cc.parse_index(data, archive_limit=512)
                self.assertEqual(rows, [dict(path='Scene.CU3', offset=8, packed_size=20, size=20, flags=0)])
                report = cc.diagnose_index(data, archive_limit=512)
                self.assertEqual(report['status'], 'complete')
                self.assertTrue(report['prefix_validated'])
                self.assertTrue(report['complete_index_validated'])
                self.assertEqual(report['tables_end'], len(data))
                self.assertEqual(report['layout']['name_record_bytes'], width)
                spans = {span['name']: span for span in report['table_spans']}
                self.assertEqual(spans['name_records'], dict(name='name_records', offset=46,
                                                            end=46 + width, bytes=width))
                self.assertEqual(spans['file_records']['bytes'], 16)
                self.assertEqual(report['index_sha256'], hashlib.sha256(data).hexdigest())
                self.assert_inspection_only(report)

    def test_unknown_suffix_stays_refused_for_every_known_layout(self):
        for kind, version in ((-8, 1), (-8, 2), (-12, 2)):
            for suffix in (bytes(128), b'ROTV' + struct.pack('>I', 0xffffffff), b'unknown'):
                with self.subTest(kind=kind, version=version, suffix=suffix[:8]):
                    data = fixture(kind=kind, version=version, suffix=suffix)
                    with self.assertRaisesRegex(cc.CCIndexError, 'Extraction remains blocked') as caught:
                        cc.parse_index(data)
                    report = caught.exception.diagnostics
                    self.assertEqual(report, cc.diagnose_index(data))
                    self.assertEqual(report['status'], 'unsupported_suffix')
                    self.assertTrue(report['prefix_validated'])
                    self.assertFalse(report['complete_index_validated'])
                    self.assertEqual(report['suffix']['bytes'], len(suffix))
                    self.assertEqual(report['suffix']['offset'], len(data) - len(suffix))
                    self.assertEqual(report['suffix']['sha256'], hashlib.sha256(suffix).hexdigest())
                    self.assertLessEqual(len(report['suffix']['first_bytes_hex']), 128)
                    self.assert_inspection_only(report)

    def test_suffix_refusal_does_not_mask_corrupt_path_mapping(self):
        data = bytearray(fixture(suffix=b'ROTV' + bytes(16)))
        struct.pack_into('>I', data, len(fixture()) - 12, 123)
        with self.assertRaisesRegex(cc.CCIndexError, 'no verified file reference') as caught:
            cc.parse_index(data)
        report = caught.exception.diagnostics
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertEqual(report['phase'], 'path_mapping')
        self.assertFalse(report['prefix_validated'])
        self.assertFalse(report['complete_index_validated'])
        self.assertNotIn('suffix', report)
        self.assertNotIn('tables_end', report)

    def test_suffix_cannot_mask_invalid_file_extents(self):
        report = cc.diagnose_index(fixture(suffix=b'ROTV'), archive_limit=20)
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertEqual(report['phase'], 'file_records')
        self.assertIn('archive data region', report['error'])
        self.assertNotIn('suffix', report)

    def test_unclassified_tags_are_bounded_and_never_followed(self):
        suffix = b'odd' + (b'ROTV' + struct.pack('>4I', 0xffffffff, 0x12345678, 0, 1)) * 100
        report = cc.diagnose_index(fixture(suffix=suffix))
        tail = report['suffix']
        candidates = tail['tag_candidates']
        self.assertEqual(len(candidates), cc.MAX_DIAGNOSTIC_TAGS)
        self.assertTrue(tail['tag_candidates_truncated'])
        self.assertEqual(candidates[0]['suffix_offset'], 3)
        self.assertEqual(candidates[0]['following_u32_be'], [0xffffffff, 0x12345678, 0, 1])
        self.assertEqual(candidates[0]['following_u32_le'], [0xffffffff, 0x78563412, 0, 0x01000000])
        self.assertEqual(tail['first_bytes_hex'], suffix[:64].hex())
        self.assertIn('not a decoded record', candidates[0]['interpretation'])
        self.assertFalse(report['complete_index_validated'])
        self.assert_inspection_only(report)

    def test_marker_truncated_following_words_are_not_read(self):
        report = cc.diagnose_index(fixture(suffix=b'ROTVx'))
        candidate = report['suffix']['tag_candidates'][0]
        self.assertEqual(candidate['following_u32_be'], [])
        self.assertEqual(candidate['following_u32_le'], [])
        self.assertFalse(report['suffix']['tag_candidates_truncated'])

    def test_wrong_layout_and_declared_size_remain_rejected(self):
        data = fixture()
        report = cc.diagnose_index(data, expected_layout=(-12, 2))
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertIn('expected', report['error'])
        for damaged in (data[:-1], data + b'ROTV'):
            report = cc.diagnose_index(damaged)
            self.assertEqual(report['status'], 'invalid_prefix')
            self.assertEqual(report['phase'], 'header')
            self.assertNotIn('suffix', report)

    def test_invalid_override_framing_is_not_reported_as_a_suffix(self):
        data = bytearray(fixture(suffix=b'ROTV'))
        struct.pack_into('>2I', data, len(fixture()) - 8, 1, 0xffffffff)
        report = cc.diagnose_index(data)
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertEqual(report['phase'], 'named_overrides')
        self.assertIn('exceeds bounds', report['error'])
        self.assertNotIn('suffix', report)

    def test_oversized_input_is_not_hashed_or_sampled(self):
        data = fixture(suffix=b'ROTV')
        with patch.object(cc, 'MAX_INDEX_BYTES', len(data) - 1), patch.object(cc.hashlib, 'sha256') as digest:
            report = cc.diagnose_index(data)
        digest.assert_not_called()
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertIsNone(report['index_sha256'])
        self.assertIn('limit', report['index_hash_omitted_reason'])
        self.assertNotIn('suffix', report)


class CCFileInspection(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'GAME.DAT'

    def test_dat_reads_only_declared_index_and_reports_source_offsets(self):
        data = fixture(suffix=b'ROTV' + bytes(4))
        offset = write_dat(self.source, data)
        tracked = TrackedFile(self.source.open('rb'))
        with patch.object(Path, 'open', return_value=tracked):
            report = cc.diagnose_archive(self.source)
        self.assertEqual(tracked.reads, [8, len(data)])
        self.assertEqual(tracked.seeks, [offset])
        self.assertEqual(report['source']['index_offset'], offset)
        self.assertEqual(report['suffix']['source_offset'], offset + len(fixture()))
        self.assertEqual(report['suffix']['tag_candidates'][0]['source_offset'], offset + len(fixture()))
        self.assertNotIn('path', report['source'])
        with self.assertRaises(cc.CCIndexError) as caught:
            cc.index(self.source)
        self.assertEqual(caught.exception.diagnostics['source'], report['source'])

    def test_hdr_uses_same_handle_metadata_without_directory_stat(self):
        source = self.root / 'detached.hdr'
        source.write_bytes(fixture(suffix=b'ROTV'))
        with patch.object(Path, 'stat', side_effect=AssertionError('directory metadata is not authoritative')):
            report = cc.diagnose_archive(source)
        self.assertEqual(report['source']['index_offset'], 0)
        self.assertIn('unavailable', report['source']['archive_extent_check'])
        self.assertEqual(report['suffix']['source_offset'], len(fixture()))

    def test_dat_uses_same_handle_metadata_without_directory_stat(self):
        write_dat(self.source, fixture())
        with patch.object(Path, 'stat', side_effect=AssertionError('directory metadata is not authoritative')):
            self.assertEqual(cc.index(self.source)[0]['offset'], 8)

    def test_changed_open_handle_metadata_refuses_results(self):
        write_dat(self.source, fixture())
        with self.source.open('rb') as stream:
            before = os.fstat(stream.fileno())
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        for field in fields:
            with self.subTest(changed_field=field):
                after = types.SimpleNamespace(**{name: getattr(before, name) for name in fields})
                setattr(after, field, getattr(after, field) + 1)
                with patch.object(cc.os, 'fstat', side_effect=[before, after]), self.assertRaisesRegex(ValueError, 'changed'):
                    cc.diagnose_archive(self.source)

    def test_short_index_read_is_rejected_even_if_stamps_match(self):
        data = fixture()
        write_dat(self.source, data)
        tracked = TrackedFile(self.source.open('rb'), short_read=True)
        with patch.object(Path, 'open', return_value=tracked), self.assertRaisesRegex(ValueError, 'completely'):
            cc.index(self.source)

    def test_actual_source_growth_during_read_refuses_results(self):
        data = fixture()
        write_dat(self.source, data)
        source = self.source
        class GrowingFile(TrackedFile):
            def read(self, size):
                result = super().read(size)
                if size != 8:
                    with open(source, 'ab') as writer:
                        writer.write(b'changed')
                return result
        tracked = GrowingFile(self.source.open('rb'))
        with patch.object(Path, 'open', return_value=tracked), self.assertRaisesRegex(ValueError, 'changed'):
            cc.diagnose_archive(self.source)

    def test_oversized_declared_index_is_rejected_before_index_read(self):
        write_dat(self.source, fixture())
        tracked = TrackedFile(self.source.open('rb'))
        with patch.object(Path, 'open', return_value=tracked), patch.object(cc, 'MAX_INDEX_BYTES', 32):
            with self.assertRaisesRegex(ValueError, 'outside archive'):
                cc.diagnose_archive(self.source)
        self.assertEqual(tracked.reads, [8])
        self.assertEqual(tracked.seeks, [])

    def test_hdr_over_limit_is_rejected_without_reading_bytes(self):
        source = self.root / 'detached.hdr'
        source.write_bytes(fixture())
        tracked = TrackedFile(source.open('rb'))
        with patch.object(Path, 'open', return_value=tracked), patch.object(cc, 'MAX_INDEX_BYTES', 32):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                cc.diagnose_archive(source)
        self.assertEqual(tracked.reads, [])


class CCInspectionCLI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'GAME.DAT'
        self.output = self.root / 'report.json'

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_archive_cc.py')),
                               *map(str, args)], capture_output=True, text=True)

    def test_help_works_without_blender(self):
        result = self.run_cli('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('without extracting', result.stdout)
        self.assertIn('new, user-selected report filename', result.stdout)

    def test_unknown_suffix_writes_bounded_report_and_returns_nonzero(self):
        original = fixture(suffix=b'ROTV' + bytes(1024))
        write_dat(self.source, original)
        before = self.source.read_bytes()
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('Extraction remains blocked', result.stdout)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'unsupported_suffix')
        self.assertFalse(report['extraction_allowed'])
        self.assertNotIn('entries', report)
        self.assertLess(self.output.stat().st_size, 8000)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['GAME.DAT', 'report.json'])

    def test_invalid_prefix_is_saved_as_failure_not_suffix_evidence(self):
        data = bytearray(fixture(suffix=b'ROTV'))
        struct.pack_into('>I', data, len(fixture()) - 12, 123)
        write_dat(self.source, data)
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertEqual(report['phase'], 'path_mapping')
        self.assertNotIn('suffix', report)

    def test_existing_report_is_preserved_before_source_read(self):
        self.output.write_bytes(b'keep this report')
        result = self.run_cli(self.source, self.output)  # Source intentionally absent.
        self.assertEqual(result.returncode, 2)
        self.assertIn('new diagnostic report filename', result.stderr)
        self.assertEqual(self.output.read_bytes(), b'keep this report')

    def test_dangling_report_link_is_preserved(self):
        try:
            self.output.symlink_to(self.root / 'missing')
        except OSError:
            self.skipTest('Symbolic links unavailable')
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse((self.root / 'missing').exists())

    def test_competing_report_created_after_preflight_is_preserved(self):
        report = cc.diagnose_index(fixture())
        def competing_inspection(_):
            self.output.write_bytes(b'competing report')
            return report
        with patch.object(cli, 'diagnose_archive', side_effect=competing_inspection), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main([str(self.source), str(self.output)])
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.output.read_bytes(), b'competing report')

    def test_complete_tables_report_does_not_claim_payload_support(self):
        write_dat(self.source, fixture())
        result = self.run_cli(self.source, self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('does not test payload codecs or game support', result.stdout)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'complete')
        self.assertFalse(report['extraction_allowed'])
        self.assertNotIn('entries', report)


if __name__ == '__main__':
    unittest.main()

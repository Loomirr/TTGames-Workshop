"""Synthetic publication/failure/race checks; no Blender or game assets required."""
import concurrent.futures
import errno
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import ModuleType
import unittest
from unittest import mock

package = ModuleType('bundle_fixture')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from bundle_fixture import bundle_output as output
from bundle_fixture.cu3 import FormatError


class BundleOutputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / 'export'
        self.payloads = [('CHARS/Hero.GHG', b'original-model'), ('CHARS/Hero.TEX', b'textures')]
        self.report = dict(schema='tt.loose-source-export.v1', game='synthetic')

    def publish(self, **kwargs):
        return output.publish_bundle(self.destination, self.payloads, self.report, **kwargs)

    def assert_no_output(self):
        self.assertFalse(os.path.lexists(self.destination))
        self.assertEqual(list(self.root.glob('.export.tt-stage-*')), [])

    def assert_complete(self, report, expected=None):
        expected = self.payloads if expected is None else expected
        self.assertEqual(json.loads((self.destination / output.MANIFEST_NAME).read_text()), report)
        self.assertEqual({entry['path'] for entry in report['files']}, {p for p, _ in expected})
        for path, payload in expected:
            self.assertEqual((self.destination / path).read_bytes(), payload)
            entry = next(entry for entry in report['files'] if entry['path'] == path)
            self.assertEqual(entry['bytes'], len(payload))
            self.assertEqual(entry['sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(list(self.root.glob('.export.tt-stage-*')), [])

    def test_complete_verified_bundle_and_immutable_input_report(self):
        report = self.publish()
        self.assert_complete(report)
        self.assertEqual(self.report, dict(schema='tt.loose-source-export.v1', game='synthetic'))
        self.assertFalse(report['publication']['replaces_existing'])
        self.assertEqual(report['publication']['scope'], 'same-filesystem directory rename')

    def test_existing_file_empty_and_nonempty_directories_are_never_touched(self):
        for kind in ('file', 'empty', 'nonempty'):
            with self.subTest(kind=kind):
                if kind == 'file':
                    self.destination.write_bytes(b'existing')
                else:
                    self.destination.mkdir()
                    if kind == 'nonempty':
                        (self.destination / 'keep.txt').write_bytes(b'existing')
                with mock.patch.object(output, '_write_exclusive') as write:
                    with self.assertRaisesRegex(FormatError, 'already exists'):
                        self.publish()
                    write.assert_not_called()
                if kind == 'file':
                    self.assertEqual(self.destination.read_bytes(), b'existing')
                    self.destination.unlink()
                else:
                    if kind == 'nonempty':
                        self.assertEqual((self.destination / 'keep.txt').read_bytes(), b'existing')
                        (self.destination / 'keep.txt').unlink()
                    self.destination.rmdir()
                self.assert_no_output()

    def test_existing_symlink_and_dangling_symlink_are_rejected(self):
        target = self.root / 'target'
        target.mkdir()
        for link_target in (target, self.root / 'missing'):
            with self.subTest(target=link_target):
                try:
                    self.destination.symlink_to(link_target, target_is_directory=True)
                except OSError as error:
                    self.skipTest('Symlink creation unavailable: ' + str(error))
                with self.assertRaisesRegex(FormatError, 'already exists'):
                    self.publish()
                self.assertTrue(self.destination.is_symlink())
                self.destination.unlink()
        self.assertEqual(list(target.iterdir()), [])
        self.assert_no_output()

    def test_path_aliases_and_file_directory_collisions_are_preflight_errors(self):
        cases = [
            ['A.GHG', 'A.GHG'], ['A.GHG', 'a.ghg'],
            ['Folder/A.GHG', 'folder/B.GHG'], ['folder', 'folder/a.ghg'],
            ['folder/a.ghg', 'FOLDER'], ['caf\u00e9.GHG', 'cafe\u0301.GHG'],
            ['tt_source_export.JSON'], ['TT_Source_Export.json/child'],
            ['ok', '../escape'], ['/absolute'], ['C:/absolute'], ['C:relative'],
            ['//server/share'], ['a//b'], ['a/./b'], ['a/../b'], ['a/'],
            ['CON.txt'], ['file:stream'], ['NUL'], ['bad.'], ['bad '], ['bad\x00name'],
        ]
        for paths in cases:
            with self.subTest(paths=paths), mock.patch.object(output, '_native_publisher') as publish:
                with self.assertRaises(FormatError):
                    output.publish_bundle(self.destination, [(p, b'x') for p in paths], self.report)
                publish.assert_not_called()
                self.assert_no_output()

    def test_dat_restriction_is_explicit_and_backslash_paths_keep_spelling(self):
        with self.assertRaisesRegex(FormatError, 'Forbidden'):
            output.publish_bundle(self.destination, [('GAME.DAT', b'x')], self.report,
                                  forbidden_suffixes=('.dat',))
        self.assert_no_output()
        report = output.publish_bundle(self.destination, [('Folder\\Hero.GHG', b'x')], self.report)
        self.assert_complete(report, [('Folder/Hero.GHG', b'x')])

    def test_second_payload_and_manifest_write_failures_cleanup_and_retry(self):
        real_write = output._write_exclusive
        unrelated = self.root / '.export.tt-stage-somebody-else'
        unrelated.mkdir()
        (unrelated / 'keep').write_bytes(b'owned-by-another-operation')
        for failed_name in ('Hero.TEX', output.MANIFEST_NAME):
            with self.subTest(failed=failed_name):
                calls = []
                def fail(path, data):
                    calls.append(path.name)
                    if path.name == failed_name:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data[:2])
                        raise OSError(errno.ENOSPC, 'injected full disk')
                    real_write(path, data)
                with mock.patch.object(output, '_write_exclusive', side_effect=fail):
                    with self.assertRaisesRegex(OSError, 'injected full disk'):
                        self.publish()
                self.assertIn('Hero.GHG', calls)
                self.assertFalse(self.destination.exists())
                self.assertEqual(list(self.root.glob('.export.tt-stage-*')), [unrelated])
                self.assertEqual((unrelated / 'keep').read_bytes(), b'owned-by-another-operation')
        unrelated.rename(self.root / 'unrelated')
        self.assert_complete(self.publish())

    def test_flush_failure_and_interruption_leave_no_destination(self):
        with mock.patch.object(output.os, 'fsync', side_effect=OSError('flush failure')):
            with self.assertRaisesRegex(OSError, 'flush failure'):
                self.publish()
        self.assert_no_output()
        with mock.patch.object(output, '_write_exclusive', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.publish()
        self.assert_no_output()

    def test_short_stream_write_is_not_reported_as_a_completed_file(self):
        real_open = Path.open
        class ShortWriter:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def write(self, data):
                return self.stream.write(data[:-1])
        def short_open(path, *args, **kwargs):
            stream = real_open(path, *args, **kwargs)
            return ShortWriter(stream) if args and args[0] == 'xb' else stream
        with mock.patch.object(Path, 'open', short_open):
            with self.assertRaisesRegex(OSError, 'Short native bundle write'):
                self.publish()
        self.assert_no_output()
        self.assert_complete(self.publish())

    def test_payload_manifest_and_inventory_corruption_prevent_publication(self):
        real_verify = output._verify_stage
        for corruption in ('payload', 'manifest', 'missing', 'extra-file', 'extra-directory', 'symlink'):
            with self.subTest(corruption=corruption):
                def corrupt(stage, *args):
                    payload = stage / self.payloads[0][0]
                    if corruption == 'payload':
                        payload.write_bytes(b'tampered-model')
                    elif corruption == 'manifest':
                        (stage / output.MANIFEST_NAME).write_bytes(b'{}')
                    elif corruption == 'missing':
                        payload.unlink()
                    elif corruption == 'extra-file':
                        (stage / 'unexpected').write_bytes(b'x')
                    elif corruption == 'extra-directory':
                        (stage / 'unexpected').mkdir()
                    else:
                        payload.unlink()
                        try:
                            payload.symlink_to(self.root / 'outside')
                        except OSError as error:
                            self.skipTest('Symlink creation unavailable: ' + str(error))
                    return real_verify(stage, *args)
                with mock.patch.object(output, '_verify_stage', side_effect=corrupt):
                    with self.assertRaises(FormatError):
                        self.publish()
                self.assert_no_output()

    def test_concurrent_empty_folder_file_and_symlink_creation_are_not_replaced(self):
        real_publish, method = output._native_publisher()
        for kind in ('empty-directory', 'nonempty-directory', 'file', 'symlink'):
            with self.subTest(kind=kind):
                def race(stage, destination):
                    if kind == 'file':
                        destination.write_bytes(b'other-exporter')
                    elif kind == 'symlink':
                        try:
                            destination.symlink_to(self.root / 'missing', target_is_directory=True)
                        except OSError as error:
                            self.skipTest('Symlink creation unavailable: ' + str(error))
                    else:
                        destination.mkdir()
                        if kind == 'nonempty-directory':
                            (destination / 'keep').write_bytes(b'other-exporter')
                    real_publish(stage, destination)
                with mock.patch.object(output, '_native_publisher', return_value=(race, method)):
                    with self.assertRaisesRegex(FormatError, 'created during publication'):
                        self.publish()
                self.assertFalse((self.destination / output.MANIFEST_NAME).exists())
                self.assertEqual(list(self.root.glob('.export.tt-stage-*')), [])
                if kind == 'file':
                    self.assertEqual(self.destination.read_bytes(), b'other-exporter')
                    self.destination.unlink()
                elif kind == 'symlink':
                    self.assertTrue(self.destination.is_symlink())
                    self.destination.unlink()
                else:
                    if kind == 'nonempty-directory':
                        self.assertEqual((self.destination / 'keep').read_bytes(), b'other-exporter')
                        (self.destination / 'keep').unlink()
                    self.destination.rmdir()
        self.assert_complete(self.publish())

    def test_two_simultaneous_exporters_publish_one_complete_winner(self):
        real_publish, method = output._native_publisher()
        barrier = threading.Barrier(2)
        def synchronized(stage, destination):
            barrier.wait(timeout=10)
            real_publish(stage, destination)
        def worker(label):
            payloads = [('A.GHG', label), ('B.TEX', label * 2)]
            try:
                report = output.publish_bundle(self.destination, payloads, self.report)
                return label, report
            except FormatError as error:
                return label, error
        with mock.patch.object(output, '_native_publisher', return_value=(synchronized, method)):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, (b'one', b'two')))
        winners = [(label, result) for label, result in results if isinstance(result, dict)]
        failures = [result for _, result in results if isinstance(result, FormatError)]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(failures), 1, results)
        label, report = winners[0]
        self.assert_complete(report, [('A.GHG', label), ('B.TEX', label * 2)])

    def test_failed_publication_and_unsupported_operation_cleanup_and_retry(self):
        with mock.patch.object(output, '_native_publisher', side_effect=FormatError('unsupported')):
            with self.assertRaisesRegex(FormatError, 'unsupported'):
                self.publish()
        self.assert_no_output()
        for error in (OSError(errno.EXDEV, 'cross-device'), OSError(errno.EIO, 'failed rename')):
            with self.subTest(error=error):
                publisher = mock.Mock(side_effect=error)
                with mock.patch.object(output, '_native_publisher', return_value=(publisher, 'injected')):
                    with self.assertRaises(OSError):
                        self.publish()
                self.assert_no_output()
        self.assert_complete(self.publish())

    def test_cleanup_refuses_a_replacement_staging_directory(self):
        real_verify = output._verify_stage
        replacement = []
        def replace(stage, *args):
            real_verify(stage, *args)
            stage.rename(self.root / 'moved-original-stage')
            stage.mkdir()
            (stage / 'belongs-to-other-operation').write_bytes(b'keep')
            replacement.append(stage)
        with mock.patch.object(output, '_verify_stage', side_effect=replace):
            with self.assertWarnsRegex(UserWarning, 'ownership changed'):
                with self.assertRaisesRegex(FormatError, 'ownership changed'):
                    self.publish()
        self.assertFalse(self.destination.exists())
        self.assertEqual((replacement[0] / 'belongs-to-other-operation').read_bytes(), b'keep')
        self.assertTrue((self.root / 'moved-original-stage' / output.MANIFEST_NAME).exists())

    def test_streamed_names_preflight_before_consumption_or_output(self):
        consumed = []
        def payloads():
            consumed.append(True)
            yield 'A.GHG', b'x'
        for paths in (['A.GHG', 'a.ghg'], ['A.GHG', '../escape'], ['TT_Source_Export.json']):
            with self.subTest(paths=paths):
                with self.assertRaises(FormatError):
                    output.publish_bundle(self.destination, payloads(), self.report, expected_paths=paths)
                self.assertEqual(consumed, [])
                self.assert_no_output()

    def test_streamed_payloads_are_written_as_consumed_and_metadata_is_retained(self):
        def payloads():
            yield 'A.GHG', b'a'
            stages = list(self.root.glob('.export.tt-stage-*'))
            self.assertEqual(len(stages), 1)
            self.assertEqual((stages[0] / 'A.GHG').read_bytes(), b'a')
            self.assertFalse(self.destination.exists())
            self.report['decoded_entries'] = ['A.GHG', 'B.TEX']
            yield 'B.TEX', b'b'
        report = output.publish_bundle(self.destination, payloads(), self.report,
                                       expected_paths=['A.GHG', 'B.TEX'])
        self.assertEqual(report['decoded_entries'], ['A.GHG', 'B.TEX'])
        self.assert_complete(report, [('A.GHG', b'a'), ('B.TEX', b'b')])

    def test_streamed_missing_duplicate_unexpected_and_decoder_failure_cleanup(self):
        for payloads in ([('A', b'a')], [('A', b'a'), ('A', b'a')],
                         [('A', b'a'), ('../escape', b'b')], [('A', b'a'), ('C', b'c')]):
            with self.subTest(payloads=payloads):
                with self.assertRaises(FormatError):
                    output.publish_bundle(self.destination, iter(payloads), self.report,
                                          expected_paths=['A', 'B'])
                self.assert_no_output()
        def broken():
            yield 'A', b'a'
            raise ValueError('injected decoder failure')
        with self.assertRaisesRegex(ValueError, 'decoder failure'):
            output.publish_bundle(self.destination, broken(), self.report, expected_paths=['A', 'B'])
        self.assert_no_output()

    def test_manifest_schema_and_serialization_errors_are_preflight_errors(self):
        for report in ({}, {'schema': ''}, {'schema': 'synthetic', 'value': float('nan')},
                       {'schema': 'synthetic', 'value': object()}):
            with self.subTest(report=report):
                with self.assertRaises((FormatError, ValueError, TypeError)):
                    output.publish_bundle(self.destination, self.payloads, report)
                self.assert_no_output()


if __name__ == '__main__':
    unittest.main()

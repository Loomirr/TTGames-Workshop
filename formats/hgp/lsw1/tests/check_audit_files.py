"""Ensure an era audit exposes rejected, unknown and non-default-layer inputs."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from check_header_layouts import fixture
from check_animation_records import fixture as animation_fixture

spec = importlib.util.spec_from_file_location('audit_files', Path(__file__).resolve().parents[1] / 'tools/audit_files.py')
audit_files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_files)


class AuditTests(unittest.TestCase):
    def test_animation_record_pass_is_not_playback(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'clip.ani').write_bytes(animation_fixture())
            (Path(folder) / 'face.bsa').write_bytes(animation_fixture('BSA'))
            result = audit_files.audit(folder)
            self.assertEqual(result['counts'], {'record_pass': 2})
            self.assertFalse(result['complete'])
            self.assertIn('no rig ownership', result['files'][0]['animation']['scope'])

    def test_reader_pass_does_not_hide_other_file_types_or_claim_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'good.HGP').write_bytes(fixture(0x30))
            (root / 'bad.hgp').write_bytes(b'NU20')
            (root / 'clip.an3').write_bytes(b'4INA')
            result = audit_files.audit(root)
            self.assertFalse(result['complete'])
            self.assertEqual(result['counts'], {'reader_rejected': 1, 'not_examined': 1, 'reader_pass': 1})

    def test_bad_hidden_layer_is_not_skipped(self):
        data = fixture(0x30)
        data[0x30 + 0x80 + 0x7e] = 2
        # Layer 0 is empty/valid; layer 1 has an invalid rigid table.
        struct.pack_into('<II', data, 0x30 + 0x1e0 + 20, 0x50, 0xffffff00)
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'hidden.hgp').write_bytes(data)
            result = audit_files.audit(folder)
            self.assertEqual(result['counts'], {'reader_rejected': 1})
            self.assertIn('rigid object table', result['files'][0]['error'])

    def test_unhandled_layer_field_is_reported(self):
        data = fixture(0x30)
        struct.pack_into('<I', data, 0x30 + 0x1e0 + 12, 123)
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'unhandled.hgp').write_bytes(data)
            result = audit_files.audit(folder)
            self.assertEqual(result['files'][0]['unhandled_layer_fields'], 1)
            self.assertFalse(result['complete'])

    def test_size_limit_and_empty_input_are_not_success(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(audit_files.audit(folder)['complete'])
            (Path(folder) / 'large.hgp').write_bytes(fixture(0x30))
            self.assertEqual(audit_files.audit(folder, max_hgp_bytes=2)['counts'], {'size_limit': 1})


if __name__ == '__main__':
    unittest.main()

"""CLI regression checks for refused input and empty decode sets."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent


class CliTests(unittest.TestCase):
    def test_empty_bvh_manifest_is_a_valid_report_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);decoded=root/'decoded';decoded.mkdir()
            (decoded/'skeleton.json').write_text('{}')
            (decoded/'decode-manifest.json').write_text(json.dumps([{'status':'unsupported'}]))
            command=[sys.executable,str(HERE/'export_bvh.py'),str(decoded),str(root/'bvh')]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((root/'bvh/export-manifest.json').read_text())
            self.assertEqual(report['clips'],[])
            self.assertEqual(report['status'],'no_decoded_clips')
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertNotIn('Traceback',result.stderr)
            self.assertEqual(json.loads((root/'bvh/export-manifest.json').read_text()),report)

    def test_bad_skeleton_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'bad.GHG').write_bytes(b'wrong layout')
            result=subprocess.run([sys.executable,str(HERE/'decode_an4.py'),str(root),str(root/'bad.GHG'),str(root/'out'),'--actor','Actor'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Skeleton refused',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()

"""Direct face decoder: no extractor log dependency, no proprietary fixtures."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from test_mesh_edit import face_fixture
import decode_face_targets


class FaceDecoderCLI(unittest.TestCase):
    def test_direct_ghg_without_log_for_each_verified_mesh_version(self):
        for version in (169,170,175):
            with patch.object(sys,'argv',['decode','fixture.GHG','--output','new.json']),patch.object(Path,'read_bytes',return_value=face_fixture(version)),patch.object(Path,'exists',return_value=False),patch.object(Path,'write_text') as write,contextlib.redirect_stdout(io.StringIO()):
                decode_face_targets.main()
                result=json.loads(write.call_args.args[0])
                self.assertEqual(result['mesh_version'],version)
                self.assertEqual(result['parts']['0']['vertex_count'],3)
                self.assertEqual(result['parts']['0']['targets'][0]['id'],17)

    def test_existing_output_is_protected(self):
        with patch.object(sys,'argv',['decode','fixture.GHG','--output','existing.json']),patch.object(Path,'exists',return_value=True),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):decode_face_targets.main()

if __name__=='__main__':unittest.main()

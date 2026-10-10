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

    def test_summary_is_distinct_from_an_editable_companion(self):
        with patch.object(sys,'argv',['decode','fixture.GHG','--summary','--output','new.json']),patch.object(Path,'read_bytes',return_value=face_fixture(175)),patch.object(Path,'exists',return_value=False),patch.object(Path,'write_text') as write,contextlib.redirect_stdout(io.StringIO()):
            decode_face_targets.main()
            result=json.loads(write.call_args.args[0])
            self.assertEqual(result['schema'],'tt.face-target-summary.v1')
            self.assertEqual(result['parts'][0]['targets'][0]['id'],17)
            self.assertNotIn('offsets',result['parts'][0]['targets'][0])
            from io_scene_lego_cu3.face_edit import patch_targets
            with self.assertRaisesRegex(ValueError,'schema'):
                patch_targets(face_fixture(175),result)

if __name__=='__main__':unittest.main()

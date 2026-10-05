"""Asset-free native writer checks, including immutable fields and RLE limits."""
from pathlib import Path
import copy
import struct
import sys
import types
import unittest
R = Path(__file__).resolve().parent.parent
p = types.ModuleType('io_scene_lego_cu3')
p.__path__ = [str(R / 'Addon/io_scene_lego_cu3')]
sys.modules[p.__name__] = p
from io_scene_lego_cu3.morph import read_targets
from io_scene_lego_cu3.face_edit import patch_targets, digest
from io_scene_lego_cu3.cu3 import FormatError
from test_mesh_edit import face_fixture,fixture as mesh_fixture
from io_scene_lego_cu3.native_mesh import read_mesh_bytes


def fixture(dx, dense):
    version = 0xaf if dx else 0xa9
    raw = b'GHG!HSEM' + struct.pack('>I', version)
    raw += struct.pack('>3I', 1, 17, 0)
    if dx:
        raw += b'ROTV'
    if dense:
        raw += struct.pack('>I9f', 3, 0, 0, 0, 0, 0, 0, .125, -.25, .5) + b'X' * 21
    else:
        runs = struct.pack('>I3fI3fI3f', 2, 0, 0, 0, 1, .125, -.25, .5, 0, 0, 0, 0)
        raw += struct.pack('>I', 0) + b'P' * (4 if dx else 13)
        raw += struct.pack('>I', len(runs)) + runs
        raw += b'ROTV' + struct.pack('>3I', 2, 1234, 5678) + b'ROTV' if dx else struct.pack('>3I', 2, 1234, 5678)
    raw += b'UNRELATED MATERIALS AND FILE TAIL'
    companion = dict(schema='tt.relative-position-targets.v1', mesh_version=version,
                     sha256=digest(raw), parts={'2': read_targets(raw, 20, 1, 3, dx)})
    return raw, companion


class FaceEditTests(unittest.TestCase):
    def test_full_mesh_170_dense_and_run_encoded_targets(self):
        for dense in (False,True):
            raw=face_fixture(170)
            if not dense:
                raw=mesh_fixture(170)[:-76]+struct.pack('>3I',1,17,0)
                runs=struct.pack('>I3fI3f',2,0,0,0,1,.125,-.25,.5)
                raw+=struct.pack('>I',0)+bytes(13)+struct.pack('>I',len(runs))+runs
                raw+=struct.pack('>3I',2,1234,5678)+bytes(4)+bytes(36)+bytes(32)
            before=read_mesh_bytes(raw)
            companion=dict(schema='tt.relative-position-targets.v1',mesh_version=170,sha256=digest(raw),parts={'0':before['parts'][0]['morphs']})
            unchanged,_=patch_targets(raw,companion);self.assertEqual(unchanged,raw)
            companion['parts']['0']['targets'][0]['offsets'][2]=[.25,-.5,1]
            changed,report=patch_targets(raw,companion);after=read_mesh_bytes(changed)
            self.assertEqual(after['parts'][0]['morphs']['targets'][0]['offsets'][2],[.25,-.5,1])
            self.assertEqual(before['parts'][0]['vertices'],after['parts'][0]['vertices'])
            self.assertEqual(before['parts'][0]['triangles'],after['parts'][0]['triangles'])
            self.assertEqual(len(raw),len(changed));self.assertGreater(report['changed_bytes'],0)

    def test_mesh_170_rejects_fake_part_membership(self):
        raw=face_fixture(170);part=read_mesh_bytes(raw)['parts'][0]['morphs']
        companion=dict(schema='tt.relative-position-targets.v1',mesh_version=170,sha256=digest(raw),parts={'99':part})
        with self.assertRaisesRegex(FormatError,'decoded native target part'):patch_targets(raw,companion)
    def test_noop_exact_all_encodings(self):
        for dx in (False, True):
            for dense in (False, True):
                with self.subTest(dx=dx, dense=dense):
                    raw, companion = fixture(dx, dense)
                    result, report = patch_targets(raw, companion)
                    self.assertEqual(raw, result)
                    self.assertEqual(report['changed_bytes'], 0)

    def test_edit_reparse_all_encodings(self):
        for dx in (False, True):
            for dense in (False, True):
                with self.subTest(dx=dx, dense=dense):
                    raw, companion = fixture(dx, dense)
                    companion['parts']['2']['targets'][0]['offsets'][2] = [.25, -.5, 1]
                    result, report = patch_targets(raw, companion)
                    self.assertEqual(len(result), len(raw))
                    self.assertGreater(report['changed_bytes'], 0)
                    after = read_targets(result, 20, 1, 3, dx)
                    self.assertEqual(after['targets'][0]['offsets'][2], [.25, -.5, 1])
                    self.assertFalse(report['game_tested'])
                    self.assertTrue(result.endswith(b'UNRELATED MATERIALS AND FILE TAIL'))

    def test_run_splitting_rejected(self):
        raw, companion = fixture(True, False)
        companion['parts']['2']['targets'][0]['offsets'][1] = [1, 0, 0]
        with self.assertRaisesRegex(FormatError, 'stream repacking'):
            patch_targets(raw, companion)

    def test_hash_and_structure_rejected(self):
        raw, original = fixture(False, True)
        for mutate in (lambda c: c.update(sha256='wrong'),
                       lambda c: c['parts']['2']['targets'][0].update(id=18),
                       lambda c: c['parts']['2']['targets'][0].update(companion_hex=''),
                       lambda c: c['parts']['2'].update(end_offset=1),
                       lambda c: c['parts']['2']['targets'][0]['offsets'].pop(),
                       lambda c: c['parts']['2']['targets'][0]['offsets'][0].__setitem__(0, float('nan')),
                       lambda c: c['parts']['2']['targets'][0]['offsets'][0].__setitem__(0, 1e100)):
            companion = copy.deepcopy(original)
            mutate(companion)
            with self.assertRaises(FormatError):
                patch_targets(raw, companion)


if __name__ == '__main__':
    unittest.main()

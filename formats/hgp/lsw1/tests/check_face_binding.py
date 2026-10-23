"""Explicit facial ownership, layout and bake-allocation guards."""
import hashlib
from types import SimpleNamespace
import unittest

from check_animation_records import fixture, AnimationRecords
from bake_face_preview import prepare


class FaceBindingTests(unittest.TestCase):
    def setUp(self):
        clip = AnimationRecords(fixture('BSA'), 'BSA')
        self.clip = AnimationRecords(clip.transform_channel(0, 1, scale=.1,
                                    expected_sha256=clip.sha256), 'BSA')
        self.part = dict(layer=0, morph=dict(targets=[dict(id=0), dict(id=2)]))
        self.model = SimpleNamespace(data=b'model', layer_count=2,
                                     layer_meshes=lambda i: [self.part] if i == 0 else [])
        self.binding = dict(profile='lsw1-pc-bsa-preview-v1',
            model_sha256=hashlib.sha256(self.model.data).hexdigest(),
            animation_sha256=self.clip.sha256, layers=[0], fps=30,
            evidence='Synthetic explicit pairing, not gameplay evidence')

    def test_native_frames_and_id_mapping(self):
        parts, frames = prepare(self.model, self.clip, self.binding)
        self.assertEqual(len(frames), 33)
        self.assertEqual(frames[0][0][0], 2.)
        self.assertEqual(frames[0][0][2], 1.)
        self.assertEqual(parts, [self.part])

    def test_binding_guards(self):
        for field, value in (('profile', 'ANI'), ('model_sha256', 'wrong'),
            ('animation_sha256', 'wrong'), ('layers', [0, 0]), ('layers', [True]),
            ('layers', [2]), ('layers', [1]), ('fps', float('nan')),
            ('fps', True), ('evidence', '')):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                prepare(self.model, self.clip, dict(self.binding, **{field: value}))

    def test_missing_targets_and_slider_overflow_refused(self):
        self.part['morph']['targets'].append(dict(id=3))
        with self.assertRaisesRegex(ValueError, 'padding'):
            prepare(self.model, self.clip, self.binding)
        self.part['morph']['targets'].pop()
        raw = AnimationRecords(fixture('BSA'), 'BSA')
        with self.assertRaisesRegex(ValueError, 'slider'):
            prepare(self.model, raw, dict(self.binding, animation_sha256=raw.sha256))


if __name__ == '__main__':
    unittest.main()

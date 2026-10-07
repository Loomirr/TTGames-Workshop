"""Exercise the real live-preview dispatcher without Blender geometry nodes."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('face_live_fixture');package.__path__ = [str(source)]
sys.modules[package.__name__] = package
bpy = types.ModuleType('bpy');sys.modules.setdefault('bpy', bpy)
from face_live_fixture import face_live, face_preview


class Object(dict):
    __hash__ = object.__hash__
    def __eq__(self, other):return self is other
    def __init__(self, name, source, mask, parent, kind='MESH'):
        super().__init__(source_model=source, tt_colour_write_mask=mask)
        self.name, self.parent, self.type = name, parent, kind


class Scene(dict):
    def __init__(self, objects):
        super().__init__()
        self.name = 'Synthetic facial preview'
        self.objects = objects
        self.render = types.SimpleNamespace()
        collection = types.SimpleNamespace(collection=types.SimpleNamespace(all_objects=objects),
            children=[], exclude=False, holdout=False, indirect_only=False)
        self.view_layers = [types.SimpleNamespace(layer_collection=collection)]


class StopAfterPlanning(Exception):
    pass


class FaceLiveGroupingTests(unittest.TestCase):
    def planned(self, objects):
        scene = Scene(objects)
        data = types.SimpleNamespace(scenes=[scene], collections=types.SimpleNamespace(
            new=Mock(side_effect=StopAfterPlanning)))
        with patch.object(face_live.bpy, 'data', data, create=True), \
                patch.object(face_live, 'cameras'), \
                patch.object(face_preview, 'prepare_depth') as depth, \
                patch.object(face_live, 'clip_details') as clip:
            with self.assertRaises(StopAfterPlanning):face_live.prepare_live(scene, detail_level=4)
            return depth.call_args_list, clip.call_args_list

    def test_spiderface_receives_the_same_mask_and_detail_setup_as_face_resources(self):
        for source in ('SpiderFace', 'spiderface', 'SPIDERFACE',
                       'FACE_SYNTHETIC', 'face_synthetic', 'Face_Synthetic'):
            with self.subTest(source=source):
                parent = object()
                mask = Object('Mask', source, 0, parent)
                detail = Object('Eyes', source, 15, parent)
                depth, clips = self.planned([mask, detail])
                self.assertEqual(len(depth), 1)
                self.assertEqual(depth[0].args[0], [mask, detail])
                self.assertEqual(len(clips), 1)
                self.assertIs(clips[0].args[0], detail)
                self.assertEqual(clips[0].args[1], [mask])
                self.assertEqual(clips[0].args[3], 4)

    def test_masks_do_not_cross_source_instances_or_facial_resources(self):
        first, second = object(), object()
        a = Object('First mask', 'SpiderFace', 0, first)
        b = Object('First detail', 'SpiderFace', 15, first)
        c = Object('Second mask', 'SpiderFace', 0, second)
        d = Object('Second detail', 'SpiderFace', 15, second)
        e = Object('Other mask', 'FACE_OTHER', 0, first)
        f = Object('Other detail', 'FACE_OTHER', 15, first)
        _, clips = self.planned([a, b, c, d, e, f])
        self.assertEqual([(call.args[0], call.args[1]) for call in clips], [(b, [a]), (d, [c]), (f, [e])])

    def test_unrelated_and_solid_printing_objects_stay_out_of_mask_clipping(self):
        parent = object()
        mask = Object('Mask', 'SpiderFace', 0, parent)
        printing = Object('Printing', 'SpiderFace', 15, parent)
        printing['tt_native_alpha_test'] = 5
        unrelated = Object('Body', 'BODY', 15, parent)
        fake_mesh = Object('Armature', 'SpiderFace', 15, parent, 'ARMATURE')
        depth, clips = self.planned([mask, printing, unrelated, fake_mesh])
        self.assertEqual(depth[0].args[0], [mask, printing])
        self.assertEqual(clips, [])

    def test_unmasked_source_is_not_modified(self):
        depth, clips = self.planned([Object('Detail', 'SpiderFace', 15, object())])
        self.assertEqual(depth, [])
        self.assertEqual(clips, [])

    def test_resource_case_changes_classification_without_rewriting_provenance(self):
        parent = object()
        sources = ['face_lower', 'Face_Mixed', 'spiderface', 'not_face_lower', 'SpiderFaceExtra', None]
        objects = [Object(str(value), value, 0, parent) for value in sources]
        self.assertEqual(face_preview.face_objects(Scene(objects)), objects[:3])
        self.assertEqual([obj.get('source_model') for obj in objects], sources)


if __name__ == '__main__':
    unittest.main()

"""Target diagnostic tests use independently constructed in-memory records."""
import copy
import math
import unittest
from face_target_summary import summarize_targets, MAX_PARTS, MAX_TARGETS


def fixture():
    return dict(mesh_version=169,parts=[dict(index=7,vertex_count=3,palette=[2,8],record_offset=100,
        morphs=dict(table_offset=200,end_offset=300,targets=[dict(id=19,record_offset=220,
            encoding='dense_be_vec3',offsets=[[0,0,0],[3,-4,0],[-1,0,2]])]))])


class SummaryTests(unittest.TestCase):
    def test_preserves_native_identity_and_source_space_statistics(self):
        model=fixture();before=copy.deepcopy(model);report=summarize_targets(model)
        self.assertEqual(model,before)
        part=report['parts'][0];target=part['targets'][0]
        self.assertEqual((part['index'],part['vertex_count'],part['palette_size']),(7,3,2))
        self.assertEqual((target['id'],target['affected_vertices']),(19,2))
        self.assertEqual(target['max_displacement'],5)
        self.assertEqual(target['delta_min'],[-1,-4,0])
        self.assertEqual(target['delta_max'],[3,0,2])
        self.assertNotIn('offsets',target)
        self.assertNotIn('expression_name',target)

    def test_empty_and_non_morph_parts(self):
        report=summarize_targets(dict(mesh_version=175,parts=[dict(morphs=None)]))
        self.assertEqual(report['total_parts'],0)
        self.assertEqual(report['total_part_targets'],0)

    def test_detail_caps_do_not_hide_total_counts(self):
        model=fixture();part=model['parts'][0]
        part['morphs']['targets']*=MAX_TARGETS+2
        model['parts']*=MAX_PARTS+1
        report=summarize_targets(model)
        self.assertEqual(report['total_parts'],MAX_PARTS+1)
        self.assertEqual(report['total_part_targets'],(MAX_PARTS+1)*(MAX_TARGETS+2))
        self.assertEqual(report['omitted_parts'],1)
        self.assertEqual(report['parts'][0]['omitted_targets'],2)
        self.assertEqual(len(report['parts'][0]['targets']),MAX_TARGETS)

    def test_invalid_decoded_vectors_are_rejected(self):
        for offsets in ([],[[0,0,0]],[[0,0,0],[0,0,0],[1,2]],
                        [[0,0,0],[0,0,0],[math.inf,0,0]]):
            model=fixture();model['parts'][0]['morphs']['targets'][0]['offsets']=offsets
            with self.assertRaises(ValueError):summarize_targets(model)


if __name__=='__main__':unittest.main()

"""Asset-free ANI-D writer checks with nonmonotonic samples and exact trees."""
import hashlib
import struct
import sys
import unittest
from test_an4_standalone import tree
from tt_an4_test.an4 import AnimationFile
from tt_an4_test.cu3 import Animation,Reader,FormatError
from tt_an4_test.an4_edit import encode_samples,patch_record


class AN4Edits(unittest.TestCase):
    def test_nine_channels_preserve_scale_and_gate_degenerate_scale(self):
        rows=[[[v,0,0,0,0,0,1,1,1]] for v in (0,.1,-.2)]
        raw,error=encode_samples(rows,[0xb],9);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertEqual(anim.curves,9);self.assertEqual(anim.sample(1)[0][6:],[1,1,1])
        rows[0][0][6]=2
        raw,error=encode_samples(rows,[0xb],9);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertAlmostEqual(anim.sample(0)[0][6],2,places=4)
        rows[0][0][6]=0
        with self.assertRaisesRegex(FormatError,'nonzero scale'):encode_samples(rows,[0xb],9)

    def test_auxiliaries_require_explicit_omission(self):
        raw=tree();struct.pack_into('>I',raw,224+60,80);raw=bytes(raw)
        rows=[[[0]*6]]*2;sha=hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(FormatError,'auxiliaries'):patch_record(raw,'Actor',0,rows,sha)
        output,report=patch_record(raw,'Actor',0,rows,sha,omit_auxiliary=True)
        self.assertEqual(report['omitted_auxiliary_offsets'],[0,80,0,0])
    def test_nonmonotonic_frames_and_fractional_interpolation(self):
        rows=[[[v,3.5,0,1,0,0]] for v in (0,1,-2,4,-1)]
        raw,error=encode_samples(rows,[0x20]);anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
        self.assertLess(error,.0001);self.assertEqual(anim.node_flags,(0x23,))
        for index,frame in enumerate(rows):
            for a,b in zip(anim.sample(index)[0],frame[0]):self.assertAlmostEqual(a,b,places=3)
        self.assertAlmostEqual(anim.sample(.5)[0][0],.5,places=3)

    def test_existing_tree_names_matrix_and_record_pointer(self):
        raw=bytes(tree());rows=[[[0,0,0,0,0,0]],[[.1,0,0,0,.2,0]]]
        output,report=patch_record(raw,'Actor',0,rows,hashlib.sha256(raw).hexdigest())
        parsed=AnimationFile('output.AN4',data=output);actor=parsed.actors[0]
        self.assertEqual(actor['name'],'Actor');self.assertEqual(actor['records'][0]['name'],'Clip')
        self.assertEqual(actor['records'][0]['matrix'],AnimationFile('original.AN4',data=raw).actors[0]['records'][0]['matrix'])
        self.assertEqual(output[8:212],raw[8:212]);self.assertEqual(report['frames'],2)

    def test_rejects_unknown_node_flags_bad_samples_frame_changes_and_hash(self):
        for rows,flags in (([],[3]),([[[0]*6]],[8]),([[[float('nan')]*6]],[3]),([[[0]*7]],[3])):
            with self.assertRaises(FormatError):encode_samples(rows,flags)
        raw=bytes(tree());sha=hashlib.sha256(raw).hexdigest()
        for actor,index,rows,h in (('Unknown',0,[],sha),('Actor',10,[],sha),('Actor',0,[[[0]*6]],sha),('Actor',0,[], 'wrong')):
            with self.assertRaises(FormatError):patch_record(raw,actor,index,rows,h)

if __name__=='__main__':unittest.main()

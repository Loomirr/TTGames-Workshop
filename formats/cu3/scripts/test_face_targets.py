"""Portable checks of bounds and run expansion; no game assets included."""
from pathlib import Path
import sys, types, struct, unittest
R=Path(__file__).resolve().parent.parent
p=types.ModuleType('io_scene_lego_cu3');p.__path__=[str(R/'Addon/io_scene_lego_cu3')];sys.modules[p.__name__]=p
from io_scene_lego_cu3.morph import decode_runs, read_targets
from io_scene_lego_cu3.cu3 import FormatError

class FaceTargetTests(unittest.TestCase):
    def test_run_order_and_repeats(self):
        raw=struct.pack('>I3fI3fI3f',2,0,0,0,1,.125,-.25,.5,0,0,0,0)
        self.assertEqual(decode_runs(raw,0,len(raw),3),[[0.,0.,0.],[0.,0.,0.],[.125,-.25,.5]])

    def test_reject_invalid_inputs(self):
        bad=[(struct.pack('>I3f',100000000,0,0,0),16,3),
             (b'\0'*15,16,1),(struct.pack('>I3f',1,float('nan'),0,0),16,1),
             (struct.pack('>I3f',1,0,0,0),16,2)]
        for raw,size,count in bad:
            with self.subTest(size=size,count=count):
                with self.assertRaises(FormatError):decode_runs(raw,0,size,count)

    def test_internal_zero_padding_preserves_vertex_order(self):
        raw = struct.pack('>I3fI3fI3f', 1, 1, 2, 3, 0, 0, 0, 0, 1, 4, 5, 6)
        self.assertEqual(decode_runs(raw, 0, len(raw), 2), [[1., 2., 3.], [4., 5., 6.]])
        with self.assertRaises(FormatError):
            decode_runs(struct.pack('>I3f', 0, 1, 0, 0), 0, 16, 0)

    def test_dx_companion_counts_preserve_next_record_boundary(self):
        for n in (0,2,4):
            raw=struct.pack('>3I',1,17,0)+b'ROTV'+struct.pack('>3I',0,2,16)
            raw+=struct.pack('>I3f',1,.125,0,0)
            raw+=b'ROTV'+struct.pack('>I',n)+bytes(n*4)+b'ROTV'+b'TAIL'
            result=read_targets(raw,8,1,1,True)
            self.assertEqual(result['end_offset'],len(raw)-4)
            self.assertEqual(result['targets'][0]['offsets'],[[.125,0.,0.]])
        last_zero=raw[:-8]+bytes(4)+b'TAIL'
        self.assertEqual(read_targets(last_zero,8,1,1,True)['end_offset'],len(last_zero)-4)
        broken=raw[:-8]+b'BAD!'+b'TAIL'
        with self.assertRaises(FormatError):read_targets(broken,8,1,1,True)

if __name__=='__main__':unittest.main()

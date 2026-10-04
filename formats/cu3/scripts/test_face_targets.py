"""Portable checks of bounds and run expansion; no game assets included."""
from pathlib import Path
import sys, types, struct, unittest
R=Path(__file__).resolve().parent.parent
p=types.ModuleType('io_scene_lego_cu3');p.__path__=[str(R/'Addon/io_scene_lego_cu3')];sys.modules[p.__name__]=p
from io_scene_lego_cu3.morph import decode_runs
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

if __name__=='__main__':unittest.main()

"""Portable material layout/bounds checks, without proprietary assets."""
import unittest,struct,sys,types
from pathlib import Path
R=Path(__file__).resolve().parents[1];p=types.ModuleType('io_scene_lego_cu3');p.__path__=[str(R/'Addon/io_scene_lego_cu3')];sys.modules[p.__name__]=p
from io_scene_lego_cu3.material_flags import footer,read_render_flags

def fixture(version,mask=15,variant=0xffffffff):
    # Independent scalar fixture: 18 historic flags, two later booleans,
    # one 190+ fixup flag, and alpha test mode.
    flags=bytearray(20+(version>=190)+1);flags[3]=125;flags[17]=mask
    raw=bytes(flags)+struct.pack('>5I2BH',1,2,3,4,0xffffffff,180,0,2)
    if version<199:raw+=struct.pack('>H',0)
    raw+=struct.pack('>2B4f2I',0,0,0.,0.,0.,0.,variant,0xffffffff)
    raw+=bytes(16+(version>=187)+(version>=191))
    return raw+struct.pack('>2I',123,2)

class MaterialFlagTests(unittest.TestCase):
    def test_version_gates_and_no_colour_mask(self):
        for version in (174,176,177,183,187,190,191,194,198,199,202):
            with self.subTest(version=version):
                raw=b'prefix'+fixture(version,0);start,flags=footer(raw,len(raw),version)
                self.assertEqual(start,6);self.assertEqual(flags['colourWriteMask'],0)
                self.assertEqual(flags['aref'],125);self.assertEqual(flags['shortPri16bit'],2)
                self.assertEqual(flags['firstVariantIdx'],0xffffffff);self.assertEqual(flags['defaultRenderStage'],2)

    def test_bounded_record_and_final_marker(self):
        raw=b'x'*64+fixture(202)+b'ROTV'+bytes(17)+b'TDML'
        rows=read_render_flags(raw,[dict(name='material',offset=0)],202)
        self.assertEqual(rows[0]['offset'],64)

    def test_reject_bad_bounds_versions_and_variants(self):
        for data,end,version in ((b'123',3,202),(bytes(200),250,202),(bytes(200),200,203)):
            with self.assertRaises(ValueError):footer(data,end,version)
        with self.assertRaises(ValueError):read_render_flags(bytes(100),[],202)
        with self.assertRaises(ValueError):read_render_flags(bytes(100),[dict(offset=-1)],202)
        raw=b'x'*64+fixture(202,variant=99)+b'ROTV'+bytes(17)+b'TDML'
        with self.assertRaises(ValueError):read_render_flags(raw,[dict(name='bad',offset=0)],202)

if __name__=='__main__':unittest.main()

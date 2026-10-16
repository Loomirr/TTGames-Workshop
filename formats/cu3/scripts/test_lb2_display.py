"""LEGO Batman 2 DISP 12-14: per-clip arrays before the specials (synthetic fixtures)."""
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('lb2_display_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from lb2_display_fixture.native_display import read_display, model_bindings
from lb2_display_fixture.cu3 import FormatError


def fixture(version=14, *, marked_rest=False, ranges=(0.0,)):
    """Two LOD clips; three per-clip u32 arrays, only the first with ROTV."""
    names=b'Prop\0'
    data=b'LBTN'+struct.pack('>2I',64,len(names))+names+b'PSID'+struct.pack('>I',version)
    data+=struct.pack('>I',0)+b'ROTV'+struct.pack('>I',2)+struct.pack('>BBI',0xb3,0,0)+struct.pack('>BBI',0xb3,0,1)
    data+=b'ROTV'+struct.pack('>I',2)+struct.pack('>H4I',0,1,0,1,0)+struct.pack('>H4I',0,1,0,1,1)
    data+=b'ROTV'+struct.pack('>I2H',2,1,1)+b'ROTV'+struct.pack('>3I',2,0,0)
    data+=b'ROTV'+struct.pack('>3I',2,0,0)
    for _ in range(2):
        data+=(b'ROTV' if marked_rest else b'')+struct.pack('>3I',2,0,0)
    body=bytearray(204+4*len(ranges))
    struct.pack_into('>I16f',body,0,0,1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1)
    struct.pack_into('>3I',body,180,0,0,len(ranges))
    struct.pack_into(f'>{len(ranges)}f',body,192,*ranges)
    data+=b'ROTV'+struct.pack('>I',1)+bytes(body)+b'ROTV'
    return data


class LB2Display(unittest.TestCase):
    def read(self,data,parts=2):
        with tempfile.NamedTemporaryFile(suffix='.gsc',delete=False) as f:
            f.write(data);path=Path(f.name)
        try:return read_display(path,parts)
        finally:path.unlink()

    def test_lb2_versions_reach_the_specials(self):
        for version in (12,13,14):
            data=fixture(version);display=self.read(data)
            self.assertEqual(display['end_offset'],len(data)-4)
            special=display['specials'][0]
            self.assertEqual(special['name'],'Prop')
            self.assertEqual(special['matrix'][12:15],[2,3,4])
            self.assertEqual(model_bindings(display,special),[dict(part=0,material=0)])

    def test_far_to_near_lod_selects_the_last_clip(self):
        display=self.read(fixture(ranges=(25.0,0.0)))
        self.assertEqual(model_bindings(display,display['specials'][0]),[dict(part=1,material=0)])

    def test_marked_or_miscounted_arrays_are_refused(self):
        with self.assertRaises(FormatError):self.read(fixture(marked_rest=True))
        bad=fixture().replace(b'ROTV'+struct.pack('>3I',2,0,0)+struct.pack('>3I',2,0,0),
                              b'ROTV'+struct.pack('>3I',2,0,0)+struct.pack('>3I',3,0,0),1)
        with self.assertRaises(FormatError):self.read(bad)

    def test_versions_between_stay_unsupported(self):
        for version in (10,11,15):
            with self.assertRaisesRegex(FormatError,'separate verified reader'):self.read(fixture(version))


if __name__=='__main__':
    unittest.main()

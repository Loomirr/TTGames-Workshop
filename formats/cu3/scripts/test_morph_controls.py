"""Independent packed type-7 scalar values for both observed BSA flag variants."""
import struct
import sys
import types
import unittest
from pathlib import Path
source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('morph_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from morph_fixture.cu3 import Animation,Reader,FormatError


def fixture(flags):
    types_at=88;keys_at=196;flags_at=220
    raw=bytearray(flags_at+1);raw[:4]=b'DINA'
    struct.pack_into('<6H',raw,4,1,4,8,4,53,0)
    raw[19]=flags;struct.pack_into('<H',raw,22,4)
    struct.pack_into('<9I',raw,36,80,88,types_at,keys_at,flags_at,0,0,0,0)
    struct.pack_into('<2f',raw,72,1,0)
    struct.pack_into('<2f',raw,80,.001,0)
    struct.pack_into('<53H',raw,types_at,7,*([14]*52))
    struct.pack_into('<4H',raw,keys_at,0,0xf000,0xf555,0xfaaa)
    struct.pack_into('<4H',raw,keys_at+8,1000,0,0,0)
    struct.pack_into('<4H',raw,keys_at+16,1000,0,0,0)
    return raw


class MorphControls(unittest.TestCase):
    def test_both_flags_sample_known_scalar_values(self):
        for flags in (0xa4,0xac):
            raw=fixture(flags);anim=Animation(Reader(raw),0,len(raw));anim.prepare(morph_channels=True)
            for frame,expected in enumerate((0,1/3,2/3,1)):
                values=anim.sample(frame)[0]
                self.assertAlmostEqual(values[0],expected,places=6)
                self.assertEqual(values[1:],[0]*52)

    def test_unknown_flag_and_bad_stride_rejected(self):
        for flags,stride in ((0xa0,8),(0xac,4)):
            raw=fixture(flags);struct.pack_into('<H',raw,8,stride)
            with self.assertRaises(FormatError):Animation(Reader(raw),0,len(raw)).prepare(morph_channels=True)

if __name__=='__main__':unittest.main()

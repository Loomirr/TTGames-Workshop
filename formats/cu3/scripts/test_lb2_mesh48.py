"""LEGO Batman 2 MESH 48: untagged vertex buffers on the MESH 169 part layout (synthetic fixtures)."""
import struct
import sys
import types
import unittest
from pathlib import Path

pkg=types.ModuleType('mesh48_fixture');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')];sys.modules[pkg.__name__]=pkg
from mesh48_fixture.native_mesh import read_mesh_bytes
from mesh48_fixture.cu3 import FormatError


def fixture(version, *, tagged, skin=False):
    raw=b'HSEM'+struct.pack('>I',version)+b'ROTV'+struct.pack('>I',1)
    raw+=struct.pack('>I',1)+struct.pack('>3I',1,0,3)
    raw+=(b'DXTV'+struct.pack('>I',169) if tagged else b'')
    if skin:
        raw+=struct.pack('>I',4)+bytes((0,3,0,1,8,12,9,7,16,10,8,20))+(bytes(6) if tagged else b'')
        for x,y,z in ((0,0,0),(1,0,0),(0,1,1)):
            raw+=struct.pack('>3f',x,y,z)+bytes((128,128,255,255,0,1,255,255,128,127,0,0))
    else:
        raw+=struct.pack('>I',3)+bytes((0,3,0,5,5,12,2,9,16))+(bytes(6) if tagged else b'')
        for x,y,z in ((0,0,0),(1,0,0),(0,1,1)):
            raw+=struct.pack('>3f2e',x,y,z,x,y)+bytes((10,20,30,255))
    raw+=struct.pack('>2I',0,0)
    raw+=struct.pack('>4I',1,0,3,2)+struct.pack('>3H',0,1,2)
    if skin:
        raw+=struct.pack('>3IH3I',0,3,0,0,3,0,5)+bytes((3,7,11,21,55))
    else:
        raw+=struct.pack('>3IH3I',0,3,0,0,3,0,0)
    raw+=bytes(4)+bytes(4)+bytes(36)+bytes(32)
    return raw


class LB2Mesh48(unittest.TestCase):
    def test_untagged_buffers_match_the_169_layout(self):
        for skin in (False,True):
            old=read_mesh_bytes(fixture(48,tagged=False,skin=skin))
            new=read_mesh_bytes(fixture(169,tagged=True,skin=skin))
            self.assertEqual(old['mesh_version'],48)
            self.assertEqual(old['end_offset'],len(fixture(48,tagged=False,skin=skin)))
            for a,b in zip(old['parts'],new['parts']):
                self.assertEqual(a['triangles'],b['triangles'])
                self.assertEqual([v['position'] for v in a['vertices']],[v['position'] for v in b['vertices']])
                if skin:
                    self.assertEqual([v['weights'] for v in a['vertices']],[v['weights'] for v in b['vertices']])

    def test_layouts_are_not_mixed(self):
        # A tagged buffer under MESH 48, or an untagged one under 169, is refused.
        with self.assertRaises(FormatError):read_mesh_bytes(fixture(48,tagged=True))
        with self.assertRaises(FormatError):read_mesh_bytes(fixture(169,tagged=False))

    def test_other_lb2_versions_stay_unsupported(self):
        for version in (46,):          # MESH 47: test_lb2_mesh47.py
            raw=bytearray(fixture(48,tagged=False));struct.pack_into('>I',raw,4,version)
            with self.assertRaisesRegex(FormatError,'supported native MESH'):read_mesh_bytes(bytes(raw))


if __name__=='__main__':
    unittest.main()

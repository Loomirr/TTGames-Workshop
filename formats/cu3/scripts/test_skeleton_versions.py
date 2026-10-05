"""Independent skeleton-layout fixtures and native hierarchy validation."""
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

pkg=types.ModuleType('skeleton_fixture');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')];sys.modules[pkg.__name__]=pkg
from skeleton_fixture.skeleton import read_skeleton
from skeleton_fixture.cu3 import FormatError

IDENTITY=(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)


def fixture(version, parent=255):
    names=b'Root\0Layer\0'
    data=b'LBTN'+struct.pack('>2I',1,len(names))+names+b'LOGH'+struct.pack('>I',version)
    marker=b'ROTV' if version!=10 else b''
    data+=marker+struct.pack('>I',1)
    data+=struct.pack('>H',5)+b'Root\0' if version>=15 else struct.pack('>I',0)
    data+=struct.pack('>16f3f2B',*IDENTITY,0,0,0,parent,0)
    for i in range(2):data+=marker+struct.pack('>I16f',1,*IDENTITY)
    data+=marker+struct.pack('>I',0)
    data+=marker+struct.pack('>I',1)
    data+=struct.pack('>H',5)+b'Root\0' if version>=12 else struct.pack('>I',0)
    data+=struct.pack('>16fB',*IDENTITY,0)
    data+=marker+struct.pack('>IB',1,0)
    data+=struct.pack('>I',0)
    data+=marker+struct.pack('>IBBHB',1,0,0,0,0)
    data+=marker+struct.pack('>I',1)
    data+=struct.pack('>H',6)+b'Layer\0' if version>=15 else struct.pack('>I',5)
    return data+struct.pack('>3H',0,1,0)


class SkeletonTests(unittest.TestCase):
    def read(self,data,expected=None):
        with tempfile.NamedTemporaryFile(suffix='.ghg',delete=False) as f:f.write(data);path=Path(f.name)
        try:return read_skeleton(path,expected)
        finally:path.unlink()

    def test_versioned_names_arrays_locators_and_layers(self):
        for version in (10,12,15,16,17):
            with self.subTest(version=version):
                r=self.read(fixture(version),1)
                self.assertEqual(r['joints'][0]['name'],'Root')
                self.assertEqual(r['joints'][0]['local_bind_row_major'],list(IDENTITY))
                self.assertEqual(r['layers'][0]['name'],'Layer')
                self.assertEqual(r['points_of_interest'][0]['name'],'Root')
                self.assertEqual(r['post_poi_bytes'],[0])

    def test_hierarchy_count_and_marker_rejection(self):
        with self.assertRaises(FormatError):self.read(fixture(17,parent=0))
        with self.assertRaises(FormatError):self.read(fixture(12),2)
        with self.assertRaises(FormatError):self.read(fixture(17).replace(b'ROTV',b'BAD!'))
        with self.assertRaises(FormatError):self.read(fixture(16)[:40])


if __name__=='__main__':unittest.main()

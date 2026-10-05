"""Synthetic DISP fixture: empty locators must retain native instance indices."""
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('display_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from display_fixture.native_display import read_display
from display_fixture.cu3 import FormatError


def fixture(clip=0xffffffff):
    def array(count):return b'ROTV'+struct.pack('>I',count)
    data=b'PSID'+struct.pack('>I',32)
    data+=array(1)+struct.pack('>BBI',0x80,0,0)
    data+=array(1)+struct.pack('>H2I',1,0,0)
    data+=array(2)
    for name,slot in ((b'Anchor\0',clip),(b'Mesh\0',0)):
        body=bytearray(136)
        struct.pack_into('>16f',body,0,1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1)
        struct.pack_into('>3I',body,112,slot,0x80002002,0)
        data+=struct.pack('>H',len(name))+name+body
    return data


class DisplayTests(unittest.TestCase):
    def test_legacy_static_auxiliary_arrays_before_specials(self):
        names=b'Accessory\0'
        data=b'LBTN'+struct.pack('>2I',64,len(names))+names+b'PSID'+struct.pack('>I',16)
        data+=struct.pack('>I',0)+b'ROTV'+struct.pack('>IBBI',1,0xb3,0,0)
        data+=b'ROTV'+struct.pack('>IH4I',1,0,1,0,1,0)
        data+=b'ROTV'+struct.pack('>IH',1,1)+b'ROTV'+struct.pack('>II',1,0)
        for value in (123,0,0):data+=b'ROTV'+struct.pack('>II',1,value)
        body=bytearray(208)
        struct.pack_into('>I16f',body,0,0,1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1)
        struct.pack_into('>4I',body,180,0,0x80000402,1,123)
        data+=b'ROTV'+struct.pack('>I',1)+body
        result=self.read(data)['specials'][0]
        self.assertEqual(result['name'],'Accessory')
        self.assertEqual(result['matrix'][12:15],[2,3,4])
        self.assertEqual(result['parts'],[{'part':0,'material':0}])
        malformed=data.replace(b'ROTV'+struct.pack('>II',1,123),b'ROTV'+struct.pack('>II',2,123),1)
        with self.assertRaises(ValueError):self.read(malformed)

    def read(self,data):
        # Windows can restrict TemporaryDirectory permissions; use a file.
        with tempfile.NamedTemporaryFile(suffix='.gsc',delete=False) as f:
            f.write(data);path=Path(f.name)
        try:return read_display(path,1)
        finally:path.unlink()

    def test_empty_locator_preserves_table_indices(self):
        result=self.read(fixture())['specials']
        self.assertEqual([s['index'] for s in result],[0,1])
        self.assertTrue(result[0]['locator_only'])
        self.assertEqual(result[0]['parts'],[])
        self.assertEqual(result[0]['matrix'][12:15],[2,3,4])
        self.assertEqual(result[1]['parts'],[{'part':0,'material':0}])

    def test_invalid_clip_is_not_treated_as_locator(self):
        with self.assertRaisesRegex(FormatError,'display instance'):self.read(fixture(1))

    def test_hobbit_vector_arrays_and_global_special_name(self):
        names=b'Mesh\0'
        data=b'LBTN'+struct.pack('>2I',1,len(names))+names+b'PSID'+struct.pack('>I',26)
        data+=b'ROTV'+struct.pack('>IBBI',1,0x80,0,0)
        data+=b'ROTV'+struct.pack('>IH2I',1,1,0,0)
        body=bytearray(204)
        struct.pack_into('>I16f',body,0,0,1,0,0,0,0,1,0,0,0,0,1,0,2,3,4,1)
        struct.pack_into('>3I',body,180,0,0,0)
        data+=b'ROTV'+struct.pack('>I',1)+body
        result=self.read(data)['specials'][0]
        self.assertEqual(result['name'],'Mesh')
        self.assertEqual(result['matrix'][12:15],[2,3,4])
        self.assertEqual(result['parts'],[{'part':0,'material':0}])

if __name__=='__main__':unittest.main()

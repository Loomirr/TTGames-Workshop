"""LEGO Batman 2 definition streams 18, 19 and 22-24 (constructed fixtures, no game data)."""
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('lb2_definition_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from lb2_definition_fixture.definitions import read_definition_bytes, character_definition
from lb2_definition_fixture.cu3 import FormatError


def block(name,payload):
    name=name.encode('ascii')+b'\0'
    return struct.pack('<2I',8+len(name)+len(payload),len(name))+name+payload


def string(value):
    raw=value.encode('ascii')+b'\0'
    return struct.pack('<I',len(raw))+raw


def fixture(version,count=2,model_field='Skeleton Name'):
    """One class (int, string, float) and `count` objects in the layout of `version`."""
    words=5 if version>=27 else 4 if version>=22 else 3
    fields=[(2,'Object Attributes'),(5,model_field),(4,'Default Alpha')]
    schema=b''.join(struct.pack('<I',typ)+string(name)+bytes(4*words) for typ,name in fields)
    cls=block('Class',string('Character Definition')+block('Types',struct.pack('<I',len(fields))+schema))
    header=bytes(4 if version>=28 else 3 if version>=25 else 5)
    objects=b''.join(block('MOBJ',header+struct.pack('<i',7)+string('SUPER_MINIFIG')+struct.pack('<f',0.5))
                     for _ in range(count))
    listed=struct.pack('<HI' if version>=24 else '<HH',0,count)
    return block('StreamInfo',struct.pack('<I',version))+block('ClassList',cls)+block('OLST',listed+objects)


class LB2Definitions(unittest.TestCase):
    def test_older_streams_decode_like_25(self):
        expected={'Object Attributes':7,'Skeleton Name':'SUPER_MINIFIG','Default Alpha':0.5}
        for version in (18,19,22,23,24,25,27,28):
            result=read_definition_bytes(fixture(version))
            self.assertEqual(len(result['objects']),2,version)
            for item in result['objects']:
                self.assertEqual(item['fields'],expected,version)
                self.assertTrue(item['complete'],version)

    def test_older_model_file_names_the_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'face.cd'
            path.write_bytes(fixture(23,count=1,model_field='Model File'))
            fields=character_definition(path)['character']
            self.assertEqual((fields['Override Model File'],fields['Skeleton Name']),('SUPER_MINIFIG',''))
            path.write_bytes(fixture(25,count=1,model_field='Model File'))   # only before stream 24
            with self.assertRaisesRegex(FormatError,'skeleton name'):character_definition(path)
            path.write_bytes(fixture(23,count=2,model_field='Model File'))   # one definition only
            with self.assertRaisesRegex(FormatError,'skeleton name'):character_definition(path)

    def test_unobserved_versions_stay_refused(self):
        for version in (17,20,21,32):
            with self.assertRaisesRegex(FormatError,'not verified'):read_definition_bytes(fixture(version))

    def test_layout_of_another_version_does_not_decode(self):
        data=bytearray(fixture(23))
        at=data.find(b'StreamInfo\0')+11
        struct.pack_into('<I',data,at,24)          # 16-bit list count read as 32 bits
        with self.assertRaises(FormatError):read_definition_bytes(bytes(data))


if __name__=='__main__':
    unittest.main()

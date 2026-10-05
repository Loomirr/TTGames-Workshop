"""Synthetic loose-animation bank and newer archive-family checks."""
from pathlib import Path
import struct
import sys
import types
import unittest

package = types.ModuleType('tt_source_test')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_source_test.animation_bank import AnimationBank
from tt_source_test.archive_cc import parse_index, path_hash
from tt_source_test.cu3 import FormatError


def bank(name='idle.an4'):
    name = name.encode()+b'\0'
    offset = 52+len(name)
    return struct.pack('<6I',0x1234567A,1,offset+3,0,0,0)+struct.pack('<7I',52,offset,3,0,0,0,0)+name+b'abc'


def archive(kind, version):
    names = b'CHARS\0IDLE.AN4\0'
    node = 'IHhH' if version == 1 else 'IHHhH'
    records = struct.pack('>'+node, *([0,65535,0,0] if version==1 else [0,65535,0,0,0]))
    records += struct.pack('>'+node, *([6,0,0,1] if version==1 else [6,0,0,0,1]))
    if kind == -12:
        value=0xcbf29ce484222325
        for byte in b'CHARS\\IDLE.AN4':value=((value^byte)*1099511628211)&0xffffffffffffffff
        table=struct.pack('>iIQIIQ',kind,1,273,20,20,value)
    else:
        table=struct.pack('>iI4II2I',kind,1,1,20,20,17,path_hash('CHARS/IDLE.AN4'),0,0)
    raw=struct.pack('>I8si4I',0,b'.CC40TAD',kind,version,1,2,len(names))+names+bytes(4)+records+table
    return struct.pack('>I',len(raw)-4)+raw[4:]


class Checks(unittest.TestCase):
    def test_bank_read(self):
        source=AnimationBank('fixture.pak',data=bank())
        self.assertEqual(source.read('IDLE.AN4'),b'abc')
        with self.assertRaises(FormatError):source.read('absent.an4')

    def test_bank_path_and_bounds(self):
        for raw in (bank('../idle.an4'),bank('/idle.an4'),bank()[:-1],b'bad'):
            with self.assertRaises(FormatError):AnimationBank('fixture.pak',data=raw)

    def test_bank_extent(self):
        raw=bytearray(bank());struct.pack_into('<I',raw,28,99999)
        with self.assertRaises(FormatError):AnimationBank('fixture.pak',data=raw)

    def test_three_archive_families(self):
        for kind,version in [(-8,1),(-8,2),(-12,2)]:
            self.assertEqual(parse_index(archive(kind,version),1024),[dict(path='CHARS/IDLE.AN4',offset=273,packed_size=20,size=20,flags=0)])

    def test_archive_payload_bounds(self):
        for kind,version in [(-8,1),(-8,2),(-12,2)]:
            with self.assertRaises(ValueError):parse_index(archive(kind,version),280)
            with self.assertRaises(ValueError):parse_index(archive(kind,version)[:-1])


if __name__ == '__main__':unittest.main()

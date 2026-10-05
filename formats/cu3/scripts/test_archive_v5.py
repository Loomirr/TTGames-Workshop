"""Portable malformed-input and tree/hash regression checks for DAT -5."""
import struct
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package = types.ModuleType('archive_v5_fixture'); package.__path__ = [str(root)]
sys.modules[package.__name__] = package
from archive_v5_fixture.archive_v5 import _parse_index, _path_hash, index_v5


def fixture(name='TWO.TEX'):
    # ROOT -> CHARS -> ONE.CD, ROOT -> CUT -> TWO.TEX. Name records are
    # interleaved and sibling links point backwards, unlike an explicit parent.
    names = ['', 'chars', 'one.cd', 'cut', name]
    strings = bytearray(); offsets = []
    for value in names:
        offsets.append(len(strings)); strings.extend(value.encode('ascii')+b'\0')
    result = bytearray(struct.pack('<iI', -5, 2))
    result.extend(struct.pack('<4I', 2, 4, 4, 0))
    result.extend(struct.pack('<4I', 3, 8, 12, 2))
    result.extend(struct.pack('<I', len(names)))
    for index,(child,previous) in enumerate(((3,0),(2,0),(0,0),(4,1),(-1,0))):
        result.extend(struct.pack('<hhiI',child,previous,offsets[index],0))
    result.extend(struct.pack('<I',len(strings)));result.extend(strings)
    result.extend(struct.pack('<2I',_path_hash('CHARS\\ONE.CD'),_path_hash('CUT\\'+name.upper())))
    result.extend(b'\0'*8)
    return result


class DatV5(unittest.TestCase):
    def test_tagged_name_variant_keeps_full_path_hash_validation(self):
        raw=fixture();struct.pack_into('<I',raw,44+8,0x12345678)
        with self.assertRaises(ValueError):_parse_index(raw,1024)
        self.assertEqual(_parse_index(raw,1024,name_tags=True)[0]['path'],'CHARS/ONE.CD')
        raw[-16]^=1
        with self.assertRaisesRegex(ValueError,'hash'):_parse_index(raw,1024,name_tags=True)

    def test_archive_header_and_encoded_index_offset(self):
        table=fixture()
        for offset_word in (1024,0xfffffffc):
            archive=bytearray(1024)+table
            struct.pack_into('<2I',archive,0,offset_word,len(table))
            with patch.object(Path,'open',return_value=io.BytesIO(archive)):
                self.assertEqual(index_v5('fixture.dat'),_parse_index(table,1024))

    def test_archive_header_outside_file_rejected(self):
        for header in (b'short',struct.pack('<2I',1024,128),struct.pack('<2I',8,0xffffffff)):
            with patch.object(Path,'open',return_value=io.BytesIO(header)),self.assertRaises(ValueError):
                index_v5('fixture.dat')

    def test_tree_hash_and_ranges(self):
        rows=_parse_index(fixture(),1024)
        self.assertEqual(rows,[{'path':'CHARS/ONE.CD','offset':512,'packed_size':4,'size':4,'flags':0},
                               {'path':'CUT/TWO.TEX','offset':768,'packed_size':8,'size':12,'flags':2}])

    def test_unsafe_names_rejected_even_with_matching_hash(self):
        for name in ('..','.','../ESCAPE.TEX','A\\B.TEX','C:ESCAPE','/ABSOLUTE','CON.TEX','TRAIL.','TRAIL '):
            with self.subTest(name=name),self.assertRaises(ValueError):_parse_index(fixture(name),1024)

    def test_truncated_arrays_and_counts(self):
        raw=fixture()
        for length in (0,7,25,45,95,len(raw)-1):
            with self.subTest(length=length),self.assertRaises(ValueError):_parse_index(raw[:length],1024)
        for offset in (4,40):
            changed=bytearray(raw);struct.pack_into('<I',changed,offset,0xffffffff)
            with self.assertRaises(ValueError):_parse_index(changed,1024)

    def test_path_hash_and_ordinal_mismatch(self):
        raw=fixture();raw[-16]^=1
        with self.assertRaisesRegex(ValueError,'hash'):_parse_index(raw,1024)
        raw=fixture();struct.pack_into('<h',raw,44+4*12,-2)
        with self.assertRaisesRegex(ValueError,'ordinal'):_parse_index(raw,1024)

    def test_cyclic_and_unowned_name_tree(self):
        raw=fixture();struct.pack_into('<h',raw,44+3*12+2,3)
        with self.assertRaisesRegex(ValueError,'Cyclic'):_parse_index(raw,1024)
        raw=fixture();struct.pack_into('<h',raw,44+3*12+2,0)
        with self.assertRaisesRegex(ValueError,'Incomplete'):_parse_index(raw,1024)
        raw=fixture();struct.pack_into('<h',raw,44+3*12,2)
        with self.assertRaisesRegex(ValueError,'multiply-owned'):_parse_index(raw,1024)

    def test_payload_extent_and_storage_flags(self):
        for offset,value in ((8,20),(12,10000),(20,3),(24,0),(32,0)):
            raw=fixture();struct.pack_into('<I',raw,offset,value)
            with self.subTest(offset=offset),self.assertRaises(ValueError):_parse_index(raw,1024)

    def test_unknown_version_and_trailer(self):
        raw=fixture();struct.pack_into('<i',raw,0,-6)
        with self.assertRaisesRegex(ValueError,'version'):_parse_index(raw,1024)
        raw=fixture();raw[-1]=1
        with self.assertRaisesRegex(ValueError,'trailer'):_parse_index(raw,1024)


if __name__=='__main__':unittest.main()

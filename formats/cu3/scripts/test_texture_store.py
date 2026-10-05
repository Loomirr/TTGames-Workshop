"""Portable fixtures for texture inventory IDs and malformed boundaries."""
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package = types.ModuleType('texture_fixture');package.__path__ = [str(root)]
sys.modules[package.__name__] = package
from texture_fixture.texture_store import read_texture_store
from texture_fixture.cu3 import FormatError


def fixture(version=12):
    raw = bytearray(b'TSXT'+b'\0'*4+b'TSXT'+struct.pack('>I',version))
    raw += struct.pack('>I',8)+b'CONVDATE'+b'ROTV'+struct.pack('>I',3)
    for name, kind in ((b'color\0',0),(b'\0' if version==12 else b'',0),(b'float\0',3)):
        raw += b'\0'*16
        raw += (b'\0\1\0'+struct.pack('>H',len(name))) if version==12 else struct.pack('>I',len(name))
        raw += name+(bytes([kind]) if version==12 else struct.pack('>I',kind<<8))
    for _ in range(2):
        header = bytearray(128);header[:4] = b'DDS '
        struct.pack_into('<I',header,4,124)
        struct.pack_into('<2I',header,12,4,4)
        struct.pack_into('<I',header,76,32)
        raw += header+b'\xff'*8
    return bytes(raw)


def read(raw):
    with patch.object(Path,'read_bytes',return_value=raw):
        return read_texture_store(Path('fixture.NXG_TEXTURES'))


class TextureInventory(unittest.TestCase):
    def test_modern_opaque_refs_and_named_cube(self):
        for cube in (False,True):
            name=b'cube\0' if cube else b'color\0'
            raw=b'TSXT'+bytes(4)+b'TSXT'+struct.pack('>I',14)+struct.pack('>I',1)+b'\0ROTV'+struct.pack('>I',1)
            raw+=bytes(16)+b'\0\1\0'+struct.pack('>H',len(name))+name+bytes([6 if cube else 0])+struct.pack('>I',255 if cube else 4)
            if cube:raw+=struct.pack('>H',len(name))+name+b'\x05'
            else:raw+=struct.pack('>3H',2,2,7)
            dds=bytearray(128);dds[:4]=b'DDS ';struct.pack_into('<I',dds,4,124);struct.pack_into('<2I',dds,12,4,4);struct.pack_into('<I',dds,76,32)
            row=read(raw+dds+bytes(8))['entries'][0]
            self.assertEqual(row['name'],name[:-1].decode());self.assertEqual(row['width'],4)
            if not cube:self.assertEqual(row['opaque_refs'],[2,7])
            if cube:
                with self.assertRaisesRegex(FormatError,'disagrees'):read(raw[:-len(name)-1]+b'fake\0\x05'+dds)
    def test_shared_slots_do_not_shift_dds_indices(self):
        for version in (1,12):
            rows = read(fixture(version))['entries']
            self.assertEqual([r['index'] for r in rows],[0,1,2])
            self.assertNotIn('offset',rows[1])
            self.assertEqual(rows[2]['kind'],3)
            self.assertGreater(rows[2]['offset'],rows[0]['offset'])

    def test_empty_store(self):
        raw = fixture();at = raw.index(b'ROTV')
        self.assertEqual(read(raw[:at+4]+b'\0'*4)['entries'],[])

    def test_empty_conversion_metadata_preserves_inventory(self):
        for version in (1,12):
            raw=fixture(version)
            raw=raw[:16]+bytes(4)+raw[28:]
            result=read(raw)
            self.assertEqual(len(result['entries']),3)
            self.assertEqual(result['entries'][0]['width'],4)
            self.assertNotIn('offset',result['entries'][1])

    def test_metadata_must_be_at_the_declared_boundary(self):
        raw=fixture().replace(b'CONVDATE',b'NOTMETA!')+b'CONVDATE'
        with self.assertRaisesRegex(FormatError,'metadata'):read(raw)
        raw=fixture()[:16]+struct.pack('>I',0xffffffff)+fixture()[20:]
        with self.assertRaisesRegex(FormatError,'metadata'):read(raw)

    def test_missing_payload_rejected(self):
        raw = fixture();last = raw.rfind(b'DDS ')
        with self.assertRaisesRegex(FormatError,'boundaries'):
            read(raw[:last])

    def test_bad_dimensions_rejected(self):
        raw = bytearray(fixture());at = raw.index(b'DDS ')
        struct.pack_into('<I',raw,at+12,0)
        with self.assertRaisesRegex(FormatError,'dimensions'):read(bytes(raw))

    def test_unknown_layout_and_truncation_rejected(self):
        raw = bytearray(fixture());struct.pack_into('>I',raw,12,35)
        with self.assertRaisesRegex(FormatError,'version'):read(bytes(raw))
        with self.assertRaises(FormatError):read(fixture()[:45])


if __name__ == '__main__':unittest.main()

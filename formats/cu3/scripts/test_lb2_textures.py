"""LEGO Batman 2 embedded textures: HGXT 9/10 lists and contiguous DDS images (synthetic)."""
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path

package=types.ModuleType('lb2_texture_fixture')
package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from lb2_texture_fixture.texture_store import read_embedded_texture_store
from lb2_texture_fixture.cu3 import FormatError


def dds(width=4, height=4):
    raw=bytearray(128);raw[:4]=b'DDS '
    struct.pack_into('<7I',raw,4,124,0x1007,height,width,0,0,1)
    struct.pack_into('<2I',raw,76,32,4);raw[84:88]=b'DXT1'
    struct.pack_into('<2I',raw,108,0x1000,0)
    return bytes(raw)+bytes(8*max(1,width//4)*max(1,height//4))


def entry(version, name, size=(4,4)):
    text=name.encode()+b'\0' if name else b''
    if version==9:
        return bytes(16)+struct.pack('>2I',*size)+bytes(29)+struct.pack('>I',len(text))+text+bytes(14)
    return bytes(16)+struct.pack('>I',len(text))+text+bytes(4)


def model(version, names, images, *, sizes=None, gap=b''):
    raw=b'NU20'+b'HGXT'+struct.pack('>I',version)+b'ROTV'+struct.pack('>I',len(names))+bytes(4*len(names))
    raw+=b'ROTV'+struct.pack('>I',len(names))
    raw+=b''.join(entry(version,n,(sizes or {}).get(i,(4,4))) for i,n in enumerate(names))
    return raw+b'ROTV'+bytes(4)+images[0]+gap+b''.join(images[1:])+b'HSEM'


class LB2Textures(unittest.TestCase):
    def read(self, data):
        f=tempfile.NamedTemporaryFile(suffix='.ghg',delete=False);f.write(data);f.close()
        self.addCleanup(Path(f.name).unlink)
        return read_embedded_texture_store(Path(f.name))

    def test_named_entries_map_to_images_in_order(self):
        for version in (9,10):
            store=self.read(model(version,['dummy.nut','','hat.nut'],[dds(),dds(8,8)],sizes={2:(8,8)}))
            entries=store['entries']
            self.assertEqual([e['name'] for e in entries],['dummy.nut','','hat.nut'])
            self.assertNotIn('offset',entries[1])
            self.assertEqual((entries[2]['width'],entries[2]['height']),(8,8))
            self.assertEqual(store['data'][entries[2]['offset']:entries[2]['offset']+4],b'DDS ')

    def test_mismatches_are_refused(self):
        with self.assertRaises(FormatError):self.read(model(9,['a.nut','b.nut'],[dds(),dds(8,8)]))
        with self.assertRaises(FormatError):self.read(model(10,['a.nut','b.nut'],[dds(),dds()],gap=bytes(4)))
        with self.assertRaises(FormatError):self.read(model(8,['a.nut'],[dds()]))
        with self.assertRaises(FormatError):self.read(model(10,['a.nut','b.nut'],[dds()]))


if __name__=='__main__':
    unittest.main()

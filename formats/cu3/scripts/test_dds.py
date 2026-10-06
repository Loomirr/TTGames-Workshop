"""DDS storage fixtures independent of game assets and Blender."""
import struct
import sys
import types
import unittest
from pathlib import Path

package=types.ModuleType('dds_fixture')
package.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from dds_fixture.dds import read_dds, read_embedded_dds
from dds_fixture.cu3 import FormatError


def header(width=4, height=4, *, fourcc=b'DXT1', mips=1, caps2=0, depth=0,
           dxgi=71, dimension=3, array=1, misc=0):
    raw=bytearray(148 if fourcc==b'DX10' else 128)
    raw[:4]=b'DDS '
    struct.pack_into('<7I',raw,4,124,0x1007|(0x800000 if depth else 0),
                     height,width,0,depth,mips)
    struct.pack_into('<2I',raw,76,32,4)
    raw[84:88]=fourcc
    struct.pack_into('<2I',raw,108,0x1000,caps2)
    if fourcc==b'DX10':struct.pack_into('<5I',raw,128,dxgi,dimension,misc,array,0)
    return raw


class DDSSpans(unittest.TestCase):
    def test_bc_small_and_nonmultiple_dimensions(self):
        for width,height,code,size in ((1,1,b'DXT1',8),(5,7,b'DXT1',32),
                                       (4,4,b'DXT5',16),(7,2,b'BC5U',32)):
            raw=header(width,height,fourcc=code)+bytes(size)+b'trailer'
            result=read_dds(raw)
            self.assertEqual(result['end'],128+size)
            self.assertEqual(result['payload_bytes'],size)
            with self.assertRaisesRegex(FormatError,'Truncated'):read_dds(raw[:128+size-1])

    def test_all_mips_are_counted(self):
        raw=header(8,8,mips=4)+bytes(32+8+8+8)
        result=read_dds(raw)
        self.assertEqual([r['bytes'] for r in result['levels']],[32,8,8,8])
        self.assertEqual(result['end'],len(raw))
        with self.assertRaisesRegex(FormatError,'Truncated'):read_dds(raw[:-1])

    def test_legacy_partial_and_full_cube_faces(self):
        for caps2,faces in ((0xfe00,6),(0x200|0x400|0x2000|0x4000,3)):
            raw=header(8,8,mips=2,caps2=caps2)+bytes((32+8)*faces)
            result=read_dds(raw)
            self.assertEqual(result['face_count'],faces)
            self.assertEqual(result['end'],len(raw))
            with self.assertRaises(FormatError):read_dds(raw[:-1])

    def test_dx10_array_and_cube_array(self):
        for misc,faces in ((0,1),(4,6)):
            raw=header(8,8,mips=2,fourcc=b'DX10',array=3,misc=misc)+bytes((32+8)*3*faces)
            result=read_dds(raw)
            self.assertEqual(result['header_bytes'],148)
            self.assertEqual(result['array_size'],3)
            self.assertEqual(result['face_count'],faces)
            self.assertEqual(result['end'],len(raw))
            with self.assertRaisesRegex(FormatError,'Truncated'):read_dds(raw[:-1])

    def test_volume_depth_shrinks_with_mips(self):
        for code in (b'DXT1',b'DX10'):
            raw=header(8,8,fourcc=code,depth=4,mips=4,caps2=0x200000,
                       dimension=4)+bytes(32*4+8*2+8+8)
            result=read_dds(raw)
            self.assertEqual([r['depth'] for r in result['levels']],[4,2,1,1])
            self.assertEqual(result['end'],len(raw))

    def test_rgb_payload_and_padded_pitch_gate(self):
        raw=header(3,2);struct.pack_into('<7I',raw,80,0x41,0,32,0xff0000,0xff00,0xff,0xff000000)
        result=read_dds(raw+bytes(24));self.assertEqual(result['payload_bytes'],24)
        struct.pack_into('<I',raw,8,0x100f);struct.pack_into('<I',raw,20,16)
        with self.assertRaisesRegex(FormatError,'padded'):read_dds(raw+bytes(32))

    def test_dxgi_storage_families(self):
        for dxgi,size in ((2,256),(6,192),(10,128),(28,64),(54,32),
                          (61,16),(66,4),(71,8),(77,16),(80,8),(98,16)):
            raw=header(fourcc=b'DX10',dxgi=dxgi)+bytes(size)
            self.assertEqual(read_dds(raw)['payload_bytes'],size)

    def test_numeric_fourcc_requires_explicit_context(self):
        raw=header(fourcc=struct.pack('<I',113))+bytes(128)
        with self.assertRaisesRegex(FormatError,'verified D3D9'):read_dds(raw)
        self.assertEqual(read_dds(raw,legacy_d3d9=True)['payload_bytes'],128)

    def test_invalid_header_format_and_limits(self):
        for field,value in ((4,123),(76,31),(12,0),(16,65537),(28,4)):
            raw=header()+bytes(256);struct.pack_into('<I',raw,field,value)
            with self.assertRaises(FormatError):read_dds(raw)
        for raw in (header(fourcc=b'WHAT')+bytes(512),
                    header(fourcc=b'DX10',dxgi=103)+bytes(512),
                    header(65536,65536)):
            with self.assertRaises(FormatError):read_dds(raw)
        with self.assertRaisesRegex(FormatError,'byte limit'):read_dds(header()+bytes(8),max_bytes=135)
        with self.assertRaisesRegex(FormatError,'DX10'):read_dds(header(fourcc=b'DX10')[:140])

    def test_invalid_cube_array_and_dimension_combinations(self):
        cases=[dict(caps2=0x200),dict(caps2=0x400),dict(caps2=0xfe00,width=8),
               dict(fourcc=b'DX10',array=0),dict(fourcc=b'DX10',array=2049),
               dict(fourcc=b'DX10',dimension=1),dict(fourcc=b'DX10',dimension=2),
               dict(fourcc=b'DX10',dimension=4,depth=4,array=2),
               dict(fourcc=b'DX10',misc=4,caps2=0x600),
               dict(fourcc=b'DX10',caps2=0xfe00),dict(depth=8)]
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaises(FormatError):
                read_dds(header(**arguments)+bytes(4096))

    def test_embedded_span_preserves_trailer_and_ignores_pixel_magic(self):
        raw=header(32,32)+bytearray(512)
        raw[160:296]=header()+bytes(8)
        result=read_embedded_dds(b'native-prefix'+raw+b'native-trailer')
        self.assertEqual(result['offset'],13)
        self.assertEqual(result['end'],13+640)
        self.assertEqual(result['trailer_end']-result['trailer_offset'],14)
        with self.assertRaisesRegex(FormatError,'multiple DDS'):
            read_embedded_dds(raw+header()+bytes(8))

    def test_explicit_span_limit_and_bad_bounds(self):
        raw=b'prefix'+header()+bytes(8)+b'trailer'
        self.assertEqual(read_dds(raw,6,limit=142)['end'],142)
        for offset,limit in ((-1,len(raw)),(6,len(raw)+1),(6,141),(10,9)):
            with self.assertRaises(FormatError):read_dds(raw,offset,limit=limit)


if __name__=='__main__':unittest.main()

"""Portable material layout/bounds checks, without proprietary assets."""
import unittest,struct,sys,types
from pathlib import Path
R=Path(__file__).resolve().parents[1];p=types.ModuleType('io_scene_lego_cu3');p.__path__=[str(R/'Addon/io_scene_lego_cu3')];sys.modules[p.__name__]=p
from io_scene_lego_cu3.material_flags import footer,read_render_flags
from io_scene_lego_cu3.native_materials import costume_slot,shader_prefix,read_materials
from unittest.mock import patch

def fixture(version,mask=15,variant=0xffffffff):
    # Independent scalar fixture: 18 historic flags, two later booleans,
    # one 190+ fixup flag, and alpha test mode.
    flags=bytearray(20+(version>=190)+1);flags[3]=125;flags[17]=mask
    raw=bytes(flags)+struct.pack('>5I2BH',1,2,3,4,0xffffffff,180,0,2)
    if version<199:raw+=struct.pack('>H',0)
    raw+=struct.pack('>2B4f2I',0,0,0.,0.,0.,0.,variant,0xffffffff)
    raw+=bytes(16+(version>=187)+(version>=191))
    return raw+struct.pack('>2I',123,2)

class MaterialFlagTests(unittest.TestCase):
    def test_modern_shader_and_footer_boundaries(self):
        for version in (229,232,234,235):
            prefix_size=0x1ae if version==229 else 0x1ad if version==232 else 0x1af
            shader_at=0x181 if version==229 else 0x180 if version==232 else 0x182
            raw=bytearray(0x480)
            struct.pack_into('>I',raw,0,2)
            struct.pack_into('>4I',raw,shader_at,4,10,2,0)
            fields,end=shader_prefix(raw,0,version)
            self.assertEqual(end,prefix_size);self.assertEqual(fields['shaderVersion'],4)
            struct.pack_into('>17iI',raw,prefix_size,*([-1]*17),17)
            raw[prefix_size+72:prefix_size+89]=bytes([4]*17)
            name_at=0x40a if version==229 else 0x3fd if version==232 else 0x3ff
            name=b'NativeMaterial\0';struct.pack_into('>H',raw,name_at,len(name));raw[name_at+2:name_at+2+len(name)]=name
            flags=bytearray(76);flags[3]=125;flags[15]=15
            struct.pack_into('>2I',flags,47,0xffffffff,0xffffffff)
            struct.pack_into('>I',flags,72,2)
            start,result=footer(flags,76,version)
            self.assertEqual(start,0);self.assertEqual(result['aref'],125);self.assertEqual(result['colourWriteMask'],15)
            model=b'LTMU'+struct.pack('>2I',version,1)+raw+flags+b'ROTV'+bytes(17)+b'TDML'
            with patch.object(Path,'read_bytes',return_value=model):
                material=read_materials(Path('fixture.GHG'))['materials'][0]
            self.assertEqual(material['texture_formats'],[4]*17)
            self.assertEqual(material['texture_ids'],[-1]*17)
            if version==229:self.assertIsNone(material['fields']['vertAlbedo'])

    def test_native_costume_role_overrides_name_guess(self):
        self.assertEqual(costume_slot({'name':'LEFTARM_GAME:VARIANT_AUTO','render_flags':{'special_id':24}}),24)
        self.assertEqual(costume_slot({'name':'LEGS_GAME','render_flags':{'special_id':8}}),8)
        self.assertIsNone(costume_slot({'name':'stud','render_flags':{'special_id':1}}))
        self.assertIsNone(costume_slot({'name':'VERTEXCOLOURS_GAME','render_flags':{'special_id':0}}))
        self.assertEqual(costume_slot({'name':'Hulk_MAT','table_version':235,'render_flags':{'special_id':3}}),3)
        self.assertEqual(costume_slot({'name':'CAPE_GAME_DX11','render_flags':{'special_id':11}}),11)

    def test_version_gates_and_no_colour_mask(self):
        for version in (174,176,177,183,187,190,191,194,198,199,202):
            with self.subTest(version=version):
                raw=b'prefix'+fixture(version,0);start,flags=footer(raw,len(raw),version)
                self.assertEqual(start,6);self.assertEqual(flags['colourWriteMask'],0)
                self.assertEqual(flags['aref'],125);self.assertEqual(flags['shortPri16bit'],2)
                self.assertEqual(flags['firstVariantIdx'],0xffffffff);self.assertEqual(flags['defaultRenderStage'],2)

    def test_bounded_record_and_final_marker(self):
        raw=b'x'*64+fixture(202)+b'ROTV'+bytes(17)+b'TDML'
        rows=read_render_flags(raw,[dict(name='material',offset=0)],202)
        self.assertEqual(rows[0]['offset'],64)

    def test_reject_bad_bounds_versions_and_variants(self):
        for data,end,version in ((b'123',3,202),(bytes(200),250,202),(bytes(200),200,203)):
            with self.assertRaises(ValueError):footer(data,end,version)
        with self.assertRaises(ValueError):read_render_flags(bytes(100),[],202)
        with self.assertRaises(ValueError):read_render_flags(bytes(100),[dict(offset=-1)],202)
        raw=b'x'*64+fixture(202,variant=99)+b'ROTV'+bytes(17)+b'TDML'
        with self.assertRaises(ValueError):read_render_flags(raw,[dict(name='bad',offset=0)],202)

if __name__=='__main__':unittest.main()

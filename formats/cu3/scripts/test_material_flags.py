"""Portable material layout/bounds checks, without proprietary assets."""
import unittest,struct,sys,types
from pathlib import Path
R=Path(__file__).resolve().parents[1];p=types.ModuleType('io_scene_lego_cu3');p.__path__=[str(R/'Addon/io_scene_lego_cu3')];sys.modules[p.__name__]=p
from io_scene_lego_cu3.material_flags import footer,read_render_flags
from io_scene_lego_cu3.native_materials import costume_slot,costume_uv_index,shader_prefix,read_materials,surface_normal_binding
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
    def normal_entry(self):
        return dict(table_version=176,texture_ids=[-1]*6+[3]+[-1]*11,
            fields=dict(surfaceMapMethod=1,surfaceMapFormat0=5,uvSets=[(0,0xffffffff)]*4+[(1,0)]+[(0,0xffffffff)]*11))

    def test_verified_normal_slot_and_uv(self):
        self.assertEqual(surface_normal_binding(self.normal_entry(),169),dict(texture=3,uv=0,packed_x_alpha=True))
        for mesh, table in ((170,191),(175,196),(175,202),(175,232),(175,234)):
            entry=self.normal_entry();entry['table_version']=table
            self.assertEqual(surface_normal_binding(entry,mesh),dict(texture=3,uv=0,packed_x_alpha=True))

    def test_normal_version_gate(self):
        for mesh,table in ((175,176),(169,175),(169,232)):
            entry=self.normal_entry();entry['table_version']=table
            self.assertIsNone(surface_normal_binding(entry,mesh))

    def test_unknown_surface_encoding_is_not_a_normal(self):
        entry=self.normal_entry();entry['fields']['surfaceMapFormat0']=4
        self.assertIsNone(surface_normal_binding(entry,169))

    def test_normal_requires_enabled_valid_uv(self):
        for uv in ((0,0),(1,0xffffffff),(1,16)):
            entry=self.normal_entry();entry['fields']['uvSets'][4]=uv
            self.assertIsNone(surface_normal_binding(entry,169))

    def test_absent_normal_texture_not_assigned(self):
        entry=self.normal_entry();entry['texture_ids'][6]=-1
        self.assertIsNone(surface_normal_binding(entry,169))

    def test_174_prefix_two_byte_boundary_and_opaque_flags(self):
        raw=bytearray(0x3c1)
        struct.pack_into('>3I',raw,0,2,2,2)
        struct.pack_into('>I',raw,104,1)
        for i in range(16):struct.pack_into('>2I',raw,122+i*8,1 if i==0 else 0,0 if i==0 else 0xffffffff)
        struct.pack_into('>4I',raw,329,4,10,2,4)
        struct.pack_into('>18i',raw,406,3,*([-1]*17))
        name=b'OlderAttachment\0';raw+=struct.pack('>H',len(name))+name
        model=b'LTMU'+struct.pack('>3I',174,1,1)+raw+fixture(174)+b'ROTV'+bytes(17)+b'TDML'
        fields,end=shader_prefix(raw,0,174)
        self.assertEqual(end,406);self.assertEqual(fields['shaderVersion'],4)
        with patch.object(Path,'read_bytes',return_value=model):
            entry=read_materials(Path('fixture.GHG'))['materials'][0]
        self.assertEqual(entry['texture_ids'],[3]+[-1]*17)
        self.assertIsNone(entry['fields']['vertAlbedo'])
        self.assertIsNone(entry['fields']['canAlphaBlend'])

    def test_legacy_static_shader_prefix_and_footer(self):
        raw=bytearray(0x3c1)
        struct.pack_into('>3I',raw,0,2,2,2)
        for i in range(16):struct.pack_into('>2I',raw,120+i*8,1 if i==0 else 0,0 if i==0 else 0xffffffff)
        struct.pack_into('>4I',raw,319,4,10,2,4)
        struct.pack_into('>18i',raw,397,3,*([-1]*17))
        name=b'LegacyAccessory\0';raw+=struct.pack('>H',len(name))+name
        model=b'LTMU'+struct.pack('>3I',163,1,1)+raw+fixture(163)+b'ROTV'+bytes(17)+b'TDML'
        with patch.object(Path,'read_bytes',return_value=model):
            entry=read_materials(Path('fixture.GSC'))['materials'][0]
        self.assertEqual(entry['fields']['uvSets'][0],(1,0))
        self.assertEqual(entry['texture_ids'],[3]+[-1]*17)
        self.assertEqual(entry['render_flags']['colourWriteMask'],15)
        self.assertEqual(entry['render_flags']['firstVariantIdx'],0xffffffff)
        self.assertIsNone(entry['fields']['vertAlbedo'])
        struct.pack_into('>I',raw,124,99)
        with self.assertRaises(ValueError):shader_prefix(raw,0,163)

    def test_modern_shader_and_footer_boundaries(self):
        for version in (229,232,234,235):
            prefix_size={229:0x1ae,232:0x1a9,234:0x1ab,235:0x1ab}[version]
            shader_at=0x181 if version==229 else 0x180 if version==232 else 0x182
            raw=bytearray(0x480)
            struct.pack_into('>I',raw,0,2)
            struct.pack_into('>4I',raw,shader_at,4,10,2,0)
            if version in (232,234,235):
                uv_at=0x9a if version==232 else 0x9c
                struct.pack_into('>I',raw,uv_at-18,2);raw[uv_at-1]=4
                for i in range(17):struct.pack_into('>2I',raw,uv_at+i*8,1 if i in (0,4) else 0,2 if i==4 else 0 if i==0 else 0xffffffff)
            fields,end=shader_prefix(raw,0,version)
            self.assertEqual(end,prefix_size);self.assertEqual(fields['shaderVersion'],4)
            slots=18 if version in (232,234,235) else 17
            texture_ids=[-1]*slots;texture_ids[0]=2;texture_ids[6]=5
            struct.pack_into('>'+str(slots)+'iI',raw,prefix_size,*texture_ids,17)
            raw[prefix_size+slots*4+4:prefix_size+slots*4+21]=bytes([4]*17)
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
            self.assertEqual(material['texture_ids'],texture_ids)
            if version in (229,232,234,235):self.assertIsNone(material['fields']['vertAlbedo'])
            if version in (232,234,235):
                self.assertEqual(material['fields']['uvSets'][0],(1,0))
                self.assertEqual(material['fields']['uvSets'][4],(1,2))
                self.assertEqual(material['fields']['numBones'],4)
                self.assertEqual(material['fields']['numUVSets'],2)
                struct.pack_into('>I',raw,uv_at+4,99)
                with self.assertRaises(ValueError):shader_prefix(raw,0,version)

    def test_native_costume_role_overrides_name_guess(self):
        self.assertEqual(costume_slot({'name':'LEFTARM_GAME:VARIANT_AUTO','render_flags':{'special_id':24}}),24)
        self.assertEqual(costume_slot({'name':'LEGS_GAME','render_flags':{'special_id':8}}),8)
        self.assertIsNone(costume_slot({'name':'stud','render_flags':{'special_id':1}}))
        self.assertIsNone(costume_slot({'name':'VERTEXCOLOURS_GAME','render_flags':{'special_id':0}}))
        self.assertEqual(costume_slot({'name':'Hulk_MAT','table_version':235,'render_flags':{'special_id':3}}),3)
        self.assertEqual(costume_slot({'name':'CAPE_GAME_DX11','render_flags':{'special_id':11}}),11)

    def test_lmsh1_print_uv_exception_is_layout_and_role_gated(self):
        def entry(name,role,version=176):
            return dict(name=name,table_version=version,render_flags={'special_id':role},fields={'uvSets':[(1,0)]})
        for name,role in (('LEFTARM_GAME',24),('RIGHTARM_GAME:VARIANT',5),
                          ('HEAD_FRONT_GAME',1),('HEAD_BACK_GAME:VARIANT',2)):
            self.assertEqual(costume_uv_index(entry(name,role),169),0)
            self.assertEqual(costume_uv_index(entry(name,role),175),1)
            self.assertEqual(costume_uv_index(entry(name,role,202),169),1)
        self.assertEqual(costume_uv_index(entry('LEFTARM_GAME',7),169),1)
        self.assertEqual(costume_uv_index(entry('HEAD_FRONT_GAME',7),169),1)
        self.assertEqual(costume_uv_index(entry('BODY_FRONT_GAME',3),169),1)
        self.assertEqual(costume_uv_index(entry('RIGHTARM_GAME_DX11',5,202),175),1)
        accessory=entry('Hat',0);accessory['fields']['uvSets']=[(1,2)]
        self.assertEqual(costume_uv_index(accessory,169),2)
        accessory['fields']['uvSets']=[(0,0xffffffff)]
        self.assertEqual(costume_uv_index(accessory,169),0)

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

    def test_shader_fields_cannot_borrow_bytes_from_the_next_region(self):
        for version,size in ((163,397),(174,406),(229,0x1ae),(232,0x1a9)):
            raw=bytes(2048)
            with self.subTest(version=version),self.assertRaisesRegex(ValueError,'span'):
                shader_prefix(raw,0,version,limit=size-1)

    def test_name_and_texture_spans_cannot_overlap_footer(self):
        raw=b'x'*64+fixture(202)+b'ROTV'+bytes(17)+b'TDML'
        for field in ('name_end','texture_end','prefix_end'):
            entry=dict(name='bad',offset=0);entry[field]=65
            with self.assertRaisesRegex(ValueError,'overlaps'):
                read_render_flags(raw,[entry],202,table_end=len(raw)-4)

    def test_tdml_inside_a_material_is_not_a_table_boundary(self):
        raw=bytearray(0x3c1);struct.pack_into('>3I',raw,0,2,2,2)
        for i in range(16):struct.pack_into('>2I',raw,120+i*8,0,0xffffffff)
        struct.pack_into('>4I',raw,319,4,10,2,4)
        struct.pack_into('>18i',raw,397,*([-1]*18))
        raw[650:654]=b'TDML'
        name=b'MarkerInOpaqueField\0';raw+=struct.pack('>H',len(name))+name
        model=b'LTMU'+struct.pack('>3I',163,1,1)+raw+fixture(163)+b'ROTV'+bytes(17)+b'TDML'
        with patch.object(Path,'read_bytes',return_value=model):
            parsed=read_materials(Path('fixture.DX11.GSC'))
        entry=parsed['materials'][0]
        self.assertEqual(entry['name'],'MarkerInOpaqueField')
        self.assertLessEqual(entry['name_end'],entry['footer_offset'])
        self.assertEqual(parsed['table_end'],len(model))
        # Adjacent unverified versions do not inherit this layout from a suffix.
        for version in (164,172,173,228,230,231,233,236):
            bad=bytearray(model);struct.pack_into('>I',bad,4,version)
            with patch.object(Path,'read_bytes',return_value=bad),self.assertRaisesRegex(ValueError,'version/count'):
                read_materials(Path('fixture.NXG.GSC'))

    def test_explicit_table_boundary_is_validated(self):
        raw=b'x'*64+fixture(202)+b'ROTV'+bytes(17)+b'FAKE'
        with self.assertRaisesRegex(ValueError,'boundary'):
            read_render_flags(raw,[dict(name='material',offset=0)],202,table_end=len(raw)-4)

if __name__=='__main__':unittest.main()

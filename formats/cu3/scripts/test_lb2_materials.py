"""LEGO Batman 2 UMTL 106-132: texture IDs, 91-byte footer and HSCB boundary (synthetic tables)."""
import struct
import sys
import types
import unittest
from pathlib import Path

source=Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3'
package=types.ModuleType('lb2_material_fixture');package.__path__=[str(source)];sys.modules[package.__name__]=package
from lb2_material_fixture.native_materials import read_materials_bytes
from lb2_material_fixture.cu3 import FormatError

LAYOUT={132:(389,903,18),125:(346,844,16),123:(345,843,16),121:(342,840,16),111:(342,839,16),108:(341,838,16),106:(341,838,16)}
TAIL={106:8,108:10,111:10,121:10,123:11}


def footer(*,cull=0,cwm=15,cast=1,first=0xffffffff,tail=12,alpha_test=True):
    flags=bytearray(19);flags[4]=cull;flags[8]=3;flags[11]=1;flags[15]=cast;flags[17]=cwm;flags[18]=8
    if not alpha_test:flags=flags[:18]                      # UMTL 106
    body=bytes(flags)+struct.pack('>5I',0,0,0,0,3)+bytes(2)+struct.pack('>2H',0,0)+bytes(2)
    body+=struct.pack('>4f',1,1,1,1)+struct.pack('>2I',first,0xffffffff)+bytes((0,0,1,0,0,0,0,0,1,0,0,0)[:tail])
    body+=struct.pack('>2I',0x42,0)
    assert len(body)==60+len(flags)+tail
    return body


def record(version,name,textures,**flags):
    tex,name_at,slots=LAYOUT[version]
    raw=bytearray(name_at);struct.pack_into('>I',raw,0,2)
    ids=[-1]*slots
    for slot,value in textures.items():ids[slot]=value
    struct.pack_into(f'>{slots}i',raw,tex,*ids)
    text=name.encode()+b'\0'
    return bytes(raw)+struct.pack('>H',len(text))+text+bytes(11)+footer(tail=TAIL.get(version,12),alpha_test=version!=106,**flags)


def table(version,records,*,end=b'\x01HSCB'):
    return b'LTMU'+struct.pack('>3I',version,len(records),len(records))+b''.join(records)+end+bytes(12)


class LB2Materials(unittest.TestCase):
    def test_version_132_textures_and_footer(self):
        data=table(132,[record(132,'LEGO_Hard:Base',{0:3,4:3}),record(132,'BODY_BACK_GAME',{0:6},cull=2,cast=0)])
        result=read_materials_bytes(data)
        self.assertEqual([m['name'] for m in result['materials']],['LEGO_Hard:Base','BODY_BACK_GAME'])
        self.assertEqual(result['materials'][0]['texture_ids'][:5],[3,-1,-1,-1,3])
        self.assertEqual(len(result['materials'][0]['texture_ids']),18)
        flags=result['materials'][1]['render_flags']
        self.assertEqual((flags['cull'],flags['castShadows'],flags['colourWriteMask'],flags['alphaTestMode']),(2,0,15,8))
        self.assertEqual((flags['localTID'],flags['name_ix'],flags['su']),(3,0x42,1.0))
        self.assertEqual(result['materials'][0]['fields']['version'],2)
        self.assertIsNone(result['materials'][0]['fields']['shaderType'])

    def test_version_125_has_sixteen_slots(self):
        result=read_materials_bytes(table(125,[record(125,'Prop',{0:1,6:2}),record(125,'Prop2',{})]))
        self.assertEqual(result['materials'][0]['texture_ids'],[1,-1,-1,-1,-1,-1,2]+[-1]*9)

    def test_versions_106_to_123_have_shorter_tails(self):
        for version,tail in TAIL.items():
            result=read_materials_bytes(table(version,[record(version,'Prop',{0:1,15:2}),record(version,'Glow',{},cull=2)]))
            self.assertEqual(result['materials'][0]['texture_ids'],[1]+[-1]*14+[2])
            flags=result['materials'][1]['render_flags']
            self.assertEqual((flags['cull'],flags['colourWriteMask'],flags['localTID']),(2,15,3))
            self.assertEqual(len(flags['lb2TailFlags']),tail)
            self.assertEqual(flags['alphaTestMode'],None if version==106 else 8)
        # A 123 table read with 121's shorter tail does not fit.
        data=bytearray(table(123,[record(123,'A',{0:0}),record(123,'B',{0:0})]))
        struct.pack_into('>I',data,4,121)
        with self.assertRaises((FormatError,ValueError)):read_materials_bytes(bytes(data))

    def test_boundary_and_versions_are_strict(self):
        records=[record(132,'A',{0:0}),record(132,'B',{0:0})]
        with self.assertRaises(FormatError):read_materials_bytes(table(132,records,end=b'\x00HSCB'))
        with self.assertRaises(FormatError):read_materials_bytes(table(132,records,end=b'\x01XXXX'))
        for version in (119,124,131):
            with self.assertRaises(FormatError):read_materials_bytes(table(version,records))

    def test_unverified_footer_values_are_refused(self):
        with self.assertRaises((FormatError,ValueError)):
            read_materials_bytes(table(132,[record(132,'A',{0:0},first=7),record(132,'B',{0:0})]))


if __name__=='__main__':
    unittest.main()

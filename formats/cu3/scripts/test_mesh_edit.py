"""Independent native vertex fixtures: byte order, bounds and round trips."""
import hashlib
import struct
import sys
import types
import unittest
from pathlib import Path

pkg=types.ModuleType('mesh_fixture');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')];sys.modules[pkg.__name__]=pkg
from mesh_fixture.native_mesh import read_mesh_bytes
from mesh_fixture.mesh_edit import patch_vertices,SCHEMA
from mesh_fixture.cu3 import FormatError


def fixture(version=175):
    dx=version==175;e='<' if dx else '>'
    raw=b'HSEM'+struct.pack('>I',version)+(b'' if dx else b'ROTV')+struct.pack('>I',1)
    if dx:raw+=struct.pack('>I',1)
    raw+=struct.pack('>I',1) # stream count
    raw+=struct.pack('>3I',1,0,3)+b'DXTV'+struct.pack('>2I',169,3)
    raw+=bytes((0,3,0,5,5,12,2,9,16))+bytes(6)
    for x,y,z in ((0,0,0),(1,0,0),(0,1,1)):
        raw+=struct.pack(e+'3f2e',x,y,z,x,y)+bytes((30,20,10,255) if dx else (10,20,30,255))
    raw+=struct.pack('>2I',0,0) # byte offset, reserved
    raw+=struct.pack('>4I',1,0,3,2)+struct.pack(e+'3H',0,1,2)
    raw+=struct.pack('>3IH3I',0,3,0,0,3,0,0) # index range, count, reserved, palette size
    raw+=bytes(4)+bytes(4)+bytes(36) # targets terminator, retained word, bounds
    if not dx:raw+=bytes(32)
    return raw


def edits(data,changes):
    return dict(schema=SCHEMA,sha256=hashlib.sha256(data).hexdigest(),mesh_version=read_mesh_bytes(data)['mesh_version'],parts={'0':changes})


def face_fixture(version=175):
    dx=version==175;raw=fixture(version)[:-(44 if dx else 76)]
    raw+=struct.pack('>3I',1,17,0)+(b'ROTV' if dx else b'')
    raw+=struct.pack('>I9f',3,*([0.]*9))+bytes(21)
    raw+=(b'' if dx else bytes(4))+bytes(36)+(b'' if dx else bytes(32))
    return raw


class MeshEdits(unittest.TestCase):
    def test_face_basis_is_immutable_but_uv_edits_are_allowed(self):
        for version in (169,170,175):
            raw=face_fixture(version)
            with self.assertRaisesRegex(FormatError,'Basis'):
                patch_vertices(raw,edits(raw,{'position':[[0,0,0],[.5,0,0],[0,1,1]]}))
            output,report=patch_vertices(raw,edits(raw,{'uv':[[.5,.5],[1,0],[0,1]]}))
            self.assertEqual(read_mesh_bytes(output)['parts'][0]['morphs'],read_mesh_bytes(raw)['parts'][0]['morphs'])
    def test_shared_buffer_changes_are_reported_and_conflicts_rejected(self):
        raw=bytearray(fixture());struct.pack_into('>I',raw,8,2)
        raw+=struct.pack('>2I',1,1)+struct.pack('>2I',0xc0000100,1)+struct.pack('>2I',0,0)
        raw+=struct.pack('>2I',0xc0000101,1)+struct.pack('>3IH3I',0,3,0,0,3,0,0)+bytes(44)
        raw=bytes(raw);manifest=edits(raw,{'color':[[99,50,25,255]]*3})
        output,report=patch_vertices(raw,manifest)
        self.assertEqual(len(report['shared_buffer_changes']),3)
        self.assertEqual(read_mesh_bytes(output)['parts'][1]['vertices'][0]['color'],[99,50,25,255])
        manifest['parts']['1']={'color':[[1,2,3,255]]*3}
        with self.assertRaisesRegex(FormatError,'Conflicting'):patch_vertices(raw,manifest)
    def test_noop_preserves_exact_bytes_for_all_three_versions(self):
        for version in (169,170,175):
            raw=fixture(version);part=read_mesh_bytes(raw)['parts'][0]
            changes={f:[v[f] for v in part['vertices']] for f in ('position','uv','color')}
            output,report=patch_vertices(raw,edits(raw,changes))
            self.assertEqual(output,raw);self.assertEqual(report['changed_bytes'],0)

    def test_position_half_uv_and_bgra_color_roundtrip(self):
        for version in (169,170,175):
            raw=fixture(version);changes={'position':[[0,0,0],[.5,0,0],[0,1,1]],'uv':[[.25,.75],[1,0],[0,1]],'color':[[90,50,10,255]]*3}
            output,report=patch_vertices(raw,edits(raw,changes));part=read_mesh_bytes(output)['parts'][0]
            self.assertEqual(len(output),len(raw));self.assertGreater(report['changed_bytes'],0)
            for field,rows in changes.items():self.assertEqual([v[field] for v in part['vertices']],rows)
            changed={i for i,(a,b) in enumerate(zip(raw,output)) if a!=b}
            allowed={i for w in report['writes'] for i in range(w['offset'],w['offset']+w['bytes'])}
            self.assertTrue(changed<=allowed)

    def test_invalid_count_nonfinite_bounds_hash_and_attribute_rejected(self):
        raw=fixture()
        for changes in ({'position':[[0,0,0]]},{'position':[[0,0,0],[2,0,0],[0,1,1]]},{'uv':[[float('nan'),0]]*3},{'weights':[]},{'color':[[0.,0,0,0]]*3}):
            with self.assertRaises(FormatError):patch_vertices(raw,edits(raw,changes))
        manifest=edits(raw,{});manifest['sha256']='bad'
        with self.assertRaises(FormatError):patch_vertices(raw,manifest)

if __name__=='__main__':unittest.main()

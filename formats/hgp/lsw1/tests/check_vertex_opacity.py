"""Decode packed alpha on real primitive records, including subset remapping."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec=importlib.util.spec_from_file_location('lsw1_opacity_reader',Path(__file__).parents[1]/'hgp.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)

def primitive(vertex_type):
    h=reader.HGP.__new__(reader.HGP);h.path=Path('primitive.hgp');h.count=1
    h.body=bytearray(512);geometry=64;prim=144;indices=224
    struct.pack_into('<I',h.body,12,geometry)
    for at,value in ((geometry+8,0),(geometry+12,vertex_type),(geometry+28,1),(geometry+48,prim),
                     (prim+4,5),(prim+12,indices)):
        struct.pack_into('<I',h.body,at,value)
    struct.pack_into('<H',h.body,prim+8,3)
    struct.pack_into('<3H',h.body,indices,2,0,1)
    stride=36 if vertex_type==0x59 else 56;raw=bytearray(stride*3)
    for index,alpha in enumerate((0,118,255)):
        at=index*stride;struct.pack_into('<3f',raw,at,index%2,index//2,0)
        if vertex_type==0x5d:
            struct.pack_into('<5f',raw,at+12,1.,0.,0.,0.,0.)
            struct.pack_into('<2H',h.body,prim+20,1,0)
        struct.pack_into('<3f',raw,at+(12 if vertex_type==0x59 else 32),0,0,1)
        struct.pack_into('<4B',raw,at+(24 if vertex_type==0x59 else 44),72,72,72,alpha)
        struct.pack_into('<2f',raw,at+(28 if vertex_type==0x59 else 48),0,0)
    h.buffers=[bytes(raw)]
    return h

class OpacityTests(unittest.TestCase):
    def test_rigid_and_skinned_alpha_follow_native_vertex_remap(self):
        for kind in (0x59,0x5d):
            with self.subTest(vertex_type=hex(kind)):
                h=primitive(kind);p=list(h.object_meshes(0,0 if kind==0x59 else None))[0]
                self.assertEqual(p['colors'],[(72,72,72,0),(72,72,72,118),(72,72,72,255)])
                self.assertEqual(p['faces'],[(2,1,0)])
                self.assertTrue(all(w=={0:1.0} for w in p['weights']))

    def test_unused_vertices_do_not_shift_native_opacity_indices(self):
        h=primitive(0x59);struct.pack_into('<3H',h.body,224,2,2,0)
        p=list(h.object_meshes(0,0))[0]
        self.assertEqual(p['colors'],[(72,72,72,0),(72,72,72,255)])
        self.assertEqual(len(p['vertices']),2)
        self.assertEqual(p['faces'],[])

if __name__=='__main__':unittest.main()

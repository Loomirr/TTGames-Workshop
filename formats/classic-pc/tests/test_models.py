"""Constructed malformed NU20 checks; original assets are tested separately."""
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nu20 import NU20, unpack, decode_vertex_format


class ClassicModels(unittest.TestCase):
    def test_negative_offsets_cannot_wrap(self):
        with self.assertRaisesRegex(ValueError,'outside'):unpack('<I',bytes(16),-4)

    def test_future_version_and_truncated_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'file.ghg'
            p.write_bytes(struct.pack('<4siIi',b'NU20',-16,99,-1)+bytes(16))
            with self.assertRaisesRegex(ValueError,'version'):NU20(p)
            p.write_bytes(struct.pack('<4siIi',b'NU20',-4096,4,-1)+bytes(16))
            with self.assertRaisesRegex(ValueError,'metadata'):NU20(p)

    def test_container_version_gate(self):
        # Version 3 (LB1 and LIJ1 PC) passes the gate and fails later on the truncated fixture;
        # unobserved versions are still refused at the gate.
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'file.ghg'
            for version in (1,2,3,4):
                p.write_bytes(struct.pack('<4siIi',b'NU20',-4096,version,-1)+bytes(16))
                with self.assertRaisesRegex(ValueError,'metadata'):NU20(p)
            for version in (0,5,99):
                p.write_bytes(struct.pack('<4siIi',b'NU20',-4096,version,-1)+bytes(16))
                with self.assertRaisesRegex(ValueError,'version'):NU20(p)

    def test_pointer_and_count_limits(self):
        n=NU20.__new__(NU20);n.nu20_size=16;n.d=struct.pack('<i',-100)+bytes(20)
        with self.assertRaises(ValueError):n.ptr(0)
        for at,count,stride in ((0,1,4),(8,4,4),(8,-1,4),(8,1000001,0)):
            with self.assertRaises(ValueError):n.table(at,count,stride,'fixture')

    def test_observed_packed_skin_layout(self):
        fmt,stride=decode_vertex_format(0x28909)
        fields={n:(k,o) for n,k,o in fmt}
        self.assertEqual(stride,36)
        self.assertEqual(fields['blend_weights'],('byte4',28))
        self.assertEqual(fields['blend_indices'],('byte4',32))

    def test_non_vector_slots_are_not_normals(self):
        fmt,_=decode_vertex_format(0x2000080)
        self.assertIn('unknown_2000000',[x[0] for x in fmt])
        self.assertNotIn('bitangent',[x[0] for x in fmt])


def layer_fixture(rigid_target=None, second=False, count=2):
    """Constructed TCS-style character layer table (no game data): 2 joints, 3 special objects."""
    d=bytearray(0x1000);g=0x100;so_at=0x800
    def rel(at,target):struct.pack_into('<i',d,at,target-at if target else 0)
    def record(at,special):rel(at+8,so_at+special*0xD0 if special>=0 else 0x7F0)
    struct.pack_into('<i',d,g+0x18C,count);rel(g+0x190,0x400)
    d[0x300:0x304]=b'TT1\0'
    rel(0x400,0x300);rel(0x404,0x600);rel(0x408,0x700)            # layer 0: name, rigid table, skin
    rel(0x600+4,0x710)                                             # joint 1 -> record 0x710
    record(0x700,0);record(0x710,1 if rigid_target is None else rigid_target)
    rel(0x414+12,0x620 if second else 0);rel(0x414+16,0x720)       # layer 1: unnamed, extra object
    if second:rel(0x620,0x700)
    record(0x720,2)
    n=NU20.__new__(NU20);n.d=bytes(d);n.nu20_size=len(d);n.gsnh=g;n.special_at=so_at
    n.bones=[{'name':'root'},{'name':'head'}];n.special_objects=[{'index':i} for i in range(3)]
    return n


class ClassicCharacterLayers(unittest.TestCase):
    def test_observed_layout(self):
        result=layer_fixture().character_layers()
        self.assertEqual([l['name'] for l in result['layers']],['TT1',''])
        self.assertEqual(result['rigid'],{1:(1,0)})
        self.assertEqual((result['layers'][0]['skin'],result['layers'][1]['extra']),(0,2))
        self.assertEqual(result['notes'],[])

    def test_second_joint_table_is_counted_not_decoded(self):
        result=layer_fixture(second=True).character_layers()
        self.assertEqual(result['layers'][1]['second_joint_entries'],1)
        self.assertEqual(len(result['notes']),1)

    def test_object_must_be_a_special_object_record(self):
        with self.assertRaisesRegex(ValueError,'special object'):layer_fixture(rigid_target=-1).character_layers()

    def test_rigid_and_layer_object_cannot_overlap(self):
        with self.assertRaisesRegex(ValueError,'both'):layer_fixture(rigid_target=0).character_layers()

    def test_layer_count_and_extent(self):
        for count in (-1,0,65):
            with self.assertRaisesRegex(ValueError,'layer count'):layer_fixture(count=count).character_layers()
        n=layer_fixture();n.nu20_size=0x410                          # table runs past the metadata
        with self.assertRaisesRegex(ValueError,'outside'):n.character_layers()

    def test_no_skeleton_means_no_layers(self):
        n=layer_fixture();n.bones=[]
        self.assertEqual(n.character_layers()['layers'],[])

if __name__=='__main__':unittest.main()

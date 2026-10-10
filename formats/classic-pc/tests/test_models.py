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


if __name__=='__main__':unittest.main()

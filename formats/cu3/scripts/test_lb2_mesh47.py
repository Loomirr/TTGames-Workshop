"""LEGO Batman 2 MESH 47: full records, depth copies, 40/72-byte tails and buffer numbering (synthetic fixtures)."""
import struct
import sys
import types
import unittest
from pathlib import Path

pkg=types.ModuleType('mesh47_fixture');pkg.__path__=[str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')];sys.modules[pkg.__name__]=pkg
from mesh47_fixture.native_mesh import read_mesh_bytes
from mesh47_fixture.cu3 import FormatError

TRIANGLE=((0,0,0),(1,0,0),(0,1,1))


def vertices(points, colour=False):
    """A new untagged vertex buffer: position float3 (and a colour byte4)."""
    desc=bytes((0,3,0,2,9,12)) if colour else bytes((0,3,0))
    raw=struct.pack('>4I',1,0,len(points),len(desc)//3)+desc
    for p in points:raw+=struct.pack('>3f',*p)+(bytes((10,20,30,255)) if colour else b'')
    return raw


def full(*, word=1, long_tail=False):
    raw=struct.pack('>I',word)+vertices(TRIANGLE,colour=True)+struct.pack('>I',0)
    raw+=struct.pack('>I',0)+struct.pack('>4I',1,0,6,2)+struct.pack('>6H',0,1,2,0,1,2)   # depth=0, new index buffer
    raw+=struct.pack('>3IH3I',0,3,0,0,3,0,0)+struct.pack('>I',0)                       # ranges, vertex count, palette, morphs
    raw+=struct.pack('>I9f',2,0,0,0,1,0.5,0.5,0.5,0,0.7)+(bytes(32) if long_tail else b'')
    return raw


def depth(reference, *, first_vertex=0, repeated=0, word=1):
    """Depth copy: own position-only buffer, the shared index buffer by reference."""
    raw=struct.pack('>I',word)+vertices(TRIANGLE)+struct.pack('>I',0)
    raw+=struct.pack('>I',3)+struct.pack('>2I',0xc0000000|reference,1)
    return raw+struct.pack('>3I',first_vertex,3,repeated)


def section(*records, count=1):
    return b'HSEM'+struct.pack('>2I',47,count)+b''.join(records)+struct.pack('>I',1)+b'LTMU'


class LB2Mesh47(unittest.TestCase):
    def test_full_record_and_depth_copy(self):
        for long_tail in (False,True):
            data=section(full(long_tail=long_tail),depth(0x21))
            mesh=read_mesh_bytes(data)
            self.assertEqual(mesh['end_offset'],len(data)-8)
            part,=mesh['parts'];copy,=mesh['depth_copies']
            self.assertEqual(part['triangles'],[[0,1,2]])
            self.assertEqual([v['color'] for v in part['vertices']],[[10,20,30,255]]*3)
            self.assertEqual((copy['of_part'],copy['first_index'],copy['index_count']),(0,3,3))
            self.assertEqual([v['position'] for v in copy['vertices']],[v['position'] for v in part['vertices']])

    def test_depth_copies_may_follow_the_last_full_record(self):
        mesh=read_mesh_bytes(section(full(),depth(5,word=0x25),depth(5,word=0x601)))
        self.assertEqual((len(mesh['parts']),len(mesh['depth_copies'])),(1,2))

    def test_unverified_records_are_refused(self):
        with self.assertRaisesRegex(FormatError,'depth record'):read_mesh_bytes(section(full(),depth(5,repeated=1)))
        with self.assertRaises(FormatError):read_mesh_bytes(section(depth(5),full()))   # nothing to copy
        with self.assertRaisesRegex(FormatError,'only on depth copies'):read_mesh_bytes(section(full(word=0x25)))
        with self.assertRaisesRegex(FormatError,'record word'):read_mesh_bytes(section(full(word=3)))
        with self.assertRaisesRegex(FormatError,'beyond the declared'):read_mesh_bytes(section(full(),full()))
        with self.assertRaisesRegex(FormatError,'long part tail'):
            read_mesh_bytes(section(full(long_tail=True)[:-4]+struct.pack('>I',7)))


if __name__=='__main__':
    unittest.main()

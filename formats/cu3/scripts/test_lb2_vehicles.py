"""LEGO Batman 2 (HGOL 9) vehicle collision groups in the variant trailer (synthetic fixtures, no game files)."""
import struct
import sys
import types
import unittest
from pathlib import Path
package = types.ModuleType('lb2_vehicle_fixture')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from lb2_vehicle_fixture.cu3 import FormatError, Reader
from lb2_vehicle_fixture.native_variants import _trailer

JOINTS = 3
NORMALS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


def hull(normals=NORMALS, corners_per_face=4, tail=None):
    raw = struct.pack('>I', len(normals))
    raw += b''.join(struct.pack('>3fI', *n, corners_per_face) for n in normals)
    count = len(normals) * corners_per_face
    raw += struct.pack('>I', count)
    raw += b''.join(struct.pack('>3fI', i * .01, 0, 0, len(normals) if tail is None else tail) for i in range(count))
    return raw


def group(kind=0, hulls=(), joint=1, primitive=None):
    raw = struct.pack('>2I', 0, kind)
    if kind == 1:
        raw += struct.pack('>14f', *(primitive or [0.0] * 14))
    return raw + struct.pack('>I', len(hulls)) + b''.join(hulls) + bytes([joint])


def standard_fields(threshold=0.0):
    raw = bytes(8) + struct.pack('>6f', -1, -1, -1, 1, 1, 1) + bytes(12) + struct.pack('>f', threshold)
    joint_map = struct.pack('>I', JOINTS) + bytes(range(JOINTS))
    return raw + joint_map + joint_map + struct.pack('>f', 1) + struct.pack('>I', 0) + b'\0'


def tail(groups, version=9):
    return struct.pack('>I', len(groups)) + b''.join(groups) + standard_fields()


def read(raw, version=9):
    candidate = dict(end_offset=0, version=version, joints=[{}] * JOINTS)
    return _trailer(raw, Reader(raw), candidate)


class LB2VehicleCollision(unittest.TestCase):
    def test_hull_and_primitive_groups_are_read_to_the_standard_fields(self):
        prim = [float(i) for i in range(14)]
        raw = tail([group(0, [hull()], 2), group(1, [], 1, prim), group(1, [hull()], 0, prim)])
        result = read(raw)
        self.assertEqual(result['end_offset'], len(raw))
        self.assertEqual(result['joint_map'], [0, 1, 2])
        groups = result['collision']
        self.assertEqual([(g['type'], g['joint'], len(g['hulls'])) for g in groups], [(0, 2, 1), (1, 1, 0), (1, 0, 1)])
        self.assertEqual(groups[1]['primitive'], prim)
        box = groups[0]['hulls'][0]
        self.assertEqual(len(box['faces']), 6)
        self.assertEqual(len(box['corners']), 24)
        self.assertEqual(box['faces'][2], dict(normal=[0.0, 1.0, 0.0], corners=4))

    def test_no_collision_keeps_the_existing_trailer_fields(self):
        raw = struct.pack('>I', 0) + standard_fields()
        self.assertNotIn('collision', read(raw))

    def test_inconsistent_collision_is_refused(self):
        bad = {
            'joint outside the rig': tail([group(0, [hull()], JOINTS)]),
            'unknown group type': tail([group(2, [hull()], 1)]),
            'type 0 without hulls': tail([group(0, [], 1)]),
            'corner field differs from the face count': tail([group(0, [hull(tail=5)], 1)]),
            'normal not unit length': tail([group(0, [hull(normals=((2, 0, 0),) + NORMALS[1:])], 1)]),
            'too few corners per face': tail([group(0, [hull(corners_per_face=2)], 1)]),
        }
        for name, raw in bad.items():
            with self.subTest(name), self.assertRaises(FormatError):
                read(raw)
        broken = bytearray(tail([group(0, [hull()], 1)]))
        struct.pack_into('>I', broken, 4 + 8 + 4 + 6 * 16, 23)
        with self.assertRaises(FormatError):
            read(bytes(broken))

    def test_only_hgol9_reads_collision(self):
        raw = tail([group(0, [hull()], 1)])
        with self.assertRaisesRegex(FormatError, 'exceeds its verified bound'):
            read(raw, version=10)


if __name__ == '__main__':
    unittest.main()

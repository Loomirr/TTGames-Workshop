"""LEGO Batman 2 MESH 48 vertex animation: a frame count and position-only frame streams after a part's streams
(synthetic fixtures)."""
import struct
import sys
import types
import unittest
from unittest.mock import patch
from pathlib import Path

pkg = types.ModuleType('mesh48_frames_fixture')
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
from mesh48_frames_fixture.native_mesh import read_mesh_bytes
from mesh48_frames_fixture.cu3 import FormatError

TRIANGLE = ((0, 0, 0), (1, 0, 0), (0, 1, 1))


def fixture(version=48, *, frames=2, own_position=False, frame_descriptor=(0, 3, 0)):
    raw = b'HSEM' + struct.pack('>I', version) + b'ROTV' + struct.pack('>I', 1)
    raw += struct.pack('>I', 1) + struct.pack('>3I', 1, 0, 3)          # one stream, a new vertex buffer
    if own_position:
        raw += struct.pack('>I', 2) + bytes((0, 3, 0, 2, 9, 12))
        for p in TRIANGLE:
            raw += struct.pack('>3f', *p) + bytes((10, 20, 30, 255))
    else:
        raw += struct.pack('>I', 2) + bytes((5, 5, 0, 2, 9, 4))        # uv and colour only
        for x, y, _z in TRIANGLE:
            raw += struct.pack('>2e', x, y) + bytes((10, 20, 30, 255))
    raw += struct.pack('>I', 0)                                        # the stream's byte offset
    raw += struct.pack('>I', frames)                                   # frame count (0 = none)
    for k in range(frames):
        raw += struct.pack('>3I', 1, 0, 3) + struct.pack('>I', 1) + bytes(frame_descriptor)
        for x, y, z in TRIANGLE:
            raw += struct.pack('>3f', x, y + k, z)
        raw += struct.pack('>I', 0)
    raw += struct.pack('>4I', 1, 0, 3, 2) + struct.pack('>3H', 0, 1, 2)
    raw += struct.pack('>3IH3I', 0, 3, 0, 0, 3, 0, 0)
    raw += bytes(4) + bytes(4) + bytes(36) + bytes(32)
    return raw


class LB2Mesh48Frames(unittest.TestCase):
    def test_decoded_frame_allocation_is_bounded(self):
        with patch('mesh48_frames_fixture.native_mesh.MAX_FRAME_VERTICES', 8):
            with self.assertRaisesRegex(FormatError, 'frame allocation limit'):
                read_mesh_bytes(fixture(frames=3))
            self.assertEqual(len(read_mesh_bytes(fixture(frames=2))['parts']), 1)

    def test_frames_are_read_and_frame_0_gives_the_positions(self):
        mesh = read_mesh_bytes(fixture(frames=3))
        part = mesh['parts'][0]
        self.assertEqual(len(part['frame_positions']), 3)
        self.assertEqual(part['frame_positions'][2][1], [1.0, 2.0, 0.0])
        self.assertEqual(part['position_source'], 'vertex frame 0')
        self.assertEqual([v['position'][:3] for v in part['vertices']], [list(map(float, p)) for p in TRIANGLE])
        self.assertEqual(part['triangles'], [[0, 1, 2]])
        self.assertEqual(mesh['end_offset'], len(fixture(frames=3)))

    def test_own_positions_are_kept(self):
        part = read_mesh_bytes(fixture(frames=2, own_position=True))['parts'][0]
        self.assertNotIn('position_source', part)
        self.assertEqual(len(part['frame_positions']), 2)

    def test_no_frames_keeps_the_old_record(self):
        part = read_mesh_bytes(fixture(frames=0, own_position=True))['parts'][0]
        self.assertNotIn('frame_positions', part)
        self.assertNotIn('vertex_frames', part)
        with self.assertRaisesRegex(FormatError, 'verified 3D position'):
            read_mesh_bytes(fixture(frames=0))

    def test_frames_must_be_position_only_and_lb2(self):
        with self.assertRaisesRegex(FormatError, 'position-only'):
            read_mesh_bytes(fixture(frame_descriptor=(1, 3, 0)))
        raw = bytearray(fixture())
        struct.pack_into('>I', raw, 4, 169)
        with self.assertRaises(FormatError):
            read_mesh_bytes(bytes(raw))


if __name__ == '__main__':
    unittest.main()

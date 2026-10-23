"""Synthetic legacy DDS cube layout and refusal checks; no game data."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from shader_cubemap import split_faces


def fixture(code=b'DXT3'):
    raw=bytearray(128);raw[:4]=b'DDS '
    for offset,value in ((4,124),(8,4103),(12,4),(16,4),(76,32),
                         (80,4),(108,0x1008),(112,0xfe00)):
        struct.pack_into('<I',raw,offset,value)
    raw[84:88]=code
    size=8 if code==b'DXT1' else 16
    return bytes(raw)+b''.join(bytes([i])*size for i in range(6))


class CubeLayouts(unittest.TestCase):
    def test_all_faces_preserve_compressed_payload_and_order(self):
        for code in (b'DXT1',b'DXT3',b'DXT5'):
            raw=fixture(code);faces=split_faces(raw)
            size=8 if code==b'DXT1' else 16
            self.assertEqual(len(faces),6)
            for i,face in enumerate(faces):
                self.assertEqual(face[128:],bytes([i])*size)
                self.assertEqual(struct.unpack_from('<II',face,108),(0x1000,0))
                self.assertEqual(face[:108],raw[:108])

    def test_uncompressed_bgr_faces(self):
        raw=bytearray(fixture()[:128]);raw[84:88]=b'\0'*4
        for offset,value in ((80,0x40),(88,24),(92,0xff0000),(96,0xff00),(100,0xff)):
            struct.pack_into('<I',raw,offset,value)
        raw+=bytes(range(48))*6
        self.assertTrue(all(face[128:]==bytes(range(48)) for face in split_faces(raw)))

    def test_unknown_and_malformed_layouts_refused(self):
        raw=fixture()
        bad=[raw[:127],raw[:-1],raw+b'\0',fixture(b'DX10')]
        for offset,value in ((4,123),(76,31),(112,0x200),(12,8),(16,8192),
                             (24,1),(28,2),(80,0)):
            changed=bytearray(raw);struct.pack_into('<I',changed,offset,value);bad.append(changed)
        for changed in bad:
            with self.assertRaises(ValueError):split_faces(changed)


if __name__=='__main__':unittest.main()

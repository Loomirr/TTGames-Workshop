"""Synthetic endian and boundary checks for standalone AN4, without game files."""
import struct
import sys
import types
import unittest
from pathlib import Path
pkg = types.ModuleType('tt_an4_test')
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
from tt_an4_test.cu3 import Animation, Reader, FormatError
from tt_an4_test.an4 import AnimationFile


def animation(endian):
    raw = bytearray(93)
    raw[:4] = b'ANID' if endian == '>' else b'DINA'
    struct.pack_into(endian + '6H', raw, 4, 1, 2, 0, 2, 6, 0)
    raw[19] = 0xe0
    struct.pack_into(endian + 'H', raw, 22, 2)
    struct.pack_into(endian + '2f', raw, 28, 0, 1)
    struct.pack_into(endian + '9I', raw, 36, 80, 80, 80, 80, 92, 0, 0, 0, 0)
    struct.pack_into(endian + '2f', raw, 72, 1, 0)
    struct.pack_into(endian + '6H', raw, 80, *range(16, 22))
    raw[92] = 3
    return raw


def tree():
    raw = bytearray(224) + animation('>') + b'Actor\0Clip\0'
    struct.pack_into('>2I', raw, 0, 14, len(raw))
    struct.pack_into('>H', raw, 8, 1)
    struct.pack_into('>2I', raw, 16, 317, 72)
    raw[84] = 1
    struct.pack_into('>3I', raw, 92, 0, 144, 1)
    struct.pack_into('>16f', raw, 144, *[1 if i % 5 == 0 else 0 for i in range(16)])
    struct.pack_into('>2I', raw, 208, 7, 224)
    return raw


class AN4Checks(unittest.TestCase):
    def test_big_endian_facial_scalar_block(self):
        raw=tree();at=len(raw)
        scalar=bytearray(187);scalar[:4]=b'ANID'
        struct.pack_into('>6H',scalar,4,1,2,0,2,53,0);scalar[19]=0xa4
        struct.pack_into('>H',scalar,22,2);struct.pack_into('>2f',scalar,28,0,1)
        struct.pack_into('>9I',scalar,36,80,80,80,80,186,0,0,0,0)
        struct.pack_into('>2f',scalar,72,1,0)
        struct.pack_into('>53H',scalar,80,*[15 if i==17 else 14 for i in range(53)])
        raw+=b'BSA\0'+struct.pack('>4I',20,len(scalar)+20,len(scalar)+20,0)+scalar
        struct.pack_into('>I',raw,4,len(raw));struct.pack_into('>I',raw,108,at)
        source=AnimationFile('fixture.an4',data=raw)
        face=source.morph_animation(source.actors[0])
        self.assertEqual(face.curves,53);self.assertEqual(face.sample(1)[0][17],1)
        self.assertEqual(sum(face.sample(1)[0]),1)
        for field,value in ((at+4,24),(at+12,0xffffffff),(at+16,1),(108,len(raw))):
            bad=raw[:];struct.pack_into('>I',bad,field,value)
            with self.assertRaises(FormatError):
                instance=AnimationFile('fixture.an4',data=bad);instance.morph_animation(instance.actors[0])
        original=AnimationFile('fixture.an4',data=tree())
        self.assertIsNone(original.morph_animation(original.actors[0]))

    def test_both_byte_orders(self):
        for endian in ('<', '>'):
            raw = animation(endian)
            anim = Animation(Reader(raw), 0, len(raw))
            self.assertEqual(anim.sample(0), [[16, 17, 18, 19, 20, 21]])
            self.assertEqual(anim.sample(1), anim.sample(0))

    def test_tree_and_actor_selection(self):
        source = AnimationFile('fixture.an4', data=tree())
        actor = source.choose_actor(1)
        self.assertEqual(actor['name'], 'Actor')
        self.assertEqual(actor['records'][0]['name'], 'Clip')
        with self.assertRaises(FormatError):
            source.choose_actor(2)

    def test_unknown_version_and_wrapper(self):
        raw = tree()
        struct.pack_into('>I', raw, 0, 99)
        for data in (raw, b'Deflate_v1.0' + b'\0' * 70, b'bad'):
            with self.assertRaises(FormatError):
                AnimationFile('fixture.an4', data=data)

    def test_invalid_tree_bounds_and_cycle(self):
        for at, fmt, value in ((16, 'I', 999999), (20, 'I', 0), (212, 'I', 999999)):
            raw = tree()
            struct.pack_into('>' + fmt, raw, at, value)
            with self.assertRaises(FormatError):
                AnimationFile('fixture.an4', data=raw)
        raw = tree()
        struct.pack_into('>H', raw, 80, 1)
        struct.pack_into('>I', raw, 92, 72)
        with self.assertRaises(FormatError):
            AnimationFile('fixture.an4', data=raw)


if __name__ == '__main__':
    unittest.main()

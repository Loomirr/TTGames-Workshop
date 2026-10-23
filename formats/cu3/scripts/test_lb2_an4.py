"""LEGO Batman 2 AN4: big-endian trees 2/4-7, little-endian trees 1/2 with 44-byte header and nodes, and ANI-B
blocks (synthetic fixtures, no game files)."""
import struct
import sys
import types
import unittest
from pathlib import Path
pkg = types.ModuleType('lb2_an4_test')
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
from lb2_an4_test.cu3 import FormatError
from lb2_an4_test.an4 import AnimationFile


def animation(endian, magic):
    """One node, six constant curves (types 16-21), two keys."""
    raw = bytearray(93)
    raw[:4] = magic if endian == '>' else magic[::-1]
    struct.pack_into(endian + '6H', raw, 4, 1, 2, 0, 2, 6, 0)
    raw[19] = 0xe0
    struct.pack_into(endian + 'H', raw, 22, 2)
    struct.pack_into(endian + '2f', raw, 28, 0, 1)
    struct.pack_into(endian + '9I', raw, 36, 80, 80, 80, 80, 92, 0, 0, 0, 0)
    struct.pack_into(endian + '2f', raw, 72, 1, 0)
    struct.pack_into(endian + '6H', raw, 80, *range(16, 22))
    raw[92] = 3
    return raw


def tree(endian='>', version=7, magic=b'ANIB', roots=2):
    """`roots` root nodes with one record each; nodes are as long as the header (72 or 44)."""
    head = 72 if endian == '>' else 44
    nodes, records = head, head + roots * head
    anims = records + roots * 80
    raw = bytearray(anims)
    names = b'Actor\0Clip\0'
    for i in range(roots):
        node, rec, ani = nodes + i * head, records + i * 80, anims + i * 93
        raw[node + 12] = 1
        struct.pack_into(endian + '3I', raw, node + 20, 0, rec, 1)
        struct.pack_into(endian + '16f', raw, rec, *[1 if k % 5 == 0 else 0 for k in range(16)])
        struct.pack_into(endian + '2I', raw, rec + 64, 7, ani)
    for _ in range(roots):
        raw += animation(endian, magic)
    strings = len(raw)
    raw += names
    struct.pack_into(endian + '2I', raw, 0, version, len(raw))
    struct.pack_into(endian + 'H', raw, 8, roots)
    struct.pack_into(endian + '2I', raw, 16, strings, nodes)
    return bytes(raw)


def samples(source):
    out = []
    for actor in source.actors:
        for record in actor['records']:
            animation = record['animation']
            animation.prepare()
            out.append([animation.sample(frame) for frame in (0, 1)])
    return out


class LB2AN4(unittest.TestCase):
    def test_big_endian_lb2_trees_and_ani_b(self):
        reference = samples(AnimationFile('d.an4', data=tree(magic=b'ANID')))
        for version in (2, 4, 5, 6, 7):
            source = AnimationFile('b.an4', data=tree(version=version))
            self.assertEqual((source.endian, len(source.actors)), ('>', 2))
            self.assertEqual([a['name'] for a in source.actors], ['Actor', 'Actor'])
            self.assertEqual(source.actors[0]['records'][0]['animation'].variant, 'ANIB')
            self.assertEqual(samples(source), reference)

    def test_little_endian_lb2_trees_use_44_byte_nodes(self):
        reference = samples(AnimationFile('d.an4', data=tree(magic=b'ANID')))
        for version in (1, 2):
            source = AnimationFile('l.an4', data=tree('<', version))
            self.assertEqual((source.endian, source.header_size, len(source.actors)), ('<', 44, 2))
            self.assertEqual(source.actors[1]['records'][0]['name'], 'Clip')
            self.assertEqual(samples(source), reference)

    def test_unobserved_or_inconsistent_trees_are_refused(self):
        # Version 8 is now verified in LOTR; 9 remains unobserved.
        for raw in (tree(version=3), tree(version=9), tree('<', 3)):
            with self.assertRaisesRegex(FormatError, 'verified big-endian'):AnimationFile('x.an4', data=raw)
        bad = bytearray(tree('<', 2));struct.pack_into('<I', bad, 4, len(bad) + 4)
        with self.assertRaises(FormatError):AnimationFile('x.an4', data=bytes(bad))
        # No facial pointer (node +40 in little-endian trees): no facial block.
        source = AnimationFile('l.an4', data=tree('<', 2))
        self.assertIsNone(source.morph_animation(source.actors[0]))


if __name__ == '__main__':
    unittest.main()

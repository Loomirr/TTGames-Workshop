"""LEGO Batman 2's oldest UMTL tables, 52-105: name position and length rule, texture slots, flag set and tail
(synthetic tables)."""
import struct
import sys
import types
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('lb2_old_material_fixture'); package.__path__ = [str(source)]
sys.modules[package.__name__] = package
from lb2_old_material_fixture.native_materials import read_materials_bytes
from lb2_old_material_fixture.cu3 import FormatError

# version: texture slots at, name at, name length counts the closing zero, flags without noprepass, tail flags
OLD = {52: (321, 820, False, True, 7), 55: (321, 820, False, True, 8), 56: (321, 820, False, True, 8),
       58: (322, 821, False, False, 8), 61: (336, 833, True, False, 8), 105: (336, 833, True, False, 8)}


def footer(version, *, cull=0):
    flags = bytearray(18)                      # old_alpha .. colourWriteMask, no alphaTestMode
    flags[3], flags[4], flags[7], flags[8], flags[15], flags[17] = 0x7c, cull, 1, 3, 1, 15
    if OLD[version][3]:
        del flags[7]                           # no noprepass in 52-56
    tail = OLD[version][4]
    body = bytes(flags) + struct.pack('>5I', 0, 0, 0, 0, 3) + bytes(2) + struct.pack('>2H', 0, 0) + bytes(2)
    body += struct.pack('>4f', 1, 1, 1, 1) + struct.pack('>2I', 0xffffffff, 0xffffffff) + bytes((0, 1, 0, 0, 0, 0, 0, 0)[:tail])
    return body + struct.pack('>2I', 0x2f, 4)


def record(version, name, textures, **flags):
    tex, name_at, counted = OLD[version][:3]
    raw = bytearray(name_at); struct.pack_into('>I', raw, 0, 2)
    ids = [-1] * 16
    for slot, value in textures.items():
        ids[slot] = value
    struct.pack_into('>16i', raw, tex, *ids)
    text = name.encode() + b'\0'
    return bytes(raw) + struct.pack('>H', len(text) if counted else len(text) - 1) + text + bytes(17) + footer(version, **flags)


def table(version, records):
    return b'LTMU' + struct.pack('>3I', version, len(records), len(records)) + b''.join(records) + b'\x01HSCB' + bytes(12)


class LB2OldMaterials(unittest.TestCase):
    def test_versions_52_to_105(self):
        for version in OLD:
            with self.subTest(version=version):
                result = read_materials_bytes(table(version, [record(version, 'LEGO_Hard:LEGO_Base', {0: 1, 10: 0}),
                                                              record(version, 'network_Screen', {}, cull=2)]))
                self.assertEqual([m['name'] for m in result['materials']], ['LEGO_Hard:LEGO_Base', 'network_Screen'])
                self.assertEqual(result['materials'][0]['texture_ids'], [1] + [-1] * 9 + [0] + [-1] * 5)
                flags = [m['render_flags'] for m in result['materials']]
                self.assertEqual((flags[0]['aref'], flags[0]['filter'], flags[0]['castShadows'], flags[0]['colourWriteMask']),
                                 (0x7c, 3, 1, 15))
                self.assertEqual(flags[1]['cull'], 2)
                self.assertIsNone(flags[0]['alphaTestMode'])
                self.assertEqual(flags[0]['noprepass'], None if OLD[version][3] else 1)
                self.assertEqual(len(flags[0]['lb2TailFlags']), OLD[version][4])

    def test_name_length_rule_is_per_version(self):
        # a 56 table written with the zero counted (the 106 rule) does not read
        data = bytearray(table(56, [record(56, 'A1', {0: 0}), record(56, 'B2', {0: 0})]))
        start = 16
        struct.pack_into('>H', data, start + 820, 3)
        with self.assertRaises((FormatError, ValueError)):
            read_materials_bytes(bytes(data))

    def test_tail_lengths_are_per_version(self):
        # 55's 8-byte tail does not fit a 52 table
        data = bytearray(table(52, [record(52, 'A', {0: 0}), record(52, 'B', {0: 0})]))
        struct.pack_into('>I', data, 4, 55)
        with self.assertRaises((FormatError, ValueError)):
            read_materials_bytes(bytes(data))

    def test_unobserved_neighbours_stay_refused(self):
        for version in (51, 53, 54, 57, 59, 60, 104):
            with self.assertRaises(FormatError):
                read_materials_bytes(table(56, [record(56, 'A', {0: 0})])[:4] + struct.pack('>I', version) +
                                     table(56, [record(56, 'A', {0: 0})])[8:])


if __name__ == '__main__':
    unittest.main()

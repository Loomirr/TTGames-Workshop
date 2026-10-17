"""LMSH1 DISP 17 (the DISP 16 layout) and DISP 22 (the DISP 21 layout), and their LOD tables (synthetic fixtures)."""
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('lmsh1_display_fixture'); package.__path__ = [str(source)]
sys.modules[package.__name__] = package
from lmsh1_display_fixture.native_display import read_display, model_bindings
from lmsh1_display_fixture.cu3 import FormatError


def fixture(version, aux_counts=(1, 1, 1)):
    """One command, one clip drawing part 0, one named instance; DISP 16/17 carry three per-clip arrays."""
    data = b'PSID' + struct.pack('>I', version)
    data += struct.pack('>I', 0) + b'ROTV'                                   # byte array, separator
    data += struct.pack('>I', 1) + struct.pack('>BBI', 0x80, 0, 0) + b'ROTV'  # commands
    data += struct.pack('>I', 1) + bytes(2) + struct.pack('>4I', 1, 0, 1, 0)   # one clip: material 0, command 0
    data += b'ROTV' + struct.pack('>I', 0) + b'ROTV' + struct.pack('>I', 0)    # 2- and 4-byte arrays
    if version in (16, 17):
        for count in aux_counts:
            data += b'ROTV' + struct.pack('>I', count) + bytes(4 * count)
    data += b'ROTV'
    special = bytearray(204)
    struct.pack_into('>I', special, 0, 0)
    struct.pack_into('>16f', special, 4, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    struct.pack_into('>3I', special, 180, 0, 0, 0)
    data += struct.pack('>I', 1) + bytes(special)
    names = b'Body\0'
    return data + b'LBTN' + struct.pack('>2I', 1, len(names)) + names


def read(raw):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'model.ghg'
        path.write_bytes(raw)
        return read_display(path, 1)


class LMSH1DisplayVersions(unittest.TestCase):
    def test_disp_17_reads_as_disp_16(self):
        a, b = read(fixture(16)), read(fixture(17))
        self.assertEqual(b['version'], 17)
        self.assertEqual((a['specials'], a['clips'], a['commands']), (b['specials'], b['clips'], b['commands']))
        self.assertEqual(b['specials'][0]['name'], 'Body')
        self.assertEqual(b['specials'][0]['parts'], [dict(part=0, material=0)])
        with self.assertRaisesRegex(FormatError, 'DISP 17 auxiliary count'):
            read(fixture(17, aux_counts=(1, 2, 1)))

    def test_disp_22_reads_as_disp_21(self):
        a, b = read(fixture(21)), read(fixture(22))
        self.assertEqual((a['specials'], a['clips']), (b['specials'], b['clips']))

    def test_neighbours_stay_refused(self):
        for version in (19, 20):
            with self.assertRaisesRegex(FormatError, 'separate verified reader'):
                read(fixture(version))

    def test_lod_tables_of_17_and_22(self):
        for version in (17, 22):
            display = dict(version=version, commands=[(0xb3, 0, i) for i in range(3)],
                           clips=[dict(materials=[0], items=[i]) for i in range(3)])
            special = dict(clip=0, lod_ranges=[16, 9, 0], parts=[dict(part=0, material=0)])
            self.assertEqual(model_bindings(display, special), [dict(part=2, material=0)])
            with self.assertRaises(FormatError):
                model_bindings(display, dict(special, lod_ranges=[0, 9, 16]))
        with self.assertRaises(FormatError):
            model_bindings(dict(display, version=23), special)


if __name__ == '__main__':
    unittest.main()

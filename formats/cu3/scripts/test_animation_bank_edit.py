"""Asset-free regression for ordered animation bank replacement."""
import hashlib
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

package = types.ModuleType('tt_bank_edit_test')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_bank_edit_test import animation_bank
from tt_bank_edit_test.animation_bank import AnimationBank
from tt_bank_edit_test.cu3 import FormatError
from tt_bank_edit_test.tt_deflate import compress


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fixture(payloads=None):
    payloads = payloads or [b'idle data', b'walking', b'running data']
    count = len(payloads)
    output = bytearray(24 + 28 * count)
    for index in range(count):
        struct.pack_into('<I', output, 24 + 28 * index, len(output))
        output.extend(f'clip{index}.an4'.encode() + b'\0')
    output.extend(bytes((-len(output)) % 4))
    for index, payload in enumerate(payloads):
        struct.pack_into('<6I', output, 28 + 28 * index,
                         len(output), len(payload), 4, 13, 17 + index, 19)
        output.extend(payload)
        output.extend(b'\0\0')
        if index + 1 < count:
            output.extend(bytes((-len(output)) % 4))
    struct.pack_into('<6I', output, 0, 0x1234567A, count, len(output), 1234, 0, 0)
    return bytes(output)


class BankEditTests(unittest.TestCase):
    def test_unchanged_is_byte_identical(self):
        data = fixture()
        bank = AnimationBank('source.pak', data=data)
        self.assertEqual(bank.replace_members({}, digest(data)), data)
        self.assertEqual(bank.replace_members({'CLIP0.AN4': b'idle data'}, digest(data)), data)

    def test_growing_and_shrinking_members_keep_later_walk_and_run(self):
        data = fixture()
        bank = AnimationBank('source.pak', data=data)
        for length in (1, 2, 3, 4, 500):
            with self.subTest(length=length):
                result = bank.replace_members({'clip0.an4': b'x' * length}, digest(data))
                edited = AnimationBank('edited.pak', data=result)
                self.assertEqual(edited.read('clip0.an4'), b'x' * length)
                for index in (1, 2):
                    name = f'clip{index}.an4'
                    self.assertEqual(edited.read_stored(name), bank.read_stored(name))
                    entry = edited.entries[name]
                    previous = edited.entries[f'clip{index-1}.an4']
                    self.assertEqual(entry['offset'] % 4, 0)
                    gap = entry['offset'] - previous['offset'] - previous['size']
                    self.assertIn(gap, (2, 3, 4, 5))
                    self.assertEqual(result[entry['offset']-gap:entry['offset']], bytes(gap))
                self.assertEqual(result[-2:], b'\0\0')
                for index in range(3):
                    start = 36 + 28 * index
                    self.assertEqual(result[start:start+16], data[start:start+16])
                self.assertEqual(bank.data, data)

    def test_compressed_multiple_replacements_and_corrupt_stream(self):
        data = fixture([compress(b'idle'), compress(b'walk'), compress(b'run')])
        bank = AnimationBank('source.pak', data=data)
        edits = {'clip0.an4': compress(b'edited idle' * 200), 'clip2.an4': compress(b'fast')}
        result = AnimationBank('out.pak', data=bank.replace_members(edits, digest(data)))
        self.assertEqual(result.read('clip0.an4'), b'edited idle' * 200)
        self.assertEqual(result.read('clip1.an4'), b'walk')
        self.assertEqual(result.read('clip2.an4'), b'fast')
        with self.assertRaises(FormatError):
            bank.replace_members({'clip0.an4': edits['clip0.an4'][:-3]}, digest(data))
        with self.assertRaisesRegex(FormatError, 'storage changed'):
            bank.replace_members({'clip0.an4': b'raw'}, digest(data))

    def test_stale_unknown_duplicate_empty_and_size_limit(self):
        data = fixture()
        bank = AnimationBank('source.pak', data=data)
        for edits, sha in (({}, 'wrong'), ({'absent': b'abc'}, digest(data)),
                           ({'clip0.an4': b'a', 'CLIP0.AN4': b'b'}, digest(data)),
                           ({'clip0.an4': b''}, digest(data))):
            with self.assertRaises(FormatError):
                bank.replace_members(edits, sha)
        with patch.object(animation_bank, 'MAX_PACKED', len(data)):
            with self.assertRaisesRegex(FormatError, 'packed-byte limit'):
                bank.replace_members({'clip0.an4': b'x' * len(data)}, digest(data))

    def test_unmeasured_layouts_refused(self):
        original = fixture()
        cases = []
        for offset, value in ((16, 1), (20, 1), (36, 9)):
            data = bytearray(original)
            struct.pack_into('<I', data, offset, value)
            cases.append(bytes(data))
        data = bytearray(original)
        data[-1] = 1
        cases.append(bytes(data))
        # Old append-and-redirect method: readable, but unsuitable for export.
        data = bytearray(original)
        data.extend(bytes((-len(data)) % 4))
        struct.pack_into('<2I', data, 28, len(data), 4)
        data.extend(b'new!\0\0')
        struct.pack_into('<I', data, 8, len(data))
        cases.append(bytes(data))
        # Aliased payloads also remain a read-only layout.
        data = bytearray(original)
        data[56:64] = data[28:36]
        cases.append(bytes(data))
        for data in cases:
            with self.subTest(header=data[:24]):
                bank = AnimationBank('unsupported.pak', data=data)
                with self.assertRaises(FormatError):
                    bank.replace_members({}, digest(data))


if __name__ == '__main__':
    unittest.main()

"""Constructed bounds and mode regressions for the observed CC12 extension.

No game bytes are included. Original-file framing and payload checks are
documented separately; opaque records never select a compression codec.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import types
import unittest

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3 import archive_cc as cc
from io_scene_lego_cu3.archive_compression import decode_entry
from io_scene_lego_cu3.cu3 import FormatError

PATHS = ['Chars/Hero.GHG', 'Chars/Hero.CD', 'Chars/Hero.TXT']
OPAQUE = [bytes(range(48)), b'ROTV' + bytes(44)]


def declared(data):
    return struct.pack('>I', len(data) - 4) + data[4:]


def fixture(prefix=b'Chars'):
    names = b''.join(name.encode('ascii') + b'\0' for name in PATHS)
    base = struct.pack('>I8si4I', 0, b'.CC40TAD', -12, 2, 3, 3, len(names)) + names + bytes(4)
    at = 0
    for name in PATHS:
        base += struct.pack('>IHHhH', at, 65535, 0, 0, 1)
        at += len(name) + 1
    base += struct.pack('>iI', -12, 3)
    for offset, packed, raw, compressed in ((8, 5, 5, False), (32, 5, 9, True), (64, 15, 3, True)):
        base += struct.pack('>QII', offset, packed, raw | (0x80000000 if compressed else 0))
    for name in PATHS:
        value = 0xcbf29ce484222325
        for byte in name.upper().replace('/', '\\').encode('ascii'):
            value = ((value ^ byte) * 1099511628211) & 0xffffffffffffffff
        base += struct.pack('>Q', value)
    suffix = bytes(8) + prefix + b'\0' + bytes(16)
    for records in (*OPAQUE, bytes((0, 2, 6)), struct.pack('>3I', 5, 5, 15)):
        suffix += struct.pack('>II', 0, 3) + records
    return declared(base + suffix), len(base)


class CC12SuffixTests(unittest.TestCase):
    def assert_rejected(self, data, reason=None):
        report = cc.diagnose_index(data, archive_limit=128)
        self.assertEqual(report['status'], 'unsupported_suffix')
        self.assertTrue(report['prefix_validated'])
        self.assertFalse(report['complete_index_validated'])
        self.assertFalse(report['extraction_allowed'])
        if reason:
            self.assertIn(reason, report['suffix']['validation_error'])
        with self.assertRaises(cc.CCIndexError):
            cc.parse_index(data, archive_limit=128)

    def test_modes_are_not_collapsed_and_opaque_arrays_remain_file_ordered(self):
        data, _ = fixture()
        rows = cc.parse_index(data, archive_limit=128, expected_layout=(-12, 2))
        self.assertEqual([row['path'] for row in rows], PATHS)
        self.assertEqual([row['flags'] for row in rows], [0, 2, 6])
        self.assertEqual([row['packed_size'] for row in rows], [5, 5, 15])
        self.assertEqual([row['size'] for row in rows], [5, 9, 3])
        self.assertEqual(rows[1]['cc12_records'], [array[16:32].hex() for array in OPAQUE])
        self.assertEqual(json.loads(json.dumps(rows)), rows)
        with self.assertRaisesRegex(FormatError, 'storage mode 6'):
            decode_entry(b'x' * 15, 3, storage_mode=rows[2]['flags'])

    def test_bounded_metadata_reports_all_tables_without_dumping_records(self):
        data, start = fixture()
        report = cc.diagnose_index(data, archive_limit=128)
        self.assertEqual(report['status'], 'complete')
        self.assertFalse(report['extraction_allowed'])
        suffix = report['suffix']
        self.assertEqual(suffix['grammar'], 'pc_cc12_v2_16_16_1_4')
        self.assertEqual(suffix['directory_prefix'], 'Chars')
        at = start + 8 + len(b'Chars\0') + 16
        for table, width in zip(suffix['record_tables'], (16, 16, 1, 4)):
            self.assertEqual(table['offset'], at)
            self.assertEqual(table['count'], 3)
            self.assertEqual(table['record_bytes'], width)
            self.assertEqual(table['sha256'], hashlib.sha256(data[at + 8:at + 8 + width * 3]).hexdigest())
            at += 8 + width * 3
        self.assertEqual(at, len(data))
        text = json.dumps(report)
        self.assertNotIn('cc12_records', text)
        self.assertNotIn('Hero.GHG', text)

    def test_all_zero_headers_and_file_counts_are_mandatory(self):
        data, start = fixture()
        first = start + 8 + len(b'Chars\0') + 16
        for at in range(start, start + 8):
            self.assert_rejected(data[:at] + b'\1' + data[at + 1:], 'extension header')
        for at in range(first - 16, first):
            self.assert_rejected(data[:at] + b'\1' + data[at + 1:], 'reserved')
        for at in (first, first + 56, first + 112, first + 123):
            for replacement in (b'ROTV', b'\0\0\0\1'):
                self.assert_rejected(data[:at] + replacement + data[at + 4:], 'tag/count')
            for count in (0, 2, 4, 0xffffffff, 0x03000000):
                self.assert_rejected(data[:at + 4] + struct.pack('>I', count) + data[at + 8:], 'tag/count')

    def test_extra_or_missing_bytes_are_not_padding(self):
        data, start = fixture()
        for changed in (data + b'\0', data[:-1], data[:start + 12]):
            self.assert_rejected(declared(changed))

    def test_safe_prefix_must_be_a_shared_directory(self):
        for prefix in (b'', b'chars'):
            data, _ = fixture(prefix)
            self.assertEqual(len(cc.parse_index(data, archive_limit=128)), 3)
        for prefix in (b'Char', b'CharsOther', b'Chars/Hero.GHG', b'../Chars', b'/Chars',
                       b'C:Chars', b'Chars\xff', b'x' * 4097):
            self.assert_rejected(fixture(prefix)[0])

    def test_mode_and_duplicate_sizes_must_agree_with_primary_table(self):
        data, start = fixture()
        modes = start + 8 + len(b'Chars\0') + 16 + 112 + 8
        for offset, value, reason in ((0, 2, 'presence'), (1, 0, 'presence'), (2, 5, 'storage mode')):
            at = modes + offset
            self.assert_rejected(data[:at] + bytes((value,)) + data[at + 1:], reason)
        sizes = modes + 3 + 8
        for i, value in enumerate((4, 9, 0xffffffff)):
            at = sizes + i * 4
            self.assert_rejected(data[:at] + struct.pack('>I', value) + data[at + 4:], 'packed size')

    def test_valid_suffix_cannot_mask_bad_extents_or_cross_layout(self):
        data, _ = fixture()
        report = cc.diagnose_index(data, archive_limit=70)
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertEqual(report['phase'], 'file_records')
        with self.assertRaisesRegex(cc.CCIndexError, 'expected'):
            cc.parse_index(data, archive_limit=128, expected_layout=(-8, 2))


if __name__ == '__main__':
    unittest.main()

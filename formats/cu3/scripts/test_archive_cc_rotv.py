"""Independent synthetic regressions for original-observed CC8 ROTV framing.

No game bytes are included. The fixtures test grammar and refusal behavior;
the separate original-index pass establishes the supported (-8, 1) layout.
"""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import types
import unittest

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3 import archive_cc as cc
from io_scene_lego_cu3.archive_compression import decode_entry
from io_scene_lego_cu3.cu3 import FormatError


PATHS = ['Chars/Hero.GHG', 'Chars/Hero.CD', 'Chars/Hero.TXT']
RECORDS = [[bytes(16), b'ROTV' + bytes(range(12)), bytes(range(16))],
           [b'a' * 16, bytes(reversed(range(16))), b'z' * 16]]


def fixture(prefix=b'Chars', *, version=1, override=True):
    names = b''.join(path.encode('ascii') + b'\0' for path in PATHS)
    header = struct.pack('>I8si4I', 0, b'.CC40TAD', -8, version, 3, 3, len(names))
    name_records, at = b'', 0
    for name in PATHS:
        name_records += (struct.pack('>IHhH', at, 65535, 0, 1) if version == 1 else
                         struct.pack('>IHHhH', at, 65535, 0, 0, 1))
        at += len(name) + 1
    files = struct.pack('>iI', -8, 3)
    for offset, packed, raw, flags in ((8, 5, 5, 0), (32, 5, 9, 2), (64, 15, 3, 6)):
        files += struct.pack('>4I', offset >> 8, packed, raw, (flags << 24) | (offset & 255))
    hashes = [cc.path_hash(path) for path in PATHS]
    if override:
        hashes[1] = 0
        named = PATHS[1].encode('ascii') + b'\0'
        named += bytes(len(named) & 1) + struct.pack('>H', 1)
    else:
        named = b''
    base = (header + names + bytes(4) + name_records + files + struct.pack('>3I', *hashes) +
            struct.pack('>2I', int(override), len(named)) + named)
    suffix = prefix + b'\0' + bytes(16)
    for records in RECORDS:
        suffix += b'ROTV' + struct.pack('>I', len(records)) + b''.join(records)
    data = base + suffix
    return struct.pack('>I', len(data) - 4) + data[4:], len(base)


def declared(data):
    return struct.pack('>I', len(data) - 4) + data[4:]


class ROTVFramingTests(unittest.TestCase):
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
        return report

    def test_records_retained_in_file_order_without_codec_or_digest_inference(self):
        data, _ = fixture()
        rows = cc.parse_index(data, archive_limit=128, expected_layout=(-8, 1))
        self.assertEqual([row['path'] for row in rows], PATHS)
        self.assertEqual([row['flags'] for row in rows], [0, 2, 6])
        self.assertEqual([row['rotv_records'] for row in rows],
                         [[RECORDS[0][i].hex(), RECORDS[1][i].hex()] for i in range(3)])
        self.assertEqual(json.loads(json.dumps(rows)), rows)
        with self.assertRaisesRegex(FormatError, 'storage mode 6'):
            decode_entry(b'x' * 15, 3, storage_mode=rows[2]['flags'])

    def test_bounded_report_retains_both_spans_and_hashes_but_no_arrays(self):
        data, start = fixture()
        report = cc.diagnose_index(data, archive_limit=128)
        self.assertEqual(report['status'], 'complete')
        self.assertTrue(report['complete_index_validated'])
        self.assertFalse(report['extraction_allowed'])
        self.assertEqual(report['validated_file_count'], 3)
        self.assertEqual(report['named_override_count'], 1)
        self.assertEqual(report['tables_end'], start)
        suffix = report['suffix']
        self.assertEqual(suffix['directory_prefix'], 'Chars')
        self.assertTrue(suffix['validated'])
        self.assertIn('Opaque', suffix['record_semantics'])
        first = start + len(b'Chars\0') + 16
        for i, table in enumerate(suffix['record_tables']):
            self.assertEqual(table['offset'], first + i * 56)
            self.assertEqual(table['records_offset'], table['offset'] + 8)
            self.assertEqual(table['end'], table['records_offset'] + 48)
            self.assertEqual(table['count'], 3)
            self.assertEqual(table['record_bytes'], 16)
            self.assertEqual(table['zero_records'], 1 if i == 0 else 0)
            self.assertEqual(table['sha256'], hashlib.sha256(b''.join(RECORDS[i])).hexdigest())
        text = json.dumps(report)
        self.assertNotIn('rotv_records', text)
        self.assertNotIn('Hero.GHG', text)
        self.assertLess(len(text), 12000)

    def test_empty_and_case_insensitive_common_prefixes_are_valid(self):
        for prefix in (b'', b'Chars', b'chars'):
            with self.subTest(prefix=prefix):
                data, _ = fixture(prefix, override=False)
                self.assertEqual(len(cc.parse_index(data, archive_limit=128)), 3)

    def test_other_cc_version_cannot_reuse_observed_extension(self):
        data, _ = fixture(version=2)
        self.assert_rejected(data)

    def test_tags_and_big_endian_counts_are_required_for_both_tables(self):
        data, start = fixture()
        first = start + len(b'Chars\0') + 16
        for at in (first, first + 56):
            for value in (b'V TOR', b'XXXX'):
                damaged = data[:at] + value[:4] + data[at + 4:]
                self.assert_rejected(damaged, 'tag/count')
            for count in (0, 2, 4, 0xffffffff, 0x03000000):
                damaged = data[:at + 4] + struct.pack('>I', count) + data[at + 8:]
                self.assert_rejected(damaged, 'tag/count')

    def test_extra_and_missing_bytes_never_become_padding(self):
        data, start = fixture()
        for damaged in (data + b'\0', data + b'ROTV', data[:-1], data[:start + 20],
                        data[:start + 30] + data[start + 31:]):
            self.assert_rejected(declared(damaged), 'size')

    def test_reserved_bytes_must_all_be_zero(self):
        data, start = fixture()
        for i in range(16):
            at = start + len(b'Chars\0') + i
            self.assert_rejected(data[:at] + b'\1' + data[at + 1:], 'reserved')

    def test_prefix_is_bounded_safe_ascii_and_a_directory_not_a_string_prefix(self):
        for prefix in (b'CharsOther', b'Char', b'Chars/Hero.GHG', b'../Chars', b'/Chars',
                       b'C:Chars', b'Chars\xff', b'x' * 4097):
            with self.subTest(prefix=prefix[:30]):
                data, _ = fixture(prefix)
                self.assert_rejected(data)

    def test_valid_suffix_cannot_mask_invalid_prefix_mapping_or_extents(self):
        data, _ = fixture()
        report = cc.diagnose_index(data, archive_limit=70)
        self.assertEqual(report['status'], 'invalid_prefix')
        self.assertEqual(report['phase'], 'file_records')
        self.assertNotIn('suffix', report)
        report = cc.diagnose_index(data, expected_layout=(-8, 2))
        self.assertEqual(report['status'], 'invalid_prefix')

    def test_cli_reads_index_only_and_reports_absolute_table_offsets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data, _ = fixture()
            archive = root / 'synthetic.DAT'
            archive.write_bytes(struct.pack('<II', 128, len(data)) + bytes(120) + data)
            output = root / 'report.json'
            run = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_archive_cc.py')),
                                  str(archive), str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report['status'], 'complete')
            for table in report['suffix']['record_tables']:
                self.assertEqual(table['source_offset'], table['offset'] + 128)
                self.assertEqual(table['records_source_offset'], table['records_offset'] + 128)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['report.json', 'synthetic.DAT'])


if __name__ == '__main__':
    unittest.main()

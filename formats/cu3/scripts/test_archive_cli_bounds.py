"""Headless archive CLI parity, bounds and safe-output regression checks."""
from pathlib import Path
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

from archive_index import extract, index, _read_entry
from test_archive_assets import archive
from test_archive_cc8 import fixture as cc8_fixture
from archive_index_cc4 import index as index_cc4
from archive_index_cc8 import index as index_cc8
from io_scene_lego_cu3.archive_assets import _path_hash
from io_scene_lego_cu3.archive_cc import index as shared_cc_index

ROOT = Path(__file__).resolve().parents[3]


def compressed_archive(path, raw, *, mode=2):
    packed = zlib.compress(raw)
    payload = struct.pack('<4sII', b'ZLIB', len(raw), len(packed)) + packed
    archive(path, payload=payload)
    data = bytearray(path.read_bytes())
    at = struct.unpack_from('<I', data)[0]
    struct.pack_into('<I', data, at + 16, len(raw))
    struct.pack_into('<I', data, at + 20, mode)
    path.write_bytes(data)


def cc4_fixture():
    # A synthetic inventory frame, not evidence of any new game support.
    name = b'Scene.CU3\0'
    header = struct.pack('>I8si4I', 0, b'.CC40TAD', -12, 2, 1, 1, len(name))
    records = struct.pack('>IHHhH', 0, 65535, 0, 0, 1)
    table = struct.pack('>iIQII', -12, 1, 256, 20, 20)
    hashed = 0xcbf29ce484222325
    for byte in b'SCENE.CU3':
        hashed = ((hashed ^ byte) * 1099511628211) & 0xffffffffffffffff
    data = header + name + b'\0' * 4 + records + table + struct.pack('>Q', hashed)
    return struct.pack('>I', len(data) - 4) + data[4:]


class ArchiveCliBounds(unittest.TestCase):
    def test_wrong_layout_cli_errors_are_short_and_leave_no_output(self):
        self.source.write_bytes(b'not an archive index')
        scripts=Path(__file__).resolve().parent
        for name in ('archive_index.py','archive_index_cc4.py','archive_index_cc8.py'):
            with self.subTest(script=name):
                result=subprocess.run([sys.executable,str(scripts/name),str(self.source),str(self.output)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('error:',result.stderr)
                self.assertNotIn('Traceback',result.stderr)
                self.assertFalse(self.output.exists())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'GAME.DAT'
        self.output = self.root / 'output'

    def test_standalone_and_shared_chunk_order_agree(self):
        raw = b'ABCD' * 100
        compressed_archive(self.source, raw)
        rows = index(self.source)
        target = extract(self.source, rows[0], self.output)
        self.assertEqual(target.read_bytes(), raw)

    def test_invalid_name_or_existing_target_rejected_before_decode(self):
        archive(self.source)
        entry = index(self.source)[0]
        with patch('archive_index._read_entry') as read:
            with self.assertRaises(ValueError):
                extract(self.source, dict(entry, path='../escape'), self.output)
            read.assert_not_called()
        self.output.mkdir()
        prior = self.output / 'SAMPLE.CD'
        prior.write_bytes(b'keep')
        with patch('archive_index._read_entry') as read, self.assertRaises(FileExistsError):
            extract(self.source, entry, self.output)
        read.assert_not_called()
        self.assertEqual(prior.read_bytes(), b'keep')

    def test_truncated_or_forged_index_rejected(self):
        self.source.write_bytes(b'short')
        with self.assertRaises(ValueError):
            index(self.source)
        archive(self.source)
        entry = index(self.source)[0]
        with self.assertRaises(ValueError):
            extract(self.source, dict(entry, offset=8), self.output)
        self.assertFalse(self.output.exists())

    def test_unknown_storage_mode_cannot_reach_decompression(self):
        compressed_archive(self.source, b'abc' * 30, mode=3)
        entry = index(self.source)[0]
        with patch('archive_index.decode_entry') as decode, self.assertRaisesRegex(ValueError, 'mode'):
            _read_entry(self.source, entry)
        decode.assert_not_called()

    def test_independent_cc_readers_retain_explicit_layout_gates(self):
        cc8 = self.root / 'cc8.hdr'
        cc4 = self.root / 'cc4.hdr'
        cc8.write_bytes(cc8_fixture())
        cc4.write_bytes(cc4_fixture())
        self.assertEqual(index_cc8(cc8), shared_cc_index(cc8))
        self.assertEqual(index_cc4(cc4), shared_cc_index(cc4))
        self.assertEqual(index_cc4(cc4)[0]['path'], 'Scene.CU3')
        with self.assertRaisesRegex(ValueError, 'version'):
            index_cc4(cc8)
        with self.assertRaisesRegex(ValueError, 'version'):
            index_cc8(cc4)

    def test_standalone_cc4_rejects_reserved_names_and_truncated_table(self):
        header = self.root / 'test.hdr'
        raw = cc4_fixture()
        header.write_bytes(raw[:-1])
        with self.assertRaises(ValueError):
            index_cc4(header)
        # No valid path/hash pair can make a reserved Windows destination safe.
        header.write_bytes(cc8_fixture(filename='NUL.CU3'))
        with self.assertRaises(ValueError):
            index_cc8(header)

    def test_cli_inventory_preserves_array_format_and_publishes_manifest(self):
        archive(self.source)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('archive_index.py')),
                                 str(self.source), str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.output / 'GAME-index.json').read_text()), index(self.source))
        self.assertEqual(json.loads((self.output / 'archive-manifest.json').read_text())['indexed_files'], 1)
        original = (self.output / 'GAME-index.json').read_bytes()
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('archive_index.py')),
                                 str(self.source), str(self.output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.output / 'GAME-index.json').read_bytes(), original)

    def test_explicit_parent_version_five_does_not_relax_default_or_unknown_gates(self):
        archive(self.source)
        raw=bytearray(self.source.read_bytes());at=struct.unpack_from('<I',raw)[0]
        struct.pack_into('<i',raw,at,-5);self.source.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'version'):index(self.source)
        entry=index(self.source,version_expected=-5)[0]
        target=extract(self.source,entry,self.output,version_expected=-5)
        self.assertEqual(target.read_bytes(),b'abc')
        with self.assertRaisesRegex(ValueError,'layout'):index(self.source,version_expected=-7)
        with self.assertRaisesRegex(ValueError,'version'):index_cc8(self.source)

    def test_cli_explicit_parent_version_and_manifest(self):
        archive(self.source)
        raw=bytearray(self.source.read_bytes());at=struct.unpack_from('<I',raw)[0]
        struct.pack_into('<i',raw,at,-5);self.source.write_bytes(raw)
        args=[sys.executable,str(Path(__file__).with_name('archive_index.py')),str(self.source),str(self.output)]
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.output.exists())
        result=subprocess.run(args+['--index-version','-5'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        manifest=json.loads((self.output/'archive-manifest.json').read_text())
        self.assertEqual(manifest['index_version'],-5)
        self.assertEqual(manifest['indexed_files'],1)


if __name__ == '__main__':
    unittest.main()

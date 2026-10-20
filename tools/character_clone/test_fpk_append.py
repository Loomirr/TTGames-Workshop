"""Synthetic preservation and rejection checks for experimental TXT-bank append."""
import hashlib
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from fpk_append import append_character_text, parse_pak


def fixture():
    names = [b'chars\\alpha\\alpha.txt\0', b'chars\\zulu\\zulu.txt\0']
    texts = [b'name ALPHA\r\n', b'name ZULU\r\n']
    cursor = 24 + 28 * 2
    records, body = [], b''
    for name, text in zip(names, texts):
        records.append((cursor, cursor + len(name), len(text), 1, 0, 12345, 0))
        body += name + text + b'\0\0'
        cursor += len(name) + len(text) + 2
    data = bytearray(struct.pack('<6I', 0x1234567A, 2, cursor, 0, 0, 0) + b''.join(struct.pack('<7I', *r) for r in records) + body)
    struct.pack_into('<I', data, 12, (0x12345678 + sum(data)) & 0xffffffff)
    return bytes(data)


class AppendTests(unittest.TestCase):
    def call(self, data=None, **kwargs):
        data = fixture() if data is None else data
        options = dict(name='chars/middle/middle.txt', payload=b'name MIDDLE\r\n',
                       donor='chars/alpha/alpha.txt', expected_sha256=hashlib.sha256(data).hexdigest(), game='lmsh1')
        options.update(kwargs)
        return append_character_text(data, **options)

    def test_sorted_append_preserves_original_storage_and_metadata(self):
        original = fixture()
        result = self.call(original)
        entries = parse_pak(result)
        self.assertEqual([e['name'] for e in entries], ['chars/alpha/alpha.txt', 'chars/middle/middle.txt', 'chars/zulu/zulu.txt'])
        self.assertEqual(result[108:108 + len(original) - 80], original[80:])
        self.assertEqual(result[16:24], original[16:24])
        without_checksum = bytearray(result)
        without_checksum[12:16] = b'\0' * 4
        self.assertEqual(struct.unpack_from('<I', result, 12)[0], (0x12345678 + sum(without_checksum)) & 0xffffffff)
        self.assertEqual([e['crc'] for e in entries], [12345] * 3)

    def test_rejects_collision_traversal_wrong_hash_and_profile(self):
        for options in ({'name':'chars/alpha/alpha.txt'}, {'name':'../escape.txt'},
                        {'expected_sha256':'0'*64}, {'game':'lb3'}, {'payload':b'bad\0text'},
                        {'donor':'chars/missing.txt'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.call(**options)

    def test_rejects_malformed_existing_payload(self):
        broken = bytearray(fixture())
        struct.pack_into('<I', broken, 28, len(broken) + 1)
        broken[12:16] = b'\0' * 4
        struct.pack_into('<I', broken, 12, (0x12345678 + sum(broken)) & 0xffffffff)
        with self.assertRaises(ValueError):
            self.call(bytes(broken))

    def test_rejects_bad_checksum_even_with_matching_sha(self):
        broken = bytearray(fixture())
        broken[-3] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.call(bytes(broken))

    def test_cli_writes_only_new_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, text, output = [root / name for name in ('original.fpk', 'new.txt', 'new.fpk')]
            original = fixture()
            source.write_bytes(original)
            text.write_bytes(b'name MIDDLE\r\n')
            command = [sys.executable, str(Path(__file__).with_name('fpk_append.py')),
                       str(source), str(text), str(output), '--game', 'lmsh1',
                       '--name', 'chars/middle/middle.txt', '--donor', 'chars/alpha/alpha.txt',
                       '--source-sha256', hashlib.sha256(original).hexdigest()]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = self.call(original)
            self.assertEqual(output.read_bytes(), expected)
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(source.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

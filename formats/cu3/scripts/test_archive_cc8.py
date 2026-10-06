"""Synthetic bounds/path checks for the TFA archive inventory reader."""
import struct
import unittest
from archive_index_cc8 import parse_index, path_hash


def fixture(override=False, filename='SCENE.CU3'):
    strings = b'CUT\0' + filename.encode('ascii') + b'\0'
    header = struct.pack('>I8si4I', 0, b'.CC40TAD', -8, 2, 1, 2, len(strings))
    names = struct.pack('>IHHhH', 0, 65535, 0, 0, 0)
    names += struct.pack('>IHHhH', 4, 0, 0, 0, 0)  # Terminal marker omitted.
    path = 'CUT/' + filename
    table = struct.pack('>iI4II', -8, 1, 1, 20, 20, 17,
                        0 if override else path_hash(path))
    explicit = path.lower().replace('/', '\\').encode('ascii') + b'\0'
    explicit += b'\0' * (len(explicit) & 1)
    explicit += struct.pack('>H', 0)
    footer = struct.pack('>2I', 1, len(explicit)) + explicit if override else bytes(8)
    data = header + strings + bytes(4) + names + table + footer
    return struct.pack('>I', len(data) - 4) + data[4:]


class ArchiveTests(unittest.TestCase):
    def test_normal_hash_and_offset(self):
        rows = parse_index(fixture(), archive_limit=1024)
        self.assertEqual(rows, [dict(path='CUT/SCENE.CU3', offset=273,
                                    packed_size=20, size=20, flags=0)])

    def test_explicit_zero_hash_name(self):
        self.assertEqual(parse_index(fixture(True)), parse_index(fixture()))

    def test_unknown_version_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('>i', data, 12, -12)
        with self.assertRaisesRegex(ValueError, 'version'):
            parse_index(data)

    def test_truncation_rejected(self):
        with self.assertRaises(ValueError):
            parse_index(fixture()[:-1])

    def test_index_bounds_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, 28, len(data))
        with self.assertRaises(ValueError):
            parse_index(data)

    def test_file_bounds_rejected(self):
        with self.assertRaisesRegex(ValueError, 'archive data'):
            parse_index(fixture(), archive_limit=280)

    def test_unsafe_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            parse_index(fixture(filename='../SCENE.CU3'))

    def test_unresolved_hash_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, len(data)-12, 123)
        with self.assertRaisesRegex(ValueError, 'verified file reference'):
            parse_index(data)

    def test_windows_reserved_names_rejected_with_matching_hash(self):
        for name in ('NUL.CU3', 'COM1.CU3', 'name.', 'name ', 'CONIN$', 'bad\x7fname'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_index(fixture(filename=name))

    def test_source_path_spelling_is_retained(self):
        rows = parse_index(fixture(filename='Scene.cu3'))
        self.assertEqual(rows[0]['path'], 'CUT/Scene.cu3')

    def test_unresolved_file_parent_is_not_assumed_root(self):
        data = bytearray(fixture())
        string_size = struct.unpack_from('>I', data, 28)[0]
        second_name = 32 + string_size + 4 + 12
        struct.pack_into('>H', data, second_name + 4, 123)
        with self.assertRaisesRegex(ValueError, 'parent'):
            parse_index(data)

    def test_trailing_index_bytes_are_not_silently_ignored(self):
        data = bytearray(fixture()) + b'unknown'
        struct.pack_into('>I', data, 0, len(data) - 4)
        with self.assertRaisesRegex(ValueError, 'after CC8'):
            parse_index(data)


if __name__ == '__main__':
    unittest.main()

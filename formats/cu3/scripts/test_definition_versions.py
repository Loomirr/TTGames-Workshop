"""Observed stream-20/21 layout regressions without redistributed game assets."""
from pathlib import Path
import hashlib
import struct
import sys
import types
import unittest

source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('definition_versions_fixture')
package.__path__ = [str(source)]
sys.modules[package.__name__] = package
from definition_versions_fixture.definitions import read_definition_bytes
from definition_versions_fixture.cu3 import FormatError


def string(value):
    raw = value.encode('ascii') + b'\0'
    return struct.pack('<I', len(raw)) + raw


def block(name, payload):
    body = string(name) + payload
    return struct.pack('<I', len(body) + 4) + body


def fixture(version, *, schema_words=3, header_bytes=5, unknown=False):
    """Measured older layout: three schema words, u16 count, five-byte ID."""
    fields = [(5, 'Model File'), (4, 'Default Alpha'), (8, 'Offset')]
    if unknown:
        fields += [(99, 'Opaque'), (5, 'After opaque')]
    schema = b''.join(struct.pack('<I', typ) + string(name) + bytes(4*schema_words)
                      for typ, name in fields)
    cls = block('Class', string('Character Definition') +
                block('Version', struct.pack('<I', 1)) +
                block('Types', struct.pack('<I', len(fields)) + schema))
    members = []
    for name, alpha in (('MODEL_A', 0.5), ('MODEL_B', 0.75)):
        payload = string(name) + struct.pack('<4f', alpha, 1.0, -2.0, 3.0)
        if unknown:
            payload += b'opaque' + string('NOT_A_VERIFIED_REFERENCE')
        members.append(block('MOBJ', bytes(header_bytes) + payload))
    return (block('StreamInfo', struct.pack('<I', version)) +
            block('ClassList', struct.pack('<I', 1) + cls) +
            struct.pack('<I', 1) + block('OLST', struct.pack('<HH', 0, 2) + b''.join(members)))


class ObservedDefinitionVersions(unittest.TestCase):
    def test_observed_layout_values_and_source_spans(self):
        for version in (20, 21):
            with self.subTest(version=version):
                data = fixture(version)
                result = read_definition_bytes(data)
                self.assertEqual(result['version'], version)
                self.assertEqual(result['source_sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(len(result['objects']), 2)
                for obj, name, alpha in zip(result['objects'], ('MODEL_A', 'MODEL_B'), (0.5, 0.75)):
                    self.assertTrue(obj['complete'])
                    self.assertEqual(obj['fields'], {'Model File': name, 'Default Alpha': alpha,
                                                     'Offset': (1.0, -2.0, 3.0)})
                    span = obj['field_spans']['Model File']
                    self.assertEqual(span['offset'], data.index(string(name)))
                    self.assertEqual(data[span['offset']:span['end']], string(name))
                    self.assertEqual(obj['decoded_end'], obj['offset'] + obj['size'])

    def test_newer_schema_width_is_not_guessed(self):
        for version in (20, 21):
            with self.assertRaises(FormatError):
                read_definition_bytes(fixture(version, schema_words=4))

    def test_wrong_object_header_is_refused(self):
        for version in (20, 21):
            for width in (3, 4, 6):
                with self.assertRaises(FormatError):
                    read_definition_bytes(fixture(version, header_bytes=width))

    def test_list_count_cannot_escape_declared_extent(self):
        for version in (20, 21):
            data = bytearray(fixture(version))
            struct.pack_into('<H', data, data.index(b'OLST\0') + 7, 65535)
            with self.assertRaises(FormatError):
                read_definition_bytes(data)

    def test_invalid_class_stays_refused(self):
        data = bytearray(fixture(20))
        struct.pack_into('<H', data, data.index(b'OLST\0') + 5, 1)
        with self.assertRaisesRegex(FormatError, 'unknown class'):
            read_definition_bytes(data)

    def test_unknown_fields_remain_explicitly_incomplete(self):
        for version in (20, 21):
            for obj in read_definition_bytes(fixture(version, unknown=True))['objects']:
                self.assertFalse(obj['complete'])
                self.assertNotIn('After opaque', obj['fields'])
                self.assertEqual(obj['decoded_end'], obj['field_spans']['Offset']['end'])

    def test_truncated_streams_are_refused(self):
        for version in (20, 21):
            data = fixture(version)
            for size in (0, 12, len(data)//2, len(data)-1):
                with self.assertRaises(FormatError):
                    read_definition_bytes(data[:size])

    def test_unobserved_versions_are_not_enabled(self):
        for version in (17, 32, 38, 65535):
            with self.assertRaisesRegex(FormatError, 'not verified'):
                read_definition_bytes(fixture(version))


if __name__ == '__main__':
    unittest.main()

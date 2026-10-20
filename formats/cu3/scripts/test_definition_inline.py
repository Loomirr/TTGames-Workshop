"""Asset-free inline-class and later primitive definition regressions."""
from pathlib import Path
import struct
import sys
import types
import unittest

source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('definition_inline_fixture')
package.__path__ = [str(source)]
sys.modules[package.__name__] = package
from definition_inline_fixture.definitions import read_definition_bytes
from definition_inline_fixture.cu3 import FormatError


def text(value):
    data = value.encode('ascii') + b'\0'
    return struct.pack('<I', len(data)) + data


def block(name, payload):
    data = text(name) + payload
    return struct.pack('<I', len(data) + 4) + data


def fixture(version=31, *, recursive=False, unknown=False, bad_type=None,
            type_list=True, short=False, flags=0xa0000000, nonfinite=False):
    words = 5 if version >= 27 else 4 if version >= 22 else 3
    def field(typ, name, bits=0):
        return struct.pack('<I', typ) + text(name) + struct.pack('<3I', 0, 0, bits) + bytes(4*(words-3))
    def cls(name, fields):
        return block('Class', text(name) + block('Types', struct.pack('<I', len(fields)) + b''.join(fields)))
    fields = [field(2, 'Before'), field(1, 'Light', flags), field(5, 'Resource File')]
    nested = [field(2, 'Enabled'), field(5, 'Texture')]
    if recursive:
        nested.append(field(0, 'Cycle', 0xa0000000))
    if unknown:
        nested.append(field(99, 'Opaque'))
    if version >= 30:
        fields.insert(1, field(19, 'Tint'))
        nested.append(field(14, 'Intensity'))
    schema = block('ClassList', struct.pack('<I', 2) + cls('Outer', fields) + cls('LightDesc', nested))
    payload = struct.pack('<i', 7)
    if version >= 30:
        payload += struct.pack('<4f', 1., .5, .25, float('nan') if nonfinite else 0.)
    payload += struct.pack('<i', 1) + text('LIGHT_DDS')
    if unknown:
        payload += b'opaque bytes'
    if version >= 30:
        payload += struct.pack('<e', .25)
    payload += text('HAIR_MODEL')
    if short:
        payload = payload[:5]
    header = bytes(4 if version >= 28 else 3 if version >= 25 else 5)
    obj = block('MOBJ', header + payload)
    objects = block('OLST', struct.pack('<HI' if version >= 24 else '<HH', 0, 1) + obj)
    types = b''
    if type_list:
        entries = [('Unknown', 0)] * 20
        entries[14] = ('Half', 2)
        entries[19] = bad_type or ('Colour4', 16)
        types = block('TypeList', struct.pack('<I', len(entries)) + b''.join(
            block('Type', text(name) + struct.pack('<i', size)) for name, size in entries))
    return block('StreamInfo', struct.pack('<I', version)) + types + schema + struct.pack('<I', 1) + objects


class DefinitionInlineTests(unittest.TestCase):
    def test_inline_ownership_and_subsequent_reference_across_versions(self):
        for version in (18, 19, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31):
            with self.subTest(version=version):
                data = fixture(version)
                obj = read_definition_bytes(data)['objects'][0]
                self.assertTrue(obj['complete'])
                self.assertEqual(obj['fields']['Before'], 7)
                self.assertEqual(obj['fields']['Resource File'], 'HAIR_MODEL')
                light = obj['fields']['Light']
                self.assertEqual(light['class'], 'LightDesc')
                self.assertEqual(light['fields']['Texture'], 'LIGHT_DDS')
                span = obj['field_spans']['Resource File']
                self.assertEqual(data[span['offset']:span['end']], text('HAIR_MODEL'))
                nested_span = light['field_spans']['Texture']
                self.assertEqual(data[nested_span['offset']:nested_span['end']], text('LIGHT_DDS'))
                # A class index must never look like a primitive string type
                # to the constrained native-field writer.
                self.assertIsNone(obj['field_spans']['Light']['type'])
                if version >= 30:
                    self.assertEqual(obj['fields']['Tint'], (1., .5, .25, 0.))
                    self.assertEqual(light['fields']['Intensity'], .25)

    def test_unknown_inline_member_retains_only_verified_outer_prefix(self):
        obj = read_definition_bytes(fixture(25, unknown=True))['objects'][0]
        self.assertEqual(obj['fields'], {'Before': 7})
        self.assertFalse(obj['complete'])
        self.assertEqual(obj['decoded_end'], obj['field_spans']['Before']['end'])

    def test_colour_requires_matching_declared_name_and_width(self):
        for kwargs in ({'type_list':False}, {'bad_type':('Colour4', 8)}, {'bad_type':('Unknown', 16)}):
            obj = read_definition_bytes(fixture(**kwargs))['objects'][0]
            self.assertEqual(obj['fields'], {'Before': 7})
            self.assertFalse(obj['complete'])

    def test_unknown_inline_flags_stay_partial(self):
        obj = read_definition_bytes(fixture(25, flags=0x80000000))['objects'][0]
        self.assertEqual(obj['fields'], {'Before':7})
        self.assertFalse(obj['complete'])

    def test_recursive_schema_refused(self):
        with self.assertRaisesRegex(FormatError, 'inline definition schema'):
            read_definition_bytes(fixture(25, recursive=True))

    def test_expanding_empty_inheritance_is_bounded(self):
        # Every class inherits the next one twice, with no primitive leaves.
        # Counting decoded primitives alone cannot bound this hostile graph.
        classes = []
        for index in range(18):
            fields = b''
            if index < 17:
                fields = b''.join(struct.pack('<I', index+1) + text(name) +
                                  struct.pack('<4I', 0, 0, 0xc0000000, 0)
                                  for name in ('BaseA', 'BaseB'))
            classes.append(block('Class', text('Class'+str(index)) +
                                 block('Types', struct.pack('<I', 2 if fields else 0) + fields)))
        data = block('StreamInfo', struct.pack('<I', 25))
        data += block('ClassList', struct.pack('<I', 18) + b''.join(classes))
        data += block('OLST', struct.pack('<HI', 0, 1) + block('MOBJ', bytes(3)))
        with self.assertRaisesRegex(FormatError, 'expanded definition field count'):
            read_definition_bytes(data)

    def test_truncated_nested_field_refused(self):
        with self.assertRaises(FormatError):
            read_definition_bytes(fixture(25, short=True))

    def test_nonfinite_colour_refused(self):
        with self.assertRaisesRegex(FormatError, 'Non-finite'):
            read_definition_bytes(fixture(nonfinite=True))

    def test_type_list_count_cannot_escape_its_extent(self):
        data = bytearray(fixture())
        struct.pack_into('<I', data, data.index(b'TypeList\0') + 9, 21)
        with self.assertRaises(FormatError):
            read_definition_bytes(data)

    def test_truncated_schema_not_reported_complete(self):
        data = bytearray(fixture(25))
        obj = read_definition_bytes(data)['objects'][0]
        at = obj['field_spans']['Resource File']['offset']
        size = len(data)-at
        # Keep native block sizes consistent while dropping a required field.
        for marker in (b'OLST\0', b'MOBJ\0'):
            start = data.index(marker)-8
            struct.pack_into('<I', data, start, struct.unpack_from('<I', data, start)[0]-size)
        out = read_definition_bytes(data[:at])['objects'][0]
        self.assertFalse(out['complete'])
        self.assertNotIn('Resource File', out['fields'])


if __name__ == '__main__':
    unittest.main()

"""Asset-free native-field editing and refusal regressions."""
import hashlib
import struct
import unittest
from definition_patch import patch_definition, read_definition_bytes


def string(value):
    raw = value.encode('ascii') + b'\0'
    return struct.pack('<I', len(raw)) + raw


def block(name, payload):
    raw = name.encode('ascii') + b'\0'
    return struct.pack('<2I', 8 + len(raw) + len(payload), len(raw)) + raw + payload


def fixture(version=25):
    schema = struct.pack('<I', 5) + string('Skeleton Name') + bytes(16)
    schema += struct.pack('<I', 99) + string('Unknown') + bytes(16)
    cls = block('Class', string('Character Definition') + block('Types', struct.pack('<I', 2) + schema))
    member = block('MOBJ', bytes(3) + string('SUPER_MINIFIG') + b'opaque SUPER_MINIFIG payload')
    return block('StreamInfo', struct.pack('<I', version)) + block('ClassList', cls) + block('OLST', struct.pack('<HI', 0, 1) + member)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.obj = read_definition_bytes(self.data)['objects'][0]
        self.edit = dict(object_offset=self.obj['offset'], **{'class':'Character Definition'},
                         field='Skeleton Name', expected='SUPER_MINIFIG', replacement='PILOT_MINIFIG')

    def run_patch(self, edits=None, **options):
        return patch_definition(self.data, edits if edits is not None else [self.edit],
                                expected_sha256=options.get('sha', self.sha), game=options.get('game', 'lmsh1'))

    def test_exact_field_only_and_opaque_tail_preserved(self):
        self.assertFalse(self.obj['complete'])
        result = self.run_patch()
        self.assertTrue(result.endswith(b'opaque SUPER_MINIFIG payload'))
        after = read_definition_bytes(result)['objects'][0]
        self.assertEqual(after['fields']['Skeleton Name'], 'PILOT_MINIFIG')
        self.assertEqual(after['field_spans'], self.obj['field_spans'])
        span = self.obj['field_spans']['Skeleton Name']
        self.assertEqual(result[:span['offset']], self.data[:span['offset']])
        self.assertEqual(result[span['end']:], self.data[span['end']:])

    def test_identity_and_game_guards(self):
        for kwargs in ({'sha':'0'*64}, {'game':'lb3'}):
            with self.assertRaises(ValueError): self.run_patch(**kwargs)

    def test_refuse_unknown_wrong_owner_wrong_value_and_resize(self):
        for change in ({'field':'Unknown'}, {'object_offset':0}, {'class':'Other'},
                       {'expected':'wrong'}, {'replacement':'LONGER_NAME_HERE'},
                       {'replacement':'PILOT_MINIFI\0'}, {'replacement':'PILOT_MINIFIé'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_patch([dict(self.edit, **change)])

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            self.run_patch([self.edit, self.edit])

    def test_truncation_refused(self):
        data = self.data[:-1]
        with self.assertRaises(ValueError):
            patch_definition(data, [self.edit], expected_sha256=hashlib.sha256(data).hexdigest(), game='lmsh1')

    def test_compressed_refused(self):
        data = b'Deflate_v1.0' + self.data
        with self.assertRaisesRegex(ValueError, 'Compressed'):
            patch_definition(data, [self.edit], expected_sha256=hashlib.sha256(data).hexdigest(), game='lmsh1')


if __name__ == '__main__':
    unittest.main()

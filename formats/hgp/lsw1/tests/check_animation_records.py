"""Synthetic LSW1 ANI/BSA records, including off-clip keys and malformed tables."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from animation_records import AnimationRecords, AnimationError
from animation_cli import main


def fixture(family='ANI'):
    base = 0x12340020
    delta = 0 if family == 'ANI' else 4
    components = 9 if family == 'ANI' else 3
    values = 36 if family == 'ANI' else 48
    types = values + components * 4
    flags = types + components
    data = bytearray((flags + 1 + 3) & ~3)
    struct.pack_into('<III', data, 0, 2, base, base + 12 + delta)
    struct.pack_into('<fHHIIII', data, 12 + delta, 34, 1, components, 2,
                     base + values, base + types, base + flags)
    for i in range(components):
        struct.pack_into('<f', data, values + i * 4, 1.0)
    data[flags] = 0x43
    for channel, kind in enumerate((1, 2)):
        at = len(data)
        data.extend(bytes(12))
        data[types + channel] = kind
        struct.pack_into('<I', data, values + channel * 4, base + at)
        payload = len(data)
        if kind == 1:
            for time, value, tangent in ((1, 2, .25), (33, 4, -.5), (43, 8, .125)):
                data.extend(struct.pack('<4f', time, 1/32, value, tangent))
        else:
            data.extend(struct.pack('<ff', .01, .25))
            for value, tangent, time in ((100, -2, 0), (-200, 3, 32), (250, 4, 42)):
                data.extend(struct.pack('<hbB', value, tangent, time))
        masks = len(data)
        data.extend(struct.pack('<IIHH', 1, 1, 0, 1))
        struct.pack_into('<III', data, at, base + masks, base + masks + 8, base + payload)
    data.extend(b'unknown trailer\x00\xfe')
    return data


class AnimationTests(unittest.TestCase):
    def test_both_profiles_and_off_clip_keys(self):
        for family in ('ANI', 'BSA'):
            clip = AnimationRecords(fixture(family), family)
            self.assertEqual(clip.summary()['extra_keys'], 2)
            self.assertEqual(clip.records[0]['mask_frames'], [0, 32])
            self.assertEqual(clip.records[1]['keys'][2]['stored_time'], 42)
            self.assertEqual(clip.records[1]['keys'][0]['value'], 25)
            self.assertAlmostEqual(clip.records[1]['keys'][0]['tangent'], -.02)
            self.assertEqual(clip.transform_channel(0, 0, expected_sha256=clip.sha256), clip.data)

    def test_float_edit_preserves_times_tables_and_other_channels(self):
        clip = AnimationRecords(fixture(), 'ANI')
        output = clip.transform_channel(0, 0, scale=2, offset=3, expected_sha256=clip.sha256)
        edited = AnimationRecords(output, 'ANI')
        self.assertEqual([k['value'] for k in edited.records[0]['keys']], [7, 11, 19])
        self.assertEqual([k['tangent'] for k in edited.records[0]['keys']], [.5, -1, .25])
        allowed = {at for key in clip.records[0]['keys'] for at in range(key['at']+8, key['at']+16)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(clip.data, output))))
        self.assertEqual(len(output), len(clip.data))
        self.assertEqual(edited.records[1:], clip.records[1:])

    def test_quantized_edit_retains_compressed_keys_and_lookup_tables(self):
        clip = AnimationRecords(fixture(), 'ANI')
        output = clip.transform_channel(0, 1, scale=-.5, expected_sha256=clip.sha256)
        edited = AnimationRecords(output, 'ANI')
        p = clip.records[1]['payload']
        self.assertEqual(clip.data[:p], output[:p])
        self.assertEqual(clip.data[p+8:], output[p+8:])
        for old, new in zip(clip.records[1]['keys'], edited.records[1]['keys']):
            self.assertAlmostEqual(new['value'], old['value'] * -.5)
            self.assertAlmostEqual(new['tangent'], old['tangent'] * -.5)

    def test_offset_and_constant_edit(self):
        clip = AnimationRecords(fixture('BSA'), 'BSA')
        output = clip.transform_channel(0, 1, offset=.5, expected_sha256=clip.sha256)
        edited = AnimationRecords(output, 'BSA')
        self.assertEqual(edited.records[1]['keys'][0]['value'], 25.5)
        output = clip.transform_channel(0, 2, scale=3, offset=4, expected_sha256=clip.sha256)
        self.assertEqual(AnimationRecords(output, 'BSA').records[2]['value'], 7)

    def test_edit_rejections(self):
        clip = AnimationRecords(fixture(), 'ANI')
        with self.assertRaisesRegex(AnimationError, 'hash'):
            clip.transform_channel(0, 0, expected_sha256='stale')
        for channel, options in ((-1, {}), (9, {}), (0, {'scale': float('nan')}),
                                 (0, {'scale': 1e300}), (1, {'offset': 1e300}),
                                 (1, {'scale': 0, 'offset': 1})):
            with self.assertRaises(AnimationError):
                clip.transform_channel(0, channel, expected_sha256=clip.sha256, **options)

    def test_unknown_type_and_profile(self):
        data = fixture()
        types = struct.unpack_from('<I', data, 28)[0] - struct.unpack_from('<I', data, 4)[0]
        data[types] = 7
        with self.assertRaisesRegex(AnimationError, 'curve type'):
            AnimationRecords(data, 'ANI')
        with self.assertRaises(AnimationError):
            AnimationRecords(fixture(), 'AN3')
        with self.assertRaises(AnimationError):
            AnimationRecords(fixture('BSA'), 'ANI')

    def test_truncation_pointers_and_nonfinite(self):
        for at, value in ((0, 3), (24, 0xffffffff), (12, 0x7fc00000),
                          (16, 0xffffffff), (20, 0xffffffff), (44, 0x7f800000)):
            data = fixture()
            struct.pack_into('<I', data, at, value)
            with self.assertRaises(AnimationError):
                AnimationRecords(data, 'ANI')
        for length in (0, 35, 50, 90, 150):
            with self.assertRaises(AnimationError):
                AnimationRecords(fixture()[:length], 'ANI')

    def test_lookup_prefix_and_region_overlap(self):
        clip = AnimationRecords(fixture(), 'ANI')
        curve = clip.records[0]['address']
        data = bytearray(clip.data)
        prefixes = clip.pointer(curve+4)
        struct.pack_into('<H', data, prefixes+2, 42)
        with self.assertRaisesRegex(AnimationError, 'prefix'):
            AnimationRecords(data, 'ANI')
        data = bytearray(clip.data)
        struct.pack_into('<I', data, 32, clip.base + 36)
        with self.assertRaisesRegex(AnimationError, 'Overlapping'):
            AnimationRecords(data, 'ANI')

    def test_same_count_does_not_establish_ownership(self):
        clip = AnimationRecords(fixture(), 'ANI')
        self.assertIn('no rig ownership', clip.summary()['scope'])

    def test_shared_curve_can_be_inspected_but_not_edited_accidentally(self):
        data = fixture()
        data[73] = 1  # second channel now aliases the first float curve
        data[40:44] = data[36:40]
        clip = AnimationRecords(data, 'ANI')
        self.assertTrue(clip.aliases)
        self.assertEqual(clip.transform_channel(0, 0, expected_sha256=clip.sha256), bytes(data))
        with self.assertRaisesRegex(AnimationError, 'shared'):
            clip.transform_channel(0, 0, scale=2, expected_sha256=clip.sha256)

    def test_time_disagreement_is_reported_and_preserved(self):
        data = fixture()
        clip = AnimationRecords(data, 'ANI')
        struct.pack_into('<f', data, clip.records[0]['keys'][1]['at'], -22)
        clip = AnimationRecords(data, 'ANI')
        self.assertEqual(clip.summary()['key_time_mask_disagreements'], 1)
        output = clip.transform_channel(0, 0, scale=2, expected_sha256=clip.sha256)
        self.assertEqual(AnimationRecords(output, 'ANI').records[0]['keys'][1]['stored_time'], -22)

    def test_cli_never_overwrites_and_hash_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'source.ani', Path(folder)/'new.ani'
            source.write_bytes(fixture())
            clip = AnimationRecords(source.read_bytes(), 'ANI')
            args = ['transform', str(source), '--family', 'ANI', '--output', str(target),
                    '--track', '0', '--component', '0', '--scale', '2', '--source-sha256', clip.sha256]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                main(args)
                saved = target.read_bytes()
                with self.assertRaises(SystemExit):
                    main(args)
                self.assertEqual(target.read_bytes(), saved)
                with self.assertRaises(SystemExit):
                    main(args[:-2])
            self.assertEqual(source.read_bytes(), clip.data)

    def test_cli_sample_and_time_option_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.ani'
            source.write_bytes(fixture())
            output = io.StringIO()
            with redirect_stdout(output):
                main(['sample', str(source), '--family', 'ANI', '--track', '0',
                      '--component', '0', '--time', '17'])
            self.assertEqual(json.loads(output.getvalue())['sample']['value'], 6)
            for operation in ('inspect', 'transform'):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main([operation, str(source), '--family', 'ANI', '--time', '17'])


if __name__ == '__main__':
    unittest.main()

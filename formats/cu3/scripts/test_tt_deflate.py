"""Asset-free TT compression, bank bounds and wrapper checks."""
from pathlib import Path
import random
import struct
import sys
import types
import unittest
import zlib

package = types.ModuleType('tt_deflate_test')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_deflate_test.tt_deflate import compress, decompress, MAX_OUTPUT, _fixed_to_tt
from tt_deflate_test.cu3 import FormatError


def wrapper(stream, size):
    return b'Deflate_v1.0'.ljust(32,b'\0') + struct.pack('<I',size) + stream


class Checks(unittest.TestCase):
    def test_compressor_reduces_repetitive_animation_like_data(self):
        payload = struct.pack('<4f', 0, 0, 0, 1) * 4096
        result = compress(payload)
        self.assertEqual(decompress(result), payload)
        self.assertLess(len(result), len(payload) // 10)
        # This small fixed-only output retains standard DEFLATE framing.
        self.assertEqual((result[36] >> 1) & 3, 1)
        self.assertEqual(zlib.decompress(result[36:], -15), payload)

    def test_compressor_incompressible_multiple_stored_blocks(self):
        payload = random.Random(17).randbytes(200000)
        result = compress(payload)
        self.assertEqual(decompress(result), payload)
        self.assertEqual((result[36] >> 1) & 3, 2)
        with self.assertRaisesRegex(FormatError, 'block count'):
            compress(payload, max_blocks=1)

    def test_translation_mixed_fixed_stored_fixed_blocks(self):
        first, middle, last = b'a' * 1000, bytes(range(100)), b'z' * 1000
        # Each fixed block ends at byte alignment using zlib's empty stored
        # sync block. Insert a genuine nonempty stored block between them.
        encoder = zlib.compressobj(wbits=-15, strategy=zlib.Z_FIXED)
        prefix = encoder.compress(first) + encoder.flush(zlib.Z_SYNC_FLUSH)
        suffix_encoder = zlib.compressobj(wbits=-15, strategy=zlib.Z_FIXED)
        suffix = suffix_encoder.compress(last) + suffix_encoder.flush()
        stored = b'\x00' + struct.pack('<HH', len(middle), len(middle) ^ 0xffff) + middle
        raw = prefix + stored + suffix
        payload = first + middle + last
        self.assertEqual(zlib.decompress(raw, -15), payload)
        translated = _fixed_to_tt(raw, len(payload), 100)
        self.assertEqual(len(translated), len(raw) - 4)
        self.assertEqual(decompress(wrapper(translated, len(payload))), payload)

    def test_compressor_boundaries_and_bytes_like_inputs(self):
        for size in (1, 2, 257, 258, 65535, 65536, 131072):
            payload = (bytes(range(256)) * (size // 256 + 1))[:size]
            with self.subTest(size=size):
                for source in (payload, bytearray(payload), memoryview(payload)):
                    self.assertEqual(decompress(compress(source)), payload)

    def test_compressor_refuses_invalid_limits_and_inputs(self):
        for kwargs in ({'max_input': -1}, {'max_input': MAX_OUTPUT + 1},
                       {'max_packed': -1}, {'max_packed': 1.5},
                       {'max_blocks': 0}, {'max_blocks': 65537}):
            with self.subTest(kwargs=kwargs), self.assertRaises(FormatError):
                compress(b'abc', **kwargs)
        for source in (b'', 'abc', b'Deflate_v1.0nested'):
            with self.subTest(source=source), self.assertRaises(FormatError):
                compress(source)
        with self.assertRaisesRegex(FormatError, 'input exceeds'):
            compress(b'abc', max_input=2)
        packed = compress(b'abc')
        with self.assertRaisesRegex(FormatError, 'packed output'):
            compress(b'abc', max_packed=len(packed)-1)
        self.assertEqual(compress(b'abc', max_packed=len(packed)), packed)

    def test_translation_refuses_malformed_or_unexpected_standard_blocks(self):
        for raw, expected in ((b'\x07', 1), (b'\x05', 1),
                              (b'\x01\x01\0\0\0a', 1),
                              (b'\x01\x01\0\xfe\xff', 1),
                              (b'\x01\x01\0\xfe\xffa', 2),
                              (b'\x01\x01\0\xfe\xffa\0', 1),
                              (b'\x01\x01\0\xfe\xffa', 0)):
            with self.subTest(raw=raw), self.assertRaises(FormatError):
                _fixed_to_tt(raw, expected, 100)

    def test_fixed_block_and_overlapping_matches(self):
        payload = b'abcdefgh'*100
        compressor = zlib.compressobj(wbits=-15,strategy=zlib.Z_FIXED)
        raw = compressor.compress(payload)+compressor.flush()
        self.assertEqual((raw[0]>>1)&3,1)
        self.assertEqual(decompress(wrapper(raw,len(payload))),payload)

    def test_dynamic_tag_differs_from_standard_deflate(self):
        payload = bytes(range(90))*30+b'x'*2000
        compressor = zlib.compressobj(wbits=-15)
        raw = bytearray(compressor.compress(payload)+compressor.flush())
        self.assertEqual((raw[0]>>1)&3,2)
        raw[0] &= ~6
        self.assertEqual(decompress(wrapper(raw,len(payload))),payload)

    def test_stored_block_omits_complement_length(self):
        self.assertEqual(decompress(wrapper(b'\x05\x03\x00abc',3)),b'abc')

    def test_multiple_blocks(self):
        # Non-final stored block followed by final stored block.
        self.assertEqual(decompress(wrapper(b'\x04\x01\x00a\x05\x01\x00b',2)),b'ab')

    def test_invalid_inputs_and_limits(self):
        for data in (b'',wrapper(b'\x07',1),wrapper(b'\x05\x02\x00a',2),
                     wrapper(b'\x05\x02\x00ab',1),wrapper(b'',MAX_OUTPUT+1)):
            with self.assertRaises(FormatError):
                decompress(data)

    def test_decoded_size_must_match(self):
        with self.assertRaises(FormatError):
            decompress(wrapper(b'\x05\x01\x00a',2))

    def test_trailing_full_bytes_and_concatenated_frames_rejected(self):
        stream = wrapper(b'\x05\x01\x00a', 1)
        for suffix in (b'\0', b'extra', stream):
            with self.subTest(suffix=suffix[:8]), self.assertRaisesRegex(FormatError, 'Trailing'):
                decompress(stream + suffix)

    def test_packed_size_and_empty_block_work_limits(self):
        stream = wrapper(b'\x05\x01\x00a', 1)
        with self.assertRaisesRegex(FormatError, 'packed input'):
            decompress(stream, max_packed=len(stream) - 1)
        # Each non-final block consumes input even with no output. Bound that
        # work separately so a tiny decoded size cannot imply cheap decoding.
        empty_blocks = b'\x04\0\0' * 4 + b'\x05\x01\x00a'
        with self.assertRaisesRegex(FormatError, 'block count'):
            decompress(wrapper(empty_blocks, 1), max_blocks=4)
        self.assertEqual(decompress(wrapper(empty_blocks, 1), max_blocks=5), b'a')


if __name__ == '__main__':
    unittest.main()

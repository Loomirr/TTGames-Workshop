"""Asset-free TT compression, bank bounds and wrapper checks."""
from pathlib import Path
import struct
import sys
import types
import unittest
import zlib

package = types.ModuleType('tt_deflate_test')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_deflate_test.tt_deflate import decompress, MAX_OUTPUT
from tt_deflate_test.cu3 import FormatError


def wrapper(stream, size):
    return b'Deflate_v1.0'.ljust(32,b'\0') + struct.pack('<I',size) + stream


class Checks(unittest.TestCase):
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

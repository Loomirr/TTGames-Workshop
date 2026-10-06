"""Bounded, original decoder for observed TT LZ2K/DFLT/ZLIB chunk streams.

LZ2K uses MSB-first canonical Huffman blocks and overlapping LZ references.
No native executable or third-party decompressor is loaded.

The supported chunk layout is explicitly little-endian raw length followed
by packed length. LOTR mode 3 has a different, unverified frame and codec;
recognizing a DFLT tag alone must never enable that mode.
"""
import struct
import zlib
from .cu3 import FormatError

MAX_SIZE = 256 * 1024 * 1024
MAX_CHUNKS = 65536


class _Bits:
    def __init__(self, data):
        self.data, self.position = data, 0

    def take(self, count):
        if count < 0 or self.position + count > len(self.data) * 8:
            raise FormatError('Truncated LZ2K bit stream')
        value = 0
        for _ in range(count):
            value = (value << 1) | ((self.data[self.position // 8] >> (7 - self.position % 8)) & 1)
            self.position += 1
        return value


class _Codes:
    def __init__(self, lengths=(), constant=None, limit=0):
        self.constant, self.codes = constant, {}
        if constant is not None:
            if not 0 <= constant < limit:
                raise FormatError('LZ2K constant symbol outside alphabet')
            return
        if not lengths or not 0 < max(lengths) <= 16:
            raise FormatError('Invalid LZ2K Huffman lengths')
        code = 0
        for width in range(1, max(lengths) + 1):
            for symbol, length in enumerate(lengths):
                if length == width:
                    if code >= 1 << width:
                        raise FormatError('Oversubscribed LZ2K Huffman tree')
                    self.codes[width, code] = symbol
                    code += 1
            code <<= 1

    def symbol(self, bits):
        if self.constant is not None:
            return self.constant
        code = 0
        for width in range(1, 17):
            code = (code << 1) | bits.take(1)
            symbol = self.codes.get((width, code))
            if symbol is not None:
                return symbol
        raise FormatError('Invalid LZ2K Huffman code')


def _length_codes(bits, limit, width, skip_at=-1):
    count = bits.take(width)
    if count == 0:
        return _Codes(constant=bits.take(width), limit=limit)
    if count > limit:
        raise FormatError('LZ2K length alphabet exceeds its limit')
    lengths = []
    while len(lengths) < count:
        length = bits.take(3)
        if length == 7:
            while bits.take(1):
                length += 1
                if length > 16:
                    raise FormatError('Excessive LZ2K code length')
        lengths.append(length)
        if len(lengths) == skip_at:
            lengths.extend([0] * bits.take(2))
        if len(lengths) > count:
            raise FormatError('LZ2K zero run exceeds length table')
    return _Codes(lengths)


def _literal_codes(bits, lengths):
    count = bits.take(9)
    if count == 0:
        return _Codes(constant=bits.take(9), limit=510)
    if count > 510:
        raise FormatError('LZ2K literal alphabet exceeds its limit')
    result = []
    while len(result) < count:
        symbol = lengths.symbol(bits)
        if symbol > 2:
            result.append(symbol - 2)
        else:
            run = 1 if symbol == 0 else bits.take(4) + 3 if symbol == 1 else bits.take(9) + 20
            result.extend([0] * run)
        if len(result) > count:
            raise FormatError('LZ2K zero run exceeds literal table')
    return _Codes(result)


def decode_lz2k_chunk(payload, expected_size):
    if len(payload) > MAX_SIZE:
        raise FormatError('LZ2K packed chunk exceeds size limit')
    if not isinstance(expected_size, int) or not 0 < expected_size <= 32768:
        raise FormatError('Unverified LZ2K chunk output size')
    bits, output = _Bits(payload), bytearray()
    while len(output) < expected_size:
        count = bits.take(16)
        if count == 0 or count > expected_size - len(output):
            raise FormatError('Invalid LZ2K block token count')
        lengths = _length_codes(bits, 19, 5, 3)
        literals = _literal_codes(bits, lengths)
        distances = _length_codes(bits, 16, 4)
        for _ in range(count):
            value = literals.symbol(bits)
            if value < 256:
                if len(output) >= expected_size:
                    raise FormatError('LZ2K literal exceeds decoded data')
                output.append(value)
                continue
            length = value - 253
            distance = distances.symbol(bits)
            if distance:
                distance = (1 << (distance - 1)) + bits.take(distance - 1)
            distance += 1
            if distance > len(output) or len(output) + length > expected_size:
                raise FormatError('LZ2K back-reference exceeds decoded data')
            for _ in range(length):
                output.append(output[-distance])
    if len(output) != expected_size:
        raise FormatError('LZ2K output size mismatch')
    if (bits.position + 7) // 8 != len(payload):
        raise FormatError('Trailing bytes after LZ2K chunk')
    return bytes(output)


def decode_entry(data, expected_size, max_size=MAX_SIZE, *,
                 max_packed=MAX_SIZE, max_chunks=MAX_CHUNKS, storage_mode=None):
    if (not isinstance(max_size, int) or not 0 <= max_size <= MAX_SIZE or
            not isinstance(max_packed, int) or not 0 <= max_packed <= MAX_SIZE or
            not isinstance(max_chunks, int) or not 0 < max_chunks <= MAX_CHUNKS):
        raise FormatError('Invalid archive decoding limits')
    if not isinstance(expected_size, int) or not 0 <= expected_size <= max_size:
        raise FormatError('Archive asset exceeds configured size limit')
    if len(data) > max_packed:
        raise FormatError('Archive packed input exceeds configured size limit')
    if storage_mode not in (None, 0, 2):
        raise FormatError(f'Unverified archive storage mode {storage_mode}; codec must be established from original evidence')
    if storage_mode == 0:
        if len(data) != expected_size:
            raise FormatError('Uncompressed archive asset size mismatch')
        return data
    if data[:4] not in (b'LZ2K', b'DFLT', b'ZLIB'):
        if data[:4] in (b'LZMA', b'ZIPX', b'RFPK', b'RNC_'):
            raise FormatError('Unsupported archive compression: ' + repr(data[:4]))
        if len(data) != expected_size:
            raise FormatError('Uncompressed archive asset size mismatch')
        return data
    # Preflight every header and both cumulative lengths before invoking any
    # decompressor; even a late invalid frame cannot trigger prior decoding.
    offset, total, chunks = 0, 0, []
    while offset < len(data):
        if offset + 12 > len(data):
            raise FormatError('Truncated archive compression header')
        magic, raw_size, packed_size = struct.unpack_from('<4sII', data, offset)
        offset += 12
        if magic not in (b'LZ2K', b'DFLT', b'ZLIB') or not raw_size or not packed_size:
            raise FormatError('Invalid archive compression chunk')
        if offset + packed_size > len(data) or total + raw_size > expected_size:
            raise FormatError('Archive chunk exceeds declared bounds')
        chunks.append((magic, raw_size, offset, packed_size))
        if len(chunks) > max_chunks:
            raise FormatError('Archive compression chunk count exceeds limit')
        total += raw_size
        offset += packed_size
    if total != expected_size:
        raise FormatError('Archive asset output size mismatch')
    output = bytearray()
    for magic, raw_size, offset, packed_size in chunks:
        payload = data[offset:offset + packed_size]
        if packed_size == raw_size:
            decoded = payload
        elif magic == b'LZ2K':
            decoded = decode_lz2k_chunk(payload, raw_size)
        else:
            try:
                decoder = zlib.decompressobj(-15 if magic == b'DFLT' else 15)
                decoded = decoder.decompress(payload, raw_size + 1)
            except zlib.error as error:
                raise FormatError('Invalid deflate archive chunk') from error
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise FormatError('Invalid or oversized deflate archive chunk')
        if len(decoded) != raw_size:
            raise FormatError('Archive chunk output size mismatch')
        output.extend(decoded)
    if len(output) != expected_size:
        raise FormatError('Archive asset output size mismatch')
    return bytes(output)

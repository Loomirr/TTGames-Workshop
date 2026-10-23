"""Bounded reader and compressor for observed TT Deflate_v1.0 streams.

The wrapper and block conventions were researched using ttgames.bms and the
public QuickBMS undflt reference. No executable decoder or engine code is used.
TT swaps stored/dynamic block tags and omits stored-block complement lengths.
Huffman codes, length/distance alphabets and bit order follow DEFLATE.
"""
import struct
import zlib
from .cu3 import FormatError

MAX_OUTPUT = 256 * 1024 * 1024
MAX_PACKED = 256 * 1024 * 1024
MAX_BLOCKS = 65536


class Bits:
    def __init__(self, data):
        self.data, self.position = data, 0

    def take(self, count):
        if count < 0 or self.position + count > len(self.data) * 8:
            raise FormatError('Truncated TT deflate bitstream')
        value = 0
        for i in range(count):
            at = self.position + i
            value |= ((self.data[at // 8] >> (at % 8)) & 1) << i
        self.position += count
        return value


def huffman(lengths):
    counts = [lengths.count(i) for i in range(16)]
    counts[0] = 0
    code, codes = 0, {}
    next_code = [0] * 16
    for width in range(1, 16):
        code = (code + counts[width - 1]) << 1
        if code + counts[width] > 1 << width:
            raise FormatError('Oversubscribed TT Huffman tree')
        next_code[width] = code
    for symbol, width in enumerate(lengths):
        if not 0 <= width <= 15:
            raise FormatError('Invalid TT Huffman width')
        if width:
            codes[width, next_code[width]] = symbol
            next_code[width] += 1
    return codes


def symbol(bits, tree):
    code = 0
    for width in range(1, 16):
        code = (code << 1) | bits.take(1)
        if (width, code) in tree:
            return tree[width, code]
    raise FormatError('Invalid TT Huffman code')


def dynamic(bits):
    literals, distances, count = bits.take(5) + 257, bits.take(5) + 1, bits.take(4) + 4
    if literals > 286:
        raise FormatError('Invalid TT literal count')
    order = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)
    lengths = [0] * 19
    for i in range(count):
        lengths[order[i]] = bits.take(3)
    tree, values = huffman(lengths), []
    while len(values) < literals + distances:
        value = symbol(bits, tree)
        if value < 16:
            values.append(value)
        elif value == 16:
            if not values:
                raise FormatError('TT repeat has no preceding code')
            values.extend([values[-1]] * (bits.take(2) + 3))
        else:
            values.extend([0] * (bits.take(3 if value == 17 else 7) + (3 if value == 17 else 11)))
        if len(values) > literals + distances:
            raise FormatError('TT code repeat exceeds alphabet')
    if not values[256]:
        raise FormatError('TT literal tree has no end marker')
    return huffman(values[:literals]), huffman(values[literals:])


LENGTH_BASE = (3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258)
LENGTH_BITS = (0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0)
DIST_BASE = (1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577)
DIST_BITS = (0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13)


def _fixed_to_tt(raw, expected, max_blocks):
    """Translate a validated standard fixed/stored stream to TT framing.

    Removing a stored block's 16-bit NLEN preserves byte alignment for every
    later block. Fixed Huffman codes and match data are copied unchanged.
    Scan the whole stream: changing only its first header misses mixed blocks.
    """
    bits, output_size, blocks, final = Bits(raw), 0, 0, False
    changed = bytearray(raw)
    complements = []
    literals = huffman([8]*144 + [9]*112 + [7]*24 + [8]*8)
    distances = huffman([5]*32)
    while not final:
        blocks += 1
        if blocks > max_blocks:
            raise FormatError('TT deflate block count exceeds limit')
        header = bits.position
        final, kind = bits.take(1), bits.take(2)
        if kind == 0:
            # Standard stored tag 00 becomes TT stored tag 10 (LSB first).
            at = header + 2
            changed[at // 8] |= 1 << (at % 8)
            bits.position = (bits.position + 7) // 8 * 8
            count = bits.take(16)
            complement_at = bits.position // 8
            if bits.take(16) != count ^ 0xffff:
                raise FormatError('Invalid standard deflate stored length')
            complements.append(complement_at)
            if bits.position + count * 8 > len(raw) * 8:
                raise FormatError('Truncated standard deflate stored block')
            bits.position += count * 8
            output_size += count
        elif kind == 1:
            while True:
                value = symbol(bits, literals)
                if value == 256:
                    break
                if value < 256:
                    output_size += 1
                else:
                    if value > 285:
                        raise FormatError('Invalid standard deflate match length')
                    length = LENGTH_BASE[value-257] + bits.take(LENGTH_BITS[value-257])
                    distance = symbol(bits, distances)
                    if distance >= 30:
                        raise FormatError('Invalid standard deflate match distance')
                    distance = DIST_BASE[distance] + bits.take(DIST_BITS[distance])
                    if distance > output_size:
                        raise FormatError('Standard deflate match exceeds decoded bounds')
                    output_size += length
                if output_size > expected:
                    raise FormatError('Standard deflate output exceeds expected size')
        else:
            raise FormatError('TT compressor requires fixed or stored deflate blocks')
        if output_size > expected:
            raise FormatError('Standard deflate output exceeds expected size')
    if output_size != expected or (bits.position + 7) // 8 != len(raw):
        raise FormatError('Standard deflate framing or output size mismatch')
    for offset in reversed(complements):
        del changed[offset:offset+2]
    return bytes(changed)


def compress(data, max_input=MAX_OUTPUT, *, max_packed=MAX_PACKED,
             max_blocks=MAX_BLOCKS):
    """Compress bytes into one TT wrapper using fixed Huffman/stored blocks.

    zlib supplies the matches; this module translates its framing and checks
    the result with the TT decoder. No game-specific AN4 data is changed here.
    Empty or nested TT streams are outside the verified wrapper profile.
    """
    if (not isinstance(max_input, int) or not 0 <= max_input <= MAX_OUTPUT or
            not isinstance(max_packed, int) or not 0 <= max_packed <= MAX_PACKED or
            not isinstance(max_blocks, int) or not 0 < max_blocks <= MAX_BLOCKS):
        raise FormatError('Invalid TT deflate compression limits')
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise FormatError('TT deflate compressor requires bytes')
    input_size = data.nbytes if isinstance(data, memoryview) else len(data)
    if not 0 < input_size <= max_input:
        raise FormatError('TT deflate input exceeds limit or is empty')
    data = bytes(data)
    if data.startswith(b'Deflate_v1.0'):
        raise FormatError('Nested TT deflate wrapper framing is not verified')
    encoder = zlib.compressobj(level=6, wbits=-15, strategy=zlib.Z_FIXED)
    raw = encoder.compress(data) + encoder.flush()
    # Standard stored blocks include two extra bytes each, removed below.
    if len(raw) + 36 > max_packed + 2 * max_blocks:
        raise FormatError('TT deflate packed output exceeds limit')
    verifier = zlib.decompressobj(wbits=-15)
    decoded = verifier.decompress(raw, input_size + 1)
    if (decoded != data or not verifier.eof or verifier.unused_data or
            verifier.unconsumed_tail):
        raise FormatError('Standard deflate compression verification failed')
    stream = _fixed_to_tt(raw, input_size, max_blocks)
    packed = b'Deflate_v1.0'.ljust(32, b'\0') + struct.pack('<I', input_size) + stream
    if len(packed) > max_packed:
        raise FormatError('TT deflate packed output exceeds limit')
    if decompress(packed, max_input, max_packed=max_packed, max_blocks=max_blocks) != data:
        raise FormatError('TT deflate compression verification failed')
    return packed


def decompress(data, max_output=MAX_OUTPUT, *, max_packed=MAX_PACKED,
               max_blocks=MAX_BLOCKS):
    """Decode one verified wrapper, with no recursive codec guessing.

    Only the final partial byte may remain after the final block. Whole
    trailing bytes or another wrapper require an independently known frame.
    """
    if (not isinstance(max_output, int) or not 0 <= max_output <= MAX_OUTPUT or
            not isinstance(max_packed, int) or not 0 <= max_packed <= MAX_PACKED or
            not isinstance(max_blocks, int) or not 0 < max_blocks <= MAX_BLOCKS):
        raise FormatError('Invalid TT deflate decoding limits')
    if len(data) > max_packed:
        raise FormatError('TT deflate packed input exceeds limit')
    if len(data) < 36 or data[:32] != b'Deflate_v1.0'.ljust(32, b'\0'):
        raise FormatError('Invalid TT deflate wrapper')
    expected = struct.unpack_from('<I', data, 32)[0]
    if not 0 < expected <= max_output:
        raise FormatError('TT deflate output exceeds limit')
    bits, output, final, blocks = Bits(data[36:]), bytearray(), False, 0
    while not final:
        blocks += 1
        if blocks > max_blocks:
            raise FormatError('TT deflate block count exceeds limit')
        final, kind = bits.take(1), bits.take(2)
        if kind == 2:
            bits.position = (bits.position + 7) // 8 * 8
            count = bits.take(16)
            if len(output) + count > expected:
                raise FormatError('TT stored block exceeds output')
            output.extend(bits.take(8) for _ in range(count))
            continue
        if kind == 0:
            literals, distances = dynamic(bits)
        elif kind == 1:
            literals = huffman([8]*144 + [9]*112 + [7]*24 + [8]*8)
            distances = huffman([5]*32)
        else:
            raise FormatError('Reserved TT deflate block')
        while True:
            value = symbol(bits, literals)
            if value == 256:
                break
            if value < 256:
                if len(output) >= expected:
                    raise FormatError('TT literal exceeds output')
                output.append(value)
                continue
            if value > 285:
                raise FormatError('Invalid TT match length')
            length = LENGTH_BASE[value-257] + bits.take(LENGTH_BITS[value-257])
            distance = symbol(bits, distances)
            if distance >= 30:
                raise FormatError('Invalid TT match distance')
            distance = DIST_BASE[distance] + bits.take(DIST_BITS[distance])
            if distance > len(output) or len(output) + length > expected:
                raise FormatError('TT match exceeds decoded bounds')
            for _ in range(length):
                output.append(output[-distance])
    if len(output) != expected:
        raise FormatError('TT deflate output size mismatch')
    if (bits.position + 7) // 8 != len(bits.data):
        raise FormatError('Trailing bytes after final TT deflate block')
    if output.startswith(b'Deflate_v1.0'):
        raise FormatError('Nested TT deflate wrapper framing is not verified')
    return bytes(output)

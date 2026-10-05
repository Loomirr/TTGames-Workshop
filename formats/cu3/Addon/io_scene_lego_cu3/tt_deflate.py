"""Bounded, original Python reader for observed TT Deflate_v1.0 streams.

The wrapper and block conventions were researched using ttgames.bms and the
public QuickBMS undflt reference. No executable decoder or engine code is used.
TT swaps stored/dynamic block tags and omits stored-block complement lengths.
Huffman codes, length/distance alphabets and bit order follow DEFLATE.
"""
import struct
from .cu3 import FormatError

MAX_OUTPUT = 256 * 1024 * 1024


class Bits:
    def __init__(self, data):
        self.data, self.position = data, 0

    def take(self, count):
        if self.position + count > len(self.data) * 8:
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


def decompress(data, max_output=MAX_OUTPUT):
    if len(data) < 36 or data[:32] != b'Deflate_v1.0'.ljust(32, b'\0'):
        raise FormatError('Invalid TT deflate wrapper')
    expected = struct.unpack_from('<I', data, 32)[0]
    if not 0 < expected <= min(max_output, MAX_OUTPUT):
        raise FormatError('TT deflate output exceeds limit')
    bits, output, final = Bits(data[36:]), bytearray(), False
    while not final:
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
    return bytes(output)

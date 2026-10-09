"""LZ2K decompressor (TT Games). Own implementation.

The stream is a sequence of chunks:  'LZ2K', u32 unpacked_size, u32 packed_size, packed bytes.
Each chunk is an LZH bitstream of the LHA -lh5- family: 8 KB sliding window, blocks that
start with a 16-bit symbol count followed by three Huffman code-length tables
(19 "length" codes, 510 literal/length codes, 14 offset codes), bits read MSB first.
"""
import struct

WINDOW = 0x2000
NC, NT, NP = 510, 19, 14
C_TABLE_BITS, PT_TABLE_BITS = 12, 8


def _make_table(lengths, table_bits):
    """Canonical Huffman. Returns (fast, slow): fast[peek(table_bits)] = (sym << 5) | len for
    short codes, slow[(len, code)] = sym for codes longer than table_bits."""
    fast = [0] * (1 << table_bits)
    slow = {}
    code = 0
    for length in range(1, 17):
        for sym, l in enumerate(lengths):
            if l != length:
                continue
            if length <= table_bits:
                span = 1 << (table_bits - length)
                start = code << (table_bits - length)
                fast[start:start + span] = [(sym << 5) | length] * span
            else:
                slow[(length, code)] = sym
            code += 1
        code <<= 1
    return fast, slow


def decompress_chunk(src, out_size, window=None, wpos=0):
    """Decompress one chunk body. window is a shared bytearray(WINDOW) carried across chunks."""
    if window is None:
        window = bytearray(WINDOW)
    out = bytearray(out_size)
    opos = 0
    n_src = len(src)
    spos = 0
    bitbuf = 0
    bitcnt = 0

    def fill(need):
        nonlocal bitbuf, bitcnt, spos
        while bitcnt < need:
            b = src[spos] if spos < n_src else 0
            spos += 1
            bitbuf = (bitbuf << 8) | b
            bitcnt += 8

    def getbits(n):
        nonlocal bitbuf, bitcnt
        if n == 0:
            return 0
        if bitcnt < n:
            fill(n)
        bitcnt -= n
        v = (bitbuf >> bitcnt) & ((1 << n) - 1)
        bitbuf &= (1 << bitcnt) - 1
        return v

    def decode(fast, slow, table_bits, const):
        nonlocal bitbuf, bitcnt
        if fast is None:
            return const
        if bitcnt < 16:
            fill(16)
        peek16 = (bitbuf >> (bitcnt - 16)) & 0xFFFF
        e = fast[peek16 >> (16 - table_bits)]
        if e:
            bitcnt -= e & 31
            bitbuf &= (1 << bitcnt) - 1
            return e >> 5
        for length in range(table_bits + 1, 17):
            sym = slow.get((length, peek16 >> (16 - length)))
            if sym is not None:
                bitcnt -= length
                bitbuf &= (1 << bitcnt) - 1
                return sym
        raise ValueError("bad Huffman code")

    def read_pt_len(nn, nbit, special):
        n = getbits(nbit)
        if n == 0:
            return None, None, getbits(nbit)
        lens = [0] * nn
        i = 0
        while i < n:
            c = getbits(3)
            if c == 7:
                while getbits(1):
                    c += 1
            lens[i] = c
            i += 1
            if i == special:
                i += getbits(2)
        fast, slow = _make_table(lens, PT_TABLE_BITS)
        return fast, slow, 0

    def read_c_len(pt):
        n = getbits(9)
        if n == 0:
            return None, None, getbits(9)
        lens = [0] * NC
        i = 0
        while i < n:
            c = decode(pt[0], pt[1], PT_TABLE_BITS, pt[2])
            if c == 0:
                i += 1
            elif c == 1:
                i += getbits(4) + 3
            elif c == 2:
                i += getbits(9) + 20
            else:
                lens[i] = c - 2
                i += 1
        fast, slow = _make_table(lens, C_TABLE_BITS)
        return fast, slow, 0

    block_left = 0
    c_tab = p_tab = (None, None, 0)
    mask = WINDOW - 1
    while opos < out_size:
        if block_left == 0:
            block_left = getbits(16)
            pt = read_pt_len(NT, 5, 3)
            c_tab = read_c_len(pt)
            p_tab = read_pt_len(NP, 4, -1)
            if block_left == 0:
                raise ValueError("empty block")
        block_left -= 1
        c = decode(c_tab[0], c_tab[1], C_TABLE_BITS, c_tab[2])
        if c < 256:
            out[opos] = c
            window[wpos] = c
            opos += 1
            wpos = (wpos + 1) & mask
        else:
            length = c - 253
            p = decode(p_tab[0], p_tab[1], PT_TABLE_BITS, p_tab[2])
            if p > 1:
                p = (1 << (p - 1)) + getbits(p - 1)
            rpos = (wpos - p - 1) & mask
            for _ in range(length):
                b = window[rpos]
                out[opos] = b
                window[wpos] = b
                opos += 1
                rpos = (rpos + 1) & mask
                wpos = (wpos + 1) & mask
                if opos == out_size:
                    break
    return bytes(out), wpos


def decompress_chunked(data):
    """Decompress a whole stream of LZ2K chunks."""
    parts = []
    pos = 0
    window = bytearray(WINDOW)
    wpos = 0
    while pos < len(data):
        magic, usize, csize = struct.unpack_from("<4sII", data, pos)
        if magic != b"LZ2K":
            raise ValueError(f"bad chunk magic {magic!r} at {pos}")
        body = data[pos + 12:pos + 12 + csize]
        if csize == usize:
            # Stored chunk: data that would not shrink is kept as it is (seen in LEGO Marvel Super Heroes,
            # e.g. already-packed .pak files; LEGO Batman 1 has none). The bytes still enter the window.
            chunk = bytes(body)
            for b in chunk[-len(window):]:
                window[wpos] = b
                wpos = (wpos + 1) & (len(window) - 1)
        else:
            chunk, wpos = decompress_chunk(body, usize, window, wpos)
        parts.append(chunk)
        pos += 12 + csize
    return b"".join(parts)

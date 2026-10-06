"""Bound DDS image spans without decoding pixels or importing Blender.

Sizes follow Microsoft's DDS header, DX10 array and block-compression layout.
This does not identify the enclosing TT texture format or certify its shader.
Unknown pixel formats and ambiguous padded row layouts are rejected.
"""
import struct
from .cu3 import FormatError


MAX_DDS_BYTES = 512 * 1024 * 1024
MAX_DDS_DIMENSION = 65536
MAX_DDS_ARRAY = 2048
MAX_DDS_SUBRESOURCES = 65536
_CUBE = 0x200
_FACES = 0xfc00
_VOLUME = 0x200000

# Explicit DXGI storage families; video/planar/opaque formats are not inferred.
_DXGI_BITS = {
    **dict.fromkeys(range(1, 5), 128),
    **dict.fromkeys(range(5, 9), 96),
    **dict.fromkeys(range(9, 23), 64),
    **dict.fromkeys(range(23, 48), 32),
    **dict.fromkeys(range(48, 60), 16),
    **dict.fromkeys(range(60, 66), 8),
    66: 1, 67: 32, 85: 16, 86: 16,
    **dict.fromkeys(range(87, 94), 32),
    115: 16, 191: 16,
}
_DXGI_BLOCK = {
    **dict.fromkeys((70, 71, 72, 79, 80, 81), 8),
    **dict.fromkeys((73, 74, 75, 76, 77, 78, 82, 83, 84,
                     94, 95, 96, 97, 98, 99), 16),
}
_LEGACY_BLOCK = {
    b'DXT1': 8, b'DXT2': 16, b'DXT3': 16, b'DXT4': 16, b'DXT5': 16,
    b'ATI1': 8, b'BC4U': 8, b'BC4S': 8,
    b'ATI2': 16, b'BC5U': 16, b'BC5S': 16,
}
# Numeric FourCC values are ambiguous between D3DFORMAT and DXGI_FORMAT.
# A caller must supply independently established D3D9 context to use these.
_D3D9_BITS = {36: 64, 110: 64, 111: 16, 112: 32, 113: 64,
              114: 32, 115: 64, 116: 128}


def read_dds(data, offset=0, *, limit=None, max_bytes=MAX_DDS_BYTES,
             legacy_d3d9=False):
    """Return the exact header+pixel span; bytes after ``end`` are not pixels.

    Bounds are checked before allocating per-mip metadata. Row-padded legacy
    images need a separately verified policy; this reader accepts tight rows.
    Optional/incorrect pitch flags on block-compressed DDS are not trusted.
    """
    if limit is None:
        limit = len(data)
    if not (isinstance(offset, int) and isinstance(limit, int)
            and 0 <= offset <= limit <= len(data)):
        raise FormatError('Invalid DDS span bounds')
    if not isinstance(max_bytes, int) or max_bytes < 128:
        raise FormatError('Invalid DDS byte limit')
    if offset + 128 > limit or data[offset:offset+4] != b'DDS ':
        raise FormatError('Missing or truncated DDS header')

    def u32(at):
        if offset + at + 4 > limit:
            raise FormatError('Truncated DDS header extension')
        return struct.unpack_from('<I', data, offset+at)[0]

    if u32(4) != 124 or u32(76) != 32:
        raise FormatError('Invalid DDS header or pixel-format size')
    flags, height, width, pitch, depth, raw_mips = (u32(i) for i in range(8, 32, 4))
    if not (0 < width <= MAX_DDS_DIMENSION and 0 < height <= MAX_DDS_DIMENSION):
        raise FormatError('Invalid DDS image dimensions')
    pixel_flags, fourcc, bits = u32(80), bytes(data[offset+84:offset+88]), u32(88)
    caps2 = u32(112)
    header_size, array_size, faces, dimension = 128, 1, 1, 3
    block_bytes = pair_bytes = 0
    dxgi = None
    if pixel_flags & 4:
        if fourcc == b'DX10':
            if offset+148 > limit:
                raise FormatError('Truncated DDS DX10 header')
            header_size = 148
            dxgi, dimension, misc, array_size, alpha_mode = (u32(i) for i in range(128, 148, 4))
            if not 0 < array_size <= MAX_DDS_ARRAY:
                raise FormatError('Invalid or excessive DDS array size')
            if dimension not in (2, 3, 4):
                raise FormatError('Unsupported DDS resource dimension')
            if misc & ~4 or alpha_mode & ~7 or (alpha_mode & 7) > 4:
                raise FormatError('Unsupported DDS DX10 flags')
            cube = bool(misc & 4)
            if cube and (dimension != 3 or width != height):
                raise FormatError('Invalid DDS DX10 cubemap dimensions')
            if (caps2 & (_CUBE | _FACES)) and not cube:
                raise FormatError('DDS legacy and DX10 cubemap flags disagree')
            if cube and caps2 & _FACES not in (0, _FACES):
                raise FormatError('DDS DX10 cube requires all six faces')
            faces = 6 if cube else 1
            if dimension == 2 and (height != 1 or depth > 1 or caps2 & _VOLUME):
                raise FormatError('Invalid DDS 1D texture dimensions')
            if dimension == 4:
                if array_size != 1 or cube or not flags & 0x800000:
                    raise FormatError('Invalid DDS volume array/depth flags')
            elif caps2 & _VOLUME or depth > 1:
                raise FormatError('DDS resource dimension and volume depth disagree')
            block_bytes = _DXGI_BLOCK.get(dxgi, 0)
            pair_bytes = 4 if dxgi in (68, 69, 107) else 0
            bits = _DXGI_BITS.get(dxgi, 0)
            if not (bits or block_bytes or pair_bytes):
                raise FormatError(f'Unsupported DDS DXGI format {dxgi}')
            format_name = f'DXGI:{dxgi}'
        else:
            block_bytes = _LEGACY_BLOCK.get(fourcc, 0)
            pair_bytes = 4 if fourcc in (b'RGBG', b'GRGB', b'YUY2', b'UYVY') else 0
            numeric = int.from_bytes(fourcc, 'little')
            bits = _D3D9_BITS.get(numeric, 0) if legacy_d3d9 else 0
            if not (bits or block_bytes or pair_bytes):
                detail = ('; numeric FourCC requires verified D3D9 context'
                          if numeric in _D3D9_BITS else '')
                raise FormatError(f'Unsupported DDS FourCC {fourcc!r}{detail}')
            format_name = f'D3DFMT:{numeric}' if bits else fourcc.decode('ascii')
    else:
        if fourcc != bytes(4) or pixel_flags & ~(0x40 | 0x20000 | 2 | 1):
            raise FormatError('Unsupported DDS uncompressed pixel flags')
        kinds = pixel_flags & (0x40 | 0x20000 | 2)
        if kinds not in (0x40, 0x20000, 2) or bits not in (8, 16, 24, 32):
            raise FormatError('Unsupported DDS uncompressed pixel format')
        masks = [u32(i) for i in (92, 96, 100, 104)]
        occupied = 0
        for mask in masks:
            if mask >= (1 << bits) or mask & occupied:
                raise FormatError('Invalid DDS channel masks')
            occupied |= mask
        if not occupied or (kinds in (0x40, 0x20000) and not masks[0]):
            raise FormatError('Missing DDS channel masks')
        format_name = f'RGB:{bits}' if kinds == 0x40 else f'L/A:{bits}'

    if header_size == 128:
        if caps2 & _CUBE:
            if width != height or caps2 & _VOLUME or not caps2 & _FACES:
                raise FormatError('Invalid DDS cubemap dimensions/faces')
            faces = (caps2 & _FACES).bit_count()
        elif caps2 & _FACES:
            raise FormatError('DDS face flags require a cubemap')
        if caps2 & _VOLUME:
            dimension = 4
        elif depth > 1:
            raise FormatError('DDS depth requires a volume texture')
    if dimension == 4:
        if not 0 < depth <= MAX_DDS_DIMENSION:
            raise FormatError('Invalid DDS volume depth')
    else:
        depth = 1
    mips = raw_mips or 1
    if mips > max(width, height, depth).bit_length():
        raise FormatError('DDS mip count exceeds its dimensions')
    if mips * faces * array_size > MAX_DDS_SUBRESOURCES:
        raise FormatError('Excessive DDS subresource count')
    levels, chain_bytes = [], 0
    for level in range(mips):
        w, h, d = max(1, width >> level), max(1, height >> level), max(1, depth >> level)
        if block_bytes:
            row_bytes, rows = max(1, (w+3)//4)*block_bytes, max(1, (h+3)//4)
        else:
            row_bytes, rows = (((w+1)//2)*pair_bytes if pair_bytes else (w*bits+7)//8), h
        if level == 0 and not block_bytes and flags & 8 and pitch not in (0, row_bytes):
            raise FormatError('Unverified padded DDS row pitch')
        size = row_bytes * rows * d
        levels.append(dict(level=level, width=w, height=h, depth=d,
                           row_bytes=row_bytes, bytes=size))
        chain_bytes += size
        if header_size + chain_bytes*faces*array_size > max_bytes:
            raise FormatError('DDS payload exceeds the configured byte limit')
    payload_bytes = chain_bytes * faces * array_size
    end = offset + header_size + payload_bytes
    if end > limit:
        raise FormatError(f'Truncated DDS payload: needs {end-offset} bytes, has {limit-offset}')
    return dict(offset=offset, end=end, header_bytes=header_size,
                payload_offset=offset+header_size, payload_bytes=payload_bytes,
                width=width, height=height, depth=depth, mip_count=mips,
                array_size=array_size, face_count=faces, resource_dimension=dimension,
                format=format_name, dxgi_format=dxgi, levels=levels,
                row_layout='tight', legacy_numeric_fourcc=bool(pixel_flags & 4 and bits and header_size == 128))


def next_dds_header(data, start, *, limit=None):
    """Locate a header candidate outside an already bounded pixel span.

    A marker alone is insufficient. This only locates; read_dds must validate
    the full candidate before anyone uses it as an image.
    """
    end = len(data) if limit is None else limit
    if not 0 <= start <= end <= len(data):
        raise FormatError('Invalid DDS search bounds')
    at = data.find(b'DDS ', start, end)
    while at >= 0:
        if (at+128 <= end and int.from_bytes(data[at+4:at+8], 'little') == 124
                and int.from_bytes(data[at+76:at+80], 'little') == 32):
            return at
        at = data.find(b'DDS ', at+4, end)
    return None


def read_embedded_dds(data, *, legacy_d3d9=False):
    """Find exactly one bounded DDS; preserve enclosing bytes as opaque spans.

    The outer TEX preamble/trailer is not yet a verified native record parser.
    DDS-looking bytes inside the proven image span cannot become another image.
    """
    at = next_dds_header(data, 0)
    if at is None:
        raise FormatError('Native texture has no supported DDS header')
    result = read_dds(data, at, legacy_d3d9=legacy_d3d9)
    if next_dds_header(data, result['end']) is not None:
        raise FormatError('Ambiguous native texture: multiple DDS payloads')
    result.update(preamble_offset=0, preamble_end=at,
                  trailer_offset=result['end'], trailer_end=len(data))
    return result

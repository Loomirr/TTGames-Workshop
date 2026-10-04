# LIJ1 Xbox 360 prototype texture findings

This describes the two supplied samples, not a documented specification for all LIJ1 builds. Integer fields described below are **big-endian**, unless explicitly stated otherwise. Offsets are byte offsets.

## Container

Both files start with raw bytes `02UN`, a reversed `NU20` tag, followed by a 16-byte overall header. At offset 16 begins a sequence of chunks, each with a 4-byte reversed tag and a big-endian 32-bit size that **includes the 8-byte chunk header**. Examples are `DAEH` (HEAD), `LBTN` (NTBL), `FERT` (TREF), and `0TST` (TST0).

The extractor walks top-level chunk sizes to TST0. It does not search arbitrary byte strings for a DDS signature or import PC layout assumptions. It stops parsing container chunks at TST0; subsequent mesh/scene data is outside this tool's scope. The meaning of the remaining overall header fields is not established.

## Texture descriptors

Descriptors begin immediately after the TST0 chunk header, at stride **180 bytes / 0xB4**. No separate texture-count field is present in these samples. The remaining area before the first texture payload is zero-filled. Width zero terminates descriptor parsing.

| Relative offset | Type | Observed meaning |
| --- | --- | --- |
| +0 | u32 | Width |
| +4 | u32 | Height |
| +8 | 16 bytes | Opaque identifier; preserved as hex |
| +24..43 | bytes | Zero |
| +44 | u32 | Resource flags, `0x08000000` in both samples |
| +48..55 | bytes | Zero |
| +56 | u32 | Format: 1 = BC1/DXT1, 6 = BC3/DXT5 |
| +60 | signed i32 | Relative pointer: payload = descriptor address + 60 + this value |
| +64 | u32 | Mip count |
| +68 | u32 | Allocated tiled payload byte count |
| +72..79 | bytes | Zero |
| +80 | u32 | Observed 3; likely resource kind, semantics not established |
| +84 | u32 | Observed 1; layout flag, full semantics not established |
| +88..179 | bytes | Zero |

Payloads are 0x1000-aligned and contiguous through the TST0 end. The strict first-version parser verifies the observed flags, zero fields, pointer ranges, non-overlap, padding and allocation sizes.

| Sample | TST0 start | TST0 end | Descriptor start | Payload start | Allocation |
| --- | --- | --- | --- | --- | --- |
| Katanga, 1024 DXT1 | 0x2A0 | 0x119000 | 0x2A8 | 0x1000 | 0xB0000 |
| Katanga, 128 DXT1 | same | same | 0x35C | 0xB1000 | 0x8000 |
| Katanga, 512 DXT5 | same | same | 0x410 | 0xB9000 | 0x60000 |
| Army Intel icon, 256 DXT5 | 0x80 | 0x21000 | 0x88 | 0x1000 | 0x20000 |

## Xbox 360 byte order and tiling

DXT blocks are stored in Xbox 360 2D tiled order, with **8-in-16 endian swapping**. Coordinates in the address calculation are compression-block coordinates, not pixel coordinates. BC1 uses 8-byte blocks; BC3 uses 16-byte blocks. Pitch and allocation height are aligned to 32 blocks. Each consecutive pair of source bytes is swapped after recovering the block's tiled address. BC3 alpha bytes are included in that swap.

The implemented address equation is derived from Xenia's `Tiled2D` / combined-address equations:

```text
outer = ((y >> 5) * (pitch >> 5) + (x >> 5)) << 6
inner = (((y >> 1) & 7) << 3) | (x & 7)
a = (outer | inner) << log2(blockBytes)
bank = (y >> 4) & 1
pipe = ((x >> 3) & 3) ^ (((y >> 3) & 1) << 1)
address = ((y & 1) << 4) | (pipe << 6) | (bank << 11)
        | (a & 15) | (((a >> 4) & 1) << 5)
        | (((a >> 5) & 7) << 8) | ((a >> 8) << 12)
```

## Mipmap allocation and packed tail

For supported power-of-two dimensions at least 32, the first packed level is:

```text
tailLevel = max(0, min(log2(width), log2(height)) - 4)
```

Levels before that occupy individual allocations:

```text
align32(max(1, ceil(mipWidth/4)))
  * align32(max(1, ceil(mipHeight/4))) * blockBytes
```

The tail and all smaller levels share one allocation with the pitch and dimensions of `tailLevel`. For `p = level - tailLevel`, the packed offsets (in blocks) are:

```text
p < 3:
  width > height: x = 0; y = (16 >> p) / 4
  otherwise:      x = (16 >> p) / 4; y = 0
p >= 3:
  off = (max(width, height) >> tailLevel) >> (p - 2)
  width > height: x = off / 4; y = 0
  otherwise:      x = 0; y = off / 4
```

Integer division is used. These allocations exactly match all four descriptor byte counts. Small mipmaps cannot be recovered by simply incrementing a linear byte offset after every mip; ignoring the packed tail produces incorrect images.

## DDS output and verification

Output uses the classic 128-byte DDS header, **little-endian**, with DXT1 or DXT5 FOURCC, correct top-level linear size, mip count and mip/complex caps. Untiled mip blocks are appended in descending resolution order. One-dimensional final mip extents are clamped to one pixel; storage always contains at least one compression block.

No palette replacement, image synthesis, uncompressed conversion, recompression or alpha flattening occurs. Independent Python and C# outputs match across each entire DDS, including all original mip levels. Pillow decoding and visual inspection verify that the base maps and packed tail are coherent. This is sample validation, not in-game validation of rewritten prototype files; the tool does not rewrite them.

## Primary references

- Xenia tiled addresses: https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/texture_address.h
- Xenia packed mips: https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/texture_util.cc
- Microsoft DDS header: https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-header
- Microsoft DDS texture layout: https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-file-layout-for-textures

The LIJ1-specific descriptor offsets above were determined from the supplied files. Xenia explains GPU texture storage; it does not document these game containers.

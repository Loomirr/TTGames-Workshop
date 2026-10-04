# LIJ1 Xbox 360 prototype texture findings

This describes observed samples from the supplied LIJ1 Xbox 360 prototype,
not a specification for every build. Integer fields are **big-endian** unless
explicitly stated otherwise. Offsets are byte offsets.

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
| +84 | u32 | Observed 1 for original descriptors; 0 for secondary-resource descriptors |
| +88..179 | bytes | Zero for layout 1; see layout 0 below |

Normal payloads are 0x1000-aligned and contiguous through the TST0 end. The
parser verifies flags, zero fields, pointer ranges, non-overlap, padding and
allocation sizes. Resource flag `0x10000000`, codes 4/9, and dimensions below
32 occur elsewhere in the ISO but remain unsupported.

### Secondary-resource descriptors (layout 0)

The Colonel Dietritch and Thuggee Slavedriver Chief icons use layout flag 0.
Their primary fields above remain big-endian, with these additional fields:

| Relative offset | Observed meaning |
| --- | --- |
| +88..127 | Zero |
| +128 | Width in upper 16 bits, height in lower 16 bits |
| +132 | Zero |
| +136 | `0x1a200152` for BC1; `0x1a200154` for BC3 |
| +140 | Signed relative payload pointer, based at descriptor +140 |
| +144 | Duplicate mip count |
| +148 | Duplicate allocation size |
| +152..179 | Zero |

Dimensions, format, absolute payload address, mip count and allocation must
agree between the two descriptor records. The packed format word is matched
as an observed constant; this is not a general Xbox GPU descriptor decoder.
Unknown bits are rejected. The same profile occurs in other supplied game
containers, including rectangular resources.

### Observed legacy mixed-endian icon recovery

The ISO's `Stuff/Iconspoop/INDIANAJONES_ICON_360.GSC` matches the reported file.
Its NTBL declares length `0x41`, leading to TREF at `0x61`, then an invalid
chunk at `0x6d`. A duplicate TREF is present at `0x70`, followed by TST0 at
`0x80`. These are inconsistent stored headers, not a normal chunk chain.

Only this bounded envelope is recognized by the recovery path. At descriptor
`0x88`, width/height are little-endian 64, mip count is little-endian 7,
allocation is little-endian `0xc000`, and the primary format word is
little-endian `0x1a200154`. The observed primary +60 word `0x270f0129` is not
used as a relative pointer. +124 holds big-endian `0x1a200154`. Secondary
fields +128..151 are big-endian and describe the same 64x64 BC3 resource.
Other reserved fields must match the observed zero ranges.

The secondary pointer resolves to `0x1000`. TST0 declares size `0xc0bc`, ending
at `0xc13c`, but the texture allocation ends at `0xd000`, where a bounded
24-byte DXAT chunk is present. Recovery requires that exact envelope,
descriptor profile, pointer, allocation and following chunk. No arbitrary
signature scanning or general chunk-size repair is performed. Unknown or
inconsistent variants fail. Export manifests retain the recovery warning and
descriptor profile, and the source bytes stay unchanged.

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

An observed exception is the 32x32 BC1 resource with one mip level: it occupies
one 4 KiB page rather than the 8 KiB obtained by aligning both block extents to
32. This exact case is accepted; every actual tiled block access is still
checked against the allocation. It has no packed tail because only level 0 is
stored. Other allocation exceptions remain unsupported.

## DDS output and verification

Output uses the classic 128-byte DDS header, **little-endian**, with DXT1 or DXT5 FOURCC, correct top-level linear size, mip count and mip/complex caps. Untiled mip blocks are appended in descending resolution order. One-dimensional final mip extents are clamped to one pixel; storage always contains at least one compression block.

No palette replacement, image synthesis, uncompressed conversion, recompression or alpha flattening occurs. Independent Python and C# outputs match across each entire DDS, including all original mip levels. Pillow decoding and visual inspection verify that the base maps and packed tail are coherent. This is sample validation, not in-game validation of rewritten prototype files; the tool does not rewrite them.

Version 0.1.1 checks the original four DDS files/38 mips and the five reported
GSCs' seven DDS files/45 mips against independent references. All five reported
files match on-disc assets. A parser/converter survey accepts 437 of 757 ISO
GHG/GSC files, covering 2,898 resources and 24,609 mip levels; the remaining
320 containers are refused. Every DDS from the 387 containers accepted by
0.1.0 is unchanged. The survey checks compressed bytes and addressing bounds,
not every decoded image. Visual checks remain limited to selected samples.

## Primary references

- Xenia tiled addresses: https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/texture_address.h
- Xenia packed mips: https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/texture_util.cc
- Microsoft DDS header: https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-header
- Microsoft DDS texture layout: https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-file-layout-for-textures

The LIJ1-specific descriptor offsets above were determined from the supplied files. Xenia explains GPU texture storage; it does not document these game containers.

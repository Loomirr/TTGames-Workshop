# LIJ1 Xbox 360 prototype texture findings

Observed profiles from the supplied March 20, 2008 prototype, as supported by
0.1.2. Integers are big-endian unless marked otherwise. These are format
findings, not a specification for every TT game or Xbox build.

## NU20 container and standard descriptors

The raw tag is `02UN`. A 16-byte header precedes chunks with a reversed tag and
a big-endian length including the eight-byte chunk header. The reader walks
HEAD (`DAEH`), NTBL (`LBTN`) and TREF (`FERT`) to TST0 (`0TST`). It stops there;
mesh and scene chunks are not decoded. It never searches arbitrary file data
for a texture signature.

TST0 descriptors normally occupy 180 bytes. Width zero terminates the table;
remaining bytes before the first payload must be zero. Empty TST0 chunks are
valid and produce a manifest with no textures.

| Offset | Observed field |
| --- | --- |
| +0, +4 | Width, height |
| +8..23 | Opaque identifier, preserved as hex |
| +24..43 | Zero |
| +44 | Resource flags: 0x08000000 for 2D, 0x10000000 for cubemap |
| +48 | Zero |
| +52 | 0 for 2D, 1 for cubemap |
| +56 | Game format code: 1 BC1, 4 BC5, 6 BC3, 9 RGBA32 float |
| +60 | Signed relative payload pointer based at descriptor +60 |
| +64, +68 | Mip count, allocated payload bytes |
| +72..79 | Zero |
| +80 | Resource kind 3 |
| +84 | Layout 1 (standard) or 0 (secondary resource) |
| +88..179 | Zero for layout 1; secondary fields below for layout 0 |

Dimensions must be powers of two, 1..8192. Payload pointers are 4096-aligned,
allocations are checked against the chunk and each other, and standard payloads
contiguously cover the TST0 end. Individual files are limited to 512 MiB.

Layout 0 adds zero bytes at +88..127, packed `(width << 16) | height` at +128,
zero at +132, the GPU format word at +136, a second signed relative payload
pointer based at +140, duplicate mip/allocation counts at +144/+148 and zero
bytes at +152..179. The two records must agree.

| GPU word | Storage | DDS |
| --- | --- | --- |
| 0x1a200152 | BC1, 8-in-16 endian | DXT1 |
| 0x1a200153 | BC2, 8-in-16 endian | DXT3 |
| 0x1a200154 | BC3, 8-in-16 endian | DXT5 |
| 0x1a200171 | DXN / BC5, 8-in-16 endian | DX10 BC5_UNORM (83) |
| 0x1a22aba6 | RGBA32 float, 8-in-32 endian | DX10 R32G32B32A32_FLOAT (2) |

The GPU format occupies the low six bits; the endian mode occupies the next
two. The complete observed words are gated, not just their format bits.
BC5 output preserves both stored channels without reconstructing a third
normal component. Float output preserves all 32-bit patterns without clamping.
No material-role or shader-swizzle interpretation is applied.

### Cubemaps

The observed standard cubemaps are square BC1 resources with one level and
six face allocations. They occupy six 180-byte descriptor slots: the first is
the texture record, four subsequent slots are zero, and the final slot has only
0x10000000 at +44. This closing marker is at first descriptor +944. The next
texture descriptor follows all six slots; stopping at the first zero-width
slot would miss later textures in level files.

Each face uses the same aligned tiled footprint. Faces are written in native
order as +X, -X, +Y, -Y, +Z, -Z. DDS caps include COMPLEX and all six cubemap face
flags (caps2 0xfe00). The legacy secondary-only cubemap instead marks its
surface dimension at +132 and has five zero continuation slots.

## Aligned legacy containers

Twenty-one supplied containers have an unpadded NTBL length but a second TREF
at `align16(NTBL offset + declared size)`, followed by TST0 sixteen bytes later.
The reader accepts that bounded HEAD/NTBL/TREF envelope only. It does not scan
for a replacement TST0. TREF must have length 12 and count zero.

Most legacy descriptors have little-endian width/height, GPU word at +56,
mip count at +64 and allocation at +68. +60 is runtime GPU-address metadata,
not a file-relative pointer. +24..55 and +72..123 are zero. +124 contains the
big-endian GPU word. Secondary fields +128..151 provide the verified dimensions,
GPU word, relative payload pointer and duplicate counts. Secondary-only older
records have big-endian dimensions and zero primary resource metadata.

Other observed aligned descriptors retain big-endian primary fields with
secondary metadata. An earlier resource profile has flags 1 and kind 2 instead
of flags 0x08000000 and kind 3. In this legacy serializer, primary game code 4
can identify **BC2**, with secondary GPU word 0x1a200153; it must not be treated
as the BC5 code 4 profile whose GPU word is 0x1a200171.

The declared legacy TST0 length equals eight bytes plus all descriptor slots
plus logical resource allocations, omitting physical alignment padding. The
reader validates this equation, descriptor bounds, pointers and resource
extents. Payload alignment gaps and duplicated bytes before the first payload
are not interpreted as textures. A bounded DXAT (`DXAT`) chunk must follow the
last allocation. One observed final descriptor includes an ADER relocation
tail; its marker, count and table-relative indices are validated separately.

Some legacy descriptors have zero mip and allocation counts. Their secondary
pointers and the next allocation boundary identify stored data, but not a
complete mip chain. The exporter reads the unambiguous base image only and
records a warning. The manifest's MipCount describes exported levels; a
base-only warning identifies missing stored mip metadata.

The old R2D2 container uses a separate 52-byte compact descriptor: packed
dimensions at +0, zero +4, GPU word +8, relative pointer +12, mip count +16 and
zero +20..51. The logical chunk length supplies its allocation. Its verified
following chunk is MS00 (`00SM`), rather than DXAT.

The previously supported Indiana Jones icon retains its narrow recovery path:
NTBL 0x20/length 0x41, duplicate TREF at 0x70, TST0 at 0x80, little-endian 64x64
BC3 descriptor at 0x88, seven mips, allocation 0xc000, secondary payload at
0x1000 and 24-byte DXAT at 0xd000. The recovery warning and descriptor profile
are retained. No source headers are repaired.

## Standalone TEX and Xbox 360 FNT

A big-endian word at offset zero gives the resource end. A relocation footer
starts there with a count followed by signed relative pointers. Each pointer
is based at its own footer position and identifies a pointer field in the
resource. Footer size, targets and duplicates are checked.

Standard TEX uses the 180-byte descriptor at offset four, flags 0x20000000,
kind 3 and layout 1. The five observed relocation targets are 0x20, 0x2c, 0x34,
0x40 and 0x50. Its payload begins at 0x1000 and ends at the declared resource end.
The button font uses the same resource descriptor behind its font pointer.

Other TEX/font resources have compact GPU objects. The pointer field is at
object +28 or +116, identified by the footer. Allocation and GPU word follow
that field. Dimensions are at object +0/+4; unused intervening fields are zero.
Font offset +8 is a signed relative pointer to the texture object; font
relocations must include header fields +4 and +8. Glyph metrics are not exported.

These compact objects have no mip-count field. Only the base image is exported,
even when the allocation could contain additional levels. This is explicit in
the window, CLI and manifest. Float wind textures use the compact +28 profile;
font atlases and three particle textures also use compact profiles.

Existing DDS input is a separate little-endian passthrough reader. It validates
observed 2D DXT1/DXT3/DXT5 or 32-bit BGRA headers, mip counts and exact data size,
then preserves the entire DDS byte for byte. It does not apply Xbox tiling.
Other-platform fonts/CSC data are not decoded with these Xbox profiles.

## Tiling, endian and packed mips

BC1 addresses 4x4 blocks of eight bytes. BC2/3/5 address 4x4 blocks of sixteen
bytes. RGBA32 float addresses individual pixels of sixteen bytes. Pitch and
allocation height align to 32 address units. Each pair of BC bytes is reversed;
each four-byte float word is reversed. Data is never recompressed.

The Xenia-derived tiled equation is:

```text
outer = ((y >> 5) * (pitch >> 5) + (x >> 5)) << 6
inner = (((y >> 1) & 7) << 3) | (x & 7)
a = (outer | inner) << log2(bytesPerUnit)
bank = (y >> 4) & 1
pipe = ((x >> 3) & 3) ^ (((y >> 3) & 1) << 1)
address = ((y & 1) << 4) | (pipe << 6) | (bank << 11)
        | (a & 15) | (((a >> 4) & 1) << 5)
        | (((a >> 5) & 7) << 8) | ((a >> 8) << 12)
```

For mipmapped power-of-two resources, `tail = max(0, min(log2(w), log2(h)) - 4)`.
Earlier levels occupy separate `align32(unitWidth) * align32(unitHeight) *
bytesPerUnit` allocations. The tail shares one allocation. For `p = level - tail`:

```text
p < 3: width > height -> y = (16 >> p) / unitPixels
       otherwise      -> x = (16 >> p) / unitPixels
p >= 3: offset = (max(width,height) >> tail) >> (p - 2)
        width > height -> x = offset / unitPixels
        otherwise      -> y = offset / unitPixels
```

Here unitPixels is four for BC formats and one for float pixels. Integer
arithmetic is used. The formula also covers the observed tiny mipmapped
textures; single-level/base-only resources do not use a packed-tail offset.
Every tiled access is checked against its own face allocation.

Observed 32x32 BC1 base levels can use 4096 bytes, or 2048 in an aligned legacy
container. A 64x32 one-level BC1 page also fits within 4096 bytes. Nine 128x64
BC1 allocations instead declare 4096 bytes while their tiled span is 6144.
The tool preserves those exact payloads as raw `.x360.bin` and reports them;
it does not read the next resource, change dimensions or invent missing bytes.

## Output and validation

BC1/2/3 use classic 128-byte DDS headers. BC5 and float use 148-byte DX10
headers. Float headers use row pitch, compressed headers use linear size.
Cubemaps are face-major, with each face's levels in descending resolution.
Exports convert/validate before writing, use a temporary stage directory, and
move completed output to a new numbered folder. Raw-only entries are marked
in the manifest and excluded from the displayed DDS texture count.

The game survey covers 757 GHG/GSC files, 11,182 DDS resources, 92,820 face/mip
images, nine raw allocations and 90 empty containers. The additional 698
TEX/FNT/DDS inputs pass their separate survey. All 2,898 previous 0.1.1 DDS
outputs are unchanged. Extended Python checks compare 143 resources / 1,142
face/mip images, with 1,140 Pillow decodes and 131,072 float pixels checked.
Original sample regressions cover another 83 mip levels. This is parser,
binary, decoder and selected visual validation, not actual in-game validation.

## Primary references

- [Xenia tiled addresses](https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/texture_address.h)
- [Xenia packed mips](https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/texture_util.cc)
- [Xenia GPU formats/endian modes](https://github.com/xenia-project/xenia/blob/master/src/xenia/gpu/xenos.h)
- [Microsoft DDS header](https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-header)
- [Microsoft DDS cube layout](https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-file-layout-for-cubic-environment-maps)
- [Microsoft DXGI formats](https://learn.microsoft.com/en-us/windows/win32/api/dxgiformat/ne-dxgiformat-dxgi_format)

LIJ1 descriptor offsets and recovery envelopes come from the supplied files.
Xenia explains the GPU storage, not these game containers. Its BSD-3-Clause
attribution remains in `THIRD_PARTY_NOTICES.txt`.

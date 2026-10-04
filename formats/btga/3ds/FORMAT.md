# Observed Universe in Peril 3DS texture layout

The verified USA CTR-P-AL5E build stores resources in `lego_m1_3ds.fib`, a
FUSE1.00 archive. Observed index records are 12 bytes: resource hash, archive
offset and packed size/flags. Decoded size is `packed >> 5`; flags are the low
five bits. The reader supports the observed raw flags 0/12 and compressed flag
13. It does not discover the index or parse encrypted ROM containers.

The observed canonical resource path is lowercase ASCII such as
`models/textures/name.btga`. Its key is standard CRC32 XOR `0xFFFFFFFF`.
The lookup was checked against the installed build's ARM routine.

BTGA has a 56-byte prefix. The observed signature begins
`00 04 00 00 10 00 00 00 F2 FF FF FF`. Header fields are little-endian:

| Offset | Field |
| --- | --- |
| 20 | Payload size, u32 |
| 24 / 26 | Width / height, u16 |
| 28 | Repeated payload size, u32 |
| 32 | PICA format, u32 |
| 36 | Stored mip count, u32 |
| 56 | First tiled mip payload |

The supported mip chain must consume the exact payload. PICA uses 8x8 tiles;
ETC1/ETC1A4 sub-blocks are 4x4. ETC1 words are little-endian, with alpha nibbles
preceding ETC1A4 color. LA8 bytes are alpha then intensity. Native exported
pixels are flipped vertically to follow the original extraction convention.

Body textures in the verified sample include 128x64 ETC1A4 with three mips;
hair samples include LA8. Sixteen textures and 44 stored mip levels were
previously decoded and checked against PNG/DDS round trips. This is evidence
for those samples, not proof of support for every 3DS texture or game version.

Layout references: [Azahar's hardware texture decoder](https://github.com/azahar-emu/azahar/blob/master/src/video_core/texture/texture_decode.cpp),
[Ohana3DS-Rebirth](https://github.com/gdkchan/Ohana3DS-Rebirth), and
[libctru RomFS documentation/source](https://github.com/devkitPro/libctru).
External source trees and tools are not bundled.

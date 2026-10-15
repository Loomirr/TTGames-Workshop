# LEGO Star Wars II (2006, PC): `.hgp` model files

Measured on the 261 `.hgp` files of the Steam PC release (`lego_data/game.dat`, index version -1). 257 are
this format; the other four (`chars/chewbacca/_chewbacca.hgp`, `chars/yoda/_yoda.hgp`,
`chars/palpatine/walk.hgp`, `chars/obiwankenobi/tpm/obiwankenobi.hgp`) are LEGO Star Wars 1 files
shipped by mistake and are refused. Reader and writer: `../hgp.py`. Checks:
`../tests/check_roundtrip.py` (no Blender), `../tests/check_blender.py` and `../tests/check_blender_edits.py`.

Everything is little-endian. **Every pointer is an absolute file offset**; there is no relocation table.
"Always" below means in all 257 files.

## Order of the file

| Part | Where | Size |
| --- | --- | --- |
| header | 0 | 0x98 |
| material pointer table | `h[5]` (always 0x98) | 4 x `h[4]` |
| materials | via the table | 0xb4 each, 16-byte aligned |
| name strings | `h[12]` | `h[13]` bytes |
| joint records | `h[7]` | 0x60 x `h[6]` |
| local bind matrices | `h[8]` | 64 x `h[6]` |
| inverse bind matrices | `h[9]` | 64 x `h[6]` |
| two byte lists | `h[11]` (`h[10]` bytes), `h[15]` (`h[14]` bytes) | not decoded |
| attachment points | `h[17]` | 0x50 x `h[16]` |
| layer table | `h[19]` | 20 x `h[18]` |
| layer contents: objects, geometry records, morph blocks | from the layer table | |
| extra structures (69 vehicles and creatures; Padme, Qui-Gon) | `h[20]`; `h[35]` (`h[34]` records) | kept as they are |
| texture block | `h[3]` (also at 0x94) | |
| vertex block, then index buffer, to the end of the file | texture block word 1 | |

## Header (`h[i]` = u32 at 4i)

`h[0]` file size. `h[1]` `NU20`. `h[2]` texture count. `h[3]` texture block. `h[4]` material count.
`h[5]` material pointer table. `h[6]` bone count. `h[7..9]` joint, local, inverse tables. `h[10..17]`
see above. `h[18]` layer count, `h[19]` layer table. `h[20]` extra structure or 0. `h[21..31]` floats
(not decoded; perhaps bounds). `h[34]`, `h[35]` count and pointer of a small record list (two files).
`h[37]` texture block again.

## Skeleton

Joint record (0x60): a matrix (64 bytes; neither the local nor the world bind matrix, not used here),
three floats, name pointer at +0x4c, parent at +0x50 (byte, 255 = root; a model may have several roots),
a flag byte at +0x51 (33, 8 or 1).

Matrices are row-major for row vectors (translation in the last row). The world matrix of bone i is
`local[i] * world[parent]`, and the inverse table is exactly its inverse (5,171 of 5,171 bones).

Attachment point (0x50): matrix (relative to its bone), name pointer at +0x40, bone at +0x44.

The game is **left-handed**: Y up, characters face -Z, a character's left side is +X.

## Layers, objects and geometry

Layer record (20 bytes): `a` (pointer to a small all-zero record), **rigid array** (per bone: object
pointer or 0), **skinned object**, `d` (pointer to a per-bone array, always zero), **second skinned object**.
Layer names (`defaultLayer`, `TT1_Special`, `TT2_HiRes`, ...) follow the bone names in the name table;
nothing points to them.

Object (0x70): geometry pointer at +12, then floats (bounds, not decoded).

Geometry record (0xe8, 232 bytes), a linked list from the object:

| Offset | Meaning |
| --- | --- |
| +0x00 | next geometry record or 0 |
| +0x08 | material index |
| +0x10, +0x14 | vertex count (twice) |
| +0x18 | first vertex in the buffer |
| +0x2c | 0x8a80006c always |
| +0x38 | 0xb4 when a morph block follows the record, else 0 |
| +0x44 | 1 or 2 (not decoded) |
| +0x48 | vertex buffer number |
| +0x68 | vertex kind: 0x59 rigid, 0x5d skinned |
| +0x9c | 6 |
| +0xa0 | index count (u16, twice) |
| +0xac | bone list: u16 count, then up to 15 u16 bone indices (originals use at most 8) |
| +0xd0 | Direct3D 9 `DrawIndexedPrimitive` arguments: type (always 5, triangle strip), base vertex, minimum index (0), vertex count, first index, triangle count (= index count - 2) |

Rigid parts (kind 0x59) hang from the rigid array and are stored in their bone's space. Skinned parts
(0x5d) hang from the two skinned objects and are stored in model space at the bind pose.

Strips follow the Direct3D rule: triangle i is (s[i], s[i+1], s[i+2]), every odd one flipped;
repeated indices make degenerate joins.

### Vertices

| Kind | Size | Layout |
| --- | --- | --- |
| 0x59 rigid | 36 | position 3f, normal 3f, colour u32, UV 2f |
| 0x5d skinned | 56 | position 3f, weights w1 w2 (2f), bone slots j1 j2 j3 (3f, index into the part's bone list, -1 unused), normal 3f, colour u32, UV 2f; the third weight is 1 - w1 - w2 |

Every vertex buffer holds one kind and is split exactly between its parts, in file order. A few files
carry a buffer no part draws from. The colour is 0xff000000 throughout in 192 files and varies in 65.

### Morph blocks (facial shapes)

After a record flagged 0xb4: u32 block size, u32 shape count, then pointers relative to their own
position (an offset table, an ID list, the data) and -1. Shapes are 3 floats per vertex, but in 278 of
369 blocks the spacing is uneven (stored sparsely); not decoded further. Kept as they are.

## Materials (0xb4)

| Offset | Meaning |
| --- | --- |
| +0x30 | linked material, counting from 1 (0xffffffff none): 327 links, to materials whose flags and attributes vary; their meaning (normal or reflection passes?) is not settled |
| +0x40 | attributes |
| +0x54 | colour, 3 floats |
| +0x74 | opacity: 1.0 in 2,454 materials, 0.0 to 0.98 in the other 83 |
| +0x78 | texture, u16, **counting from 1** (0 = none) |
| +0x7a | texture flags (u16) |

## Texture block

At `h[3]`: eight u32: base (= block + 8), vertex block offset, texture count, (vertex block - base - 0x14),
0x18, data offset (from base), data size, 0. Entries (20 bytes each, at base + 0x18): width, height,
levels, format (12 DXT3, 14 DXT3, 15 DXT5), offset. Data starts at the next 128-byte boundary; each
texture is a whole DDS file, padded to 128 bytes.

## Vertex block

Nine u32: buffer count, 1, a size (meaning not found: 22 to 36 bytes short of the index data's end), 0x30,
header size (= next + 16), index buffer offset (from the data), table end (16-aligned 0x30 + 12 n), index
buffer offset from the block, index bytes rounded up to 16. Buffer table at +0x30: (size, number, offset
from the data) per buffer, numbers in order. At the table end: the exact index byte count. Data follows;
buffers are 16-byte aligned; the u16 index buffer follows the last buffer and ends the file.

The indices are packed tightly: their count is the sum of every part's index count.

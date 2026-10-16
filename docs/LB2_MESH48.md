# LEGO Batman 2 PC: MESH 48 geometry

Follow-up to [issue #9](https://github.com/Loomirr/TTGames-Workshop/issues/9). The
native mesh reader (`native_mesh.py`) now reads LEGO Batman 2's MESH 48 sections.
This is the geometry layer only. Full model loading still stops at display
decoding (LB2 uses DISP 12, 13 and 14, which have no reader), so no Blender import
path is enabled. Character profiles do not include LB2.

## Layout

MESH 48 has the same part records as non-DX11 MESH 169: streams, index range,
palette, morph-target table and the 72-byte part tail, with the same buffer
reference counting. Only the vertex buffer header differs:

| | MESH 169 | MESH 48 |
|---|---|---|
| after `u32 1, flags, count` | `DXTV`, u32 169, u32 descriptor count | u32 descriptor count |
| descriptors | 3 bytes each | 3 bytes each |
| before the vertices | 6 layout bytes | nothing |

The reader keeps the two layouts apart. A tagged buffer under MESH 48, or an
untagged one under MESH 169, is refused.

## Evidence

Read-only run over all 1,259 `.ghg`/`.gsc` files of the Steam PC release
(`GAME*.DAT` extracted): MESH 48 in 1,064, MESH 47 in 190, MESH 46 in 5.

- **MESH 48:** 1,036 of 1,064 now decode, and each section ends exactly where
  the next block (`u32 1`) begins. That covers 81,494 parts and 18.7 million
  triangles, including 1,881 skinned parts and 975 parts with morph targets.
- **Refused MESH 48 files (28), all by existing checks:**
  - 10 have non-finite half-float UVs (vehicles, builder props).
  - 5 have no verified 3D position stream (the `bat` creatures).
  - 2 have a secondary stream (`broken_ladder`).
  - The rest are builder-level files with a non-zero reserved field.
- **Independent cross-check:** a separate big-endian reader written for another
  project agrees on 215 randomly sampled files (seed 7, plus `super_minifig`):
  16,332 parts with identical vertex counts, triangle lists and positions.

## Still unsupported

- **MESH 47 (190 files) and MESH 46 (5 editor files).** MESH 47 stores the part
  count without `ROTV` and has a 40-byte part tail (a u32, then nine floats). It
  also has depth-only records that put the vertex count where MESH 48 has a zero
  and end after the index range. An attempt with these rules decoded 18 of 190
  files; the rest point to stream-count and buffer-numbering differences that
  are not understood. These versions stay refused.
- DISP 12-14, LB2 materials, skeletons, CU3, AN4 and `.giz`.

## Checks

- `formats/cu3/scripts/test_lb2_mesh48.py`: synthetic MESH 48 fixtures decode to
  the same positions, triangles and skin weights as their MESH 169 equivalents.
  Mixed layouts and MESH 46/47 are refused.
- Existing mesh, face and material tests; `tools/check_repository.py` and
  `tools/check_docs.py`.

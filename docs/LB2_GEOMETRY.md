# LEGO Batman 2 PC: MESH 48 geometry and DISP 12-14 display lists

Follow-up to [issue #9](https://github.com/Loomirr/TTGames-Workshop/issues/9). The
native mesh reader (`native_mesh.py`) now reads LEGO Batman 2's MESH 48 sections,
and the display reader (`native_display.py`) reads its DISP 12, 13 and 14 lists:
draw commands, clips, named instances and LOD tables. Full model loading still
stops at material decoding (LB2 material tables 121-132 are unverified) and, for
`.ghg`, at the skeleton. No Blender import path is enabled. Character profiles do
not include LB2.

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

## DISP 12-14

Same as the non-DX11 DISP 16/18/21 path up to the specials: source path, commands,
clips, then the per-clip u16 and u32 arrays. DISP 16 then has three more per-clip
u32 arrays, each with `ROTV`. LB2 has the same three, but only the first carries
`ROTV`; the other two are count and values. Instance records are the 204-byte
non-DX11 form with name offset, matrix, clip at +180, and the LOD table.

Run over every LB2 file with DISP 12-14 whose mesh decodes: 1,035 files (278 DISP
12, 10 DISP 13, 747 DISP 14). All decode, and each list ends where the next `ROTV`
begins. That is 26,271 named instances. Every instance has an LOD table, and all
of them have the shape the selector already verifies: 1-6 thresholds, strictly
far to near, ending in 0, with consecutive clips inside the table. So LB2's
versions were added to `model_bindings`. 26,098 instances select their nearest
clip. 127 are refused for draw command 0xB5 (flags 3) in an LOD clip, and 46
because an LOD clip draws nothing. Both are the selector's existing rules.

DISP 10 and 11 (two files with MESH 48) and DISP 7-10 with MESH 46/47 stay
unsupported.

## Still unsupported

- **MESH 47 (190 files) and MESH 46 (5 editor files).** MESH 47 stores the part
  count without `ROTV` and has a 40-byte part tail (a u32, then nine floats). It
  also has depth-only records that put the vertex count where MESH 48 has a zero
  and end after the index range. An attempt with these rules decoded 18 of 190
  files; the rest point to stream-count and buffer-numbering differences that
  are not understood. These versions stay refused.
- LB2 material tables (UMTL 121-132), HGOL skeletons, CU3, AN4 and `.giz`.

## Checks

- `formats/cu3/scripts/test_lb2_mesh48.py`: synthetic MESH 48 fixtures decode to
  the same positions, triangles and skin weights as their MESH 169 equivalents.
  Mixed layouts and MESH 46/47 are refused.
- `formats/cu3/scripts/test_lb2_display.py`: DISP 12-14 fixtures reach their
  instances and LOD selection. Marked or miscounted per-clip arrays, and DISP 10,
  11 and 15, are refused.
- Existing mesh, display, face and material tests; `tools/check_repository.py` and
  `tools/check_docs.py`.

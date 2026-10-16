# LEGO Batman 2 PC: model readers (MESH 48, DISP 12-14, HGOL 9, UMTL 125-132)

Follow-up to [issue #9](https://github.com/Loomirr/TTGames-Workshop/issues/9). The
native mesh reader (`native_mesh.py`) now reads LEGO Batman 2's MESH 48 sections,
the display reader (`native_display.py`) its DISP 12, 13 and 14 lists, the skeleton
reader (`skeleton.py`, `native_variants.py`) its HGOL 9 skeletons and multi-rig
groups, and the material reader (`native_materials.py`, `material_flags.py`) its
UMTL 125-132 tables. With all four, `native_model.load_model` decodes 927 LB2
models in full (728 `.gsc`, 199 `.ghg`). No Blender import path is enabled:
character profiles, cutscenes and stages do not include LB2.

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

## HGOL 9

HGOL 10's layout without the length-prefixed opaque block between the
post-locator bytes and the layer metadata (our independent reader records the
same: that list exists only from version 10). The name table is used as in 10.

Multi-rig groups (for example the minifigure's 103-, 93- and 54-joint rigs) use
HGOL 10's counted trailer, including the secondary joint map and scale. The group
ends with five zero bytes and `ATEM`, where HGOL 10 has a 1 in the fifth byte. In a
probe over the LB2 `.ghg` files with a group marker, 195 decode with each trailer
ending at the next counted HGOL and the group at that fence. The others stay
refused by the existing rules (counts under "Full loads" below).

The reader still does not verify where a single skeleton ends: a stray word
would be read into the metadata count, as in HGOL 10. Real files are covered by
the downstream layer, display and mesh ownership checks, which every loaded model
passes.

## UMTL 125-132

LB2 uses many material table versions: 47-61, 105-111, 120-123 and 125-132. Only
125-130 and 132 are added; they cover 943 files with materials.

Record layout:

| | 125/126 | 127 | 128-132 |
|---|---|---|---|
| leading word | 2 | 2 | 2 |
| texture IDs | 16 at +346 | 18 at +390 | 18 at +389 |
| name (u16 length, text, zero) | +844 | +904 | +903 |

The IDs were checked against each file's `HGXT` texture count in every record of
every file (in 125/126, slots 16 and 17 would exceed it: those are other fields).
Only the leading word is constant across all LB2 records, so the rest of the
shader prefix is kept opaque (`opaqueShaderPrefix`), and `shaderType`, `uvSets`
and the other prefix fields are `None`.

After the name comes a variable-length section, then a 91-byte footer ending at
the next record:
- 19 flag bytes: the later list without `alwaysUpdateRefraction` and `sortLast`;
- fx1-4, `localTID`, `fxid`, `special_id`, `shortPri16bit`, `shineSortID`,
  `uanmode`, `vanmode`;
- `du dv su sv`;
- the two variant pointers;
- 12 trailing flag bytes (0/1);
- `name_ix` and `defaultRenderStage`.

All 15,008 records with a following record fit this layout, under the reader's
existing checks plus the 0/1 tail. The table has no `ROTV`/`TDML` tail: the last
footer ends one byte (always 1) before the following `HSCB` section, which holds
in all 943 files. 120-123 have a shorter footer and stay unsupported.

Lead for the older tables: with the same field order, the trailing flag block is 8 bytes in UMTL 106, 10 in
108-121, 11 in 122-123 and 12 in 125-132 (each fits every record pair of every file). The length of the
leading flag block is not determined for 106-123: `colourWriteMask` sits at a fixed distance from the end
whatever that length is, and those files contain no occluder materials to anchor it. So they stay refused.

## Full loads and a Blender check

`load_model` on every LB2 `.ghg`/`.gsc`:
- 927 load, passing the existing validation.
- 195 stop at MESH 46/47.
- 58 stop at the multi-rig rules: 44 with a non-empty auxiliary array, 12 with a
  disagreeing remap, 1 with a differing secondary map, 1 (`wingsglidesuit`) whose
  joint map disagrees with names or hierarchy.
- 41 stop at material versions 120-123.
- The remaining 38 are the MESH 48 refusals above, 9 skeleton cases without a
  supported match, and 1 other.

All 1,259 are accounted for.

The CU3 add-on's `create_model` builds the giraffe, the minifigure body and the
alarm prop in Blender 5.2.2 with coherent geometry, skeleton binding and vertex
colours. The minifigure shows all its accessory layers at once, as expected
without a character definition. Textures were not checked.

The same 200 randomly sampled LMSH1 character models decode identically before
and after these changes (174 load; the one changed result is an error message
naming HGOL 9).

## Still unsupported

- **MESH 47 (190 files) and MESH 46 (5 editor files).** MESH 47 stores the part
  count without `ROTV` and has a 40-byte part tail (a u32, then nine floats). It
  also has depth-only records that put the vertex count where MESH 48 has a zero
  and end after the index range. An attempt with these rules decoded 18 of 190
  files; the rest point to stream-count and buffer-numbering differences that
  are not understood. These versions stay refused.
- UMTL 47-123 and MESH 47's display versions.
- An LB2 character profile (its `.cd` definitions begin `17000000 0b000000`),
  texture binding in Blender, CU3, AN4 and `.giz`.

## Checks

- `formats/cu3/scripts/test_lb2_mesh48.py`: synthetic MESH 48 fixtures decode to
  the same positions, triangles and skin weights as their MESH 169 equivalents.
  Mixed layouts and MESH 46/47 are refused.
- `formats/cu3/scripts/test_lb2_display.py`: DISP 12-14 fixtures reach their
  instances and LOD selection. Marked or miscounted per-clip arrays, and DISP 10,
  11 and 15, are refused.
- `formats/cu3/scripts/test_lb2_skeleton.py`: HGOL 9 without the opaque block,
  and a two-rig group that selects its zero-threshold base with the LB2 fence.
  HGOL 10's fence is refused for HGOL 9.
- `formats/cu3/scripts/test_lb2_materials.py`: UMTL 132 and 125 tables (IDs,
  footer values, 16 slots). A wrong final flag byte, a missing `HSCB`,
  versions 124/131 and an out-of-table variant pointer are refused.
- Existing mesh, display, skeleton, variant, face and material tests; `tools/check_repository.py` and
  `tools/check_docs.py`.

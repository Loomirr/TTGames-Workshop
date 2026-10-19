# LEGO Batman 2 PC: older definitions, materials, MESH 47 and DISP 7-10

Builds on [LB2_GEOMETRY.md](LB2_GEOMETRY.md) (pull request #14) and
[LB2_CHARACTERS.md](LB2_CHARACTERS.md) (pull request #15). LEGO Batman 2 ships
files from several stages of its engine; these readers now cover its older
character definitions, material tables, mesh sections and display lists.

## Definition streams 18, 19 and 22-24

`definitions.py` read only streams 25-31. LB2 has 147 `.cd` files in older
streams (4 in 18, 6 in 19, 14 in 22, 26 in 23, 97 in 24). Three rules cover them:

| | 18, 19 | 22, 23 | 24 | 25-26 |
|---|---|---|---|---|
| schema words per field | 3 | 4 | 4 | 4 |
| list (`OLST`) member count | u16 | u16 | u32 | u32 |
| object (`MOBJ`) header | 18 bytes | 18 | 18 | 16 |

The flags word stays the third schema word, so inheritance and terminators work
as before. With these rules all 147 files decode, and every object's fields
come out with the same names and plausible values as in stream 25 (the same
character in two streams gives the same model paths, tints and shadow values).
Streams 20 and 21 were not seen and stay refused.

Streams 18-23 name a character's model in `Model File` and have no `Skeleton
Name` (faces, the base minifigure). For those streams only, `character_definition`
reads `Model File` as the model override when there is exactly one such
definition.

## Material tables 106-123

The 125-132 footer (19 flag bytes, fx fields, UV transform, variant pointers,
trailing flag bytes, `name_ix`, `defaultRenderStage`) also fits the older tables,
with fewer trailing flag bytes:

| UMTL | texture IDs (16) | trailing flags | notes |
|---|---|---|---|
| 106 | +341 | 8 | no `alphaTestMode` byte (reported as `None`) |
| 108 | +341 | 10 | |
| 111 | +342 | 10 | |
| 120-122 | +342 | 10 | |
| 123 | +345 | 11 | |

The earlier lead (LB2_GEOMETRY.md) could not fix the length of the leading flag
block. Same-named materials in an older and a newer table settle it, because the
bytes before `fx1` agree:
- 123 against 125-132: 180 of 193 pairs agree over the 60 bytes before `fx1`;
- 121: 146 of 171 over 35 bytes or more.

108 and 121 records of the same material line up byte for byte. 106 lines up
with 108 one byte short at the end of the flag block, where 108 has
`alphaTestMode`. In 106 that position holds `colourWriteMask` (`0f`), never 0 or 8.

The older tables end like the newer ones: one flag byte (1) before `HSCB`. The
texture-ID positions were checked:
- **120-123:** by texture name. A material names the same textures in an old file
  and a new one (`HGXT` 9/10 names): 120 13 of 14 textured pairs, 121 197 of 228,
  122 23 of 28, 123 128 of 201.
- **106-111:** by range only. Their files reference few textures. Every ID in
  every record lies in -1 to the file's `HGXT` count at these offsets and no
  other single offset. Each offset sits the same distance before the name as in
  the later tables (497 bytes in 106-111, 498 from 120).

Tables 52-58 (51 files, mostly the unused `lego_city` level streams) stay
refused.

## MESH 47

190 LB2 files use MESH 47 (all with UMTL 47-111 and `HGXT` 5-8). Its layout:

- **Section head:** the count follows the version, with no `ROTV`. It counts only
  the **full** part records.
- **Depth copies** come between and after the full records. In such a record the
  word after the streams is a vertex count instead of 0. After the index-buffer
  reference come the first vertex, the first index and the first vertex again,
  and nothing else.
  - A depth copy is a position-only copy of the full record before it. It draws
    as many indices as that record, placed right after its indices, and skinned
    copies use that record's palette.
  - Checked on every copy in every file: all 9,535 draw exactly the same
    triangles in space as their full record.
  - They are returned in `depth_copies` (with `of_part`), not in `parts`. Display
    lists number only full records.
- **Record word:** the low two bits of the first word are the stream count.
  Values seen: 1 and 2 on full records, and 1, `0x25` and `0x601` on depth copies.
  The other bits are not decoded; `0x25`/`0x601` on a full record is refused.
- **Part tail:** a full record ends with a 40-byte tail (a u32, then nine floats).
  It is 72 bytes where MESH 48's secondary field and its 28 bytes follow, always
  zero. A record cannot start with a zero word, so the two are told apart. 7 files
  use the long tail on every part; morph parts use it inside otherwise short-tail
  files.
- **Buffer numbering** (the `0xC000nnnn` references): a long-tail full record
  counts one, a short-tail one none, a depth copy one, a palette one. With this
  rule all 187 walkable files resolve with one base, every reference names a
  buffer of its kind, and every draw range fits its buffer.
- **End:** the section ends where `u32 1` and `LTMU` (the material table) begin.

`read_mesh_bytes` now decodes 187 of 190 MESH 47 files: 19,394 full parts, 9,535
depth copies, 26.7 million triangles, 371 skinned parts and 19 parts with morph
targets (MESH 48's target reader applies unchanged). The other 3 are refused by
the existing non-finite UV check. MESH 46 (5 editor files) stays refused.

## DISP 7-10

The display lists of MESH 47 files have the DISP 12-14 layout with three
differences:

| | 7 | 8 | 9 | 10 | 12-14 |
|---|---|---|---|---|---|
| `ROTV` separators | none | none | yes | yes | yes |
| per-clip u32 arrays | 2 | 3 | 3 | 3 | 3 |
| then: command-index pairs (8 bytes), 16-byte records | yes | yes | yes | yes | no |

In 9 and 10 the separators are now checked, not skipped. The two extra arrays are
skipped, not interpreted. The instance records are the same 204-byte records.
Every LB2 DISP 7-10 file parses this way (including the 5 MESH 46 editor files).
Its clips draw part numbers below the full-record count, with opcodes `0xB3`
and `0xB5`.

The LOD tables have the shape the selector already verifies, so 7-10 were added
to `model_bindings`. 116 instances are refused for draw command `0xB5`, as in
12-14.

## Results

(Vehicles were added later: 1,150 load, [LB2_VEHICLES.md](LB2_VEHICLES.md).)

`load_model` over all 1,259 LB2 `.ghg`/`.gsc` files: **1,094 load** (895 `.gsc`,
199 `.ghg`), up from 927. 126 of them are MESH 47 files. The other 165:
- 58 at the multi-rig rules (unchanged);
- 51 at UMTL 52-58 (all MESH 47; mostly the unused `lego_city` streams);
- 19 `.ghg` at the skeleton: 10 MESH 47 files with an older skeleton layout and
  the 9 MESH 48 cases from before;
- 15 at non-finite UVs (3 of them MESH 47);
- 5 MESH 46 editor files;
- 17 by other existing mesh and display checks (see LB2_GEOMETRY.md).

Character import (Character add-on built locally, Blender 5.2.2, all 213
minifigure definitions from the extracted tree):
- **205 of 213 import**, with no material left unresolved (198 with #15 alone).
- **8 still fail:**
  - 5 are `skeleton_setup` files, internal rigs with no character: a layer
    name matches no instance;
  - `face_male`, `phantom_minifig` and `super_test` are MESH 47 models with an
    older skeleton layout.
- **Skipped attachments:** 7, down from 35:
  - 4 name resources the game does not contain;
  - 2 are `hat_construction` (UMTL 56);
  - 1 is `face_male`.
- **Newly imported:** Captain Marvel, the LexCorp scientist and the silver
  secretary (streams 23/24). Also the base minifigure and its older copy, read
  through `Model File`.

The same 200 randomly sampled LMSH1 character models decode identically before
and after (174 load).

## Checks

- `formats/cu3/scripts/test_lb2_definitions.py`: one schema in streams 18-28
  decodes to the same fields; `Model File` names the model before stream 24 only.
  Streams 17, 20, 21 and 32 are refused, and a stream-23 list read as 24 does not
  decode.
- `formats/cu3/scripts/test_lb2_materials.py`: 106, 108, 111, 121 and 123 tables
  (texture slots, trailing flags, no `alphaTestMode` in 106). A 123 table read as
  121, and 119/124/131, are refused.
- `formats/cu3/scripts/test_lb2_mesh47.py`: a full record with a depth copy (both
  tail lengths), copies after the last full record. Refused:
  - a copy whose repeated first vertex differs;
  - a copy with nothing before it;
  - flag bits on a full record, or an unseen record word;
  - an extra full record;
  - a non-zero long tail.
- `formats/cu3/scripts/test_lb2_display.py`: DISP 7-10 reach their instances and
  LOD selection. A miscounted per-clip array, and DISP 8's layout read as 9, are
  refused.
- `formats/cu3/scripts/test_lb2_mesh48.py`: MESH 46 stays refused.
- `tools/check_repository.py`, `tools/check_docs.py`.

Nothing here was checked in the game.

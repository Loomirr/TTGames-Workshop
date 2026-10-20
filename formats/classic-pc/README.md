# Classic PC file inspection

Read-only NU20, CU2, AN3 and GIZ tools for LEGO Batman (2008), LEGO Star Wars:
The Complete Saga and the reported LEGO Indiana Jones 1 PC layouts.
The character and cutscene addons also bundle **raw model inspection** and
**static CU2 reference scenes**. Complete classic character assembly, cutscene
playback, AN3 binding and native export are not available.
These readers do not modify games or bind animations to guessed skeletons.

## Use

Python 3.10+ is sufficient. Run from the repository root with extracted files:

```text
python formats/classic-pc/tools/cu2.py info "path/to/scene.cu2"
python formats/classic-pc/tools/cu2.py list "path/to/cutscenes"
python formats/classic-pc/tools/an3.py "path/to/animation.an3"
python formats/classic-pc/tools/nu20.py "path/to/model_pc.ghg"
python formats/classic-pc/tools/giz.py sections "path/to/level.giz"
python formats/classic-pc/tools/giz.py pickups "path/to/level.giz" "new-pickups.json"
```

NU20 inputs are limited to 256 MiB; other inspectors use 64 MiB. Pickup JSON refuses existing files.
CU2 reports original names, matrices, cameras, cuts and scalar animation blocks.
Unknown sections stay undecoded. Inspect notes and errors, including partial GIZ
framing: a readable header or completed command is not proof of complete coverage.

## Formats and limits

| Format | Enabled layouts | What is available |
| --- | --- | --- |
| CU2 | 516, 517, 519, 520 | Read-only camera/actor/object inspection; embedded 4INA/6INA/8INA scalar tracks |
| AN3 | 4INA, 6INA, 8INA and observed unrelocated 5INA | Nine-channel scalar inspection; no skeleton ownership or Blender pose conversion |
| GIZ | File version 1; checked section layouts | Section inventory, pickup versions 4/5/7 and empty v6, selected fixed-size records |
| NU20 GHG/GSC | Observed PC container versions 1, 2, 3, 4; separate payloads | Raw geometry, native rig/bind records, embedded DDS, UVs and normals; unsupported strides/draws are reported |
| DAT | Separate shared archive reader | LSW2 -1 ([notes](../../games/lsw2/README.md)), LB1 -2, TCS -3, LB2/SW3 -4; see [archive profiles](../../docs/COMPATIBILITY_EXPANSION_2026-10-09.md) |
| AN3 playback, native/glTF export | Not enabled | Ownership, conversion and writing remain unverified |

CU2 uses a companion script's `fpsec`, then the header rate, otherwise an
explicitly labelled 30 FPS assumption. Camera 255 remains no camera; negative
source cuts are preserved. Unknown CU2 versions cannot be forced through v520.
Raw extra root channels are not assigned guessed expression/event meanings.
AN4 is deliberately excluded from this AN3 reader.

## Blender inspection

In Character 0.5.16, select **LEGO Batman 1 (raw model inspection)** or
**LEGO Star Wars TCS (raw model inspection)** in the TT Character sidebar.
Set the installed or extracted root containing `CHARS`, then use **Browse game
characters**. You can also choose **File > Import > LEGO Character / Model**
and select a classic PC GHG/GSC with the matching game profile.

This displays raw draws with limited definition-based visibility. With the **TCS** profile,
rigid pieces named in the GHG's native character layer table (heads, hips,
helmets, hair and droid parts) are placed at their joint and weighted fully to it,
and each native layer gets its own collection. A matching sibling character
`.txt` now selects initial visibility using its explicit `layers_high` indices.
For `NAME_PC.GHG`, the match is `NAME.TXT` (case-insensitive). Every native layer,
mesh and rig is still imported; unselected layer collections are hidden in the
viewport and render, and can be enabled in the Outliner for inspection. The
Classic model report records the definition, selected indices and fallback reason.
No high-detail guess is made from triangle counts or native layer names.

Missing, duplicate, malformed or out-of-range lists leave **all** layers visible
with an explanation. `txt_file` inheritance, runtime costume switches, alternate
states, character scale and animation are not assembled. A low-resolution
`NAME_LR_PC.GHG` needs its own `NAME_LR.TXT`; the base model's indices are not
applied to a different layer table. Keep the definition beside the loose GHG;
archive extraction that only supplies a model falls back to raw visibility.
This source change needs updated addon packages before it is available in a
previously installed ZIP. With the LB1 profile, or
when a TCS layer table does not resolve exactly, unresolved rigid pieces are kept
in the hidden **Unbound rigid pieces / inspect separately** collection and the
report says why.
The Text Editor's **Classic model report** lists omissions. Geometry, native
bind records, UVs, normals and packed DDS images are preserved where decoded.
Some rigs repeat a bone name: eleven retail TCS characters (Dexter's and
Grievous's four arms, the probe droid's five legs) and LB1's robot and large
laser cannon and LIJ1's flying wing (each with its `_LR` copy). The game addresses
bones by index (AN3 clips have one node per bone and no names), so such a bone and
its vertex group are named `name#index` in Blender, the native name is kept on the
bone as `native_name`, and the report lists the names.
Rigs with non-unit rest scale, shear or reflection are explicitly refused;
diffuse RGB/vertex colors are an approximation, not native shader reconstruction.
Texture alpha is preserved as data but not automatically treated as opacity.
Do not use this mode as a character fidelity or animation/export test.

In Cutscene 0.1.25, use **File > Import > LEGO CU2 references (classic PC;
inspection only)**. This creates a separate scene with actor/object placements,
camera reference empties and shot markers where present. It does not assemble
meshes, environments, animated cameras, lens settings or animation playback.

## TCS character layer table

Facts, measured on 16 October 2026 on 21 TCS PC character GHGs (container
version 2). These were community character mods on the test machine; they keep
the original exporter structure, but they are not a retail roster census.

- Scene header `+0x18C` is the layer count (1 to 9 seen) and `+0x190` a
  self-relative pointer to 20-byte records: name (may be null), per-joint rigid
  object table, skinned object, a second per-joint table, extra object.
- Object entries are 12-byte records; their third field points at a 0xD0-byte
  special object. Every special object in all 21 files was named exactly once by
  this table (as rigid, skinned or extra).
- Rigid vertices are local to the joint. Placed with the special object's matrix
  and then the joint's bind transform, 191 of 192 rigid pieces with geometry had
  their centre within 0.15 units of the joint; the exception is an oversized
  custom head. Every sampled minifigure head spans 0.274 to 0.386 units, on top
  of its skinned body.

Not decoded: the second per-joint table (empty in every sample), the role of the
extra object (only on layer 0), and the first field of object entries. A layer
table that does not resolve exactly is reported and not used. LB1 and LIJ1
files have not been checked, so the LB1 profile keeps the earlier behaviour.

## Validation and attribution

The 9 October pass checked 135 CU2, 171 GIZ and 2,578 AN3 files extracted from
the installed Batman 1 archives. All those inspected layouts decoded. The
installed TCS tree contained 210 CU2, 259 GIZ and 2,969 AN3 files: all CU2,
253 GIZ and 2,967 AN3 passed the corresponding checks. This TCS tree has local
modifications; those counts are not a clean retail census. Embedded CU2 blocks
and AN3 scalar values were sampled at the first, middle and last frames.
The later [compatibility pass](../../docs/COMPATIBILITY_EXPANSION_2026-10-09.md)
adds raw model Blender checks with documented missing parts and overlaps; it
does not establish complete visual or in-game fidelity. Indiana Jones is not
installed on the test workstation and remains contributor-reported coverage.

NU20/CU2/GIZ code and format findings were contributed by **Gibby / stryderjoe** in
[PR #5](https://github.com/Loomirr/TTGames-Workshop/pull/5), reviewed at
`0c4eaf05cab36aefda312a8161b52dfd472326bf`. Their MIT license is preserved in
[LICENSE](LICENSE). The standalone AN3 inspector uses that shared curve reader
with explicit standalone layout checks. Workshop adds bounds checks, strict
version rejection and tests. The remaining PR exporters and archive extraction
code have not been merged. The separate archive reader extends Workshop's
existing bounded implementation. No BactaTank implementation was copied or translated.

```text
python formats/classic-pc/tests/test_readers.py
python formats/classic-pc/tests/test_models.py
python formats/classic-pc/tests/test_layer_selection.py
```

With Blender and your own TCS character GHG, the rigid-piece binding can be
checked from source (the output folder must be new; keep it under `local/`):

```text
blender -b --factory-startup --python-exit-code 1 --python formats/classic-pc/tests/check_tcs_layers_blender.py -- "path/to/CHARACTER_PC.GHG" "local/tcs-layer-check" --render
```

See [the review and outstanding work](../../docs/GITHUB_REVIEW_2026-10-09.md).

The 20 October 2026 layer-selection pass checked 782 rigged GHG layer tables in
the locally modified TCS installation. Of these, 204 had a matching definition
with a valid explicit `layers_high` list. The remaining 578 kept all layers:
395 lacked a matching definition, 173 lacked the explicit directive, nine had
indices/counts outside the native table and one had duplicate directives.
These are definition/table checks, not complete visual or retail-game coverage.
Blender 5.2.2 checks on Obi-Wan, Clone Torrent Company, 4-LOM and Yoda Ghost
preserve every layer and verify visibility and rigid binding on two posed
frames (maximum evaluated rigid-vertex error below `4.8e-8`). Eight Workbench
renders were inspected for assembly only; native shader and in-game fidelity
were not tested. Yoda Ghost exercised an out-of-range definition fallback.
The parser is independently implemented; the sibling TXT
workflow was informed by the authorized MIT-licensed
[Figure Forge review](../../docs/FIGURE_FORGE_REVIEW_2026-10-20.md).

PR [#7](https://github.com/Loomirr/TTGames-Workshop/pull/7) from
**Gibby / stryderjoe**, reviewed at
`9bd83fd986948afac972535b9baecc7e957b0fdf`, adds the explicit LSW2 DAT -1
index profile. Its original-file census is contributor-reported.
PR [#8](https://github.com/Loomirr/TTGames-Workshop/pull/8), reviewed at
`059434b9c992216dfe5ddd5f5acaeb2adaf4af18`, adds NU20 container version 3.
Existing payload, bounds and finite-value checks remain in effect. These
changes do not enable full character assembly or animation playback.

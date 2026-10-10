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
| NU20 GHG/GSC | Observed PC container versions 1, 2, 4; separate payloads | Raw geometry, native rig/bind records, embedded DDS, UVs and normals; unsupported strides/draws are reported |
| DAT | Separate shared archive reader | LB1 -2, TCS -3, LB2/SW3 -4; see [archive profiles](../../docs/COMPATIBILITY_EXPANSION_2026-10-09.md) |
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

This displays raw draws, not a configured character. Unresolved rigid pieces
(including some heads/accessories) are kept in the hidden **Unbound rigid pieces /
inspect separately** collection. Costume and visibility alternatives can overlap.
The Text Editor's **Classic model report** lists omissions. Geometry, native
bind records, UVs, normals and packed DDS images are preserved where decoded.
Rigs with non-unit rest scale, shear or reflection are explicitly refused;
diffuse RGB/vertex colors are an approximation, not native shader reconstruction.
Texture alpha is preserved as data but not automatically treated as opacity.
Do not use this mode as a character fidelity or animation/export test.

In Cutscene 0.1.25, use **File > Import > LEGO CU2 references (classic PC;
inspection only)**. This creates a separate scene with actor/object placements,
camera reference empties and shot markers where present. It does not assemble
meshes, environments, animated cameras, lens settings or animation playback.

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
```

See [the review and outstanding work](../../docs/GITHUB_REVIEW_2026-10-09.md).

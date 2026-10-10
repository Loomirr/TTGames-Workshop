# Classic PC file inspection

Read-only CU2, AN3 and GIZ tools for LEGO Batman (2008), LEGO Star Wars:
The Complete Saga and the reported LEGO Indiana Jones 1 PC layouts.
These are command-line inspectors, **not yet Blender model or cutscene importers**.
They do not modify games, bind animations to guessed skeletons or write native files.

## Use

Python 3.10+ is sufficient. Run from the repository root with extracted files:

```text
python formats/classic-pc/tools/cu2.py info "path/to/scene.cu2"
python formats/classic-pc/tools/cu2.py list "path/to/cutscenes"
python formats/classic-pc/tools/an3.py "path/to/animation.an3"
python formats/classic-pc/tools/giz.py sections "path/to/level.giz"
python formats/classic-pc/tools/giz.py pickups "path/to/level.giz" "new-pickups.json"
```

Inputs are limited to 64 MiB each. Pickup JSON refuses existing files.
CU2 reports original names, matrices, cameras, cuts and scalar animation blocks.
Unknown sections stay undecoded. Inspect notes and errors, including partial GIZ
framing: a readable header or completed command is not proof of complete coverage.

## Formats and limits

| Format | Enabled layouts | What is available |
| --- | --- | --- |
| CU2 | 516, 517, 519, 520 | Read-only camera/actor/object inspection; embedded 4INA/6INA/8INA scalar tracks |
| AN3 | 4INA, 6INA, 8INA and observed unrelocated 5INA | Nine-channel scalar inspection; no skeleton ownership or Blender pose conversion |
| GIZ | File version 1; checked section layouts | Section inventory, pickup versions 4/5/7 and empty v6, selected fixed-size records |
| DAT, NU20 GHG/GSC, glTF export | Not enabled in this component | Contribution remains under review; use of the same extension does not enable another reader |

CU2 uses a companion script's `fpsec`, then the header rate, otherwise an
explicitly labelled 30 FPS assumption. Camera 255 remains no camera; negative
source cuts are preserved. Unknown CU2 versions cannot be forced through v520.
Raw extra root channels are not assigned guessed expression/event meanings.
AN4 is deliberately excluded from this AN3 reader.

## Validation and attribution

The 9 October pass checked 135 CU2, 171 GIZ and 2,578 AN3 files extracted from
the installed Batman 1 archives. All those inspected layouts decoded. The
installed TCS tree contained 210 CU2, 259 GIZ and 2,969 AN3 files: all CU2,
253 GIZ and 2,967 AN3 passed the corresponding checks. This TCS tree has local
modifications; those counts are not a clean retail census. Embedded CU2 blocks
and AN3 scalar values were sampled at the first, middle and last frames.
No Blender visual or in-game fidelity is established. Indiana Jones is not
installed on the test workstation and remains contributor-reported coverage.

CU2/GIZ code and format findings were contributed by **Gibby / stryderjoe** in
[PR #5](https://github.com/Loomirr/TTGames-Workshop/pull/5), reviewed at
`0c4eaf05cab36aefda312a8161b52dfd472326bf`. Their MIT license is preserved in
[LICENSE](LICENSE). The standalone AN3 inspector uses that shared curve reader
with explicit standalone layout checks. Workshop adds bounds checks, strict
version rejection and tests. The remaining PR exporters and archive extraction
code have not been merged. No BactaTank implementation was copied or translated.

```text
python formats/classic-pc/tests/test_readers.py
```

See [the review and outstanding work](../../docs/GITHUB_REVIEW_2026-10-09.md).

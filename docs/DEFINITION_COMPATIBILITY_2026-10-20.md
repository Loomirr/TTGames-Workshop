# Shared definition compatibility checks

20 October 2026. This source change improves the shared CD/AS/CPD reader used
by the Character and CU3 tools. AI assistance was used for implementation and
validation. It does not enable a new complete game importer or native exporter.

## Reproduced problem

The reader stopped at an embedded class even when its complete field schema
was present. This omitted inline light declarations in character attachments,
and prevented safely reading subsequent outer fields. Later files also declare
`Half` and `Colour4` primitive fields that the reader did not decode.

[Figure Forge's typed stream reader](https://github.com/stryderjoe/figure-forge/blob/a0b02574427d6c3518bc184bc36785e083726090/forge/formats/ttstream.py)
provided a comparison implementation and format evidence for inline classes.
The changes extend Workshop's existing bounded reader; no upstream writer or
fallback layout selection was imported. See the [broader review](FIGURE_FORGE_REVIEW_2026-10-20.md)
for licensing and integration scope.

## Changed behavior

- Decode the observed embedded-class flag `0xA0000000` recursively using its
  declared class schema. Keep the resulting class and fields nested under their
  actual owning field. Inherited fields retain the existing flattened behavior.
- Continue decoding outer fields only after every inline member is understood.
  An unknown inline member leaves that entire inline value and the following
  outer fields undecoded. There is no guessing a size or skipping unknown data.
- Read and bound the optional native `TypeList`. Enable `Half` at type 14 only
  when the table declares `Half`, 2 bytes, and `Colour4` at type 19 only when it
  declares `Colour4`, 16 bytes. Other unknown types remain undecoded. In
  particular, later streams' changed pointer/resource widths are not guessed.
- Preserve exact byte spans for primitive fields and nested fields. Inline
  spans have `type: null`, a class index, and `inline: true`, so the existing
  primitive-string patcher cannot mistake a class index for a string type.
- Bound recursive depth and total expanded schema work, including repeated
  inheritance of empty classes. Reject recursion, truncation, invalid extents
  and nonfinite decoded floating-point values.
- An object ending before a required schema field is now marked incomplete.
  Reaching the end of its byte extent alone does not establish completeness.

No version gates changed. Stream versions 20, 21 and 38 remain refused. This
does not claim DCSV definition support, general dependency closure, nested
`ClassObject` decoding, complete scene lighting, or changed-length definition
writing. Native lighting values are newly available as data; Blender's light
creation code has not been changed by this pass.

## Checks run

Python 3.14.7, source checkout with unrelated local edits preserved. Original
inputs were read only. Reports and the pre-change reader snapshot are under
ignored `local/validation/definition-compatibility-20261020/`.

| Check | Result |
| --- | --- |
| Before/after decoding of 1,504 SHA-256-deduplicated local CD/AS/CPD inputs | All 1,487 previously accepted files still decode. The same 17 inputs remain refused: 13 stream-20, two stream-21, one stream-38, and one invalid string extent. |
| Existing data preservation | All prior object counts, field values and primitive field spans agree with the pre-change reader. |
| Additional decoded data | 176 files gain 1,400 outer fields, including nested inline declarations. Observed improved versions: 18, 19, 25, 27, 28, 29 and 31. Nested leaf fields are additional to this count. |
| Comparison with Figure Forge where its reader supports the observed layout | 66,579 decoded leaf values agree across the improved files. Inherited values are compared with equivalent ownership; matrix/half byte representations are decoded before comparison. |
| Extent and later primitive checks | All improved files pass primitive span checks; newly decoded Half/Colour4 values agree with the exact source bytes. No changed source files were written. |
| New asset-free regressions | 10 pass: inline ownership, subsequent references, versions 18–31, confirmed primitive widths, unknown flags/types, recursion, exponential empty inheritance, truncation, and nonfinite values. |
| Existing LB2 definition tests | 4 pass. |
| Existing constrained character-clone definition writer tests | 6 pass. |
| Existing material declaration tests | 23 pass, one optional original-input test skipped. |

The local input corpus includes LMSH1, LB3, Hobbit, Avengers, TFA and Ninjago
definitions plus legacy definitions retained in those trees. It includes cached
and installed files; this is not a clean-retail inventory of every game's
definitions. Sampled improvements include LMSH1 A-Bomb's inline attachment
light, LB3 Batman/Killer Croc declarations, and TFA Scouttrooper and Avengers
Captain America AOU fields. Presence in a newer game's directory does not
determine its embedded stream version.

Portable commands, from the repository root:

```text
python formats/cu3/scripts/test_definition_inline.py
python formats/cu3/scripts/test_lb2_definitions.py
python tools/character_clone/test_definition_patch.py
python formats/cu3/scripts/test_material_declarations.py
```

Set `TEMP`/`TMP` to a writable private test directory if the workstation's
default temporary-directory ACL prevents the temporary-file tests. The first
LB2 test run encountered that environment issue; the rerun used an ignored
workspace test directory and passed without changing the tests' protections.

Original-file reproduction harnesses: `compare.py`, `check_values.py`,
`comparison.json`, and `value-checks.json` in the private report directory.
They require the same user-owned inputs and are not distributable fixtures.
No Blender render or in-game test was performed for this reader-only change.

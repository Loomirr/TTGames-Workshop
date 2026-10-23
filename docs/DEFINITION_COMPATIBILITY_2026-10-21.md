# Older character definition files: October 21 checks

The shared definition reader now accepts the observed **stream versions 20 and
21**. These are versions of the data inside CD/AS files, not game names. The
change helps the Character and CU3 tools read recipes and animation references
that previously stopped at an unsupported-version error.

This is a file-reading improvement. It does not enable a new complete game
importer, decode every field, or establish that an exported character works
in-game. AI assistance was used for implementation and validation.

## What was checked before enabling them

The previous local corpus contained 13 stream-20 files and two stream-21 files
that the reader refused. Their measured layout uses:

- Three 32-bit schema words after each field name.
- A 16-bit class index followed by a 16-bit object count in each typed list.
- Five bytes between an object header and its field values.

Workshop already implemented this layout for neighboring observed versions.
We checked its decoded values and exact field positions against
[Figure Forge's reader at a0b0257](https://github.com/stryderjoe/figure-forge/blob/a0b02574427d6c3518bc184bc36785e083726090/forge/formats/ttstream.py).
That reference has an explicit version-20 layout. For the private version-21
comparison, we selected the same measured list/header layout and verified all
object boundaries and the final file extent; its default fallback does not
read these files correctly. No fallback or writer was copied into Workshop.

All 729 decoded primitive values and their byte offsets agree across the 15
inputs. The reference reader reaches the end of every file without partial
objects. Workshop retains its narrower field support: 104 objects are exposed,
of which 17 are marked incomplete because nested resource data or unknown
fields remain unread. It does not claim those tails were decoded.

The files are legacy resources found in a local Ninjago asset tree, including
Crablarvae, Gor, Reek, CommandoDroid and older animation sets. Their location
does not prove their original shipping game. This is not a clean-retail game
inventory or a claim of full Ninjago support. Inputs were read only.

## Checks run

Python 3.14.7 was used. Reports and comparison scripts are under the ignored
`local/validation/definition-gaps-20261021/` directory; they require the owner's
game files and are not distributed as fixtures.

| Check | Result |
| --- | --- |
| Before/after comparison of 1,504 local CD/AS/CPD files | All 1,487 previously accepted results are identical, including field values, offsets and completeness. Fifteen previously refused files now decode. |
| Remaining refused inputs | One stream-38 file and one deliberately malformed compatibility-probe file. |
| Independent original-file comparison | 15 files, 729 primitive values/offsets agree; complete reference file extents checked. |
| New portable regressions | Eight tests pass: values/spans, wrong schema/header, list bounds, invalid class, unknown fields, truncation and unverified versions. |
| Existing definition tests | Ten inline tests and four older-layout tests pass. |
| Definition patch helper | Six tests pass. |
| Material declaration checks | 23 pass; one optional original-input test skipped. |

Commands from the repository root:

```text
python formats/cu3/scripts/test_definition_versions.py
python formats/cu3/scripts/test_definition_inline.py
python formats/cu3/scripts/test_lb2_definitions.py
python tools/character_clone/test_definition_patch.py
python formats/cu3/scripts/test_material_declarations.py
```

The initial older-layout test run hit a Windows temporary-directory permission
error. It passed after `TEMP`/`TMP` were directed to an ignored writable test
folder; no protection in the reader or tests was removed.

No new Blender visual or in-game test was performed for this reader change.

## Why version 38 is still refused

The sampled DCSV Batman definition is not the older layout with a new version
number. Allowing the version alone produces an invalid class-index error.
Its list header bytes appear to put the object count before the class index,
and empty lists have a shorter header. That is a research lead, not an enabled
layout: it needs its own bounded parser and broader original-file checks.

Its embedded type list also declares an eight-byte pointer, 72-byte class
objects/references, and additional types such as `NuTransform` and `NuGuid`.
Figure Forge's current default layout fails on this sample too. Reusing its
older sizes would read the wrong fields. Stream 38 remains explicitly refused.

## Checklist for complete character compatibility

The overall goal is complete support across games. A definition parsing
success is only the first part of that work:

- **Definition fields:** retain their ownership and decode nested resource
  objects, conditional data and currently unknown fields before claiming that
  every attachment or animation reference has been found.
- **Models and rigs:** verify each mesh version, bone hierarchy, part binding,
  costume layer and detail-level selection against original assets.
- **Materials:** apply texture choices, remaps, transparency and game-specific
  shading; compare rendered output, not just whether import succeeds.
- **Animations:** match each body/face/attachment track to its owner and check
  timing, compression, events and edited files in the target game.
- **Export:** preserve unknown data, represent the intended edits and test
  both unchanged and changed files. Adding bones or replacing parts requires
  writing more than a definition string.

The [editing guide](CHARACTER_EDITING.md) describes today's user-facing export
limits. The [previous definition report](DEFINITION_COMPATIBILITY_2026-10-20.md)
records inline-field and primitive-type work from the preceding pass.

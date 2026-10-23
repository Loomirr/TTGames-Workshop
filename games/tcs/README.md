# LEGO Star Wars: The Complete Saga, PC

## Scripting documentation

The [TCS scripting guide](scripting/README.md) covers text AI scripts (`.SCP`),
their native command interface, and the related character and level text files.
It includes original examples, an evidence-labelled command reference, native
character/animation authoring, stock saber colors, portrait loading, capacity
findings, native execution rules, message/parameter examples and a mod-author
debugging workflow. A separate LSW1 comparison identifies inherited commands
whose earlier bindings are absent in TCS. It is research documentation, not a script
compiler or a claim of complete language coverage.

## Binary assets and tools

See [classic PC inspection](../../formats/classic-pc/README.md) for NU20
GHG/GSC, CU2, AN3 and GIZ support, including the
[character layer table](../../formats/classic-pc/README.md#tcs-character-layer-table)
that binds rigid heads and accessories to joints. A binary `.GSC` scene/model is not an AI
`.SCP` script. These notes apply to TCS PC; they do not establish compatibility
with LSW1, LSW2, console TCS or later TT games.

## Shader and facial completion

This edition must separately pass **1:1 shader matching, face reconstruction,
facial animation and native facial/material export**. These remain open goals;
see the [per-game checklist and required evidence](../../docs/VISUAL_AND_FACE_COVERAGE.md).

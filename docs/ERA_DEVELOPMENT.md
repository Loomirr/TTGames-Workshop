# Complete one era at a time

This is the development order for the whole project, independent of the Blender
UI. The goal is the complete workflow: import, animate, change bones or parts,
export, and use the result in the game. **No era is complete today.**

Every game also requires **1:1 shader recreation, complete faces and facial
animation, and native facial/material editing and export**. Track them separately
using the [per-game visual and facial completion list](VISUAL_AND_FACE_COVERAGE.md).
Partial material previews or body animation alone cannot close a game or era.

## Work order

| Stage | Work to finish |
| --- | --- |
| **1. Early Classic — active** | LSW1 PC first, then LSW2 PC. Inventory each release; finish models, textures/materials, definitions, body/face animation, cutscenes and native editing/export. |
| **2. NXG** | Finish each game individually, including Batman 2, Marvel Super Heroes and The Hobbit. Inventory other games before assigning layout support. |
| **3. DX11** | Finish each game's model, material, animation and scene layouts. Batman 3's DX11 models and NXG animations require both families. |
| **4. NTT** | Skywalker Saga gets its own inventory and readers. Older GHG/CU3 support is not a substitute. |
| **5. Classic** | TCS, Batman 1 and Indiana Jones 1, each with its own release/layout evidence. Finish definitions, NU20 models, animation/scene families, dependencies and export. |

Classic is scheduled last to give ongoing work by other Classic modders time
to mature and avoid duplicating it.

Existing later-era tools remain available and can receive regression fixes.
New compatibility expansion follows this order. Fortnite remains separate and
deferred. Console, handheld, prototype, regional and patched releases need
their own records; a PC pass does not cover them. Identify those outstanding
targets in the release inventory before calling an era complete.

## Completion criteria

Track **game + platform + release + file layout**, not just extension or era.
Keep input identities and detailed reports privately, with public coverage summaries.

1. **Account for the files.** Inventory the full release: archives, loose files
   and dependencies. Reconcile extraction against it. Record unknown extensions,
   signatures, versions, flags and missing samples.
2. **Understand the data.** Document structures, references and ownership.
   Inspect every stored layer, variant, attachment, material mode and animation
   channel. Preserving unknown bytes is useful but is not full understanding.
3. **Reconstruct the result.** Check models, rigs, textures, material remaps,
   additional models, visibility, body/face animation and scenes against actual
   rendered frames and game behavior. Verify native shader passes, face masks,
   expression targets and timing across angles, detail levels and transitions;
   keep approximations distinct from demonstrated 1:1 recreation.
4. **Edit and write it back.** Check unchanged preservation, decoded edited
   round trips, added bones/parts, hair swaps, custom animations and required
   definition/archive links. Identify which file families need inspection,
   assembly or writing; none may disappear from the inventory. Include facial
   targets/clips and material settings, with separate tests for new entries.
5. **Validate in-game.** Test modifications, transitions and affected actions.
   An idle passing does not validate walking, combat or facial playback.
   Retain regressions for each corrected layout.

Missing samples, unimplemented writers and untested variants stay open. Do not
move a game to complete while required workflows remain untested. New discoveries
reopen the corresponding record.

## Early Classic baseline — 22 October 2026

### LSW1 PC

The locally owned installer's File table lists **5,035 files**. This is installer
inventory, not proof every file was extracted or decoded. It includes 157 HGP,
871 ANI, 617 BSA, 35 ANM, 115 CUT, 176 NUP, 116 TER and 658 TXT entries, plus
scripts, textures, audio and other families.

The reconstructed working tree contains **157 HGP and 653 TXT files**. A fresh
reader audit passes all 157 HGPs across **575 stored layers**, with name-table
offsets `0x14`, `0x28`, `0x30`, `0x36`. These distinguish observed layouts; they
are not asserted to be format version numbers.

Every audited layer has a nonzero word at `+0x0C` that the layer reader does not
interpret. Its meaning remains research work; it is not established as missing
geometry. The new audit records this gap alongside the reader pass.

Header checks found all 871 ANI, 617 BSA and 35 ANM files in the flat extraction.
All 115 CUT files are now accounted for: the initially missing entry had a
trailing-dot cabinet name changed during extraction. Its local bytes were
verified against the exact CAB member. ANI/BSA/CUT samples begin with integer 2;
ANM samples begin with 4 or 6. These are observations, not verified animation
decoding or evidence that these files share later AN3/AN4 layouts.

The new [ANI/BSA record reader and editor](../formats/hgp/lsw1/docs/ANIMATION_RECORDS.md)
accepts 870 ANI and all 617 BSA samples. One historical ANI has a non-finite value
and is rejected. Unchanged writes are identical; 2,446 decoded channel-edit
round trips preserve all other bytes. Playback and in-game checks are still open.
The scalar curve evaluator now matches 340,724 sampled results from the original
PC routine within the documented tolerance. Its time context was synthesized;
full caller execution, rig binding and playback remain separate work.

The [facial target reader](../formats/hgp/lsw1/docs/FACE_TARGETS.md) now imports
1,643 target slots from 63 original models as initially zeroed Blender shape
keys. Raw deltas and evaluated movement were checked; BSA binding remains open.

The [character TXT layer reader](../formats/hgp/lsw1/docs/CHARACTER_LAYERS.md)
imports exact declared sets. Blender checks passed 506 valid sets across 103
models and refused 14 invalid original sets. Nested animation overrides and
runtime layer switching are not yet applied.

[Shader research](../formats/hgp/lsw1/docs/SHADERS.md) has recovered 197 compiled
program entries (100 distinct bytecode sequences) and verified the ordinary
additive blend-state branch. Version 0.1.9 fixes pod effects' black backing in
Blender. Runtime shader selection, lighting constants and frame-matched fidelity
are still unverified.

**Next:** reconcile the rest of the release; trace ANI/BSA ownership and channels using
original definitions and HGP rigs; interpret remaining model fields; implement
and verify native playback. Model/animation export, arbitrary bone/part edits
and full scene support remain open. Existing visual reports stay in the
[LSW1 feedback record](LSW1_FEEDBACK_2026-10-20.md).

```text
python formats/hgp/lsw1/tools/audit_files.py path/to/extracted-files path/to/new-report.json
```

This source-tree tool lists every present file, checks every HGP layer and ANI/BSA
record layout, marks other file types `not_examined`, and refuses to overwrite a
report. Animation `record_pass` is separate from model `reader_pass`. It does not
render, play animations or write game files. A model-only sample cannot establish
whole-game support.

### LSW2 PC

The [game record](../games/lsw2/README.md) separates contributor original-file
results from local synthetic checks. Its HGP addon imports animations and offers
experimental model export, including added bones/parts. Full original-file
retesting and in-game export validation remain outstanding locally. LSW1
leftovers in an LSW2 release retain their own layout identity.

## Source organization

Era milestones own the work; format modules implement verified layouts. Keep
LSW1 and LSW2 readers separate, and Classic separate from NXG/DX11 and future
NTT layouts. Share routines only where equivalent behavior is demonstrated,
with game/platform/layout checks at the boundary. Duplicating or renaming an
addon does not establish new format support.

AI assisted with inventory tooling and documentation. Counts above are fresh
local observations; workflow gaps are separate from passes.

# Figure Forge and Workshop fork review

Reviewed 20 October 2026 against Workshop `98c00876ca15d52bb906d574a0cc47bca9a6453b`,
with existing local changes preserved. AI assistance was used for this review.
This is research and integration planning; no importer/exporter support was
enabled by this pass.

## Sources and reuse

[Figure Forge](https://github.com/stryderjoe/figure-forge/tree/a0b02574427d6c3518bc184bc36785e083726090)
was reviewed at `a0b02574427d6c3518bc184bc36785e083726090`. Its
[MIT license](https://github.com/stryderjoe/figure-forge/blob/a0b02574427d6c3518bc184bc36785e083726090/LICENSE)
permits reuse with the copyright and permission notice retained. The repository
owner also authorized using it. Preserve component attribution when importing
code; permission does not establish format correctness.

The upstream README reports in-game replacement/new-character experiments in
seven PC games. Those are upstream results, not tests performed in this review.
Its declared modes cover TCS, Indiana Jones 1, Batman 1, Pirates, Batman 2,
Marvel Super Heroes 1 and Batman 3. They do not establish support for original
LSW1 HGP, LSW2 HGP, DCSV, Dimensions, TFA, LMSH2, handhelds or Skywalker Saga.

## Most useful components

Paths below are relative to the pinned Figure Forge revision.

| Component | Relevant capability | Workshop opportunity / boundary |
| --- | --- | --- |
| `forge/formats/classic.py`, `forge/catalog.py` | Classic native layer ownership, character text `layers_high` choices, declared clips, part classification | Improve configured TCS/LB1 assemblies beyond showing raw overlapping layers. Body-region splitting is an editing heuristic, not a native part definition. |
| `forge/formats/nu20edit.py`, `forge/gamewrite.py` | Physical classic NU20 layout writer, self-relative pointer registration, PNTR/GSNH growth, vertex/index buffers, texture atlases and layer rebuilding | Strong starting point for classic loose-GHG mesh replacement. It keeps the template skeleton and has available mesh/model slot limits. |
| `forge/nxgwrite.py` | New geometry buffers/parts, skin palettes, draw-command changes, texture companions for selected MESH 46/47/48/161/169/175 layouts | Candidate for topology-changing export on specifically validated Pirates/LB2/LMSH1/LB3 profiles. It is a template/body-layer reconstruction path, not lossless arbitrary character export. |
| `forge/formats/ttstream.py` | Embedded schema reading and structural edits of definitions, including nested objects and changed string lengths | Potential extension of our currently constrained CD/AS/CPD editing. Keep explicit version/extent/completeness guards. |
| `forge/formats/hser.py`, `forge/gameexport.py` | Resource trees, model/shader/texture references, LB3 load lists, new-character project registration | Useful for making a new loose character load correctly, beyond producing a readable GHG. |
| `forge/anim.py`, `forge/skeleton.py`, `forge/parts.py` | Classic AN3 preview, game-specific bind-relative rules, humanoid name mapping, rest-relative retargeting and part fitting | Compare against our explicit mapping API. Do not use bone count alone or apply its humanoid aliases to arbitrary rigs. |
| `forge/formats/modern.py`, `ui/js/faces.js`, `ui/js/exporters.js` | Modern facial target/clip playback and GLB morph export | Additional comparison implementation for facial IDs and animation. Native export does not preserve all of this. |
| `forge/gameportrait.py`, `forge/formats/pack.py`, `forge/newchar.py` | Portrait layouts, text/animation packs and character registration | Useful for new-character names, icons and dependencies; distinct from mesh/skeleton encoding. |
| `tools/era_survey.py` | Extension/header inventory | Useful discovery aid. Tag scanning is not a substitute for strict format identification. |

## Limits that affect the intended editing workflow

Figure Forge's native writers map GLB joints to existing recipient names. An
unknown joint walks up its ancestors to a recognized joint, falling back to
joint zero. They do not append the joint to the native skeleton. The local
custom-joint experiment below confirms this behavior. A Workshop integration
should report an unresolved joint rather than silently treating it as a new
native bone.

The modern writer skips occluders, emits new parts without morph targets,
consolidates the figure into the body layer, and clears several character
material/attachment/layer choices. Its README explicitly notes missing mouth
masks, decal settings and blend shapes in native LMSH1/LB3 exports. This path
must not replace our existing face-preserving edit path without those losses
being resolved or explicitly selected.

Other integration concerns found by source review:

- `Glb.accessor` constructs strided NumPy views without proving the final
  requested byte extent. Validate counts, strides and bounds before adopting it.
- GLB normals are transformed with the ordinary linear matrix, rather than an
  inverse transpose. Nonuniform scaling needs a dedicated regression and fix.
- `ModelFile._where` needs an explicit nonnegative-address check. Reference
  readers/writers need our allocation, malformed-input and source-identity
  checks before becoming public Workshop editing paths.
- Animation code uses minimum node counts, common-name dictionaries and
  game-level rules. Duplicate names, auxiliary bones, differing parent maps,
  root motion and scale require explicit policies and separate tests.
- Atlas baking, UV clamping and limited influence/palette counts can change
  rendering or deformation. A successful read-back does not prove fidelity.

Prefer the writer's generated file data and mod-folder path for our extracted
game workflow. Archive patching and runtime installation are separate actions;
neither was performed in this review.

## Checks actually run

Isolated reference checkouts and generated assets/reports remain under ignored
`local/references/` and `local/validation/figure-forge-20261020/`. The harnesses
read supplied game files and write only separate experiment outputs. No game,
save, installed addon, public build or user scene was changed.

| Check | Result | Meaning |
| --- | --- | --- |
| Figure Forge classic parse/write without edits | **802/802 byte-identical**: 20 extracted LB1 files, 782 files from the installed TCS character tree | Both metadata-first and payload-first physical layouts round-trip in this sample. The TCS tree includes mods and alternatives; this is not 782 distinct retail characters. |
| Workshop and Figure Forge classic readers on those inputs | Bone and mesh counts agree on all 802 | Separate reader read-back/check; counts alone do not verify geometry or rendering. |
| Custom skinned triangle written into Catwoman (LB1) and Obi-Wan (TCS) templates | Both outputs reopen in Figure Forge and Workshop | Actual edited loose-GHG construction, not merely no-op writing. Template inputs remained byte-identical. |
| Added child joint in those test GLBs | Mapped to existing `head`; output skeletons remain 25 and 31 bones | Direct evidence that Figure Forge's classic writer does not implement bone addition. |
| TCS edited output layer inspection | Two referenced draws, 639 triangles total | Template special-layer geometry can be retained; the output was not reduced to the test triangle alone. Visibility has not been tested in-game. |
| Definition parsing / unchanged `ttstream.edit` | **63/63 identical**: first 60 sorted local LMSH1 CDs and 3 cached LB3 CDs | Observed stream versions 25, 28 and 29; not a full game census. |
| HSER read/write | **46/46 present headers identical** within those 63 files | Useful dependency-header baseline; no changed dependency/game-loading test yet. |
| Modern model structure | 4/4 decode: LMSH1 shared minifig; LB3 shared minifig, cape, Batman face | Parts, DISP, skeleton lists and material names read; not rendered or exported. |
| LSW2 branch synthetic suite | **27/27 checks pass**, including added bone/part/material/texture/shape and malformed inputs | Upstream tests rerun locally with NumPy; no original LSW2 asset or in-game check in this pass. |
| LSW2 normal-only edit regression | **Bug reproduced**: actual `matches_original` reports changed normals as unchanged | Existing publication blocker remains, despite the synthetic suite passing. |
| Workshop skeleton transfer tests | **20 pass**: transfer 7, animation audit 6, item routes 7 | Existing reusable logic still passes its portable checks. |

The reference probes used Python 3.12.14 with NumPy 2.3.5 and Pillow 12.3.0;
Workshop's portable skeleton checks used Python 3.14.7. The initial plain
Python LSW2 run skipped its NumPy-dependent DXT test; the second run above
included it. No browser UI, Blender render, full modern native writer,
cross-game motion fidelity or in-game validation was run in this pass.

Local records: `probe.py`, `results.json`, `modern_probe.py`,
`modern-results.json`, `check_export_blocker.py`, `export-blocker.json`,
`forks.json`, branch snapshots and `prs.json`. The synthetic GLBs and edited
GHGs stay local because the outputs incorporate template game data.

## Public fork inventory

GitHub's public fork and branch APIs returned **two forks, 22 branch heads**:
18 in stryderjoe's fork and 4 in Snufflebox's. This inventory cannot discover
private forks or unrelated repositories. Branch histories were compared in an
isolated checkout against the official `main` above; existing branch names
alone are not evidence of unmerged features.

| Fork branches | Current disposition |
| --- | --- |
| stryderjoe: `character-game-handedness`, `lb2-animation`, `lb2-face`, `lb2-mesh48`, `lb2-mesh48-frames`, `lb2-older-versions`, `lb2-profile`, `lb2-umtl56`, `lb2-vehicles`, `lmsh-vehicles`, `lmsh1-reflection-cubemap`, `lmsh1-surface-format-2`, `tcs-duplicate-bone-names` | Already merged through PRs 12-15 and 18-26. Do not reapply old branch snapshots over the newer shared readers. |
| stryderjoe: `classic-pc-readers`, `lsw2-dat-index`, `nu20-version-3` | PRs 5/7/8 were selectively integrated and closed; their tips are not all ancestors of main. Classic export/research scripts left out of PR 5 remain references, not newly enabled features. See earlier review and component attribution. |
| stryderjoe: `lsw2-hgp-blender` at `dc55e8084338b63573914520ad8804c561d28f62` | [Open PR 10](https://github.com/Loomirr/TTGames-Workshop/pull/10), highest-priority unmerged importer/exporter candidate. |
| Snufflebox: `tcs-rigid-pieces` | Already merged through [PR 16](https://github.com/Loomirr/TTGames-Workshop/pull/16). |
| Snufflebox: `tcs-four-player-pr` at `9e4f714ac0bde8eb5f4a5332362da88d85524e35` | [Open PR 17](https://github.com/Loomirr/TTGames-Workshop/pull/17), executable-specific runtime work; not an importer. Existing memory-protection and image-bound validation blockers remain in the inspected source. |
| Snufflebox: `tcs-custom-characters` at `1b5d326f6d9b338623299162c6d4204fc014fb4a` | One additional commit beyond PR 17's head, with a loose-file overlay, registration, localized names and icon handling. Review this branch's actual diff; the PR description mentions work not all present at its head. |
| Both `main` branches | Older bases; not a source of newer unmerged importer fixes in this inventory. |

The LSW2 branch is MIT and **actually appends native bones**, unlike Figure
Forge's recipient-skeleton writers. It preserves original bones and models
extra joint data on the parent. It is specific to **LSW2 HGP**, so its serializer
cannot be dropped into TCS NU20 or modern HGOL files. Existing normals/colors
can still be silently lost by its unchanged-part test; the source is also not
hash-bound. Fix these before integration and add source-identity, normal-only,
color-only, changed-original-bone and added-bone regressions. Its README says
no exported model has yet been tested in-game.

The TCS custom-character branch provides valuable format/runtime evidence:
character lists and text IDs, packed character definitions, internal icon names,
texture record versus DDS dimensions, and why a loose file may lose precedence
to archive data. Its loader is tied to one executable build and to the runtime
patch. The PR asks about licensing; this review does not assume Figure Forge's
MIT grant applies to that separate component. Review terms before copying code.
Its runtime claims were not reproduced here.

## Reusing our skeleton work

Our [transfer tools](../tools/skeleton_transfer/README.md) already provide:

- Input hashes, native rig identity, bone/parent/rest comparisons and explicit
  one-to-one mappings with measured axis bridges (`plan.py`).
- Rest-relative rotation transfer retaining target rest translation and scale,
  with invalid scale/shear/reflection rejected (`rotation.py`).
- AN4 timing, flags and unrequested-channel comparison, including subframe
  sampling (`animation_audit.py`).
- Separate item/action declaration checks (`item_routes.py`).

Keep these as validation infrastructure. Figure Forge's common-name mapping
can propose humanoid matches, followed by our parent/axis/identity checks.
Its world-space retargeting is not interchangeable with our local rotation API;
root motion, missing parents, scale and auxiliary chains need a measured solver.

The [private Dimensions weapon experiment](SKELETON_TRANSFER.md) contributes
bind-space fitting, palette/LOD rebuilding experience and known attachment
failure cases. The stable original-animation baseline is useful. The failed
animation conversion changed byte order, compression and channels; those
regressions must not become the general encoder. Character-specific offsets,
fixed hashes and incomplete grip/body-action behavior remain experiment scope.

## Recommended integration sequence

1. Repair and validate the LSW2 branch's export blockers, then integrate it as
   its own importer/exporter. Include a new bone and a replaced part in the
   original-file, Blender and in-game test matrix.
2. Adapt classic configured layer selection and the bounded NU20 writer for
   TCS/LB1. First demonstrate a donor hair replacement on an existing head
   joint, writing a separate loose model with correct textures and native layers.
3. Add structural CD/HSER/load-list rebuilding and a gated modern mesh writer
   for one supported profile. Preserve faces, attachments and LOD ownership;
   do not silently flatten them into an atlas/body layer.
4. Implement format-specific added-joint writers using our transfer plan and
   identity checks. Validate the corresponding palette, bounds, animation and
   resource changes together. The LSW2 writer is a reference for this process,
   not a universal byte layout.
5. Reuse TCS custom-character packaging research separately from its runtime
   patch. Keep names, icons and registrations in the same explicit export job.

These findings refine the [character export roadmap](CHARACTER_EDITING.md).
No PR was merged, closed or commented on in the initial research pass.

## Subsequent integration

The continued implementation adds the LSW2 component as experimental 0.2.1,
with the export blockers above repaired and additional source, rig, numeric,
donor-material and unsupported-edit guards. Its new synthetic Blender tests
cover added bones/parts as well as unchanged output and edited attributes.
Original LSW2 retesting and in-game export are still pending; see its
[validation notes](../formats/hgp/lsw2/README.md).

The classic backend now uses explicit sibling TXT `layers_high` for initial
TCS visibility, retaining every native collection. Four local models were
checked in Blender, with eight assembly renders; the local tree has mods.
The [shared definition reader](DEFINITION_COMPATIBILITY_2026-10-20.md) now
decodes bounded inline classes and schema-confirmed Half/Colour4 primitives.
Across 1,504 local definitions, 176 gain 1,400 fields without changing prior
decoded values. These shared improvements cover several observed generations;
they do not turn every game into a fully supported importer/exporter.

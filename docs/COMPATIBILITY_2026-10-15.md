# Compatibility and export checks, 2026-10-15

Character **0.5.18**, Cutscene **0.1.27** and original LSW1 HGP **0.1.4** add
viewport file drops. The shared character readers also recover additional
verified accessories and material layouts. This is incremental compatibility
work; it does not certify every character or complete cutscenes.

## Import workflow

Drop files into the 3D Viewport in Object Mode and review the options dialog.
Character CD/GHG/GSC and CU3/CU2 drops accept a single file. HGP and AN4 drops
support multiple files; select an imported native character before dropping AN4.
Existing File > Import and sidebar workflows remain available. All existing
game/layout gates still apply. HGP remains original LSW1 PC only.

Blender 5.2.2 package checks cover registration of all three addons together,
drop-handler polls, routing to options dialogs, dependencies, versions and clean
unregistration. These checks do not synthesize an operating-system file drag.
An original Qui-Gon HGP imported through the packaged operator with 34 bones,
13 meshes, five packed textures, three normal-map nodes and seven alpha links.

## Shared reader fixes

- The command-line roster audit now uses the same model decoder, skeleton
  ownership, LOD selection and draw validation as the Blender importer. It
  recursively checks attachments and retains asset-index failures in reports.
  It is still a structural preflight, not a texture or visual fidelity test.
- Explicit DISP 18 and 26 nearest-detail layouts restore sampled LMSH1 and
  Hobbit accessories. DISP 32 four-level LOD tables accept verified repeated
  trailing zero thresholds while retaining all clip, command and bounds checks.
- LB3 definitions whose rig-family model is absent can use their own exact
  same-directory, same-stem GHG/GSC companion when there is no explicit model
  override. This restores the sampled generic male face. Ambiguous alternatives
  still fail; unrelated matching basenames are not guessed.
- Short material names such as `MAT` are accepted inside the existing checked
  material table. This restores the sampled Batman cowl variants.
- UMTL 172 and 228 have explicit prefix/footer layouts. Unknown older Boolean
  controls and shader behavior remain marked unresolved. Authored vertex colors
  provide a labelled preview fallback for supported older untextured materials;
  this is not recovery of missing atlas textures or native metallic shading.
- Non-finite vertex diagnostics identify the part, vertex, attribute, encoding
  and byte offset. Invalid data is not silently replaced with zeroes.

The [archive report](ARCHIVE_COMPATIBILITY_2026-10-15.md) records the separate
TFA, DCSV, LMSH2 and Ninjago index improvements. Later CD versions, ANI-E pose
evaluation and ZIPX payloads remain gated. No new complete character profile
is enabled by reading an archive index.

## Native export

The source writer remains a layout-preserving editor. Supported native payloads
can retain edited vertex positions, UVs, colors, normals, existing palette
weights and compatible existing face targets. Arbitrary topology, material-node
graphs, added/deleted parts, new skeletons and new character-definition/resource
identities are not encoded by this path.

New imports retain an assembly inventory. Export rejects missing/detached
attachments and changed draw membership before publishing an unchanged source
bundle. Older scenes without that inventory receive an explicit reimport
notice. Whole-model duplicate instances remain subject to identical-edit
agreement. Leave Edit Mode before exporting so edits are not read from stale
mesh data. Windows staging supports long native dependency paths without
weakening output ownership or containment checks.

All six supported edit classes were changed, written and decoded/reimported
for Black Panther, Batman, Dwalin and Captain America AOU: **24 passing original
edit checks**. See [export validation](../formats/character/EXPORT_VALIDATION.md)
for the exact scope, rejection checks and preview behavior.

## Recursive roster preflight

The same audit was run before and after the reader changes on the installed
PC games, using the default costume and highest-detail selection:

| Game | Definitions checked | Before | After |
| --- | ---: | ---: | ---: |
| LMSH1 | 467 | 367 | 402 |
| LB3 | 361 | 265 | 292 |
| The Hobbit | 417 | 297 | 353 |
| Avengers | 882 | 735 | 791 |

That is **174 additional definitions passing structural preflight**, with no
previously passing definition regressing in the final comparison. These counts
include alternate, inherited, NPC and potentially unused definitions. They are
not unique playable-character counts or complete visual support. Missing
resources, ambiguous names, unsupported skeleton variants and non-finite
attributes remain explicit failures. Older audit totals elsewhere used narrower
checks and are not directly comparable.

## Visual and original-file checks

Seven original character imports and unchanged loose-file export/reimports
passed in Blender: LMSH1 MODOK, Storm and Black Panther; LB3 Batman and B66
Riddler; Hobbit Dwalin; Avengers Captain America AOU. Render inspection confirms
recovered hair/cowls, but also exposes remaining defects. In particular, MODOK's
chair placement and older shared-texture shading remain unresolved in this
pass. Native capes can extend horizontally in an unanimated bind-pose preview;
that image alone does not establish their animated behavior.

Four further Avengers cases imported, rendered and passed unchanged loose-file
export/reimport: GorillaGirl, Batroc, Raina and Swordsman. Inspected renders show
the recovered faces and hair/headpieces. MODOK's authored skin/gold/hair colors
improve with the labelled vertex-color fallback; his chair is still unresolved.
Its authored child seat locator is a research lead, but the conditions that
enable seat alignment are not established. No guessed placement was added.

Two original CU3 actor/camera assembly regressions passed: LB3
`2BATCAVEFIGHT_INTRO_NXG` recovered 26 model instances, 160 mesh objects and 22
cameras; LMSH1 `STARKTOWER_INTRO_NXG` recovered seven model instances, 55 meshes
and 13 cameras. Start/middle/end object transforms were finite and new viewing
scenes were saved. These checks intentionally disabled static environments;
they do not establish complete scenery, lighting or cutscene fidelity.

The three updated standalone GUI archives passed extracted CLI dependency/help
checks. Interactive Tk behavior was not changed or exercised. Repository tests,
documentation links and build integrity checks are separate from original-file
and visual checks.

Private inputs, manifests, renders and Blender scenes stay under ignored
`local/validation/`. No installed game or mod was changed. No new in-game
export validation was performed. Remaining format/visual failures are retained
as failures rather than being counted as complete support.

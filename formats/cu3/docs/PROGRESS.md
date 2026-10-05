# Progress — 0.1.9 experimental

Updated October 5, 2026. This records the current implementation and checks;
it isn't a promise that every cutscene or game is supported.

## 0.1.9: shared accessory readers and tool review

The cutscene download now includes the shared verified static MESH 161 / DISP
16 / UMTL 163 / TXTS 0 readers and corrected UMTL 174 texture alignment.
Skinned or morph-bearing MESH 161 and unknown layouts remain rejected. These
readers restored Magneto's helmet and other attachments in character checks;
that is not a full cutscene fidelity test. Older Boolean shader meanings remain
unknown and rendering is approximate.

Blender 5.2.2 synthetic checks cover native normals, static-stage bindings,
composed facial holdouts, shader albedo/opacity helpers and live mask/camera
playback. The stage fixture now supplies the source file required by the
native hash baseline, in a user-selected output folder. The [tool review](../../../docs/TOOL_REVIEW_2026-10-05.md)
separates these checks from actual scene reconstruction and in-game validation.
No new game test or ANI-E/full-scene support is claimed.

## 0.1.8: game-folder imports and recovered static stages

The Blender importer now defaults to **Assemble available scene assets**.
Previously its default reference mode created actor markers without models,
which made a normal import look broken even when scene assembly was available.
The default profile detects the verified LMSH1 CU3 version 18 and LB3 version
19. Other versions require an explicit supported inspection mode.

For those two games, select the installed game folder or an extracted asset
tree once. Separate addon preferences remember the folders. The installed-game
provider reads the observed -5/-6 DAT indices and extracts only requested
registry, CD, model and texture companions to an external cache. Its original
Python LZ2K decoder removes the previous dependency on a separate extraction executable
for these assets. Cache hashes, atomic writes, path checks and bounded decoding
protect against damaged inputs/cache files; installed archives stay read-only.
See [archive loading](ARCHIVE_ASSETS.md).

The LB3 Batcave hub dialogue and LMSH1 Stark Tower intro resolved their actor
dependency closures with no missing resources or costume textures. Forty-nine
cache files matched the existing reference bytes exactly, totaling 14.4 MB.
The archive/provider checks include 23 synthetic tests, independent of game
assets. These are extraction and discovery results; successful dependency
resolution alone does not establish correct Blender rendering.

Character Layer Special records now select the proper alternative within a
visible layer. This prevents ordinary, robot and skeleton limbs from drawing
together, and selects regular versus bat capes from the shared source model.
All 52 available resolvable LB3/LMSH1 definitions passed this selection audit;
10 portable layer tests pass. Attachment tint colors now reach the material
nodes. Full layered shaders and exact source lighting remain incomplete.

The shared configuration reader now follows the selected cutscene's exact
primary and shared level declarations. **Recovered static environment
(experimental)** is enabled by default and builds supported static GSC draws
with native matrices and material indices. Named-special draws are excluded,
so the importer does not blindly draw every prop in the command pool. Source
render controls are retained in the report; their visibility and pass semantics
remain approximate. Nested LED scenes, their props and source lighting are not
reconstructed. The stage preview uses explicitly labeled inspection lighting.

Six portable `test_stage_geometry.py` tests check command bounds, native
material ownership and static/special separation. The synthetic Blender check
`check_stage_blender.py` passed native positions/matrices, UVs, topology,
vertex colors and material bindings; it also verified named-special exclusion,
unchanged input data and malformed-input rejection before scene mutation.
These are decoder and builder checks, not packaged full-scene or in-game
fidelity validation.

The packaged 0.1.8 operator was also exercised with its normal defaults and
installed-game folders. The saved scenes were reopened with the installed
addon and their packed images checked:

| Example | Character/attachment models | Static stage draws | Source cameras | Packed images |
| --- | ---: | ---: | ---: | ---: |
| LB3 `1SEWERS_MIDTRO1B` | 18 | 127 | 4 | 33 |
| LMSH1 `STARKTOWER_INTRO` | 7 | 399 | 13 | 52 |

Both assemble all recovered actor nodes. Eight material warnings remain in
the sewer example and six in Stark Tower. Rendered samples show the recovered
architecture in place around the source actors; lighting, visibility, props
and game-frame matching remain incomplete. The Green Lantern hub example
imports its actors/cameras but rejects an unverified stage rendering-control
value. This is reported rather than widening the format gate by assumption.

Additional default-operator checks imported level-15 midtro 1D and outro E.
The midtro still has shared tentacle texture warnings; outro E still has six
unassembled child nodes and two glass material warnings. A completed import
operation is not a claim that those cutscenes are complete. The current manual
repository check passes 121 portable tests; Blender checks remain separate.

Simple declared character replacements now select root resources through the
shared dependency resolver. In the Stark Tower intro, `TonyStarkPants` maps to
`TonyStark`, selecting the intended outfit and hair on the same native body
rig. Exact resource IDs are required; duplicate sources and chains/cycles are
rejected. Actor labels, animation records and rig checks remain intact. Other
registry commands are reported without being applied. See
[configuration and stage notes](SCENE_CONFIGURATION.md).

New scenes open in a prepared camera viewport: Space plays, and NumPad 0
restores camera view. Source facial masks remain evaluated during live playback.
The small post-skinning depth bias is a preview approximation; faces still
need visual work. No native Basis, topology or rest transforms are changed by
these preview modifiers.

A camera audit compared 58 initial animated matrices with independently
stored CU3 camera matrices across six LB3/LMSH1 cuts. Their maximum element
difference was 0.001568. Shot times and the inspected Flash visibility change
agree without adding an extra frame. Missing actors explained some previously
empty or misleading shots. These findings support the decoded transforms;
they do not prove frame-for-frame game composition, and no guessed camera
re-aiming was added.

TFA CU3 versions 22–27 now support structural/reference inspection. All 426
extracted files passed the reader and Blender reference operator. Two private
ANI-D examples verify source-rig motion only, with no meshes/materials/source
cameras. TFA ANI-E playback and full scene assembly remain unavailable. Camera
footer decoding is explicitly limited to the verified older versions 16–19.
See [TFA research](TFA_RESEARCH.md).

Automatic assembly still omits nested environments, rigid props, source lights,
audio and effects, and static stage visibility remains approximate. Every
assembled scene reports missing/unsupported systems and remains marked
incomplete. The following sections retain the earlier
validation history; their sample counts are not a claim of current whole-game
coverage.

## 0.1.7 and earlier validation history

## Native asset assembly and visual investigation

New original readers recover MESH 169/175 geometry, DISP 18/21/23/32 display
bindings, CD 25/28/29 character definitions and observed UMTL material fields.
They do not require OBJ files, extractor logs or a bundled external extractor.
Native stream attributes and triangles matched 31 local reference assets;
display bindings matched those same 31 assets. Twenty-seven character
definitions decoded. These are data comparisons, not visual fidelity checks.

The 0.1.7 opt-in assembly mode created supported source rigs, meshes, selected
definition layers, attachments, facial targets and source cameras from an
extracted asset folder. An LB3 sewer test constructs 18 actor/attachment models
and four cameras, with no remaining actor-node references in that test. Its
environment, rigid props, audio, source lighting and effects remain absent.
Materials report unresolved shared slots and shader features. The scene is
always explicitly marked incomplete. Broader assembly results are recorded below.

TXTS 1/12 inventories retain empty shared slots and VTF indices, so omitted
images do not shift later texture references. UMTL version-specific prefixes
fix the older hardcoded texture-table offset for Croc's version-199 materials.
The local V8 inspection copies replace selected provisional Croc/environment
materials with native texture and vertex-color bindings. Croc's 26 recovered
targets are available at zero weight; his facial timing is still unresolved.

The LB3 rigid-prop investigation found duplicate rotation/scale composition.
All seven first-sample orientations and scales match their stored anchors.
A gated helper replaces those components and applies anchored translation
deltas; it rejects tracks outside that observed convention. Local V8 copies
use it for seven props. This requires an in-game motion comparison before
being generalized. Cape definitions also disable a top mesh that the earlier
manual scene selection incorrectly included; four instances were corrected.

The new images still show major framing, surface, cape-deformation and scene
completeness issues. Missing floor/geometry and exact character appearance are
not declared fixed. V8 remains a work-in-progress copy, not a fidelity milestone.
Thirty-two portable tests pass, including texture inventories, attachment
controls, morph scalar values, empty display locators and dependency graphs.
The 0.1.7 source-only addon package is available in the builds folder. Full
scene fidelity remains incomplete; earlier builds remain available too.

## Broader assembly samples

Six additional files were exercised through the same asset-root assembly path
on October 4. Five produced saved actor scenes and midpoint images; the sixth
contains no actor nodes. This is a selected coverage sample, not an exhaustive
or statistically random test. Counts below include child animation nodes such
as faces and hair, not just whole characters. A constructed node does not mean
that its appearance or placement is correct.

| Game / file | Constructed actor nodes | Result |
| --- | ---: | --- |
| LB3 `0GAME_INTROA_NXG` | 3 / 7 | Three root actors, five model instances and eleven cameras; face/hair tracks still rejected |
| LB3 `2BATCAVEFIGHT_INTRO_NXG` | 9 / 22 | Partial actors; missing character and prop dependencies |
| LB3 `15FORTRESS_MIDTRO1D_NXG` | 4 / 11 | Partial Flash actors; helmet display layout rejected and tentacle dependencies missing |
| LB3 `16GAME_OUTROE_NXG` | 9 / 25 | Partial Batman actors; other costume dependencies missing |
| LMSH1 `GAME_INTRO_C_NXG` | 0 / 0 | Camera/control segment, no actor geometry in this CU3 |
| LMSH1 `GRANDCENTRAL_INTRO_B_NXG` | 6 / 104 | Small subset of actors; most dependencies unavailable in this test root |

Actual images show missing character parts, incorrect face composition and
framing problems. All six tests omit environment geometry, original lighting,
audio and effects. None is a complete or visually faithful cutscene preview.
Missing extracted dependencies and unsupported decoding are reported separately;
these counts must not be presented as coverage for a complete game installation.

The opening sequence exposed an eight-channel actor-control layout. The
observed flags/type pattern is now supported; other eight-channel patterns are
rejected. Visibility was boolean across both 1,017-frame source tracks. The
additional integer channel is retained without assigning it an unverified
meaning. Synthetic tests cover visibility, extra fields and unknown patterns.
Sinestro's version-195 material table also passed the bounded record/count and
footer checks and is enabled. Its face still fails separate animation-layout
validation; enabling the material reader does not fix that face.

`scripts/check_assembly_corpus_blender.py` runs this manual audit on user-supplied
files with optional saved scenes and midpoint renders. It records missing
dependencies, unassembled nodes and render errors rather than treating an
operator completion as full support. Choose a new output folder for each run:

```text
blender -b --factory-startup --python-exit-code 1 --python scripts/check_assembly_corpus_blender.py -- example.CU3 --assets extracted-assets --game LB3 --output audit-output --save-scenes --render-midpoint
```

## Shared fixes after the first broader sample

The opening test now constructs **6 / 7** actor nodes and eight model instances,
up from 3 / 7, after adding bounded attachment controls, the second observed
BSA compression flag variant and UMTL 198. The remaining Sinestro face has a
non-boolean single-channel control and is explicitly rejected. Flash's helmet
now imports in the level-15 sample: DISP 32 retains its empty VFX locator records
instead of rejecting the model. That test still has 4 / 11 actor nodes; the
static helmet is an additional model, not an additional animated actor node.

Control checks across 196 source files sampled 1,409,679 frames from 1,393
successful one/two-channel tracks; one additional track was rejected as
non-boolean. Sixty-four BSA `0xAC` tracks produced 124,232 finite scalar samples.
The opening's two such morph tracks were sampled across all 1,017 frames;
other BSA tracks used five timeline positions. These are decoding checks, not
in-game expression matching. New midpoint images still show serious framing
and completeness problems. No full-scene fidelity claim follows from the
increased import counts.

The new **Check companion files** mode and portable `check_dependencies.py`
share resource resolution with scene assembly. Reports follow CD model
overrides, active attachment layers and declared costume textures, deduplicate
repeated instances and distinguish missing files from ambiguous/unsupported
resources. A missing CD can redirect a character to a shared model, so the
report no longer incorrectly implies that every character must have its own
same-named GHG/GSC. The level-15 preflight finds three resources and identifies
one missing shared tentacle resource requested by seven actor instances.
At that release, archive extraction, environment dependencies and effects
were outside this preflight's scope. Version 0.1.8 adds installed-game actor
companion extraction and experimental declared static stages; complete
environments and effects remain separate work.

The packaged 0.1.7 ZIP was loaded directly in Blender 5.2.2. Both companion
checking and actual scene assembly completed for the opening and level-15
samples, with matching dependency reports. Saved scenes and midpoint renders
were produced from the packaged code. Every packaged Python module matches
the source bytes; archive integrity and the no-game-assets checks pass.

## Live playback

Added a copy-based EEVEE camera preview and sidebar viewing controls. Native
depth-only helpers remain evaluated dependencies for post-skinning Geometry
Nodes raycasts, so facial clipping follows recovered morphs and camera cuts
without requiring F12. Stored source geometry and native target coordinates
remain unchanged. Mask edges are approximate; the original composed scenes
and fixed movie caches remain available. See [live playback](LIVE_PLAYBACK.md).

The [workflow audit](../../../docs/WORKFLOW.md) separates portable readers and
writers from scene reconstruction. Version 0.1.8 now assembles supported actors
from installed-game companions; complete scene reconstruction remains a goal.

The V7 live LB3 sequence samples the existing edit's source frames onto one
252-frame timeline. All 6,497 curves passed sample-value comparisons; visible
rig/camera matrices matched the source at seven checked times. The Marvel
live stages retain their 385/1,350-frame source timelines. Reopened scenes
retain the composed movie, packed sound and independent face drivers. The
four live face editors preserve every native mask part in their export
collections and passed byte-identical GHG no-op checks.

Added native-flag-controlled vertex albedo/opacity helpers. The local live
stages correct texture-backed albedo modulation and cloud/light-ray vertex
fades. Synthetic Cycles/EEVEE checks cover actual baked colors and opacity,
including preservation of texture alpha and disabled flags. Material/lighting
fidelity remains incomplete; those changes do not update the fixed V6 movie.

Actual GUI viewport captures were checked through Blender's OpenGL preview
path, without calling the final renderer. This verifies viewing, not real-time
FPS on every scene. The copy operator also preserves excluded collections so
hidden variants are not revived, and rolls back failed setups.

At release 0.1.6, thirteen portable CU3 tests passed. Separate Blender checks covered live-copy
setup, mask motion, camera cuts, rollback, baked material colors and alpha.
The 0.1.6 ZIP contained the then-current 16 source modules, with
no game assets or private paths. The build manifest records its size and hash.

## Level 15 and game outro imports

Reproduced the LB3 `15FORTRESS_MIDTRO1D` and `16GAME_OUTROE` failure with the
actual Blender operator: body pose decoding passed, but the outer ANI-D track
failed with `key stride mismatch: 0 != 12`. Added the observed `0xac` control
layout with six absent transform channels and three/four discrete channels.
The indexed integer fields are retained instead of being treated as scale.
Boolean channel 6 drives visibility; auxiliary control semantics remain unknown.

All 68 observed tracks passed bounded sampling across 77,924 frames. Sixty-four
have boolean control values; four have non-boolean control values and remain
rejected for visibility rather than guessed. Disabling source visibility allows
separate inspection of a compatible pose. Unknown descriptor patterns fail.

The original-file Blender retest imported a compatible source actor in 17 of
22 level-15/outro/credits samples. The other five contain no actor records or
require a different skeleton. A separate reference-mode check inspected all
258 selected LB3 files. These are reference/rig checks, not automatic
full model/material/camera assembly or in-game verification.

The base `15FORTRESS_INTRO` and `16GAME_OUTRO` files contain no actor records;
their named A/B/etc. files contain the animated segments. The addon now reports
this explicitly and shows source-versus-record joint counts when a rig doesn't
match. It also rejects non-pose channel layouts before applying skeletal motion.

## Facial shapes and native editing

Recovered original face vertex-offset targets and observed BSA ANI-D control
curves. Corrected a separate legacy extractor issue: shared vertex streams need
their own byte offsets, and DX11 byte colors need BGRA conversion. The private
Blender scenes preserve numeric target IDs and use the source weight tracks.
The V5 scenes now use separate facial render layers for native zero-colour
depth masks. These remove the exposed mouth rectangles and stray interior
geometry in the inspected close-ups. Shader and shot fidelity remain incomplete.

Fixed a Blender 5.2 default that created every new shape key at weight 1.
Static companions now explicitly start at zero, with unmixed Basis coordinates.
Animated companions still receive their recovered BSA control values.

Audited shared streams across 31 local models/environments and repaired
Killer Croc's head positions and palette. Restored source packed normals in
verified rest-space transforms and corrected the static Sandman face companions.
Rebuilt the face galleries with native head rest geometry and facial bones.

Added a bounded native material-footer reader. All 484 materials across
27 local assets in the supported 174–202 family passed its checks. The reader
identifies zero-colour facial and body proxies directly from their flags.
Packed normal textures now have a preview reconstruction helper. These are
approximate Blender materials, not a complete TT shader implementation.

The nine portable face/material tests pass, along with a Blender regression
covering zero default weights, evaluated target motion, addon registration,
depth layers and unchanged source coordinates. Sampled V5 renders and saved
scene checks passed in Blender 5.2.2. See [facial rendering](FACIAL_RENDERING.md).

Added a hash-locked native target writer and an export button for verified
Blender editing collections. All 11 local face assets passed byte-identical
no-op writing and edited-target re-extraction. The four-character Blender lab
passed no-op checks; Batman and Hulk vertex edits passed native re-extraction.
The actual export operator matched the verified copy and protected an existing
output. These files have not been tested in-game. See
[the editing guide](FACE_GHG_EDITING.md) for supported edits and limits.

## Animation and scene fixes

- Fixed type-8 indexed integer constants and alignment of external float pools.
- Added source actor movement separately from skeletal animation.
- Added optional source visibility, including parent visibility and separate
  shot instances. Six/nine-channel motion tracks aren't treated as boolean tracks.
- Fixed cumulative parent-scale compensation that caused inflated body parts.
- Retained source skeleton checks, rest-relative pose conversion and normalized
  quaternion interpolation for supported Euler rotations.

Manual research validation covered 515 older-game cutscene files, with 6,049
accepted scene tracks and 147 files containing unsupported layouts/envelopes.
Those categories overlap: a file can contain supported and unsupported tracks.
The actual Blender operator was checked on source rigs with placement and
visibility enabled. Across 2,045 source frames in the local LB3/LMSH1 example
scenes, visible geometry had no non-finite positions. These checks don't prove
all materials, facial poses, lighting or effects match the games.

## Character replacement

The GUI and CLI can plan replacement of every root instance of a character
family. Explicit actor/object/record editing remains available. Numeric actor
references and inner record labels are shown independently; editing one root
doesn't automatically rewrite every shared inner label.

Name-growth checks passed on 446 actor-bearing older-game CU3 files, with GUI
copy saves and CLI overwrite protection checked. Old names remain in the
retained original tree, so their presence in a hex editor doesn't establish
that a rename failed.

A private Batman-to-Green-Lantern test is installed for the LB3 opening title
sequence. All ten Batman root instances are renamed, numerical animation data
is retained, and the archive patch was checked against a full backup. The
earlier Batcave test has been restored. **The user confirmed on October 3 that
the title-menu cutscene fully replaced Batman with Green Lantern in-game.**
This validates that specific larger-name CU3 and archive installation, not
every character, object or later-game format.
Game files, local installer paths and backups aren't distributed here.

## DC Super-Villains

- Added a read-only .CC40TAD v2/-12 archive index reader.
- Added partial CU3 v30 / AN4 v20 structural reading.
- Handled the optional pre-blob reference array and static animation records.
- Parsed 297 of 324 CU3 files. Longer-name checks passed in all 216 parsed
  actor-bearing files; 27 files remain rejected.
- ANI-E sampling and DCSV camera/object footer decoding are disabled until
  their semantics are verified. Full DCSV Blender scenes aren't supported yet.

## Still being worked on

Supported companion meshes/materials and cameras now assemble through the
public addon. Remaining model layouts, face composition, full shader behavior,
stage visibility, nested environments, props, source lighting, audio and
effects prevent a complete reconstruction. Some private scenes include
additional hand-prepared systems;
those assets and generated scenes are not published.

Custom animation export is still research work. Decoding tracks and growing
names don't establish a safe Blender-to-CU3 writer. Gameplay hit windows,
audio cues and other events require separate handling too.

No scheduled checks or CI are configured. The included checks are manual and
use files supplied from the user's own installation.

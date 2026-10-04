# Progress — local 0.1.7 development (unreleased)

Updated October 4, 2026. This records the current implementation and checks;
it isn't a promise that every cutscene or game is supported.

## Native asset assembly and visual investigation

New original readers recover MESH 169/175 geometry, DISP 18/21/23/32 display
bindings, CD 25/28/29 character definitions and observed UMTL material fields.
They do not require OBJ files, extractor logs or a bundled external extractor.
Native stream attributes and triangles matched 31 local reference assets;
display bindings matched those same 31 assets. Twenty-seven character
definitions decoded. These are data comparisons, not visual fidelity checks.

The opt-in assembly mode creates supported source rigs, meshes, selected
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
Eighteen portable tests pass, including five texture-inventory regression tests.
No 0.1.7 package has been published; the 0.1.6 ZIP remains the prior build.

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

## Live playback

Added a copy-based EEVEE camera preview and sidebar viewing controls. Native
depth-only helpers remain evaluated dependencies for post-skinning Geometry
Nodes raycasts, so facial clipping follows recovered morphs and camera cuts
without requiring F12. Stored source geometry and native target coordinates
remain unchanged. Mask edges are approximate; the original composed scenes
and fixed movie caches remain available. See [live playback](LIVE_PLAYBACK.md).

The [workflow audit](../../../docs/WORKFLOW.md) separates portable readers and
writers from the log/companion-dependent mesh reconstruction work. Automatic
asset-root character/cutscene assembly remains an extraction milestone.

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

Thirteen portable CU3 tests pass. Separate Blender checks cover live-copy
setup, mask motion, camera cuts, rollback, baked material colors and alpha.
The 0.1.6 ZIP contains the same 16 source modules as the addon directory, with
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

Automatic companion meshes/materials, faces, cameras, audio, environments and
effects remain outside the public addon's complete reconstruction workflow.
Local research scenes include some of those systems and cached playback, but
game assets and generated scenes aren't published.

Custom animation export is still research work. Decoding tracks and growing
names don't establish a safe Blender-to-CU3 writer. Gameplay hit windows,
audio cues and other events require separate handling too.

No scheduled checks or CI are configured. The included checks are manual and
use files supplied from the user's own installation.

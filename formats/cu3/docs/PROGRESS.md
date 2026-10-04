# Progress — local 0.1.5 (unreleased)

Updated October 4, 2026. This records the current implementation and checks;
it isn't a promise that every cutscene or game is supported.

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

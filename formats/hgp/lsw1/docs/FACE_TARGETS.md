# LSW1 PC facial shape targets

Version 0.1.7 imports the observed native position targets as Blender shape
keys. Basis is unchanged and every target starts at zero. IDs are shown as
`morph N`; names such as blink or smile have not been established.

## What was checked

The original-file reader passed 157 HGP files across 575 stored layers. Of those,
63 files contained 164 morph blocks, with 1,183 populated targets and 460 empty
target slots. All observed blocks used skinned vertex layout `0x5D`.

Blender 5.2.2 imported all 63 files with every native layer included for the test.
All 1,643 target slots were checked against source bytes, including per-primitive
vertex remapping, unchanged Basis, zero initial values and empty slots. One
populated target on each of the 164 facial mesh parts was checked through
Blender's evaluated armature. Cleanup left no orphaned shape-key data.

Basis and one populated target were also rendered and visually inspected for
Yoda, Qui-Gon Jinn and Young Anakin with identical cameras and lighting per pair
(Cycles, 32 samples, Standard view transform). The mouth poses visibly changed.
These were manual native-target poses, not game clip playback or a comparison
against the original game's rendering.

These checks establish import and evaluated displacement. They do not establish
BSA playback, game export, normal deformation fidelity or matching game shaders.

## Observed storage

Offsets below are relative to the body after the 0x30-byte file header. They
describe the tested original PC files, not LSW2, TCS or another platform.

Geometry word `+0x3C` points to a 20-byte record, or is zero when absent:

| Word | Observed contents |
| --- | --- |
| 0 | Number of target slots |
| 1 | Pointer to that many 32-bit target-data pointers |
| 2 | Pointer to that many 32-bit target IDs |
| 3 | Start of position-delta data |
| 4 | Unknown; retained as inspection metadata |

Each nonzero target pointer addresses XYZ float32 deltas for **every vertex in
the geometry's source buffer**. A zero pointer is an empty target. The target
arrays are contiguous, followed by the pointer table, the ID table and the record.
The observed IDs run from zero to count minus one. The reader rejects other
arrangements until original-file evidence supports them; allocation and finite
value checks also apply.

Primitives can use only a subset of that buffer. Import maps deltas through the
same original vertex indices as positions and weights, then applies the same
coordinate conversion. Taking the first N deltas for a primitive would move the
wrong vertices. Geometry `+0x38` is a different field and is not used as the morph
pointer. The record's last word is not assumed to identify a vertex buffer.

## Reproduce

Asset-free malformed-layout and primitive-remapping checks:

```text
python formats/hgp/lsw1/tests/check_morph_targets.py
```

Original-file and evaluated Blender checks, with your extracted HGP folder and
a new output directory:

```text
blender --background --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_morphs_blender.py -- extracted-folder new-output
```

The next step is proving which BSA channels drive which model and target, then
checking interpolation and visible results. Matching counts or IDs alone does
not establish that relationship. Native facial export remains unimplemented.

## Inspect decoded game facial channels

The BSA research tools can now sample an explicit list of HGP layer indices:

```text
python formats/hgp/lsw1/tools/animation_cli.py sample-layers path/to/Idle.bsa --family BSA --layers 0 1 -1 --time 30
```

Time is a one-based native frame, not seconds. The JSON contains the decoded
components for each selected layer. A negative layer is skipped (`null`), while
a layer absent from the clip has an empty component list (`[]`). These values
are not automatically assigned to similarly numbered Blender shape keys.

The native two-clip routine at `0x03AF9075` selects BSA tracks using signed layer
indices. It blends corresponding components, treating missing tracks or
components as zero; it does not clamp the resulting channel values to 0–1.
The new `face_channels.sample_layers` follows this behavior. Its public blend
input is limited to 0–1, and invalid times, layer indices and non-BSA inputs are
refused. This does not establish the game's clip-selection or timing policy.

The optional original-code checker executes native layer selection, scalar
evaluation and blending. Allocations and the frame-time context are supplied by
the harness. It checks actual decoded BSA files, including different component
counts, missing clips, skipped layers and absent layers:

Idle/combo pairs from Qui-Gon, Count Dooku and Yoda passed 108 cases with zero
float32 difference. These include constant, float-curve and quantized channels.

```text
python formats/hgp/lsw1/tools/check_native_face_channels.py path/to/LEGOSTAR.EXE path/to/Idle.bsa path/to/other.bsa path/to/new-report.json
python formats/hgp/lsw1/tests/check_face_channels.py
```

This is decoded game data, not a hand-keyed animation example. Final mapping
from these layer components to rendered morph targets remains unverified, so
native facial clip playback and export are still unavailable in the addon.

## Original target accumulation experiment

The renderer routine at `0x0052C340` reads the geometry's morph ID table. For
each populated target it fetches that ID from the layer's decoded component
array (after its eight-byte runtime header) and accumulates weighted XYZ deltas.
Zero weights are skipped. It does not recompute normals or rename expressions.

The new original-code checker executes `0x0052C397..0x0052C4C4`, supplying an
output buffer instead of locking a GPU buffer. An explicit pairing of original
Qui-Gon HGP and `combo1_2b.bsa` passed ten part/frame cases with zero float32
difference. This covers both visible facial parts and five sampled clip times.
Inputs with missing target channels or more than 2,000 part vertices are refused
by this experiment. It does not infer padding beyond the clip's component count.

```text
python formats/hgp/lsw1/tools/check_native_face_deltas.py path/to/LEGOSTAR.EXE path/to/model.hgp path/to/clip.bsa path/to/new-report.json
```

This establishes the target-ID lookup and accumulation for the explicit research
pairing. Automatic clip ownership, gameplay timing, native ordered depth passes
and general addon facial playback remain unfinished.

A fixed-body Blender 5.2.2 LTS research scene was baked from all 18 original
`combo1_2b.bsa` frame samples for this pairing. Frames 1, 5, 9, 13 and 18 were
rendered and inspected; the brows and mouth visibly change. The shader lab keeps
the authored normals. Reopening the saved scene verifies all 576 target/frame
values against the decoder. The example uses a declared preview playback rate,
not recovered gameplay timing, and is not a native game render comparison.

# LSW1 PC animation records

The source-tree tools can inspect and sample original PC **ANI** and **BSA**
curves, and change one existing channel without rebuilding the file.
This is research support. Explicitly bound ANI clips can now be baked into a
Blender action with the source-tree preview tools below. Automatic skeleton/face
binding, new clips and in-game export validation remain unfinished. The installed
addon still imports models without a game-animation browser.

## Inspect a file

From the repository folder, using Python 3.10 or newer:

```text
python formats/hgp/lsw1/tools/animation_cli.py inspect path/to/Idle.ani --family ANI
python formats/hgp/lsw1/tools/animation_cli.py inspect path/to/Idle.bsa --family BSA --details
```

The report includes the source hash, track/component counts, curve storage
types, extra keys, shared curves and disagreements between stored key times
and lookup masks. `--details` includes the raw time records and decoded values.
Track numbers are stored indices, **not verified bone or facial-shape names**.

## Sample a curve

```text
python formats/hgp/lsw1/tools/animation_cli.py sample path/to/Idle.bsa --family BSA --track 0 --component 0 --time 12.5
```

Time is a **one-based native frame number**, not seconds. The result is a
scalar channel value. It does not move a Blender bone or facial shape.
The lookup masks select the key pair; stored key times and tangents determine
the cubic interpolation. This distinction matters for the original files whose
stored times disagree with their masks.

## Change one existing channel

Use the hash printed by inspection. Track and component numbers start at zero.

```text
python formats/hgp/lsw1/tools/animation_cli.py transform path/to/Idle.ani --family ANI --track 0 --component 0 --scale 0.5 --source-sha256 HASH_FROM_INSPECTION --output path/to/Idle-edited.ani
```

The operation applies `value * scale + offset`; `--offset` defaults to zero.
Tangent values scale too. Compressed offsets are rounded to the existing value
step and refused if they exceed its range. Scaling changes the compressed
channel's two scale factors without expanding or dropping its keys.

Outputs must be new files. Source-hash mismatches, non-finite values, unknown
curve types, overlapping tables and edits to shared curves are refused.
No game installation is changed. This tool does not add tracks, keys, frames,
bones or character references, and it does not assemble a new animation bank.

## Observed layout

Offsets below are file-relative and little-endian. Serialized pointers are
converted by subtracting the word at `0x04`. They are not ordinary file offsets.

| Field | ANI | BSA |
| --- | --- | --- |
| Observed record tag | `0x00`: 2 | `0x00`: 2 |
| Serialized address base | `0x04` | `0x04` |
| Root pointer | `0x08`, maps to `0x0C` | `0x08`, maps to `0x10` |
| Additional header word | absent | `0x0C`: zero in the samples |
| Duration, float32 | `0x0C` | `0x10` |
| Track/component counts, uint16 pair | `0x10`; 9 components | `0x14`; varying components |
| Lookup block count, uint32 | `0x14` | `0x18` |
| Value/type/track-flag pointers | `0x18`, `0x1C`, `0x20` | `0x1C`, `0x20`, `0x24` |
| Value table starts | `0x24` | `0x30` |

Observed block counts equal `ceil((duration - 1) / 32)`. Each channel is either
a constant float32 (type 0), a float-key curve (type 1), or a compressed curve
(type 2). Each animated curve begins with three pointers: frame masks,
uint16 cumulative key counts, and key payload. One uint32 mask covers 32 frames;
the cumulative counts must agree with all preceding masks.

Type 1 has 16-byte records: stored time, reciprocal interval, value and tangent.
Type 2 has two float scales followed by 4-byte records: signed int16 value,
signed int8 tangent, and an unsigned time byte. Scale factors decode values
and tangents separately. A time byte alone is insufficient to recover long clips.

The reader retains raw times and mask frames separately. Sampling reproduces
the observed native scalar evaluator: mask lookup selects a pair, while stored
times determine its interval. Type 1 also uses the stored reciprocal interval;
type 2 uses the raw byte-time difference, including zero or negative differences.
It does not unwrap the bytes or sort anomalous keys. Query times below 1 clamp
to 1; times at or beyond duration clamp to duration minus 0.01. Stored keys,
track flags and padding/trailing bytes remain unchanged.

## Evidence and remaining work

On 22 October 2026, record checks accepted **870 of 871 ANI** and **617 of 617
BSA** original files. `Chars/QuiGonJinn/old/combo1_3a.ani` was rejected for a
non-finite value at `0x708`. No data was silently repaired.

The accepted files contain **2,895 keys beyond the mask-indexed key count** and
**26 curves with stored-time/mask disagreements**. Those records survive edits.
An unchanged operation was byte-identical for every accepted file. **2,446
edited round trips** exercised one channel of every storage type present per
file: decoded values/tangents changed as requested, lengths stayed identical,
and every byte outside the chosen value/tangent fields stayed unchanged.

Synthetic tests cover both headers, extra keys, malformed pointers/counts,
overlapping regions, invalid prefixes, non-finite values, source hashes, shared
curves, offset overflow and output overwrite protection:

```text
python formats/hgp/lsw1/tests/check_animation_records.py
python formats/hgp/lsw1/tests/check_audit_files.py
python formats/hgp/lsw1/tests/check_curve_evaluation.py
```

### Comparison with the original scalar evaluator

An isolated x86 comparison ran **340,724 samples from 1,487 original files**:
96,056 float-key samples and 244,668 compressed-key samples. There were no
differences above the stated tolerance; the largest absolute difference was
0.00000190735. Samples cover early/late key boundaries and fractional frame
times, including the observed anomalous time records. This is sampled numerical
agreement, not proof of exact equality at every possible time.

The comparison executes the original scalar routine at `0x004FA090`, with a
synthesized time context and in-memory pointer relocation. It does not start
the game or exercise the full animation caller. The executable must have SHA-256
`49f74d802596b72b8da24b76f98f249dfdb370d5607fa7e65e3a19beb833d473`;
other executable versions are refused. The time-context builder was inspected,
but has not passed isolated execution. Constant channels are tested directly.

Optional research dependencies: `pefile` and `unicorn` (tested with 2024.8.26 and
2.1.4). With those installed in your research Python environment:

```text
python formats/hgp/lsw1/tools/check_native_curves.py path/to/LEGOSTAR.EXE path/to/extracted-animations path/to/new-comparison.json
```

These checks establish record preservation and scalar evaluation, not in-game
success. Some ANI files have different track counts from sibling HGPs; even
equal counts do not establish ownership.

## Try a reviewed ANI playback example

The research renderer can create a Blender scene with a baked body animation.
Open its `importer-preview.blend` and press Space to play. This scene uses the
existing importer materials. The accompanying `shader-experiment.blend` is a
**frozen pose**: its shader inputs are sampled at one frame, so it deliberately
has no animation action. Facial targets stay at zero in both scenes.

```text
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tools/render_shader_comparison.py -- path/to/model.hgp path/to/new-preview --color-space display --animation path/to/Walk.ani --binding path/to/reviewed-binding.json --frame 8
```

The binding JSON must contain:

| Field | Meaning |
| --- | --- |
| `profile` | `lsw1-pc-ani-preview-v1` |
| `model_sha256` | SHA-256 of the reviewed HGP |
| `animation_sha256` | SHA-256 of the reviewed ANI |
| `track_bones` | Explicit native bone names in track order, each exactly once |
| `fps` | Chosen playback rate, from 1 to 240 |
| `evidence` | Why these files belong together and what is still assumed |

Do not manufacture a binding from equal bone counts. The native evaluator uses
array order, but that only describes indexing after the game has selected a
compatible clip. A binding records a reviewed pairing; its hashes prevent using
that review with different files. This is not automatic ownership detection.
Current local examples pair Clone/Walk, Qui-Gon Jinn/Walk and Yoda/Idle from their
original folders. Additional examples cover Gonk/Walk, Clone Walker/Walk and
R2-D2/Idle. Clone's TXT explicitly sets Walk to 34 fps and Clone Walker's sets it
to 24 fps; the other examples use a declared 30 fps preview assumption. Gameplay
selection remains unverified.

### Transform evidence and validation

The original PC local-track routine at `0x03B67505` establishes these steps:

- Sample translation, rotation and scale from the nine ANI components.
- Use identity rotation when flag 1 is absent and unit scale when flag 8 is absent.
- Combine rotation with the HGP joint-orientation matrix when flag `0x20` is set.
- Apply local scale to matrix rows. For flag `0x10`, cancel accumulated parent
  scale by dividing matrix columns; translation is not divided. A zero or
  near-zero parent scale is refused.
- Apply the joint pivot where present, then convert the Z handedness.

Rotation uses integer turns and a sine lookup table. The reference reconstructs
that lookup addressing; the table itself is synthesized. Isolated comparisons
used the original routine with sampled values supplied as constant channels,
without gameplay overrides. **500 synthetic cases and 430 original track/time
samples** across the three examples matched within `2.1e-7`. The synthetic cases
cover joint orientation, nonuniform scale and pivots. This is separate from the
earlier native scalar-curve comparison.

The parent-scale extension adds **1,000 synthetic cases** with positive/negative,
nonuniform parent scales and compares both the matrix and the returned scale.
Another **375 original track/time samples** cover Clone, Gonk, Clone Walker and
R2-D2. Maximum difference was below `2.4e-7`; the repeated synthetic suite in
each report is counted only once here.

Blender playback is baked at integer native frames. Native rest matrices and
source mesh coordinates remain unchanged. The saved/reopened actions are checked
against the sampled world matrices. Subframe interpolation is linear and only
approximates the original curves. Bones with parent-scale compensation use
Blender's `NONE` scale-inheritance mode, so Blender does not reintroduce the scale
and shear canceled by the native calculation. Native rest matrices and hierarchy
are preserved. Unrepresentable poses still fail the matrix comparison.

Saved/reopened playback checks on Blender 5.2.2 LTS cover Clone (25 frames), Gonk
(29), Clone Walker (29) and R2-D2 (119). All bone world matrices match the samples
within `3.6e-7`. Clone Walker stands upright in its walking clip; its source bind
pose remains unchanged. Gameplay overrides, clip blending, root-motion policy,
automatic timing/layers and facial animation are not implemented; unsupported
flags are refused.

```text
python formats/hgp/lsw1/tests/check_animation_pose.py
python formats/hgp/lsw1/tools/check_native_pose.py path/to/LEGOSTAR.EXE path/to/model.hgp path/to/Walk.ani path/to/new-report.json
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_animation_preview_blender.py -- path/to/model.hgp path/to/Walk.ani path/to/reviewed-binding.json path/to/new-validation-folder
```

The native check requires the same optional `pefile`/`unicorn` dependencies and
executable hash as the scalar check. It never starts or modifies the game.

### Binding leads still being verified

In the same executable, `0x004C05F0` enumerates selected HGP layer indices into
short integers. The caller at `0x004C1AEC` passes that list to `0x004D5C50`, whose
body at `0x03AF9075` indexes BSA tracks by those layer indices and evaluates each
component. This explains why BSA track counts can differ from facial target
counts. The final correspondence between components and rendered morph targets
and clip ownership still need end-to-end checks before
automatic Blender binding is enabled.

The layer-selection and two-clip blend step now has an original-code comparison
across Idle/combo BSA pairs for Qui-Gon, Count Dooku and Yoda: 108 cases, zero
float32 difference. The pairs cover constant, float-curve and quantized-curve
channels, different component counts, absent tracks and missing clips. Missing
components contribute zero. Allocation and frame-time context are supplied by
the harness; the original selection, scalar and blend instructions execute.
See [decoded facial channels](FACE_TARGETS.md#inspect-decoded-game-facial-channels)
for the inspection command and the remaining target-binding boundary.

This implementation was derived from local original-file observations with AI
assistance. It does not use a later AN3/AN4 parser or an external implementation.

# Facial targets: research progress

The shape key tip helped. We have recovered additive vertex offsets from the
original face models, plus separate cutscene curves that control them. The
current Blender previews still need work on facial masking and game shaders.

## What is confirmed locally

- Observed LMSH1 `MESH 0xA9` and LB3 `MESH 0xAF` face parts contain target
  tables. Each entry is two big-endian u32 values: `1`, then the target ID.
- Target data can be dense big-endian vec3 offsets, or run records containing
  a big-endian repeat count followed by a vec3 offset. Runs cover the exact
  draw-part vertex count. Zero terminal runs are supported with validation.
- The relative-position data is big-endian even when the DX11 base positions
  are little-endian. Do not decode both buffers with the same endianness.
- An observed AN4 actor field at `node + 36` points to a `BSA` wrapper. Its
  payload contains an ANI-D animation with one node and 53 scalar curves.
  Source target IDs 0–52 select those curves directly. These are separate
  from the normal face skeleton record and its eye/hair bones.
- The legacy DX11 extractor discards per-vertex-stream byte offsets. Shared
  buffers consequently produce incorrect positions, colors and weights for
  several facial draw parts. Each stream needs its own byte offset, followed
  by the draw base multiplied by that stream's stride.
- DX11 `color4char` is BGRA; converting it directly to RGBA swaps red and blue.

The private validation recovered 3,817 part targets across 145 parts in 11 face
assets. This includes LODs and repeated targets: it does not mean 3,817 distinct
expressions. Sampling checks accepted 1,126 LB3 face actors and 1,339 LMSH1
face actors in the local extracted corpus. Other layouts are rejected.

## Source tools

`Addon/io_scene_lego_cu3/morph.py` contains the target decoder, the observed CU3
BSA weight reader and Blender shape-key helpers. `native_mesh.py` now supplies
validated target offsets directly from supported GHGs. The current Face Target
Decoder 0.1.2 therefore needs no extraction log; `--log` remains an optional
cross-check for older verified layouts. The scene builder must preserve native
vertex order, Basis and target IDs.

To export a target companion without importing Blender:

```text
python formats/cu3/scripts/decode_face_targets.py FACE_MODEL.GHG --output FACE_MODEL.morph.json
```

This utility exports target data, not a complete Blender scene. Supported face
meshes can be loaded through CU3 scene assembly or the separate character
importer. A constrained native target writer and Blender editing-collection
exporter are also available; see
[face GHG editing](FACE_GHG_EDITING.md). Their output is checked by decoding,
but edited face GHGs have not been tested in-game yet.

Character addon 0.4.2 adds standalone **big-endian** AN4 BSA playback through
`an4.py`, separate from the **little-endian** CU3 reader. The observed blocks
contain 53-channel ANI-D weights indexed by `TT_Target_###`. Unique matching
face actors and compatible durations are required. This update is included in
the character package. CU3 0.1.9 includes the shared readers but its cutscene
operator uses the separate CU3 animation path; it does not offer standalone
character clip linking. Face GUI 0.1.2 retains its earlier target coverage.
See [character playback](../../character/README.md).

## What is still unresolved

The observed facial helpers use `colourWriteMask=0`, and their depth behaviour
now has an approximate two-pass Blender preview. Static target defaults have
also been fixed. Exact polygon bias, shader conventions and expression names
remain unresolved. A valid target/curve transfer alone does not produce an
accurate game face. See [facial rendering](FACIAL_RENDERING.md).

DCSV uses ANI-E in the sampled BSA wrappers. Its facial weights remain disabled
until that layout is verified. No DCSV face animation compatibility is claimed.

Cutscene actor replacement remains a separate, previously tested feature.
Custom animation export additionally needs a writer for the face curves,
broader mesh target editing, skeleton compatibility checks and in-game testing.

Related format notes: [JaanDev's MESH documentation](https://github.com/JaanDev/lego-tt-nxg-formats/blob/main/MESH.md)
and [GHG/GSC documentation](https://github.com/JaanDev/lego-tt-nxg-formats/blob/main/GHG%2C%20GSC.md).
The specific BSA pointer and target-buffer encodings above were checked against
the local game assets; the linked notes do not establish all of those details.

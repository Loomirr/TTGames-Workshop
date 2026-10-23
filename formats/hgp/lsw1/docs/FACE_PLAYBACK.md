# Preview an original LSW1 facial clip

The source-tree shader renderer can bake a decoded **PC BSA clip** onto fresh
HGP facial targets. It requires an explicitly reviewed pairing; it does not
choose gameplay animations automatically or export Blender keyframes to BSA.

Create a JSON binding with the actual source SHA-256 fingerprints:

```json
{
  "profile": "lsw1-pc-bsa-preview-v1",
  "model_sha256": "SHA256_OF_MODEL",
  "animation_sha256": "SHA256_OF_BSA",
  "layers": [0],
  "fps": 30,
  "evidence": "Describe why this model and clip belong together, and any uncertainty."
}
```

`layers` lists native HGP layers containing the imported facial meshes. Every
target ID needs an explicit BSA channel; missing channels are refused, not
silently padded or matched by mesh order. FPS is a chosen preview rate.

From the repository folder, run:

```text
blender --background --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tools/render_shader_comparison.py -- Character.hgp new-preview-folder --color-space display --legacy-plastic --face-animation clip.bsa --face-binding binding.json
```

Open `new-preview-folder/shader-experiment.blend` and play the timeline. The
folder also contains the importer scene, a report and three facial renders.
Integer native frames start at 1 and end before the clip duration. Interpolation
between those frames is linear and approximate.

## Confirmed example

Qui-Gon Jinn's original `combo1_2b.bsa` produced 17 frames on two facial meshes.
Reopening the saved Blender 5.2.2 LTS scene checked all **544 shape-key values**
against decoded BSA samples. Evaluated mesh positions matched the weighted
targets with zero measured error; authored shader normals stayed unchanged.
Inspected renders show changing brows and mouth shapes. Earlier native-code
checks established the ID lookup and delta accumulation; see
[face target evidence](FACE_TARGETS.md).

Repeat the saved-scene check with:

```text
blender --background --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_decoded_face_blender.py -- new-preview-folder/shader-experiment.blend clip.bsa new-check-report.json
```

The shader workflow requires a fixed body and ordinary facial materials.
Animated bump/reflection inputs, combined body/face playback, native facial
depth ordering and gameplay clip selection/rate remain unfinished. The installed
addon still imports static facial targets; this is a source-tree research tool.

The local Dooku and Yoda clip samples do not supply channels for every nonempty
facial target. They remain refused by this workflow pending evidence for the
missing-channel behavior; their scalar BSA decoding alone does not establish a
complete playable face binding.

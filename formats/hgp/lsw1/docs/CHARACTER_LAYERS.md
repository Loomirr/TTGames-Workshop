# Choose the parts listed by a character definition

LSW1 characters can store several bodies, hair pieces, accessories and damaged
variants in one HGP. Version **0.1.8** can read the layer lists in the character's
TXT instead of choosing parts from their names.

## Use it in Blender

1. Keep the original character TXT beside its same-named HGP.
2. Drag the TXT into Blender, or choose **File > Import > LEGO Star Wars 1
   Character (.hgp / .txt)**.
3. Under **Detail Layer**, choose **Definition: Special**, **High**, **Medium**,
   **Low** or **Dead**. A TXT opened with Automatic uses Special.
4. Import. Only the layers in that list are included.

For example, `Anakin_Boy.txt` and `Anakin_Boy.hgp` belong together. A differently
named file in another folder is not used as a replacement. If the TXT is absent,
open the HGP with **Maximum Detail (Automatic)** as before.

The labels are the original declaration names. **High does not always mean the
most detailed stored mesh**, and Special is not a universal normal gameplay pose.
Young Anakin's Special set includes goggles; his automatic model selection uses
hair. Sebulba's pod High set adds its declared extra pieces. Anakin's pod
High set includes the driver layer. Some Special sets include damaged parts.

This reads the top-level `layers_special`, `layers_high`, `layers_medium`,
`layers_low` and `layers_dead` lists. It does not yet reproduce animation-specific
overrides, gameplay switching, attachments from other files or character scripts.
An exact list can be empty of geometry even when it contains valid layer indices.

## Checks and remaining issues

Original-file checks imported **506 valid sets across 103 models** in Blender
5.2.2 LTS. Imported geometry, primitive identity, triangle order and initially
zero facial target weights were checked against the selected native layers.
Invalid selections were refused before scene data was created.

Six Cycles renders were inspected: automatic and definition selections for
Young Anakin, Anakin's pod and Sebulba's pod. The helmet/goggles and pod driver
appear in their declared sets. Those initial renders also exposed an opaque
backing behind pod energy beams, corrected separately by the
[0.1.9 additive-material fix](SHADERS.md). Full shader fidelity remains open.

Fourteen original sets were refused: the two Anakin pod Low declarations contain
`1,4.6,7`, and Kaadu, STAP, MTT and Royal Naboo Starship contain references beyond
their matching model's layer count. Valid sets in those same TXT files remain
selectable. The importer reports the bad declaration instead of silently fixing
the original text or inventing missing geometry.

Reproduce with your extracted character tree and a new output directory:

```text
python formats/hgp/lsw1/tests/check_definitions.py
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_definitions_blender.py -- path/to/Chars path/to/new-report
```

This work used AI assistance and original PC files. Successful layer selection
does not establish complete gameplay assembly or matching native shaders.

# Changelog

## 0.2.1 — Workshop integration

- Normal and raw vertex-color edits survive the unchanged-part check; split corner normals are retained.
- Imported source hashes and rig snapshots guard against wrong-source writes and silently ignored native bone edits.
- Donor and copied materials/images cannot reuse unrelated native slots.
- New bone names, parents, binds and edited geometry are validated before writing.
- Writes require a separate output; original-bone edits, multi-material faces and unbaked morph modifiers are refused.
- Drag-and-drop exposes import options in Object mode. Full readable source and upstream MIT license retained.
- Integration uses synthetic and Blender round trips. Original LSW2 files and in-game validation are unavailable here.

## 0.2.0

- New bones, rigid parts on any bone, new materials and textures (DXT5), painted textures.
- Facial morphs fully decoded: imported as shape keys and written back from them, following vertex edits.
- Animation import with ownership proof (declared by the character file, or matching skeleton proportions;
  clips that drive only the first bones when the extras are trailing roots).
- Texture colour now multiplies the material colour and texture alpha is transparency (faces were washed out).
- Asset-free synthetic tests; damaged input is refused instead of raising Python errors.

## 0.1.0

- First version: LSW2 PC `.hgp` import (bones, parts per detail layer, materials, embedded textures,
  attachment points) and export onto the original file. Checked on all 257 LSW2 models of the Steam PC
  release; not yet validated in game.

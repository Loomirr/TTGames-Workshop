# Changelog

## 0.1.10

- Correct the preview hand/wrist overlap in the six verified Clone-family rigs.
  Use reversible pose translations; preserve native source and rest data. The
  complete skeleton fingerprint excludes Sand Trooper, other rigs and edits.
- Rename the existing option to **Correct Known Preview Poses**. Turn it off for
  source bind inspection or before loading a complete animation.
- Add source-preservation, mesh-only parity and changed-rig rejection checks.

## 0.1.9

- Fix the opaque backing behind ordinary additive pod effects using the
  original PC blend-state branch as evidence. Preserve texture and vertex alpha.
- Use Eevee's Blended path so zero-coverage additive color remains visible.
- Keep auxiliary bump/reflection passes separate from the ordinary effect fix.
- Add numerical Cycles/Eevee render checks and executable-based shader inventory
  and blend-state research tools. Full shader lighting/fidelity remains open.

## 0.1.8

- Open a character TXT and its same-named HGP together. Choose the exact
  Special, High, Medium, Low or Dead layer list from that definition.
- Keep nested animation overrides separate. Refuse invalid declarations and
  missing layers without adding guessed replacement parts.
- Check 506 original definition sets in Blender; report 14 invalid original
  sets separately. Direct HGP imports retain their existing automatic selection.
- Add source-tree ANI/BSA scalar sampling with original lookup masks and cubic
  interpolation. Compare 340,724 samples against the isolated native evaluator.
  This does not yet enable body or facial clip playback in Blender.

## 0.1.7

- Import observed native PC facial position targets as zeroed Blender shape keys.
- Preserve empty target slots, native IDs and per-primitive vertex mapping.
- Validate morph ranges, layout, resource limits and finite deltas. Unrecognized
  morph layouts are refused; game facial clip playback/export remain unavailable.
- Add synthetic guard tests and original-file Blender verification.

## 0.1.6

- Select nonempty native body layers and observed complementary hair, head,
  vehicle bits, hoses and energy-binder layers. Keep broken/costume alternatives
  separate; expose explicit layer choices through index 31.
- Recover Young Anakin's hair and Bodyguard's independent head. Avoid empty
  high-detail exports and overlapping complete default/lower-detail bodies.
- Retain native layer identity on imported roots and mesh objects.
- Preserve packed vertex color bytes and use authored vertex opacity on observed
  translucent materials, multiplied with texture alpha when present. RGB tint
  semantics remain unverified and are not applied to the palette.
- Keep zero-area strip faces and all source topology, but exclude those faces
  from smooth shading so they cannot corrupt adjacent authored custom normals.
- Isolate further failed normal fans only when the failed-corner set strictly
  decreases with no new failures; restore the previous shading flags otherwise.
- Use the inverse transpose for transformed rigid normals. Native rest poses,
  bone names, hierarchy, weights and UVs stay unchanged.
- Add layer-selection, malformed-table, native-rest, skinning and shading checks.

## 0.1.5

- Default multiple-file spacing to zero and retain exact filename stems.
- Recover native joint names from the recorded offset.
- Read validated 0x28/0x36 original PC layouts, including WheelBike.
- Validate table bounds and finite bind transforms; verify native bone axes.

## 0.1.4

- Drop HGP files into the 3D Viewport in Object Mode and review import options.
- Keep multi-file import and highest-detail defaults.
- Add a packaged original-file import check and shared Blender handler checks.

## 0.1.3

- Convert native display RGB palette colors into scene-linear material inputs,
  correcting washed-out or shifted solid plastic beside the original textures.
- Explicitly retain sRGB base textures and separate Non-Color normal images.
- Preserve original and converted diffuse values as material metadata.
- Add a user-input Blender color/material-role check and color handling notes.
- Check 1,827 material records across 139 readable original PC HGP files.

## 0.1.2

- Recognize `TT1_Hi` and `TT1_MediumRes` as primary body detail layers, fixing incomplete automatic imports of Zam Wesell and Boss Nass.
- Allow optional accessory layers in the Python importer without duplicating shared geometry.
- Add a gallery builder with twelve additional characters and Young Anakin's separate hair layer.

## 0.1.1

- Decode native one-based auxiliary-material links and assign recognized normal maps automatically.
- Use Non-Color normal images while retaining separate base-colour colour-space roles.
- Preserve reflection-pass distinctions, native vertex normals and alpha-mode material connections.

## 0.1.0

- Initial original LSW1 PC character importer with native bones, weights, UVs and packed textures.

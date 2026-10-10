# Native face GHG editing — experimental

Yes, editing existing face shapes now has a working prototype for the observed
LMSH1 NXG, Hobbit NXG and LB3/Avengers DX11 assets. The writer changes native vertex-offset targets
in a **separate GHG copy** and reads them back to verify the result. Modified
face files have **not been tested in-game** yet. This is not a general GHG
mesh exporter or a complete custom-face tool.

## What can be edited

The separate **Face Target Decoder 0.1.2** reads supported MESH 169/170/175
GHGs directly. Choose the original GHG and a new target JSON filename. An
extraction log is no longer required. Older decoder downloads used a plain-text
model-extractor log with `Part`, `Number Vertices` and `Relative Position Lists`
entries; it was not the target JSON or Blender's console log. The CLI retains
`--log` as an optional cross-check for its older verified layouts.

```sh
python formats/cu3/scripts/decode_face_targets.py FACE_DX11.GHG --output face-targets.json
```

**Face Target Writer 0.1.2** and character addon 0.4.1 enable the observed MESH
170 layout alongside 169/175. MESH 170 requires a bounded full mesh and exact
native target-part membership. Decoded no-op/edit checks cover 48 cached Hobbit
faces; this is not an in-game validation or support for arbitrary MESH 170 files.

- Existing dense targets: change per-vertex additive offsets at the same count.
- Existing run-encoded targets: change offsets while preserving each original
  repeated-vertex group. All vertices covered by one run must keep the same
  offset. A strength change to an existing target is one supported example.
- Shape-key coordinates in a verified Blender editing collection. Export uses
  the original vertex order and converts the key offsets back to source space.

File size, target IDs/order, topology, skeleton, material data and unknown
companion fields stay intact. The writer checks the source SHA-256 and reparses
the target data; every changed byte must belong to an offset payload.

Do not change Basis, rename/add/remove keys, reorder vertices, subdivide, merge
parts or apply modifiers. A run that needs splitting is rejected. Growing or
repacking streams, adding targets, editing the static head/cowl, generating
updated normals and exporting CU3 facial timing remain separate work.

The existing target IDs have not been given verified semantic expression names.
`TT_Target_035`, for example, is a source ID rather than an invented label.
Shape-key values, animation playback, object placement and armature poses are
preview controls; they do not change the exported native target coordinates.

## Blender workflow

The private inspection scene has four scenes: Batman, Robin, Hulk and Sandman.
Each uses one original highest-detail FACE display variant. It is deliberately
separate from the current cutscene scenes. The revised private V6 lab includes
the approximate native depth-mask compositor and synchronized Target/Strength
controls. Press F12 for the composed result; solid viewport shading does not
reproduce that masking. The game shader is still not matched exactly.

Character addon 0.4.0 also has **Create composed face preview**, which builds
these passes in a separate scene. Use the live preview for playback and the
composed preview for closer face inspection. A manual asset-free rendering
check verifies hidden masks and preserves source coordinates:

```sh
blender --background --factory-startup --python-exit-code 1 --python formats/cu3/scripts/test_face_preview_blender.py -- output/face-render-check
```

1. Build/install the source addon ZIP and open a **copy** of the editing lab.
2. Choose a character using Blender's Scene dropdown.
3. Select a mesh in that character's **editable native face** collection.
4. In **Object Data Properties → Shape Keys**, select a `TT_Target_###` key.
   In the older lab, set its value to 1 for inspection. In V6, select the face
   armature and use **Object Properties → Custom Properties → Target/Strength**
   to drive matching parts together. Edit the selected key's vertices in Edit Mode.
5. Save your edited blend copy. In the 3D View, open **N → TT Cutscene** and
   choose **Export edited face GHG copy**. Choose a new filename.

The export creates a GHG, an edited target companion and a patch manifest.
Existing files and input files are protected. Keep exports outside the installed
game until a separate in-game test is prepared. No game installation happens
through the addon.

Edits are per mesh part and target. Other LODs, display variants and parts not
represented in the editing collection remain unchanged. Matching changes to
lower-detail variants are not generated automatically.

The helper binding is established immediately after verified source geometry
and shape keys are imported. An arbitrary mesh with matching key names cannot
be exported. CU3 scene assembly can import supported native face meshes and
source bindings. It does not automatically create the separate editing
collection expected by this face-export operator. Use the verified collection
workflow above, or the character addon's constrained loose-source exporter.

## Standalone target workflow

The source GHG must be uncompressed and use a supported native mesh layout.
The current decoder reads it directly. No proprietary game assets or extractor
logs are distributed here. Legacy logs are optional CLI cross-checks.

```text
python scripts/decode_face_targets.py FACE_MODEL.GHG --output original.morph.json
```

Duplicate the companion and edit only the `offsets` arrays. Keep its original
source hash, counts, IDs, addresses, encoding labels and companion fields.

```text
python scripts/write_face_targets.py FACE_MODEL.GHG --edited edited.morph.json --output FACE_MODEL_EDITED.GHG
```

For a bound Blender collection, a background export is also available:

```text
blender --background EditedFace.blend --python scripts/export_face_targets_blender.py -- --ghg FACE_MODEL.GHG --morph original.morph.json --collection "Batman editable native face" --output FACE_MODEL_EDITED.GHG
```

Run manual, asset-free writer checks with:

```text
python scripts/test_face_edit.py
python scripts/test_face_targets.py
```

## Validation and limits

For a small target inventory without editable vertex payloads, the standalone
decoder also accepts `--summary`. It preserves native IDs and source-space
displacement statistics, without expression labels or timing. That diagnostic
schema is deliberately rejected by the writer. See
[commands and scope](../../../docs/DIAGNOSTIC_TOOLS.md#face-target-summaries).

Local checks covered 11 face assets and 3,817 part-target records, including LOD
duplicates. All 11 no-op exports were byte-for-byte identical. A strength edit
in each asset passed a fresh full target extraction using the original log.

The saved Blender lab passed no-op checks for all four character collections.
The V6 lab also passed four byte-identical native no-op exports after reloading,
and its composed previews were rendered for each character.
Batman and Hulk vertex edits passed the native writer and fresh extraction.
Changes to Basis and key names were rejected. The actual Blender export operator
produced the same verified native output and rejected an existing output name.
Blender testing used 5.2.2 LTS; other versions still need checking.

These are decoded-data and preservation checks. They do not prove game-side
deformation, lighting or facial rendering. Unknown companion fields may carry
additional requirements for edited shapes. Exact mouth/eye depth behaviour,
shaders and normal handling remain unresolved. Static head appearance is separate from
the animated FACE GHG layers and may require another asset edit.

DCSV facial export is not supported. CU3 facial weight writing is also not
implemented. Replacing an actor in a cutscene is a separate feature from making
new native face shapes or new facial animation.

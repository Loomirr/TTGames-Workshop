# Native face GHG editing — experimental

Yes, editing existing face shapes now has a working prototype for the observed
LMSH1 NXG and LB3 DX11 assets. The writer changes native vertex-offset targets
in a **separate GHG copy** and reads them back to verify the result. Modified
face files have **not been tested in-game** yet. This is not a general GHG
mesh exporter or a complete custom-face tool.

## What can be edited

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
separate from the current cutscene scenes. Native helper parts are available
for inspection; the displayed face still lacks the game's proper masking.

1. Build/install the source addon ZIP and open a **copy** of the editing lab.
2. Choose a character using Blender's Scene dropdown.
3. Select a mesh in that character's **editable native face** collection.
4. In **Object Data Properties → Shape Keys**, select a `TT_Target_###` key.
   Set its value to 1 for inspection; edit that key's vertices in Edit Mode.
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
be exported. The general CU3 import panel still does not automatically import
face meshes or create these bindings.

## Standalone target workflow

The source GHG must be uncompressed. The decoder still needs an extractor log
to locate the verified native part/target tables; it is not a standalone mesh
parser. No proprietary game assets or extractor logs are distributed here.

```text
python scripts/decode_face_targets.py FACE_MODEL.GHG --log FACE_MODEL.log --output original.morph.json
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

Local checks covered 11 face assets and 3,817 part-target records, including LOD
duplicates. All 11 no-op exports were byte-for-byte identical. A strength edit
in each asset passed a fresh full target extraction using the original log.

The saved Blender lab passed no-op checks for all four character collections.
Batman and Hulk vertex edits passed the native writer and fresh extraction.
Changes to Basis and key names were rejected. The actual Blender export operator
produced the same verified native output and rejected an existing output name.
Blender testing used 5.2.2 LTS; other versions still need checking.

These are decoded-data and preservation checks. They do not prove game-side
deformation, lighting or facial rendering. Unknown companion fields may carry
additional requirements for edited shapes. Mouth/eye helper masking, shaders
and normal handling remain unresolved. Static head appearance is separate from
the animated FACE GHG layers and may require another asset edit.

DCSV facial export is not supported. CU3 facial weight writing is also not
implemented. Replacing an actor in a cutscene is a separate feature from making
new native face shapes or new facial animation.

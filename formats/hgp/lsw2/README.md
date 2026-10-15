# LEGO Star Wars II HGP Blender import and export

Import and export character and vehicle models (`.hgp`) of **LEGO Star Wars II: The Original Trilogy
(2006), PC**. Blender 4.2 or newer; checked with Blender 5.2.2. Separate from the
[LSW1 importer](../lsw1/README.md): the two games use different HGP layouts, and no code is shared.

## Install

In this folder run `blender --command extension build`, or zip the folder's files. In Blender:
**Edit > Preferences > Get Extensions**, the menu at the top right, **Install from Disk**.

Extract the models from your own `lego_data/game.dat` first (an index -1 archive); they are under
`chars/` and `cut/`. No game files are included.

## Import

**File > Import > LEGO Star Wars II Model (.hgp)**, or drop `.hgp` files on the 3D Viewport.

- One armature with the native bone names, hierarchy and bind pose; attachment points (weapon hands,
  `lookAt` and so on) as empties on their bones.
- One mesh object per native part, in a collection per detail layer. Shown: `defaultLayer`, the most
  detailed level (`TT1_Special`, `TT2_HiRes`, ... by vertex count) and the other layers (hair, helmets,
  hats, capes, vehicle pieces); death variants and lower levels are hidden. Skinned parts use an Armature
  modifier; rigid parts are parented to their bone in that bone's space.
- Materials: plastic colour, opacity and the embedded DDS texture (packed), the texture laid over the
  colour by its alpha. An approximation with Principled BSDF.

The game is left-handed (Y up, facing -Z); Blender gets (x, z, y), facing -Y, with the winding reversed.

## Export

Select the armature or one of its parts: **File > Export > LEGO Star Wars II Model (.hgp)**.

The export is written **onto the original file** (its path is stored at import; the dialog can name it).
The original supplies the skeleton, materials, textures, attachment points, facial morph data and the
structures this add-on does not decode, all kept byte for byte.

- A part that still matches the original is written as the original: an unchanged model exports to an
  identical file.
- An edited part is rebuilt: triangulated, one native vertex per Blender vertex and UV (the format keeps
  one normal per vertex; split an edge for a hard edge), the three strongest weights normalised, and split
  into several parts when it uses more than eight bones (the most any original part uses).
- A duplicated or new object (keeping its `lsw2_layer` / `lsw2_slot` properties) is added as a new part;
  a deleted object's part is left out.
- Unknown or damaged layouts are refused on import and export; nothing is guessed.

## Limits

- Bones, materials and textures cannot be added. A rigid part must stay on a bone that already carries a
  rigid part in its layer.
- Facial morphs (369 parts) are not decoded into shape keys: most are stored sparsely in a layout not yet
  worked out. They are kept while a part's vertex count is unchanged, and dropped with a report otherwise.
- Animation is not imported.

## Validation

On all 257 LSW2 models of the Steam PC release (four more `.hgp` files are LSW1 leftovers and are refused):

| Check | Kind | Result |
| --- | --- | --- |
| `tests/check_roundtrip.py`: read, write unchanged | decoded round trip | byte-identical, 257 of 257 |
| same, every strip rebuilt, written, read back | decoded round trip | same triangles, vertices, weights, 257 of 257 |
| `tests/check_blender.py`: import, export unchanged | Blender round trip | byte-identical, 257 of 257 |
| same: one part moved 1 cm, exported | Blender round trip | the move arrives, every other part unchanged, 257 of 257 |
| `tests/check_blender_edits.py`: duplicate, delete, weights over every bone, extra vertex on a morph face | Blender round trip | 43 of 43 checks on 12 models |
| extension built, validated, installed from the ZIP into a separate profile, menu import/export | packaging | byte-identical (Yoda) |
| front renders of 20 models | visual, Workbench and EEVEE | look right |
| exported model loaded in the game | in-game | **not done** |

    python tests/check_roundtrip.py <folder with extracted .hgp> --edit
    blender -b --factory-startup --python tests/check_blender.py -- <out folder> <model.hgp | @list.txt>
    blender -b --factory-startup --python tests/check_blender_edits.py -- <out folder> <model.hgp> [...]

The format, as measured: [docs/FORMAT.md](docs/FORMAT.md).

## Credits and license

By **Gibby** (stryderjoe), with AI assistance (Claude). Decoded from the PC files; the LSW1 importer was
read as a description of the related LSW1 layout, and none of its code is used. MIT; see [LICENSE](LICENSE).

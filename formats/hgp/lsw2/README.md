# LEGO Star Wars II model import and export (Blender add-on)

Import and export character and vehicle models (`.hgp`) of **LEGO Star Wars II: The Original Trilogy**
(2006, PC), with their animations and facial shapes. **Experimental 0.2.1**. Blender 4.2 or newer; tested with Blender 5.2.2.
By **Gibby**, MIT licence.

Separate from the [LSW1 importer](../lsw1/README.md): the two games use different HGP layouts, and no code
is shared. Extract models from `lego_data/game.dat` (an
index -1 archive, see [LSW2 notes](../../../games/lsw2/README.md)); they are under `chars/` and `cut/`.

## Install

1. Click [Download ZIP · 0.2.1](../../../builds/blender/io_lsw2_hgp-0.2.1.zip), then the **Download button (down-arrow icon) at the top right** of GitHub's file view. Keep the ZIP zipped.
2. In Blender 4.2 or newer, drag the ZIP from your file browser into the Blender window and confirm installation.
3. Alternatively, go to **Edit > Preferences > Get Extensions**, click the **drop-down arrow at the top right**, then select **Install from Disk** and choose the ZIP.
4. Enable the addon under **Add-ons** if it is not already enabled. The import entry appears under **File > Import**.

These are Blender's [standard extension installation methods](https://docs.blender.org/manual/en/4.4/editors/preferences/extensions.html).

**Developers only:** after editing this addon's source, run `blender --command extension build`
from `formats/hgp/lsw2`, then install the generated ZIP using the same steps.

## Import

**File > Import > LEGO Star Wars II Model (.hgp)**, or drag `.hgp` files into the 3D Viewport.

You get an armature named after the file with:

- one bone per game bone, at the bind pose;
- one mesh object per game part, in a collection per detail layer (`defaultLayer`, `TT2_HiRes`, ...).
  Shown: the default layer, the most detailed level and the other layers (hair, helmets, capes,
  vehicle pieces); lower levels and death variants are hidden (**Show All Detail Layers** shows all).
  Skinned parts use an Armature modifier; rigid parts (heads, hair, helmets, vehicle panels) are parented
  to their bone;
- **facial shapes as shape keys** (`morph 0`, `morph 1`, ...: blinks, mouth shapes);
- materials with the plastic colour, opacity and embedded texture (packed into the .blend): the texture
  times the colour, its alpha as transparency;
- an empty for each attachment point (weapon hands, look-at target and so on);
- **animations as actions** (option **Import Animations**, on by default), see below.

Characters face -Y (Blender's front view) with Z up.

### Animations

Every clip the character's own `.txt` declares (looked up beside the model, then in `chars/commonanims`)
becomes an action, keyed on every frame at the clip's own rate (`fpsec` in the `.txt`, else 30, which is
recorded on the action as assumed). Other `.an3` files beside the model are added only when they prove they
belong to this skeleton: the bones a clip holds still must sit at the skeleton's bind translations.
A clip with a different bone count is never bound. **Also Unproven Clips** adds clips of the same bone count
that could not be proven, bound by bone order; their actions say so in `lsw2_proof`. **Animation Folder**
takes clips from another folder, with the same checks. The `idle` clip (if any) is assigned to the armature;
pick others in the Action Editor.

## Export

Select the armature (or one of its parts) and use **File > Export > LEGO Star Wars II Model (.hgp)**.

The exporter writes a **separate HGP file based on the original source** (whose path and SHA-256 are stored on
the armature; the export dialog can name an identical copy). Exporting over the source is refused. From the original it keeps everything this
add-on does not edit, byte for byte. The armature is put in its rest pose while exporting, so a posed or
animated armature exports the same file.

What can change:

- **Meshes.** A part you did not change is written exactly as the original, so an unchanged model exports
  to an identical file. An edited part is rebuilt: triangulated, one game vertex per Blender vertex, UV and distinct corner normal. Skinned vertices keep their three
  strongest bones, normalised; a part over eight bones (the most any original uses) is split into several.
- **New meshes.** Any mesh object parented to the armature is exported: parented to a bone, it is a rigid
  part on that bone; otherwise a skinned part. Its detail layer is the layer collection it is in. Parts
  are placed relative to their bone's rest pose: rig new parts with the armature at rest (Pose Position:
  Rest), since imported models arrive posed in their idle clip.
- **Bones.** New bones (added in Edit Mode, with a parent or as roots) are written after the original ones;
  meshes may be weighted or parented to them. Original bones keep their names and bind pose (edits to
  them in Blender are refused) and cannot be removed. New names must be unique ASCII.
- **Materials.** Colour, opacity and image of an original material can be changed; a new material (a
  Principled BSDF whose Base Color is a colour, an image, or a Mix of the two) is added, modelled on an
  original one.
- **Textures.** A painted or replaced image is re-encoded; a new image is added. Textures are written as
  DXT5 at the nearest power-of-two size, at most 512 pixels a side, like the originals. Unchanged images are
  recognised by their pixels and kept exactly.
- **Facial shapes.** Shape keys named `morph <n>` go back to their slot; other shape keys are added as new
  shapes. Shapes follow edits to their mesh, including added or removed vertices.

## Limits

- **Nothing exported by this add-on has been loaded in the game yet.** What is checked is listed below.
- Animations are imported, not exported. The game's identifiers for new facial shapes and new animations
  are not known, so new shape keys are stored but the game may not use them.
- Bone matrices of new bones are derived from Blender's rest pose; a new bone's rest orientation and the
  extra joint data are modelled on its parent's.
- Materials are approximations with Principled BSDF. Linked material passes (perhaps normal or reflection
  maps) are kept but not shown; new materials have none.

## Integration checks (0.2.1)

Workshop integration on 2026-10-20 passed 82 synthetic Python checks (including NumPy DXT5),
17 Blender 5.2.2 export regressions and five synthetic edit workflows. These cover byte-identical
unchanged output; normals, colors, hard edges; copied/donor material and image identity; new bones,
parts, materials, textures and shape vertices; and refusal before output for unsupported edits.
No LSW2 install or original LSW2 model was available on the integration workstation. The 317 local
HGP candidates belonged to other layouts and were correctly refused. No in-game result is claimed.

Run the asset-free Blender guard check into a fresh folder:

```text
blender -b --factory-startup --python-exit-code 1 --python tests/check_export_guards_blender.py -- NEW_OUTPUT_FOLDER
```

Use one material per mesh object; separate faces by material first. With shape keys, bake non-armature
modifiers consistently into Basis and all keys before export. Vertex colors use the raw POINT integer
`lsw2_colour` attribute. Animation export is not implemented. Reimport older scenes to establish source
and rig identity before exporting.

## Upstream checks (0.2.0, contributor-reported)

The original-file counts below describe the upstream revision; they have **not** been repeated
on Workshop 0.2.1. Do not treat them as validation of this modified writer.

From this folder:

    python tests/test_synthetic.py
    python tests/check_roundtrip.py <folder with extracted .hgp files> --edit --features
    blender -b --factory-startup --python tests/check_blender.py -- <out folder> <model.hgp | @list.txt>
    blender -b --factory-startup --python tests/check_blender_edits.py -- <out folder> <model.hgp> [...]
    blender -b --factory-startup --python tests/check_blender_anim.py -- <out folder> <model.hgp> [clip ... | --all]

`test_synthetic.py` needs no game files: it builds a small model and clip from the documented layout and
checks reading, writing, edits, new bones, materials, textures and shapes, and that damaged files and edits
the writer cannot represent are refused. The others need your own extracted files.

| Check | Kind | Result (Steam PC release, Blender 5.2.2) |
| --- | --- | --- |
| `test_synthetic.py` | synthetic | 27 of 27 |
| `check_roundtrip.py`: read and write unchanged | decoded round trip | byte-identical, 257 of 257 LSW2 models (four LSW1 leftovers refused) |
| same: strips rebuilt; a bone, part, material and texture added; a face grown with an edited shape | edited round trip | 257 of 257 |
| `check_blender.py`: import (posed in its idle clip), export unchanged | Blender round trip | byte-identical, 257 of 257 |
| same: one part moved 1 cm | Blender round trip | arrives, others unchanged, 257 of 257 |
| `check_blender_edits.py`: duplicate, delete, bone split, edited face and shape key, new bone + mesh + material + image, recolour, paint | Blender round trip | 67 of 67 checks on 12 models |
| `check_blender_anim.py --all`: every Blender bone at four frames against the transform computed from the file | Blender animation | 738 clips on 22 models, within 2e-6 |
| renders of 20 models, Luke in four clips, faces at rest and posed | visual | look right |
| exported model or imported animation compared in the game | in-game | **not done** |

The format, as measured: [docs/FORMAT.md](docs/FORMAT.md).

## Credits and license

By **Gibby** (stryderjoe), with AI assistance (Claude). Decoded from the PC files; the LSW1 importer was
read as a description of the related LSW1 layout, and none of its code is used. MIT; see [LICENSE](LICENSE).

Workshop integration starts from [upstream PR #10](https://github.com/Loomirr/TTGames-Workshop/pull/10),
revision `dc55e8084338b63573914520ad8804c561d28f62`, with the additional guards and checks
listed above. Integration also used AI assistance. Original attribution and license are retained.

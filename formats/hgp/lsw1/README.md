# LEGO Star Wars 1 HGP Blender Importer

Import characters from **LEGO Star Wars: The Video Game (2005), original PC release** into Blender 4.2 or newer.

## Install

Download [lsw1_hgp_importer-0.1.5.zip](../../../builds/blender/lsw1_hgp_importer-0.1.5.zip), or build it using the command below. In Blender, open **Edit > Preferences > Get Extensions**, open the menu in the upper right, and choose **Install from Disk**. Select the ZIP and enable the extension.

Drag one or more extracted `.hgp` files into the **3D Viewport in Object Mode**,
review the import options and confirm. **File > Import > LEGO Star Wars 1 Character
(.hgp)** still works. Version **0.1.4** adds the file-drop handler; decoding and
material behavior are unchanged.

## Features

- Native skeleton hierarchy, bind transforms, vertex weights and rigid attachment bones.
- Original UVs and custom vertex normals.
- Solid plastic colors converted from the native RGB palette to Blender's linear color inputs, matching the texture color-space convention.
- Embedded base-colour textures, alpha transparency and linked normal maps, packed into the Blender file.
- Normal maps use Non-Color data and a tangent-space Normal Map node. Other auxiliary passes, including reflection textures, are not mistaken for normal maps.
- Automatic body detail selection, including `TT1_HighRes`, `TT1_Hi` and `TT1_MediumRes` naming variants.
- Mesh-only import, scale, placement and detail-layer options.
- Failed imports roll back their own data; successful files in a batch are retained.

Keep **Embedded Textures** enabled for face alpha and normal-map materials. **Original Normals** controls vertex normals independently. Re-import existing models to rebuild their materials with these fixes; preserve edited scenes in a separate copy first.

**0.1.3 fixes pale/wrong solid colors beside the textures.** Re-import with the
new version; existing materials in a saved scene are not changed automatically.
See [the color notes](docs/COLOURS.md) for the findings and checks. Material
Preview or Rendered mode displays textures; Solid mode cannot reproduce them.

Materials approximate the original game effects with Principled BSDF. Animation, facial morph playback, gameplay visibility and every shader effect are not reconstructed. Some characters have separate accessory layers. Additional variants can be selected using the Python importer's `variant_layers` argument.

## Import multiple models

Select multiple extracted HGP files in the import dialog. Each successful
import is kept if another selected file has an unsupported header. This
default spacing is zero; increase Multiple Character Spacing to arrange models
along X. Filename spelling and leading underscores are preserved.

## Validation

The normal-map update was installed from its ZIP and checked on 13 original PC characters. A further 12-character gallery was reopened and checked for packed textures, face alpha links, normal-map connections, custom vertex normals, native bind poses, normalized weights and finite head poses. Material links were audited across 139 readable local HGP files. That earlier sample excluded ten headers now enabled in 0.1.5; this is not universal support for every game asset.

The 0.1.3 color update checked all 1,827 material records in those 139 readable
files against Blender's own sRGB conversion, packed image roles, alpha links and
normal-map links. A private comparison was rendered under identical lighting.

The reader was derived from original LSW1 PC data. It does not use an LSW2 or Complete Saga model reader. Input must be an extracted original LSW1 PC character HGP. Observed vehicle HGPs are supported as static rigged models. Disc unpacking, level assembly and game animation extraction remain outside this add-on's scope.

## Build the extension ZIP

From the repository directory:

```text
blender --factory-startup --command extension build
```

The installable ZIP contains the add-on code, manifest, documentation and license. It contains no game meshes, textures or extracted assets.

## Credits and license

Made with assistance from **6.1sol**. Maintained by Loomirr and contributors.

GPL-3.0-or-later; see [LICENSE](LICENSE).

## 0.1.5 feedback fixes

The first bone-name offset is read from the header instead of assuming 0x30.
This preserves names previously truncated in some files. The observed 0x28 and
0x36 offsets now pass explicit table and transform checks, including WheelBike.
All 149 local originals decoded across their nonempty layers. WheelBike was
imported and rendered in Blender; the local file contains a Droid Starfighter
model, despite its filename. This does not verify a different WheelBike asset.

Bone sticks show the native local axes, not a line aimed at the next child.
Watto's opposing wing directions match the source bind matrices. No cosmetic
axis flips were applied. Blender checks cover exact names, zero batch spacing,
hierarchy and rest transforms on both Yoda files, Watto and Dooku's speeder.

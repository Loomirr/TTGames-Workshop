# Character editing and native export

The intended workflow is to import a character, edit its mesh and rig, replace
parts, and export a new loose native model with those changes preserved. The
current tools cover parts of that workflow, not arbitrary character rebuilding.
AI assistance was used in this work.

| Game/profile | Blender import | Current native export |
| --- | --- | --- |
| LSW1 original 2005 PC | HGP meshes, native rigs, textures and inspection assemblies | No HGP writer |
| TCS / LB1 PC | Classic GHG/GSC raw draws and native rigs; TCS rigid binding and explicit TXT high-layer visibility | No native writer; AN3 playback and full configured character assembly remain incomplete |
| LSW2 PC | Separate experimental HGP addon: rigs, meshes, materials, textures, morphs, AN3 | Separate HGP writer supports new bones/parts and edits; synthetic/Blender checks only in integration, original-file retesting and in-game export pending; no animation export |
| LEGO Batman 2 PC | Experimental character/vehicle import and supported animation | Export remains unverified for this older layout |
| LMSH1, LB3, The Hobbit, Avengers PC | Supported character assemblies and gated animation layouts | Constrained edits to existing geometry buffers and face targets; supported normals/weights and separate ANI-D animation writing |
| Other NXG/DX11 games | Format-specific inspection/research tools; coverage differs by game | No general character exporter; sharing an extension does not establish layout compatibility |

See the [current game table](../README.md#game-and-file-support),
[Character export instructions](../formats/character/README.md#export-loose-native-files)
and [export validation](../formats/character/EXPORT_VALIDATION.md) for exact gates.

## What existing exporters preserve

Supported exports are bound to the original source revision and topology. They
can preserve representable edits to existing vertices, normals, weights within
an existing palette, and existing face targets. Unchanged byte equality,
decoded edited round trips and in-game acceptance are separate checks.

Adding a bone changes joint tables, bind/inverse matrices, palette references
and animation bindings. Replacing a hair object can change geometry, materials,
textures, attachment ownership and multiple detail levels. The Character
exporter rejects new/removed meshes and changed rigs instead of silently losing
those edits. Copying a Blender object into a collection does not make it an
exportable native part.

## Work needed for general character rebuilding

1. Rebuild an existing rigid part slot on one verified format, including its
   vertex/index streams, bounds, material/texture dependencies and explicit LOD
   ownership. Validate a donor hair swap attached to the existing head joint.
2. Add bounded native rig and palette writers. Preserve joint identities,
   hierarchy, bind scales and markers; remap weights and verify animation
   ownership when adding bones.
3. Rebuild model definitions and companion references for a new character.
   Verify texture/material edits, part visibility and gameplay attachment names.
4. Enable each format profile only after unchanged, edited round-trip, rendered
   and in-game tests. Classic TCS containers need their own writer and physical
   offset mapping; they cannot reuse a modern DX11 serializer unchanged.

These are implementation milestones, not enabled export features. Native export
normally produces separate loose files in an extracted game tree, with originals
and unknown data preserved. It does not require repacking DAT archives.

The [Figure Forge and fork review](FIGURE_FORGE_REVIEW_2026-10-20.md) identifies
candidate classic/modern mesh writers and the LSW2 added-bone writer, alongside
our reusable skeleton validation. Its checks establish research leads, not new
export support in these addons.

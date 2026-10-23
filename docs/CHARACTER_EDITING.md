# Character editing and native export

**You can import more than you can currently export.** The Character addon can
write selected edits to existing models, but it cannot yet turn any edited
Blender character into a working game character.

Use this page before spending time on a change such as adding bones or swapping
hair. "Native export" means writing the game's own file format, such as GHG or
HGP. It does not mean exporting a GLB or saving a Blender project.

## Which workflow should I use?

| Game / tool | What can go back to the game format? |
| --- | --- |
| LMSH1, LEGO Batman 3, The Hobbit, Avengers: Character addon | Selected edits to existing vertices, UVs, colors, normals, weights and face shapes. A separate experimental exporter handles supported body AN4 clips. New meshes/bones/materials are not supported. |
| LEGO Batman 2: Character addon | Import and some animation playback are available. Native export for its older model layout is unverified. |
| The Complete Saga / LEGO Batman 1: classic inspection | No edited GHG/GSC export in Workshop. For creating characters in these PC games, use [BactaTank Classic](https://github.com/AlubJ/BactaTank-Classic) as a better starting point. It also covers PC LEGO Indiana Jones 1. |
| LEGO Star Wars 1, PC: LSW1 addon | No Blender model export. A separate [material recoloring tool](../formats/hgp/lsw1/docs/MATERIAL_EXPORT.md) writes existing RGB fields to a new HGP copy; original-file round trips checked, in-game validation pending. No added parts or bones. |
| LEGO Star Wars II, PC: separate LSW2 addon | Experimental HGP export can rebuild parts and add bones, textures and face shapes. Current integration tests are synthetic/Blender checks; original-file retesting and in-game export checks are pending. No animation export. |
| Other games | Check the [game table](../README.md#game-and-file-support). A matching file extension does not imply export support. |

LSW1 and LSW2 use separate tools. The modern Character addon's restrictions
below do not describe the separate LSW2 writer; read its
[own editing instructions](../formats/hgp/lsw2/README.md).

## Make a small model edit

For a supported modern character:

1. Import the character with the current addon. Save a copy of the Blender scene.
2. In Edit Mode, adjust a few existing vertices on the original body mesh.
   Keep the faces and vertex count unchanged, and stay inside that part's
   original size limits. Do not edit facial Basis geometry this way.
3. Select the character and click **Export model edits...**.
4. Choose a new folder outside the game and extraction cache.
5. Read `TT_Source_Export.json`. Check the exported model by importing it again.
6. Test in an extracted mod setup using backups of every replaced file.

The output preserves the original relative folders. It does not install the
mod or write back into DAT archives. Reopening an export in Blender is useful,
but the final check is whether the game loads it and plays the character correctly.

See [full export instructions](../formats/character/README.md#export-loose-native-files)
for UV, normal, weight and face-shape rules.

## Can I add a bone or swap the hair?

**Not through the modern Character exporter yet.** Copying someone else's hair
object into Blender does not create all of the game data needed to use it.
The game also needs to know its textures, materials, attachment bone and which
copies appear at different distances.

Adding a bone also changes the rig data, which bones each mesh can use, and
how animations find those bones. The current exporter rejects those changes
instead of quietly leaving them out. The separate LSW2 addon has an experimental
rebuilding path; that does not make new bones exportable in other games.

For now, keep the existing mesh objects, vertex order, faces, rig and materials
when using the modern writer. Supported weight edits can only use bones
already assigned to that part's game data. Editing a shader node or painting a
Blender image does not update a native game material or texture file.

## Can I create a new selectable character?

Exporting a model does not register a new character slot. The game may also
need a definition, roster entry, display name, icon and unlock information.
Those differ between games.

The [definition patch helper](../tools/character_clone/README.md) can make
supported string changes while preserving the original file structure. It is
a development tool, not a complete new-slot installer. For an initial export
test, replacing a backed-up existing resource avoids mixing model-export
problems with character registration problems.

## What about animations?

### File types are separate compatibility checks

The extension alone does not select a safe writer. The game, platform, internal
version, byte order and compression must also match a supported layout.

| File family | Reading / Blender use | Writing back |
| --- | --- | --- |
| CD / AS / CPD | Supported definition layouts describe characters and animation sources; some nested fields remain unread. | The definition patch helper can change supported strings; no general character-recipe writer. |
| GHG / GSC | Model and scene layouts vary by game. Modern and classic readers have separate coverage. | Selected modern model edits only; importing GSC scene data does not imply a complete scene writer. |
| HGP | Separate original LSW1 and LSW2 addons. | Experimental LSW2 model writer; no LSW1 writer. |
| AN3 | Classic scalar inspection and the separate LSW2 animation importer. | No AN3 writer. Renaming AN4 output to AN3 does not convert it. |
| AN4 | Supported body and face records can be read; playback depends on finding their correct owner and targets. | Selected big-endian ANI-D body records; edited facial/attachment tracks and other layouts are not written. |
| PAK / DAT | Containers used to locate and extract supported resources. | Active-animation export can rebuild the observed ordered PAK layout into a separate file. DAT rewriting is not supported. |

See the [game table](../README.md#game-and-file-support) for which tool handles
each game, and the [definition checks](DEFINITION_COMPATIBILITY_2026-10-21.md)
for recent version coverage. Read, edit, export and in-game validation are
separate milestones for every layout.

Use **Export animation (AN4 / PAK)...** for supported body clips. The
model-bundle export does not save your animation edits. Preserve the imported
rig and original clip length; edited facial and attachment tracks are not
currently written.

[Animation export instructions](../formats/character/README.md#export-an-edited-animation)
explain the limits and what "bake to a clean rig" means. Baking turns Blender
constraints into ordinary keyframes; it does not fix AN4 compression or make
an unsupported animation format compatible.

## What existing exporters preserve

The modern exporter checks that the original source files and model structure
still match the import. Within supported layouts it can update existing mesh
data and face targets while leaving unknown game data intact. It refuses
changes that it cannot represent, such as a new UV seam requiring more vertices.

Three different checks matter:

- **Unchanged export:** the output matches the original bytes.
- **Edited export and reimport:** our reader can reopen the output and find the change.
- **In-game test:** the target game actually loads and uses the change correctly.

Passing one does not establish the others. [Export validation](../formats/character/EXPORT_VALIDATION.md)
records which samples and edits have been checked.

## Work needed for general character rebuilding

The aim is still to support the full import, edit and export workflow. Remaining
work includes rebuilding model parts with their materials and textures, writing
changed rigs, keeping animations attached correctly, and updating character
references. Each game's file versions need separate validation.

The [Figure Forge and fork review](FIGURE_FORGE_REVIEW_2026-10-20.md) records
reusable research and candidate writers. It is development background, not an
extra setup step or a promise that those features are enabled in Workshop.

AI assistance was used in this work.

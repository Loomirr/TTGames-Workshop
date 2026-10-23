# Character models and animations for Blender

Import supported LEGO game characters into Blender, preview their animations,
and export limited edits back to their original file format.

**Version 0.5.31 — experimental. Requires Blender 4.4 or newer.**
[Download the addon ZIP](../../builds/blender/TT_Character_Importer_0.5.31.zip).
The CU3 cutscene addon is not required.

| Game | What to expect |
| --- | --- |
| LEGO Marvel Super Heroes, LEGO Batman 3, The Hobbit, LEGO Marvel's Avengers | Character assembly, supported animation playback, and limited model/animation export. Some parts, materials and animation types remain unsupported. |
| LEGO Batman 2 | Experimental characters and supported animation. Limited animation export passed Blender checks; game validation is pending. |
| LEGO Batman 1, The Complete Saga | Import models and rigs. Costume assembly is incomplete; no animation playback or game-format export. |
| LEGO Fortnite | A separate static model workflow; no animations or game-format export. [Setup](../fortnite/README.md). |

For other games, start with the [repository support table](../../README.md#game-and-file-support).
An entry in an archive browser does not mean the addon can import that asset.
See [animation support by game](../../docs/ANIMATION_SUPPORT.md) for playback,
editing and the remaining AN3/ANI-E limitations.

## Install

1. Click the ZIP link above, then the **Download button (down-arrow icon) at the
   top right** of GitHub's file view. Keep the ZIP zipped.
2. In Blender, go to **Edit > Preferences > Get Extensions**, click the
   **drop-down arrow at the top right**, then select **Install from Disk**.
3. Select the ZIP, then enable **TT Character and Animation Importer** under **Add-ons**.
4. In the 3D Viewport, press **N** to open the sidebar, then select **TT Character**.
5. Choose your game and its installation folder, or the root of an extracted
   copy. Keep any extraction cache outside the installed game folder.

For supported installed games, the addon reads the needed files from the
game's archives into a separate cache. You do not need
to extract the entire game first.

After an addon update, restart Blender. Reimport a character when a fix changes
its meshes, materials or export checks; updating the addon does not repair an
already saved Blender scene.

## Find your way around

Press **N** in the 3D Viewport and open **TT Character**. Choose one tab:

- **Import:** choose your game and folder, then browse characters or open a file.
- **Animate:** select an imported character, find and load a clip, then press Play.
- **Export:** select the character or native clip you edited and choose its export.
  Hover over a disabled button to see what is missing.

Turn on **Advanced** only when you need batch import, costume/detail choices,
custom animation copies, viewing scenes or preview settings. Those controls
stay with the relevant tab. Game support notes are beside the game choice for
model-only profiles; technical format details are under Advanced.

The game choice controls the next import. Animation and export use the selected
imported character. Export is also available under **File > Export** as
**LEGO model edits (game files)** and **LEGO animation (.an4 / .pak)**.

## Import a character

**For a first import:** choose the game and folder in **TT Character**, click
**Browse characters...**, search for a character, and import it. Select the
result and press NumPad `.` to frame it. Use Material Preview to see textures.

If you already have extracted files, use **File > Import > LEGO Character /
Model (.cd/.ghg/.gsc)**, or drag a single supported file into the 3D Viewport in
Object Mode. Confirm the game and **Game / extracted folder** in the options.

### Which file should I open?

| Input | What the addon tries to load |
| --- | --- |
| Character `.cd` | A character recipe: its model, costume, visible parts and declared attachments. Best starting point for a complete character. |
| Skeletal model `.ghg` | The model and rig. An **Optional matching CD** can supply its costume and part choices. Without it, alternate parts may overlap. |
| Model `.gsc` | Supported static model geometry. This option is not an importer for arbitrary level GSCs. |
| Animation `.an4` | A clip for an already imported native rig. Select that character before importing it. |

A CD is useful for assembling a character, but is not mandatory for inspecting
a supported model. A model still needs its texture and other companion files
in the selected game folder. Selecting a DAT archive as the model input is not
a character import.

**Costume layers** chooses the gameplay costume by default. Use **Cutscene
costume** or **Authored flags** to inspect other sets of parts. A layer is a
group of model parts that the game can show or hide.

**Mesh detail** defaults to the highest supported detail level. Games often
store simpler copies for distant viewing; these are called LODs. A raw import
can contain several copies, so overlapping geometry is not always a bad mesh.

**Mirror to game handedness** is off by default. Turn it on if the model's
left/right sides or printed text appear reversed relative to the game. This
mirrors the imported object while retaining its original mesh and animation
data for export.

### LEGO Batman 1 and The Complete Saga

Install the addon using the steps above. Press **N** in the 3D Viewport and open
**TT Character**. Choose **LEGO Batman 1 — models only** or
**LEGO Star Wars: The Complete Saga — models only**, set your game folder, then click
**Browse characters...**. Select a model to import it with its rig.

These modes show the model's stored parts. They do not play classic animations
or export edited models. They browse GHG files under `CHARS`. For TCS, a matching TXT's
`layers_high` list chooses the initial visible parts; all layers remain available.
Without a valid list, all layers stay visible and the importer reports why.
LB1 attachments can remain hidden when their binding is unresolved. Materials
are approximate and some variants may overlap.

See [classic inspection instructions](../classic-pc/README.md#blender-inspection).
For creating characters in PC TCS, LB1 or Indiana Jones 1,
[BactaTank Classic](https://github.com/AlubJ/BactaTank-Classic) is a better starting
point; this addon's classic profiles do not export edited models.

## Browse animations and preview

The first **Browse characters...** builds a file list. Large loose-file trees
are faster in 0.5.26; unchanged archive indexes can also be reused during the
session. Import still needs to decode the model and create Blender meshes and
materials, so this does not remove every pause. [Measured checks](EXPORT_VALIDATION.md#file-discovery-performance-0526--cu3-0133).

1. Import a character CD for LMSH1, LB3, The Hobbit, Avengers or experimental LB2.
2. In **TT Character**, search the animation list and select an action.
3. Click **Load selected animation**, then **Play / Pause** or Space.
   Preview runs at 30 FPS and keeps the clip's original movement.
4. For easier viewing, enable **Advanced**, expand **Custom clips / viewing scenes**,
   then click **Create viewing scene**. It creates a
   separate scene with lights and a following camera. Use camera view and
   Material Preview to watch it.

For extracted clips, select the character and use **Load a separate AN4 file** or
drop one or more `.an4` files into the viewport. Body animation is applied to
the main rig even when a body mesh or attachment is selected.

The list comes from the character's animation references, not from a running
game. Some entries are aliases, disabled actions or level-specific clips.
A listed clip can still be missing or unsupported. **TT Animation catalog**
in Blender's Text Editor explains missing or ambiguous references.

### Faces and attachments

Supported face tracks animate numeric `TT_Target_###` shape keys; supported
attachment tracks animate the matching attachment rig. These only load when
the addon can identify a compatible actor and clip. Matching names or bone
counts alone are not enough. Unknown face layouts and mismatched cape rigs
remain reported rather than being forced onto the model.

After loading a clip, the sidebar shows whether facial parts are moving, the
clip holds a fixed expression, or facial tracks did not load. **Animation
details** explains missing tracks and identifies the full report. A static
expression can be correct for that clip. [Recent playback checks](../../docs/FACE_PLAYBACK_2026-10-21.md)
describe the tested examples; edited face tracks cannot yet be exported to AN4.

To try a face shape manually, select the face mesh and open **Object Data
Properties > Shape Keys**. Adjust one `TT_Target_###` value, then return it to
zero. Unlink its shape-key action temporarily if animation keeps overriding
your value. The numbers are game target IDs, not labels such as "smile".

Faces use special masking in the game: some surfaces hide other surfaces
without appearing themselves. A normal Blender viewport does not reproduce
that exactly. **Create face render preview** builds a separate Cycles scene
for a closer check; press **F12** there. The simpler live preview can have
jagged edges. Both preserve the original scene, and neither guarantees exact
game shading. See [preview quality settings](../../docs/SHADING_AND_QUALITY.md).

Audio, events, gameplay transitions and some expression tracks are not reproduced.
For LB2's separate facial animation limits, see [LB2 faces](../../docs/LB2_FACES.md).

## Batch review galleries

Use **TT Character > Batch import for review** to inspect several assets at once.
Choose characters, vehicle models, definitions, raw models, or both. A path
filter narrows the list. The default is 20 imports; set **Maximum imports** to
**0** to attempt every match. Large batches can use a lot of memory.

**Start index** skips that many entries in the sorted, filtered list, allowing
you to review a roster in chunks. Imports form a grid in a new collection.
Escape stops after the current asset and keeps completed imports. A failed
asset is removed without removing the successful ones.

Open **TT Batch report.json** in Blender's Text Editor for individual failures
and missing-part notices. Use **Text > Save As** to share the report, checking
it for personal paths first. No files are uploaded automatically.

Vehicle and raw-model modes inspect model files, not complete vehicle recipes.
Wheels, attachments or the correct visible variant may be missing. The list
can contain shared models and duplicates. No animations load automatically,
and Fortnite is excluded. Use each character's preview buttons for face checks;
the batch grid does not set up the face masking preview.

## Export loose native files

This exports supported changes to the **original game file format**, such as
GHG. It is not an export of everything visible in Blender. Read the
[editing guide](../../docs/CHARACTER_EDITING.md) before adding parts or bones.

1. Import with the current addon and keep the original game files unchanged.
2. Make supported edits on the original mesh, usually in Edit Mode.
3. Select the character and click **Export model edits...**.
4. Choose a **new folder outside the game, source tree and cache**.
5. Read `TT_Source_Export.json` in the output before using it in a mod.

The folder contains model files and their available definition/texture
companions, with their relative paths preserved. Original animation sources
that you loaded from the catalog are included. **It does not edit DAT archives
or install a mod.** Existing output folders are not overwritten.

### Supported edits and limits

| Edit | Current rule for supported modern models |
| --- | --- |
| Move existing vertices | Preserve vertex order and triangles; stay inside the original part's bounds. Face Basis positions must stay unchanged. |
| Change UVs or SourceColor vertex colors | Preserve the original vertices. UV seams that need extra vertices are rejected. |
| Edit normals | Keep one normal per original vertex; new split vertices are not supported. |
| Weight Paint | Use existing bones already available to that part, at most four influences, with normalized weights. |
| Edit an existing `TT_Target_###` face shape | Keep Basis, target names, topology and vertex order. Some native target encodings cannot represent every edit. |
| Add/remove meshes, swap hair objects, add bones or change the rest pose | Not supported by this export path. |
| Change materials, paint/replace Blender images, apply modifiers or move objects | Not written as model edits. Material/image changes and other incompatible changes stop export. |
| Edit animation | Use the separate AN4 exporter below. The model bundle cannot save edited animation banks. |

Support also depends on the source model version. The exporter checks the
source files and imported structure before writing. Two copies of the same
source must agree on the edit. If a source or companion changed after import,
reimport it instead of bypassing the check. Do not use preview copies as the
editing source.

Unchanged files should remain byte-for-byte identical. Reopening an edited
export checks that the file can be read; it does not establish that the game
will accept it. See [export validation](EXPORT_VALIDATION.md) for tested samples
and detailed format restrictions.

## Export an edited animation

Select the imported rig with the edited clip active, then use **Export animation (AN4 / PAK)...**. Choose a new `.AN4` file outside the game, source
tree and cache. Keep the native bones, rest pose, original frame range and
clip length. Read the accompanying `.AN4.json` report.

The exporter supports checked ANI-B/ANI-D body animation records, including
LB2's big- and little-endian files. It keeps the supported tables that select reduced-detail body
animations and applies your edit to each verified native rig. Reimport with this
version to retain the per-bone edit baseline. Unknown extra tables still cause a
refusal. Leave **Omit unsupported events / auxiliary tables** off for normal game
replacements; enabling it deliberately discards those tables for a pose-only draft.
Edited face and attachment actions are not written.

Edited tracks are baked at whole frames. Motion between frames can differ from
the original curves, so check movement in-game, including at different distances.

The current writer preserves the source's raw or `Deflate_v1.0` compressed
storage, including clips loaded from PAK banks. An unchanged action retains the
original member bytes. This fixes a previous export bug that discarded the
compression wrapper; it does not establish that every rebuilt clip works in-game.

For an animation imported from a bank, enable **Write PAK with the other source clips** in
the export window to write a separate `.PAK` instead. Reimport the clip with
this version first, so the addon can detect changes to the whole source bank.
The writer keeps the other clips, file order, alignment and padding. Unknown
bank layouts are refused. Read the accompanying `.PAK.json` report, then install
the bank using your mod's normal loose-file replacement workflow.

The ordered-bank method passed an LMSH1 Captain America test: the edited idle,
walking, running and combat worked in-game. The earlier append-to-end method
broke other animations despite their payloads being unchanged. This confirms
the tested container method; it does not validate every Blender animation edit.
The 0.5.26 and 0.5.27 Blender rebakes failed their LMSH1 game tests: the character
collapsed or became tiny. Version 0.5.28 corrects the table order required by
the game's loading code and preserves the original active channels on each
bone. Editing a channel group absent from the source is refused. The LMSH1
Captain America retest passed: the Blender head edit appeared in-game and the
user reported that the other animations stayed normal. This confirms that
tested clip and bank, not every animation or game. Re-export from the original
game clip rather than reusing an older baked file.

### Make or load a custom animation

1. Load a native animation on the imported character rig.
2. Click **Copy active clip for editing** in **TT Character** and name it.
3. Edit that copy's pose keys. Keep the native bones and original clip length.
4. Export the active AN4, or enable **Write PAK with the other source clips** for a bank clip.

To preview an exported file again, select the original action in the declared
actions list and click **Load replacement AN4 / PAK...**. The file
must retain that action's native actor and clip name. A PAK must contain the
selected member. Loading a custom clip does not install it into the game.

This workflow replaces an existing character action. Adding new action slots,
rewriting character animation definitions, changing clip length and adding bones
are not supported yet.

### What does "bake to a clean rig" mean?

Baking records the final bone motion as ordinary keyframes. It is needed when
constraints, control rigs or animation modifiers are producing the motion,
because the exporter does not write those Blender features into AN4.

Work on a copy of your scene. Bake the motion onto the **same imported native
bones**, preserving their names, parents and rest pose. Keep the original clip
length and imported source information. After checking that the keyframed
motion matches, remove the constraints from the export rig and mute NLA tracks
so they do not change the result again. Simply deleting constraints without
baking can lose the motion. A new generic rig is not an export-ready substitute.

For simple edits to an imported clip that uses only keyframes, there may be
nothing to bake. **Baking does not compress the AN4 or fix its file format.**
If a clip exports but will not load in-game, report the game, source clip,
addon version and `.AN4.json` report.

## Unpacked games

Select the root of the extracted game tree, keeping folders such as `CHARS`
and `ADDITIONALCONTENT` in place. Include the model's character definition,
textures, animation declarations and referenced AN4/PAK files. A folder
containing only a GHG often lacks the files needed to assemble its character.

The same installed/extracted choice is available for enabled TT character
profiles. It does not unlock unsupported games or layouts.

## Troubleshooting

| Problem | First check |
| --- | --- |
| Missing hair, torso or costume | Use the matching CD and correct game root. Check the import report for a missing companion or unsupported attachment. |
| Overlapping parts | A raw model may show multiple costumes or detail levels. Try the CD and gameplay costume setting. |
| Face looks wrong from some angles | Compare the composed face preview, not just Solid view. Native masking and shaders remain approximate. |
| Animation is listed but will not load | Read **TT Animation catalog**. A reference can exist even when its file or layout is unsupported. |
| Export asks for a fresh import | The saved scene may predate required source checks, or its original files changed. Reimport the current source. |
| Export refuses an edit | Check the supported-edits table. Adding an object in Blender does not create the game records needed to export it. |
| Updated addon, same broken scene | Restart Blender and import again. Existing Blender objects are not rebuilt by the update. |

Reports are available in Blender's Text Editor. For a bug report, include the
game/platform, addon version, logical file name, error and screenshot. For
animation bugs, add the clip and frame. Do not upload game archives or assets
to the repository.

## Other game research

The separate `inspect_game.py` command inventories supported archive resources
without importing a Blender character. It can help investigate a game that is
not yet supported by the addon:

```powershell
python formats/character/inspect_game.py AVENGERS "D:/Games/LEGO Marvel's Avengers" "output/avengers.json" --cache "cache" --character CaptainAmerica
```

Profiles: `LB3`, `LMSH1`, `HOBBIT`, `LOTR`, `AVENGERS`, `TFA`, `DCSV`, `LMSH2`.
It uses standard Python and writes separate reports/caches. These inspector
profiles are not a list of complete character importers.

## Source and checks

The UI and assembly code are in `Addon/io_scene_tt_character`. Build before
installing from source; the build includes the shared readers from the CU3
source tree without requiring the CU3 addon to be installed.

```sh
python formats/character/build_addon.py
```

Detailed evidence and known gaps:

- [Compatibility notes](COMPATIBILITY.md) and [export validation](EXPORT_VALIDATION.md).
- [Latest shared definition work](../../docs/DEFINITION_COMPATIBILITY_2026-10-20.md) and [October 19 importer review](../../docs/PR_REVIEW_2026-10-19.md).
- [Model accuracy checks](../../docs/CHARACTER_ACCURACY_0.5.9.md), [face checks](../../docs/FACE_ACCURACY_0.5.3.md) and [remaining minifigure reports](../../docs/ISSUE_1_MINIFIGS.md).
- [Guarded definition edits](../../tools/character_clone/README.md): a development helper, not a complete new-character-slot creator.

AI assisted this project. See [licensing](../../docs/LICENSING.md); no additional
license grant is implied for unlicensed research components.

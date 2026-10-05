# TT Character and Animation Importer

A separate, lightweight Blender addon for observed PC **LMSH1 NXG** and
**LEGO Batman 3 DX11**, **The Hobbit NXG** and **LEGO Marvel's Avengers DX11** characters. Version **0.4.0**, experimental.
It installs independently of the cutscene addon and needs no external extractor
for supported companions inside the installed game's archives.

## Install

Download [the addon ZIP](../../builds/blender/TT_Character_Importer_0.4.0.zip).
In Blender 4.4+ open **Edit > Preferences > Add-ons > Install from Disk**, select
the ZIP and enable **TT Character and Animation Importer**. Expand its
preferences and set the matching game folder (or extracted asset folder).
An optional extraction cache must be outside the game installation.

## Import a character

The easiest route is **3D View > N sidebar > TT Character**: select the game,
set its folder, press **Browse game characters**, and search for a character. Supported companions are read into a separate cache automatically.
The browser lists minifig, small, bigfig and creature CD resources; individual
props/attachments use the file importer below. Some listed definitions may still use unsupported layouts.

For an already extracted file:

1. Use **File Ã¢â€ â€™ Import Ã¢â€ â€™ LEGO Character / Model (.cd/.ghg/.gsc)**.
2. Choose an extracted character **CD** and select the correct game. The CD
   selects its model, costume textures, layer variants and declared attachments.
   **Costume layers** defaults to the gameplay costume. Choose **Cutscene costume**
   or **Authored flags** when inspecting those native variants.
   Set **Game / extracted folder** in the import options if not saved in preferences.
3. Import. Select the character and press NumPad `.` to frame it. Use Material
   Preview to see textures; the report in Blender's Text Editor lists omissions.

A raw **GHG** imports a skeletal model. Supply **Optional matching CD** for its
costume and native layer choices. Without a CD, all display variants are shown
for inspection and may overlap. A supported model **GSC** imports static
geometry; arbitrary level GSCs are not supported by this character reader.
Materials and faces are still approximate, especially depth-mask surfaces,
shared texture slots and layered shaders. Importing successfully is not proof
of exact in-game appearance.

CD and texture companions must be available in the selected asset tree/game.
Selecting a packed archive itself is not a character import. No game files
are supplied in the addon download.

## Browse animations and preview

1. Import a character CD from an installed or unpacked **LB3, LMSH1, The Hobbit or Avengers** game folder.
2. Its declared animation sets appear automatically in **TT Character**.
   The search box filters action names and set names, including shared sets.
3. Select an action and press **Load selected animation**. AN4 files and
   supported PAK members are decoded from the game's DATs into a separate cache.
4. Click a loaded clip and press **Play / Pause** (or Space). Preview uses
   30 FPS and preserves original root movement.
5. Use **Create character preview scene** for a separate viewing scene with
   lighting, a camera that follows root movement and live facial mask clipping. Stay in camera view with
   Material Preview; no frame renders are needed to watch playback.

Live facial clipping can leave jagged edges, particularly on modern faces.
For closer inspection, **Create composed face preview** makes a separate Cycles
scene with facial holdout passes and a compositor. Press F12 in that scene.
The native depth-only masks are enabled for this pass, preventing overlapping
teeth and mouth surfaces from drawing in full. Raw imports hide these masks;
a plain render of the raw import does not reproduce facial masking. The composed
preview still approximates the game shader and does not supply missing expression
animation. Both preview choices preserve the original scene and native meshes.

For extracted AN4 files, **Import AN4 animations** still supports multiple
files. The addon now decodes the observed `Deflate_v1.0` wrapper itself.
No external decoder is required. Select any body mesh or attachment; body
animation goes to the main character rig.

The catalog is a reference graph, including aliases, disabled actions and
conditional/level banks. It is not the game's runtime state machine. Missing
or ambiguous sets are listed in **TT Animation catalog** in the Text Editor.
A listed action may still have an unsupported scalar format or actor layout.
Native attachment tracks are applied only when one matching skeleton and clip
can be identified. Gameplay capes and cutscene capes can have different joint
counts; mismatches remain reported instead of being forced onto the mesh.
Facial target weight timing, events, audio, IK and gameplay transitions are
not fully reproduced.

## Export loose native files

Select the character and use **Export loose native files / supported edits**.
Choose a fresh folder outside the installed game and extraction cache. This
writes native model files, character definitions, texture companions and the
original sources for catalog animations you loaded. It preserves their
relative folders and produces `TT_Source_Export.json`. **It never writes DATs.**

Existing `TT_Target_###` face coordinates can be written into supported GHG
payloads. Keep the original Basis, topology, target names and vertex order.
Edits that require splitting a native repeated-offset run are rejected.
A no-op face export preserves the original file bytes exactly. Face-target
writing is gated to the verified MESH 169/175 layouts; Hobbit MESH 170 targets
are readable, but their native writer is not yet enabled.

Version 0.4.0 can also write existing **positions, UVs and SourceColor vertex
colors** into verified MESH 169/170/175 buffers. Work in Edit Mode on the original
mesh, preserving vertex order and triangles. Position edits must stay within
the original part's bounds. Facial Basis positions stay immutable. Keep one UV
per native vertex: new UV seams requiring vertex splits are rejected. Shared
display copies must agree; the report lists any other parts affected by shared
buffer edits. A no-op export keeps the exact original bytes.

Object placement, evaluated modifiers, normals, topology, weights, material
node graphs and skeleton changes are not encoded. Native bounds are retained,
not rebuilt. Texture companions are copied; this is not a Blender image encoder.
This remains a constrained writer, not arbitrary Blender-to-game serialization.

## Export an edited animation

With a newly imported native clip active, use **Export active AN4 clip
(experimental)**. Choose a fresh file outside the game, source tree and cache.
Keep the native bones/rest pose, frame range and clip length. The writer samples
the active action and rebuilds the selected six/nine-channel ANI-D record;
other actors/records remain untouched. Six-channel records require unit scale;
nine-channel records support positive nonzero scales. Shear, reflection, ANI-E,
constraints and active NLA tracks are rejected. Bake to a clean rig first.

Many originals contain unsupported auxiliary/event tables. Modified clips with
those tables are rejected unless you explicitly enable **Omit unsupported events
/ auxiliary tables**. That produces a pose-only draft; it does not preserve the
selected animation block's gameplay cues. Unchanged clips preserve original bytes.
The separate `.AN4.json` report records this and the decoded sample error.

PAK members become separate AN4 files; their bank is not rebuilt. Neither export
operation writes DATs. Modified AN4s have been decoded and reimported in Blender;
in-game replacement/loading still needs testing. This is not a verified complete
animation mod writer.

## Unpacked games

All four enabled character profiles use the same installed/unpacked workflow.
Choose the **root of the extracted asset tree**, preserving folders such as
`CHARS` and `ADDITIONALCONTENT`. Include CDs, models, TEX/NXG_TEXTURES companions,
AS animation declarations and the AN4/PAK files they reference. A single model
folder is not a full game dump. Companion texture stores are resolved beside
their source model first, avoiding unrelated DLC stores with the same basename.
Archive and loose-folder imports were compared for one character/clip per game.
This does not enable unknown layouts or later games still listed as inspection-only.

## Other game research

`inspect_game.py` inventories installed **Avengers, TFA, DCSV, LMSH2, LOTR and The Hobbit** character,
model and animation resources with the appropriate archive readers:

```powershell
python formats/character/inspect_game.py AVENGERS "D:/Games/LEGO Marvel's Avengers" "output/avengers.json" --cache "cache" --character CaptainAmerica
```

Profiles: `LB3`, `LMSH1`, `HOBBIT`, `LOTR`, `AVENGERS`, `TFA`, `DCSV`, `LMSH2`. This inspector uses only the
standard Python library and writes separate caches/reports. It does not enable
Blender character import for all those profiles. See
[the current compatibility notes](COMPATIBILITY.md) for exact coverage.


## Source and checks

`Addon/io_scene_tt_character` contains the UI and assembly code. The build
copies the required shared native readers from `formats/cu3/Addon` into a
private `_core` namespace; neither addon depends on the other being installed.
Do not install the raw source folder before building that dependency bundle.

```sh
python formats/character/build_addon.py
```

The standalone desktop utilities remain separate downloads under `builds/`.
AI assisted this project. See [licensing](../../docs/LICENSING.md); no additional
license grant is implied for unlicensed research components.

Version 0.1.1 fixes the file importer ignoring the sidebar game selection.
The file browser starts with the selected panel game; changing it for an import
also updates the panel after a successful import.

Version 0.1.2 routes body animations to the main character rig when its cape,
face or other parented attachment is selected. Failed imports display the first
actual reason. Version 0.2.0 adds the compression reader, declared animation browser,
matching attachment tracks, separate live viewing scenes and constrained
loose source/face-target export.

Version 0.3.1 adds The Hobbit character and animation browsing, explicit costume
layer selection, more observed native skeleton/material layouts, native material
slot assignments and variable-length LB3 facial target records. The portable
`audit_characters.py` tool checks the entire declared roster and reports failures;
it does not certify visual or animation accuracy. See [coverage](COMPATIBILITY.md).

Version 0.3.1 also accepts verified texture stores with empty conversion metadata,
restoring their embedded DDS materials. Further Blender checks cover bigfigs
Killer Croc and Hulk, plus Thorin and Gandalf.

Version 0.4.0 adds Avengers character/animation browsing, verified UMTL
229/232/234/235 and TXTS 14 boundaries, native `None` layer suppression,
unpacked workflow checks and constrained vertex/ANI-D writers. Modern shader
reconstruction is still approximate; untextured materials can use native vertex
colors for inspection rather than appearing white. See [coverage](COMPATIBILITY.md).

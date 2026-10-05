# TT Character and Animation Importer

A separate, lightweight Blender addon for observed PC **LMSH1 NXG** and
**LEGO Batman 3 DX11** and **The Hobbit NXG** characters. Version **0.3.0**, experimental.
It installs independently of the cutscene addon and needs no external extractor
for supported companions inside the installed game's archives.

## Install

Download [the addon ZIP](../../builds/blender/TT_Character_Importer_0.3.0.zip).
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

1. Import a character CD from an installed **LB3, LMSH1 or The Hobbit** game folder.
2. Its declared animation sets appear automatically in **TT Character**.
   The search box filters action names and set names, including shared sets.
3. Select an action and press **Load selected animation**. AN4 files and
   supported PAK members are decoded from the game's DATs into a separate cache.
4. Click a loaded clip and press **Play / Pause** (or Space). Preview uses
   30 FPS and preserves original root movement.
5. Use **Create character preview scene** for a separate viewing scene with
   lighting, a camera that follows root movement and live facial mask clipping. Stay in camera view with
   Material Preview; no frame renders are needed to watch playback.

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

Select the character and use **Export loose native sources / face targets**.
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

**This is a source-bundle and constrained face-target exporter, not a general
Blender-to-GHG/GSC/AN4 encoder.** Geometry, UVs, material nodes, skeleton changes
and edited actions are not encoded; those source files retain their original
bytes. The UI and export manifest state this explicitly. General writers are
still needed before arbitrary custom meshes and animations can round-trip.

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

Version 0.3.0 adds The Hobbit character and animation browsing, explicit costume
layer selection, more observed native skeleton/material layouts, native material
slot assignments and variable-length LB3 facial target records. The portable
`audit_characters.py` tool checks the entire declared roster and reports failures;
it does not certify visual or animation accuracy. See [coverage](COMPATIBILITY.md).

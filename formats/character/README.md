# TT Character and Animation Importer

A separate, lightweight Blender addon for observed PC **LMSH1 NXG** and
**LEGO Batman 3 DX11** characters. Version **0.1.0**, experimental.
It installs independently of the cutscene addon and needs no external extractor
for supported companions inside the installed game's archives.

## Install

Download [the addon ZIP](../../builds/blender/TT_Character_Importer_0.1.0.zip).
In Blender 4.4+ open **Edit → Preferences → Add-ons → Install from Disk**, select
the ZIP and enable **TT Character and Animation Importer**. Expand its
preferences and set the matching game folder (or extracted asset folder).
An optional extraction cache must be outside the game installation.

## Import a character

The easiest route is **3D View → N sidebar → TT Character**: select the game,
set its folder, press **Browse game characters**, and search for a minifig
character. Supported companions are read into a separate cache automatically.
The browser lists minifig CD resources; individual props/attachments use the
file importer below. Some listed definitions may still use unsupported layouts.

For an already extracted file:

1. Use **File → Import → LEGO Character / Model (.cd/.ghg/.gsc)**.
2. Choose an extracted character **CD** and select the correct game. The CD
   selects its model, costume textures, layer variants and declared attachments.
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

## Import animations and preview

1. Select the imported body rig (or one of its meshes) in Object Mode.
2. Use **File → Import → LEGO AN4 Animations (.an4)**. Select one or multiple
   extracted, uncompressed AN4 files. Default preview timing is 30 FPS.
3. Open **3D View → N sidebar → TT Character**. Click a clip in the list, then
   press **Space** or **Play / Pause**. The timeline range switches with the clip.

One compatible root actor is chosen automatically. For ambiguous files, enter
an exact **Actor name**. Each compatible record becomes a separate retained
Blender action; existing actions are not overwritten. Original root movement
is retained. This is native-skeleton playback, not cross-character retargeting.
Pose import checks the target's names, hierarchy and rest matrices; the AN4
itself does not provide a complete rest skeleton to verify arbitrary pairings.
Supply animations belonging to the source rig.

The initial standalone AN4 gate is big-endian **v13/14 ANI-D**. Other tree
versions, ANI-E and packed PAK banks are rejected. LMSH1 source clips have been
compared with the existing decoder; LB3 standalone AN4 coverage must be tested
per layout and is not blanket support for every LB3 animation bank. Independent
attachment animation, facial timing, notifies, audio and effects are not imported
with the body action. A skipped/unsupported record appears in **TT AN4 report**.
The checked LB3 installation stores standalone AN4s inside a `Deflate_v1.0`
wrapper. That inner wrapper is not handled here yet; extracting it from DAT
alone does not make it ready for this AN4 importer.

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

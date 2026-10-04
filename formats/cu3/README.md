# TT Cutscene Importer

An experimental Blender importer and set of tools for TT Games' PC cutscenes.
I'm starting with **LEGO Marvel Super Heroes** and **LEGO Batman 3: Beyond
Gotham**, then working towards support for more games once these are working
properly. **LEGO DC Super-Villains** now has partial structural support too.

**AI was used to help with the code, research and documentation for this project.**

Current local source version: **0.1.5** (unreleased). It can inspect CU3 files and import
supported character animation onto the matching source skeleton. Full cutscene
reconstruction is still being worked on: automatic models, materials, cameras,
facial animation, audio and effects aren't automatically assembled through the addon yet.
The local research scenes have companion assets and playback previews, but
those game assets and scenes aren't included in this repo.

See [the progress notes](docs/PROGRESS.md) for what's changed and what still needs checking.
The new [face GHG editing prototype](docs/FACE_GHG_EDITING.md) exports existing
shape targets into native GHG copies from verified editing collections.
Its decoded round trips pass; edited face files still need an in-game test.

This pass fixes static faces stacking every expression at once, and adds
tools for native depth masks and packed normal textures. See
[the facial rendering notes](docs/FACIAL_RENDERING.md). The private V5 scenes
look much cleaner, but they still aren't exact copies of the game's rendering.

## Blender addon

Download the [0.1.5 addon ZIP](../../builds/blender/TT_Cutscene_Importer_0.1.5.zip)
for an existing build, or use the source build command below.

1. Run `python scripts/build_addon.py` to make
   `dist/TT_Cutscene_Importer_0.1.5.zip`.
2. In Blender, open **Preferences → Add-ons → Install from Disk**, select that
   ZIP and enable **LEGO CU3 Cutscene Importer (Experimental)**.
3. Use **File → Import → LEGO CU3 cutscene (.cu3) [experimental]**.

The addon declares Blender 4.4+ support. Testing so far has been in Blender
5.2.2; other versions still need checking. Building the ZIP only needs Python's
standard library.

There are three import modes:

- **Inspect scene references:** shows actor markers, names and a report in
  Blender's Text Editor. Markers aren't character meshes.
- **Create source armatures:** loads a matching, uncompressed source GHG or
  skeleton JSON and imports supported animation records.
- **Animate selected source rig:** applies a chosen actor record to a matching
  armature. It checks the bone names, hierarchy and rest matrices. **Work on a
  copy** is enabled by default.

Inspect first, then use an exact actor name to pick the instance you want.
The character and its face or attachments can have different skeletons.
Matching bone counts alone don't mean two rigs are compatible. This version
doesn't retarget animations to LOTDK or import character meshes from GHG.

Use extracted, uncompressed CU3 files. The optional **Use source scene
movement** setting applies static or animated actor placement separately from
skeletal motion. **Use source visibility** is enabled by default, so separate
shot instances can hide when their source track says they should. These have
been checked against decoded tracks; frame-for-frame game matching remains
research work.

## Longer character and object names

There's also a small standalone editor:

```sh
python scripts/cu3_name_editor_gui.py
```

Open a CU3, select an actor or rigid object, set its replacement name and save
an edited copy. The original file is protected. Python needs Tkinter for the
window; the command-line version doesn't need it:

```sh
python scripts/cu3_name_editor.py list scene.CU3
python scripts/cu3_name_editor.py rename scene.CU3 --actor "OldName=MuchLongerCharacterName" --output scene_edited.CU3
python scripts/cu3_name_editor.py rename scene.CU3 --object-index "0=MuchLongerObjectName" --output scene_edited.CU3
```

Use `--actor-index` when multiple actors have the same name. `--record
"ACTOR_INDEX:RECORD_INDEX=NewName"` changes an animation-record name separately.
Names use printable ASCII and are limited to 255 bytes by the editor; the
game's actual maximum is still unverified.

The GUI also has **Replace all character instances**. Select a root actor,
enter the replacement character name, and use that button to prepare all
instances of the same character family. Review the replacement column before
saving. The equivalent command is:

```sh
python scripts/cu3_name_editor.py rename scene.CU3 --character "Batman_Cutscene=GreenLantern" --output scene_edited.CU3
```

`BatmanPower` is a separate character family and needs its own edit. Combining
plans that would create duplicate root names is rejected; use explicit unique
instance names in that case. The optional `--character-scope shared-reference`
includes roots sharing the selected numeric resource reference, but its runtime
meaning is still unverified. Exact character-family replacement is the default.

Instance numbers aren't playback order. The editor shows numeric references
and inner animation labels: in the Batcave intro, Batman, Robin, Alfred and
tentacles all share the same inner record label. Those labels stay unchanged
unless explicitly edited, and aren't reliable character identifiers. Old names
can remain in the file because the original tree is retained.

The editor grows strings by relocating a copy of the embedded tree rather
than shifting animation data. It reparses the output and checks the hierarchy,
placement matrices and original animation bytes. That structural check passed
on **446 actor-bearing files across CU3 versions 16–19**, plus **216 DCSV
actor-bearing files**. The LB3 opening title/menu test was also confirmed
in-game: all ten Batman instances were renamed and Batman was fully replaced
with Green Lantern. Other swaps and games still need testing.
Replacing a character can also require compatible models,
skeletons and changes to other script references; renaming an instance alone
doesn't handle those.

## What's supported so far

- Observed PC CU3 envelope versions 16–19 and embedded AN4 versions 13–16;
  partial CU3 v30 / AN4 v20 structural support for DCSV.
- Actor hierarchy, animation records, timing and placement matrices.
- Supported six/nine-channel Euler skeletal animation with compressed curves and
  constants. Rotation endpoints are interpolated as normalized quaternions.
- Source skeleton reading for LMSH1 HGOL v10 and Batman 3 DX11 HGOL v16.
- Research readers for typed camera, shot-state and rigid-object references.
- Copy-based actor, object and animation-record name editing.
- Character-family replacement planning and source visibility/movement tracks.

The standalone readers also recognize some additional scalar layouts. This
doesn't mean all those layouts are ready for Blender pose import. Cumulative
parent-scale compensation and constant-table decoding have been corrected;
attachments, faces and camera conventions still need further work.
Unsupported layouts should report an error rather than produce guessed poses.

The local research scenes have more companion model and scene work than this
public addon. Those scenes and game assets aren't included here. A successful
decode or bounded mesh doesn't prove the scene matches the game frame for frame.

## DC Super-Villains and archive readers

Of **324 extracted DCSV CU3 files**, **297 parse structurally**. The remaining
27 fail explicit layout checks. Name-growth checks passed in all 216
actor-bearing files that parsed. **DCSV ANI-E animation playback, camera
decoding and rigid-object editing are deliberately disabled** until verified.
This isn't full DCSV cutscene import yet.

Two read-only archive readers are included:

```sh
python scripts/archive_index.py path/to/GAME0.DAT output_folder
python scripts/archive_index.py path/to/GAME0.DAT output_folder --extract-cutscenes
python scripts/archive_index_cc4.py path/to/GAME4.DAT index.json
```

The first covers the observed LB3 `-6` index and can extract raw/DFLT/ZLIB
entries. Other compression types require a separate extractor. The second
indexes the observed DCSV `.CC40TAD` v2/`-12` format using 64-bit file offsets
and path hashes; it does not extract files itself. Neither reader modifies an
archive or downloads/runs extraction programs.

## Manual checks

No scheduled checks or CI are set up. To check files from your own installation:

```sh
python scripts/validate_names.py path/to/extracted.CU3
python scripts/validate_names.py path/to/extracted/folder
```

For a Blender operator check, use matching CU3 and GHG/JSON inputs:

```sh
blender --background --factory-startup --python scripts/check_blender.py -- scene.CU3 source.GHG ExactActorName
```

## Research notes

See [the format notes](docs/FORMAT_NOTES.md) for the observed byte layouts,
name relocation approach and remaining unknowns.

Useful references include [JaanDev's NXG format research](https://github.com/JaanDev/lego-tt-nxg-formats)
and [OpenSaga](https://github.com/opensagadev/saga). OpenSaga targets older
games, so its structures are research references rather than proof that these
PC games use exactly the same layouts.

This component contains source code and documentation; packaged tools are in
the central builds folder. You'll need your
own game files. The addon and name editor run locally without network access
or bundled extraction executables.

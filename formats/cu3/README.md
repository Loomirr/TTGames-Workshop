# TT Cutscene Importer

An experimental Blender importer and set of tools for TT Games' PC cutscenes.
The main scene work is for **LEGO Marvel Super Heroes** and **LEGO Batman 3:
Beyond Gotham**, with broader game support being added through separate format
checks. **The Force Awakens** and **DC Super-Villains** currently support
reference inspection rather than complete scene import.

**AI was used to help with the code, research and documentation for this project.**

Current source and packaged build: **0.1.15** (experimental).
Version 0.1.15 retains consumed model hashes and rejects a source changed during
decoding. It enables no new layout. The character addon's companion-export
guards are documented in the [P1 checkpoint](../../docs/HANDOFF_P1_CHECKPOINT.md).
Import now defaults to assembling supported actors, attachments, materials,
source cameras and experimental static stage geometry. Supply the selected
CU3 and its installed LB3/LMSH1 game folder or an extracted asset tree. The
addon loads the needed companions, remembers
per-game folders and prepares a live camera viewport. **This is still partial
scene assembly:** stage visibility and render controls are approximate;
nested scenes, rigid props, original lighting, audio and effects are not
automatically reconstructed. Faces and native shaders also need more work.
Game assets and example Blender scenes are not included here.

Version 0.1.13 adds stage-labelled model validation and layout summaries to
actor and static-stage reports. See the
[structural compatibility notes](../../docs/STRUCTURAL_COMPATIBILITY.md).

Version 0.1.14 preserves evaluated authored normals through facial clipping
and depth bias when Blender provides the Set Mesh Normal node. The shared
material reader also corrects the verified LMSH1 CD head-print UV layout.
Create a fresh import/preview for existing projects. Scene reconstruction
limits remain unchanged; see [shading checks](../../docs/SHADING_AND_QUALITY.md).

Version 0.1.12 corrects facial preview layering, cutout alpha and Avengers texture
references in the shared model reader. Verified packed surface-normal maps now
also cover selected Hobbit/LB3 layouts. See the
[face accuracy report](../../docs/FACE_ACCURACY_0.5.3.md) for checks and limits.
Version 0.1.10 includes the shared model fixes for nearest-detail accessory
LODs and the verified LMSH1 arm print UV layout. Stage draw-pool interpretation
and source camera/animation axes remain unchanged. Reimport to rebuild actors;
see [issue #1 patch scope](../../docs/ISSUE_1_MINIFIGS.md).

See [the progress notes](docs/PROGRESS.md) for what's changed and what still needs checking.
The new [face GHG editing prototype](docs/FACE_GHG_EDITING.md) exports existing
shape targets into native GHG copies from verified editing collections.
Its decoded round trips pass; edited face files still need an in-game test.

Native layer-special selection prevents ordinary, robot and skeleton body
variants—or both cape shapes—from being drawn together. Attachment tint colors
are also applied. See [layer selection](docs/NATIVE_LAYERS.md) and the
[facial rendering notes](docs/FACIAL_RENDERING.md).

[Live playback](docs/LIVE_PLAYBACK.md) follows source cameras and recovered
facial masks in the viewport without F12. Facial depth bias and mask edges are
approximations; they do not establish exact game rendering. The
[workflow audit](../../docs/WORKFLOW.md) separates the supported systems from
the remaining reconstruction work.

## Blender addon

Download the [0.1.15 addon ZIP](../../builds/blender/TT_Cutscene_Importer_0.1.15.zip)
or use the source build command below.

1. In Blender, open **Preferences → Add-ons → Install from Disk**, select the
   ZIP and enable **LEGO CU3 Cutscene Importer (Experimental)**.
2. Use **File → Import → LEGO CU3 cutscene (.cu3) [experimental]**.
3. Choose an extracted CU3 file. Keep **Assemble available scene assets** and
   **Detect from CU3** selected for LMSH1/LB3.
4. Set **Game or extracted asset folder** to the matching installed game folder
   or extracted asset tree. Later imports can leave it blank to reuse that
   game's saved folder. The addon preferences also expose both folders and an
   optional extraction-cache location.
5. **Recovered static environment (experimental)** is enabled by default.
   It loads supported static geometry from the cutscene's declared primary and
   shared level resources. Disable it for an actor-only scene.
6. Press **Space** in the camera viewport to play. **NumPad 0** restores camera
   view. Read the scene's import report in Blender's Text Editor for omissions.

Automatic profile selection is limited to the verified LMSH1 CU3 version 18
and LB3 version 19. For TFA/DCSV, choose **Inspect scene references** explicitly;
that mode creates markers and reports, not character geometry. CU3 alone does
not contain its companion meshes and textures.

The addon declares Blender 4.4+ support. Testing so far has been in Blender
5.2.2; other versions still need checking. Building the ZIP only needs Python's
standard library.

To build the ZIP from source, run `python scripts/build_addon.py` from this
component folder.

The addon also has these inspection and animation modes:

- **Inspect scene references:** shows actor markers, names and a report in
  Blender's Text Editor. Markers aren't character meshes.
- **Create source armatures:** loads a matching, uncompressed source GHG or
  skeleton JSON and imports supported animation records.
- **Animate selected source rig:** applies a chosen actor record to a matching
  armature. It checks the bone names, hierarchy and rest matrices. **Work on a
  copy** is enabled by default.

For source-rig work, inspect first, then use an exact actor name to pick the
instance you want.
The character and its face or attachments can have different skeletons.
Matching bone counts alone don't mean two rigs are compatible. This tool
doesn't retarget animations to unrelated rigs.

**Check companion files** uses the same lookup as assembly without building
geometry. Installed LB3/LMSH1 archives are read-only; the addon's Python readers
decode requested companions into a cache outside the installation. No separate
extraction executable is needed for the supported archive layouts. Extracted
folders should contain uncompressed GHG/GSC, CD, TEX and NXG_TEXTURES companions.
See [archive loading](docs/ARCHIVE_ASSETS.md).

The companion report follows character definitions, active attachments and
declared costume texture references, including shared body models. Missing
files, conflicting matches and
unsupported definitions are reported separately. File presence does not prove
that its mesh, animation or shader can be reconstructed. The report also
records exact stage associations from the game registries, but does not
decode stage geometry. Assembly handles that separately.
The same check can run outside Blender:

```sh
python scripts/check_dependencies.py scene.CU3 --assets extracted-assets --game LB3 --report companions.json
python scripts/check_dependencies.py scene.CU3 --assets "path/to/installed-game" --game LB3 --cache "path/to/cache" --report companions.json
```

Choose a new report filename. The assembly mode embeds this dependency report
alongside its actual decoder/import results.

Static stage loading uses bounded native draw, matrix and material bindings.
Named-special draws are excluded so prop geometry is not blindly duplicated.
Visibility and render-pass semantics remain approximate, and the current
inspection light is not the game's lighting. Nested LED scenes, their props
and source lights still need reconstruction. See
[scene configuration and stage loading](docs/SCENE_CONFIGURATION.md).

Simple `replace_character` declarations now select the root actor's resource
before loading its definition. The Stark Tower intro, for example, selects
Tony Stark's intended outfit and hair through this mapping. Replacements
must be exact, unchained resource mappings; native rig compatibility checks
still apply. Other registry commands are retained as unapplied declarations.

Some files are control/audio-only parts with no actor records. For example,
LB3's base `15FORTRESS_INTRO_NXG.CU3` and `16GAME_OUTRO_NXG.CU3` contain no
actors; open their named A/B/etc. segments for character animation. A different
joint count means a different source skeleton is needed, rather than a failed
mesh import. Version 0.1.6 also fixes observed nine/ten-channel discrete outer
tracks that previously blocked the level-15 midtro and game-outro segment E.
Non-boolean control values remain unverified as visibility and are rejected.

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
  structural TFA CU3 22–27 and partial DCSV CU3 30 support.
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

## Later games and archive readers

All **426** extracted TFA CU3 files passed structural reading and Blender's
reference-inspection mode. Two private examples verify supported ANI-D motion
on source armatures only; they have no imported meshes, materials or source
cameras. ANI-E sampling, HGOL17 model binding and TFA scene assembly remain
disabled. See [TFA research](docs/TFA_RESEARCH.md).

Of **324 extracted DCSV CU3 files**, **297 parse structurally**. The remaining
27 fail explicit layout checks. Name-growth checks passed in all 216
actor-bearing files that parsed. **DCSV ANI-E animation playback, camera
decoding and rigid-object editing are deliberately disabled** until verified.
This isn't full DCSV cutscene import yet.

Standalone archive inventory tools are also included:

```sh
python scripts/archive_index.py path/to/GAME0.DAT output_folder
python scripts/archive_index.py path/to/GAME0.DAT output_folder --extract-cutscenes
python scripts/archive_index_cc4.py path/to/GAME4.DAT index.json
python scripts/archive_index_cc8.py path/to/GAME2.DAT tfa-index.json
```

The older `archive_index.py` utility covers LB3 `-6` and has a more limited
compression path than the addon's new companion loader. The CC4 and CC8 tools
inventory DCSV type `-12` and TFA type `-8` archives; they do not reconstruct
scenes. All remain read-only and do not download or run external extractors.

## Manual checks

No scheduled checks or CI are set up.

Version 0.1.9 packages the shared verified older LMSH1 static accessory readers
(unskinned MESH 161, DISP 16, UMTL 163, TXTS 0) and the UMTL 174 prefix fix.
Older shader Boolean semantics remain unresolved. This does not add ANI-E,
new supported games or exact stage/face rendering. Standalone BSA clip linking
belongs to character addon 0.4.2, not this cutscene operator.

The static-stage fixture now creates a hashed synthetic source in a new output
folder. Run it without game files from the repository root:

```sh
blender --background --factory-startup --python-exit-code 1 --python formats/cu3/scripts/check_stage_blender.py -- output/static-stage-check
```

For source-file name checks, run from `formats/cu3`:

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

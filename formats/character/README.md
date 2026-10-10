# TT Character and Animation Importer

Character 0.5.16 adds classic PC raw model inspection; CU3 0.1.25 adds a separate CU2 reference importer. These are incomplete inspection modes, not complete classic character or cutscene assembly. [Checks and remaining gaps](../../docs/COMPATIBILITY_EXPANSION_2026-10-09.md).

The latest build recovers verified additive reactor masks and untextured vertex-color glow for sampled LMSH1/LB3 layouts, plus Hulkbuster packed normals. Native glow intensity and metallic/environment shading remain incomplete. See [visual checks and remaining reports](../../docs/ISSUE_1_MINIFIGS.md).

A separate, lightweight Blender addon for observed PC **LMSH1 NXG** and
**LEGO Batman 3 DX11**, **The Hobbit NXG** and **LEGO Marvel's Avengers DX11** characters, plus a separate static **LEGO Fortnite** export profile. Version **0.5.16**, experimental.
It installs independently of the cutscene addon and needs no external extractor
for supported companions inside the installed game's archives.

## Install

**LB1 and TCS are separate inspection profiles.** They expose raw classic PC
GHG/GSC draws and native rigs, not fully assembled characters. Rigid attachments
can be hidden as unresolved, variants can overlap, shaders are approximate and
AN3 playback/native export are unavailable. See [classic instructions](../classic-pc/README.md#blender-inspection).

Download [the addon ZIP](../../builds/blender/TT_Character_Importer_0.5.16.zip).
In Blender 4.4+ open **Edit > Preferences > Add-ons > Install from Disk**, select
the ZIP and enable **TT Character and Animation Importer**. Expand its
preferences and set the matching game folder (or extracted asset folder).
An optional extraction cache must be outside the game installation.

The current build resolves the observed shared-body variant arrays, character-relative
texture paths and Avengers index extension. Nine complete character samples
were imported and rendered across the four native profiles; five character-specific
idle clips and native export checks also passed. These are sample checks, not
whole-roster fidelity certification. See the [recovery report](../../docs/RECOVERY_2026-10-07.md)
and [remaining visual reports](../../docs/ISSUE_1_MINIFIGS.md).

Version 0.5.9 fixes four shared import/preview defects: one missing vertex normal
no longer discards valid authored normals in the same part; facial asset names
are matched without a case distinction; declared loose animations retain their
same-directory scope across filename case changes; and explicit model files
outside the asset root reach the existing checked texture-companion lookup.
The native variant reader now selects the explicit full-detail base in the
supplied HGOL 10/16 model arrays, validating every rig's display/skin ownership.
The archive reader accepts the observed CC8 v1 pair of bounded ROTV tables while
retaining their opaque records. These changes have original-file, constructed
byte and Blender checks; they do not certify complete characters or in-game
fidelity. See [accuracy checks](../../docs/CHARACTER_ACCURACY_0.5.9.md).

Version 0.5.8 repairs missing import/preview setting definitions after an
in-session addon update, including issue #1's `tt_face_detail` exception.
Existing registered settings and values retained by Blender are preserved;
settings with no stored value use their documented defaults. The settings panel
offers **Restore missing settings**, and preview creation/application repairs
them automatically. This was checked with actual Blender 5.1.2 and 5.2.2 using
synthetic scenes; the reporter's original blend was not available.

The shared live face helper now processes `SpiderFace` with the same grouping
rule as composed previews. Material reports identify decoded CD fields and
native shader controls that were not applied, plus unbound normal declarations.
This does not implement native material remaps or prove the remaining named
faces correct. [Issue status](../../docs/ISSUE_1_MINIFIGS.md) separates these
fixes from the open reports. The [read-only inspectors](../../docs/DIAGNOSTIC_TOOLS.md)
can collect evidence even when skeleton ownership blocks a full import.

For **LEGO Fortnite**, select the installation or `FortniteGame/Content/Paks`
folder. The optional separately built Unreal extraction bridge indexes it and
extracts selected outfits into a separate cache in the background. Existing
exported JSON/PNG/GLB libraries also work without an extractor. No external
reader, mappings, keys or proprietary runtime is bundled. This profile has no
animations or native export. See [Fortnite setup and limits](../fortnite/README.md).
Version 0.5.2 follows declared recipe head materials, handles the verified
standard-head color selector, retries incomplete installed-mode exports and
deduplicates archive discovery. Its static preview button creates a separate
scene. The [broader Fortnite audit](../../docs/FORTNITE_IMPORT_AUDIT.md) separates
successful sample imports from unsupported layouts.

Version 0.5.3 corrects Avengers texture references, native alpha cutouts and
facial preview pass separation. Verified packed normal maps now also work on
selected Hobbit and LB3 layouts, including their packed UV channels. Reimport
to apply the changes and create a fresh preview scene. See the
[face accuracy checks and remaining limits](../../docs/FACE_ACCURACY_0.5.3.md).

## Import a character

Version 0.5.7 adds shared-source conflict rejection, verified staged output,
strict resource identity, bounded archive/DDS reads and raw skin-weight
diagnostics. Normal-helper availability is visible in preview diagnostics.
These are safety and validation improvements within the existing format gates;
new original-file and in-game verification remain local follow-up work. See
[validation review](../../docs/MERGE_PACKET_REVIEW_2026-10-06.md) and
[next steps](../../docs/ROADMAP.md).

Version 0.5.6 preserves attachment texture dependencies when an optional import
fails and records consumed companion revisions for native export. Changed
CD/TEX/AS/loaded AN4/PAK files now stop export before output is created. Older
imports need reimporting to establish these baselines. See the
[support notes](../../docs/SUPPORT.md).

Version 0.5.5 preserves authored normals through facial preview helpers and
corrects the verified LMSH1 base-head printing layout. Expand **TT Character >
Import and preview settings** for mesh/costume options and viewing-copy controls.
**Highest detail** is the default for verified native LODs. Create a preview,
adjust normal strength, clipping quality or display options there, then press
**Apply preview settings**. Reimport for mesh/costume changes. See
[shading, quality settings and limits](../../docs/SHADING_AND_QUALITY.md).

Version 0.5.4 adds shared structural validation and detected-layout information
to each model's import report. See the
[report fields and limits](../../docs/STRUCTURAL_COMPATIBILITY.md).

The easiest route is **3D View > N sidebar > TT Character**: select the game,
set its folder, press **Browse game characters**, and search for a character. Supported companions are read into a separate cache automatically.
The browser lists minifig, small, bigfig and creature CD resources; individual
props/attachments use the file importer below. Some listed definitions may still use unsupported layouts.
The classic LB1/TCS profiles instead browse GHG files beneath `CHARS`; they do
not use modern CD definitions. Read their separate inspection instructions above.

For an already extracted file:

1. Use **File > Import > LEGO Character / Model (.cd/.ghg/.gsc)**.
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

**0.4.3 fixes far-distance hair/hat LOD selection and LMSH1 arm print UVs.**
Native accessory LOD tables now select their nearest detail clip. The verified
LMSH1 shared-arm layout uses UV0 for costume printing; other mappings retain
their existing coordinates. Reimport with the new ZIP to rebuild these parts.
Authored normals and split vertices remain intact. See the
[issue #1 patch notes](../../docs/ISSUE_1_MINIFIGS.md) for checks and unresolved
head/face, mirroring and shading reports.

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
preview still approximates the game shader and cannot reconstruct missing or
unsupported expression tracks. Both preview choices preserve the original scene and native meshes.

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
Supported standalone AN4 facial BSA tracks now drive the imported
`TT_Target_###` shape keys alongside the clip. This requires a unique matching
face actor, a verified 53-channel ANI-D block and matching duration (one extra
end sample is accepted without stretching time). Numeric native target IDs
are preserved. Unknown layouts and ambiguous matches are reported. A clip
without a face track returns those keys to Basis rather than retaining the
previous expression. Reimport and reload your clips with 0.4.2 to add these
links; an older blend is not upgraded automatically.

To inspect a static target, select a face mesh and open **Object Data
Properties > Shape Keys**. Adjust one `TT_Target_###` value from zero, then
return it to zero. Select a clip without facial tracks or temporarily unlink
the mesh's shape-key action first; active facial keyframes otherwise override
manual values. Targets have numeric IDs, not verified expression names.
Composed preview is still needed to assess depth-mask rendering.
Events, audio, IK and gameplay transitions are not fully reproduced.

## Export loose native files

Version 0.5.7 groups all imported instances by canonical source path. Identical
proposed payloads produce one output file. Divergent proposals, including one
edited and one unchanged instance, reject the entire export with the source and
instance names before output is published.

The complete bundle is staged in a private sibling directory, reread and checked
against its SHA-256 inventory and manifest, then published only if the chosen
destination is still absent. Existing files, folders and symbolic links are
never replaced. A failed write removes only this operation's staging directory;
a second export can retry at the same unused destination. Publication uses the
platform's exclusive rename primitive on the same filesystem; it does not
promise cross-filesystem atomicity or survival of sudden power loss.

Select the character and use **Export loose native files / supported edits**.
Choose a fresh folder outside the installed game and extraction cache. This
writes native model files, character definitions, texture companions and the
original sources for catalog animations you loaded. It preserves their
relative folders and produces `TT_Source_Export.json`. **It never writes DATs.**

Existing `TT_Target_###` face coordinates can be written into supported GHG
payloads. Keep the original Basis, topology, target names and vertex order.
Edits that require splitting a native repeated-offset run are rejected.
A no-op face export preserves the original file bytes exactly. Face-target
writing is gated to the verified MESH 169/170/175 layouts. Version 0.4.1 enables
the observed Hobbit MESH 170 targets after bounded mesh and target checks.

Version 0.4.1 can also write existing **positions, UVs and SourceColor vertex
colors** into verified MESH 169/170/175 buffers. Work in Edit Mode on the original
mesh, preserving vertex order and triangles. Position edits must stay within
the original part's bounds. Facial Basis positions stay immutable. Keep one UV
per native vertex: new UV seams requiring vertex splits are rejected. Shared
display copies must agree; the report lists any other parts affected by shared
buffer edits. A no-op export keeps the exact original bytes.

Existing native **normals and skin weights** can now be edited too. Keep one
normal per native vertex; corner splits needing new vertices are rejected.
Normal padding stays intact. Weight Paint edits must be normalized, use at most
four influences, and reference only bones already in that part's native palette.
The verified byte weights keep a total of 255. Rigid joint reassignment, new
palette bones, changed rest bones and conflicting shared buffers are rejected.
Reimport with the current build to establish normal/material baselines and rigid bindings;
older saved imports do not contain those new validation fields.

Object placement, evaluated modifiers, topology, new skin palettes, material
node graphs and skeleton changes are not encoded. Native bounds are retained,
not rebuilt. Texture companions are copied; this is not a Blender image encoder.
This remains a constrained writer, not arbitrary Blender-to-game serialization.

Version 0.4.2 also reads the verified **unskinned MESH 161 static LMSH1 GSC**
accessories, DISP 16, UMTL 163 and TXTS 0, restoring attachments such as
Magneto's helmet. It fixes the two-byte UMTL 174 prefix mismatch that rejected
other accessories. Texture IDs, UVs and render footers are decoded, but the
older shader Boolean meanings remain unresolved and shading is approximate.
Skinned or morph-bearing MESH 161 files are rejected. The new 161 writer check
covers a constructed UV edit; actual helmet validation covers byte-identical
no-op export/reimport, not edited-file gameplay.

Material node changes, painted/replaced Blender images and edited loaded clips
now stop a source-bundle export instead of being silently copied as originals.
Native material/texture encoding is unfinished. Export the model bundle before
editing clips, then use the separate active AN4 exporter for supported animation
edits. That writer does not repack a PAK bank or preserve unsupported events.
Version 0.4.2 additionally detects edits to the linked facial and attachment
actions created by this version. Neither exporter writes their edited BSA or
attachment curves; export is rejected rather than silently losing those edits.
Unchanged linked tracks keep their original native bytes. Older clip imports
lack these companion fingerprints; reimport to establish them.

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

Version 0.4.1 fixes custom-normal setup order, adds constrained normal/skin
weight writing, and detects unsupported material/image edits in native exports.
Normal and weight changes were exported and reimported for one character per
enabled game. A static Avengers GSC normal edit also passed. Hobbit MESH 170
face targets passed decoded edits on 48 cached face assets. No new in-game
validation or general mesh/material/skeleton encoder is implied.

Version 0.4.2 restores verified older LMSH1 static accessories, corrects UMTL
174 texture alignment and plays supported standalone facial BSA tracks when
switching clips. Magneto's helmet, face and cape were checked with three idle
clips. Facial sampling checks also cover Wolverine, B66 Catwoman, Bilbo and
Captain America. See [compatibility](COMPATIBILITY.md) for scope and failures.

Version 0.5.15 retains facial and attachment animation bindings through repeated
preview copies. Clip changes in the viewing scene leave the source character
unchanged. Native facial shaders and expression fidelity remain approximate.

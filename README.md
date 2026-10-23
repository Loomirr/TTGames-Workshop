# TTGames Workshop

Tools for bringing supported LEGO game models and animations into Blender,
inspecting game files, and making limited edits back to game formats.

## Download and install

Choose your game below. Click **Download ZIP**, then the **Download button
(down-arrow icon) at the top right** of GitHub's file view. Keep the ZIP zipped.

| What you want to open | Download | First steps |
| --- | --- | --- |
| LEGO Star Wars 1, PC — models | [Download ZIP · 0.1.10](builds/blender/lsw1_hgp_importer-0.1.10.zip) | [Install and import](formats/hgp/lsw1/README.md) |
| LEGO Star Wars II, PC — models and animations | [Download ZIP · 0.2.1](builds/blender/io_lsw2_hgp-0.2.1.zip) | [Install and import](formats/hgp/lsw2/README.md) |
| The Complete Saga / LEGO Batman 1, PC — models and rigs; no animation playback | [Download ZIP · 0.5.31](builds/blender/TT_Character_Importer_0.5.31.zip) | [Import classic models](formats/character/README.md#lego-batman-1-and-the-complete-saga) |
| LEGO Batman 2 / Marvel Super Heroes / Batman 3 / The Hobbit / Marvel's Avengers, PC — characters and supported animations | [Download ZIP · 0.5.31](builds/blender/TT_Character_Importer_0.5.31.zip) | [Install and import](formats/character/README.md) |
| Marvel Super Heroes / Batman 3, PC — cutscenes, with missing features | [Download ZIP · 0.1.37](builds/blender/TT_Cutscene_Importer_0.1.37.zip) | [Install and import](formats/cu3/README.md#blender-addon) |

In Blender, go to **Edit > Preferences > Get Extensions**, click the **drop-down
arrow at the top right**, then select **Install from Disk** and choose the ZIP.
Enable the addon under **Add-ons**, then go to **File > Import**. For Star Wars
1 and II, you can also drag the ZIP into the Blender window to install it.

Star Wars 1 and II need **Blender 4.2+**; the other downloads need **4.4+**.
The two model rows using version 0.5.31 share one download, listed in Blender
as **TT Character and Animation Importer**. Install it once and choose your game.

Need a different tool? See [all downloads, including face and texture tools](builds/README.md).
For other games, check [game and file support](#game-and-file-support).
See [viewing and editing animations](docs/ANIMATION_SUPPORT.md) before choosing
an animation workflow.

For **creating characters in the PC versions of The Complete Saga, LEGO Batman 1
or LEGO Indiana Jones 1**, [BactaTank Classic](https://github.com/AlubJ/BactaTank-Classic)
is a better starting point than Workshop's inspection tools. Follow that
project's instructions for its supported editing workflow. Workshop does not
currently export edited classic GHG models.

## Using the tools

The Character addon can open a supported character definition (`.cd`) to find
its model, costume and attachments. It can also open supported model files
(`.ghg` and model `.gsc`) directly. Opening a model alone is useful for inspecting
one part; it may not include the character's full costume or attachments.
See [which input to choose](formats/character/README.md#import-a-character).

Each tool works separately. The Character addon does not require the CU3 addon;
the desktop utilities do not require Blender. There is no single installation
that enables every file type. The [combined toolbox](tools/WORKSHOP_GUI.md) is
optional.

Before editing a character, check the [export limits](docs/CHARACTER_EDITING.md).
Most supported modern games allow edits to existing vertices and face shapes,
not arbitrary new meshes, bones or materials. Exports use separate files and
do not modify the installed game automatically.

## Game and file support

Choose by **game and platform first**. The families often called Early Classic,
Classic, NXG, DX11 and NTT help describe the files, but do not guarantee support.
A `.ghg` or `.cu3` from one game may have a different layout in another.
See [how the format families relate to the downloads](builds/README.md#game-families).

This table describes available workflows, not a promise that every character
works. **Partial import** means Blender assembly with known gaps.
**Inspection** means viewing model data or file references without a complete
character or scene. **Experimental export** still needs in-game testing.

Every game also has separate completion targets for [1:1 shaders, faces, facial
animation and native facial/material export](docs/VISUAL_AND_FACE_COVERAGE.md).
These targets do not imply those features already work.

| Game / platform | File types covered | What works here |
| --- | --- | --- |
| LEGO Star Wars: The Video Game (2005), PC | HGP | [Separate LSW1 addon](formats/hgp/lsw1/README.md): models, rigs and textures, including observed vehicle files. No game-format export. |
| LEGO Star Wars II: The Original Trilogy, PC | HGP, AN3, CU2, DAT | [Separate experimental LSW2 addon](formats/hgp/lsw2/README.md): models, rigs, textures, face shapes and animation import. HGP export allows new bones and parts; original-file retesting and in-game export checks are pending. [Other file tools](games/lsw2/README.md). |
| LEGO Star Wars: The Complete Saga, PC | GHG, GSC, CU2, AN3, GIZ, DAT | [Classic inspection](formats/classic-pc/README.md): models, rigs, textures and static cutscene references. A matching character TXT can choose visible layers. Full character assembly, animation playback and game-format export are incomplete. The local test installation includes mods. |
| LEGO Batman (2008), PC | GHG, GSC, CU2, AN3, GIZ, DAT | [Classic inspection](formats/classic-pc/README.md): models and static cutscene references, from installed or extracted files. No complete character assembly, animation playback or game-format export. |
| LEGO Indiana Jones 1, PC | GHG, GSC, CU2, AN3, GIZ | [Classic inspection tools](formats/classic-pc/README.md) for matching layouts. No local game validation yet. |
| LEGO Indiana Jones 1, Xbox 360 prototype | GHG, GSC, TEX, FNT, DDS | [Texture extractor](formats/nu20/lij1-xbox360/README.md), not a character mesh importer. |
| LEGO Batman 2, PC | CD, GHG, model GSC, AN4, DAT | Experimental [characters](docs/LB2_CHARACTERS.md), [body animation](docs/LB2_ANIMATION.md) and [facial animation](docs/LB2_FACES.md). Materials, cutscenes and export remain incomplete. |
| LEGO Marvel Super Heroes, PC | CD, GHG, model GSC, AN4, CU3, DAT | [Character addon](formats/character/README.md): partial characters and supported animations. [CU3 addon](formats/cu3/README.md): partial cutscenes. Limited model edits and experimental AN4 export. |
| LEGO Batman 3, PC | CD, GHG, model GSC, AN4, CU3, DAT | [Character addon](formats/character/README.md): partial characters and supported animations. [CU3 addon](formats/cu3/README.md): partial cutscenes. Limited model edits and experimental AN4 export. |
| LEGO The Hobbit, PC | CD, GHG, model GSC, AN4, DAT | [Character addon](formats/character/README.md): partial characters, supported animations and limited export. Full cutscene assembly is not enabled. |
| LEGO Marvel's Avengers, PC | CD, GHG, model GSC, AN4, DAT | [Character addon](formats/character/README.md): partial characters, supported animations and limited export. Full cutscene assembly is not enabled. |
| LEGO Star Wars: The Force Awakens, PC | DAT/HDR, CU3 and referenced model/animation files | [Archive tools](docs/ARCHIVE_COMPATIBILITY_2026-10-15.md) and [cutscene reference inspection](formats/cu3/README.md). No full character assembly or animation playback. |
| LEGO DC Super-Villains, PC | DAT/HDR, CU3 and referenced model/animation files | [Archive tools](docs/ARCHIVE_COMPATIBILITY_2026-10-15.md), cutscene reference inspection and [skeleton-transfer research](docs/SKELETON_TRANSFER.md). No general character importer/exporter. |
| LEGO Marvel Super Heroes 2, PC | DAT/HDR, CD, GHG, AN4 | [Archive inspection/extraction](docs/ARCHIVE_COMPATIBILITY_2026-10-15.md) for supported compression types. Later character definitions and animation layouts are incomplete; no complete character importer. |
| LEGO The Lord of the Rings, PC | DAT, CD, GHG, AN4 | [Archive and character inspection](formats/character/COMPATIBILITY.md). Sample model versions are outside the full character importer. |
| The LEGO Movie Videogame, PC | DAT | [Archive index tools](docs/COMPATIBILITY_EXPANSION_2026-10-09.md). Character and cutscene assembly are not enabled. |
| LEGO Star Wars III, PC | DAT | [Archive index tools](docs/COMPATIBILITY_EXPANSION_2026-10-09.md). Character and cutscene files remain unverified. |
| LEGO Jurassic World, PC | DAT research | Unresolved archive indexes; no supported character workflow yet. |
| LEGO Star Wars: The Skywalker Saga, PC | DAT research | Archive and character layouts remain unverified. |
| The LEGO Ninjago Movie Videogame / LEGO Dimensions | Ninjago DAT/HDR; selected GHG and AN4 files | [Ninjago archive indexes](docs/ARCHIVE_COMPATIBILITY_2026-10-15.md) and [skeleton-transfer diagnostics](tools/skeleton_transfer/README.md). No general game importer/exporter. |
| LEGO Marvel Super Heroes: Universe in Peril, Nintendo 3DS | BTGA, FUSE | [Texture and file tools](formats/btga/3ds/README.md). No full character or animation importer. |
| LEGO Fortnite | Exported JSON, GLB, PNG; optional Paks extraction | [Static character profile](formats/fortnite/README.md). An external tool is needed for Paks extraction. No animation or game-format export. |

Games often reuse file extensions while changing the contents. Choosing a
similar game in the importer does not make an unsupported file compatible.
For exact file versions and known omissions, see the linked component pages
and [support notes](docs/SUPPORT.md).

## Research and detailed reports

Development follows **Early Classic → NXG → DX11 → NTT → Classic**.
LSW1 PC is the active starting point; no era is complete. See the
[project-wide completion criteria and current gaps](docs/ERA_DEVELOPMENT.md).

These pages are for investigating bugs or developing support; they are not
required reading for a first import.

- [Game index](games/README.md), [format index](formats/README.md) and [project layout](docs/LAYOUT.md).
- [Current priorities](docs/ROADMAP.md) and [character editing/export limits](docs/CHARACTER_EDITING.md).
- [Import and preview quality settings](docs/SHADING_AND_QUALITY.md).
- [October 19 importer review](docs/PR_REVIEW_2026-10-19.md), [LSW1 feedback](docs/LSW1_FEEDBACK_2026-10-20.md) and [remaining minifigure issues](docs/ISSUE_1_MINIFIGS.md).
- [Figure Forge and fork review](docs/FIGURE_FORGE_REVIEW_2026-10-20.md) and [community reference review](docs/RESEARCH_REFERENCES_2026-10-07.md).
- [Skeleton transfer work](docs/SKELETON_TRANSFER.md), [validation review](docs/MERGE_PACKET_REVIEW_2026-10-06.md) and [earlier tool review](docs/TOOL_REVIEW_2026-10-05.md).
- [TCS scripting guide](games/tcs/scripting/README.md): character definitions, scripts and game limits; no script compiler is included.

## Contributing

Maintained by Loomirr and contributors. AI helped with code, research and documentation.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, tests and pull requests.
You can help by reporting a reproducible problem, checking a model in-game,
or improving documentation; coding experience is not required for a useful
bug report. Include the game, tool version, file name, expected result and what
actually happened. Do not upload game assets to the repository.

[AGENTS.md](AGENTS.md) contains coding instructions. The
[AI contribution guide](docs/AI_CONTRIBUTING.md) includes task prompts; a
repository link alone does not tell an assistant what to work on or give it
access to your game files.

Existing component licenses stay with their folders. See
[licensing and credits](docs/LICENSING.md). This is not an official LEGO,
TT Games, Lucasfilm, Marvel, DC or Epic Games project.

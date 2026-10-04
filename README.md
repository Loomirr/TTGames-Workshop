# TTGames Workshop

A place for our TT Games / LEGO game file format research, Blender importers,
texture readers and other reusable modding tools. Everything lives in one repo,
with each game and format keeping its own notes and instructions.

**AI was used to help with this project's code, research and documentation,
including assistance from 6.1sol.** Maintained by Loomirr and contributors.

This first version brings together our existing projects. Some tools are ready
to use for specific formats; others are still research scripts. Support for one
game does not mean support for every TT game that uses the same extension.

## Start here

| Area | What is here | Current status |
| --- | --- | --- |
| [CU3 cutscenes](formats/cu3/README.md) | Blender addon, name editor, source animation, face target editing and render helpers | 0.1.5 source; experimental LMSH1/LB3 support, partial DCSV structure |
| [LSW1 HGP models](formats/hgp/lsw1/README.md) | Character meshes, native skeletons, corrected palette colors, textures, face alpha and normal maps | 0.1.3; original 2005 PC game only |
| [LIJ1 Xbox 360 prototype textures](formats/nu20/lij1-xbox360/README.md) | Drag-and-drop Windows DDS extractor and format notes | 0.1.1; alternate descriptors and bounded legacy icon recovery |
| [LMSH1 AN4 animation](formats/an4/lmsh1/README.md) | Scalar decoder, corrected rotation sampler and experimental BVH export | Observed ANI-D layouts and original Marvel rig |
| [3DS BTGA / FUSE](formats/btga/3ds/README.md) | PICA texture decoding, PNG/DDS export and FUSE payload reader | Universe in Peril USA build research |

See the [game index](games/README.md), [format index](formats/README.md),
[support notes](docs/SUPPORT.md), [project layout](docs/LAYOUT.md) and
[next steps](docs/ROADMAP.md).

## Using the tools

Ready-to-use packages are in [builds/](builds/README.md), with download and
installation notes. The packages contain only our tools and their licenses.

Each folder has its own requirements and commands. There is no single install
that enables everything. Blender addons are built from their own folders;
Python tools and the .NET extractor run separately.

You supply your own extracted game files. Game meshes, textures, audio, full
Blender scenes, archive keys and proprietary runtimes are not in Git. On the
research workstation those files live under ignored `local/`; see
[the local workspace guide](docs/LOCAL_WORKSPACE.md).

Character-specific experiments, suit profiles, LOTDK texture mapping and
Fortnite research are also kept local. This repo focuses on reusable TT file
format tools and importers, rather than character projects.

## Contributing

Keep original inputs intact and make edited copies. Include the exact game,
platform, file version and what was checked when adding support. Preserve
native skeletons and source data, and clearly label guessed or approximate
rendering. More samples help, especially when a file is rejected by the reader.

Existing component licenses stay with their folders. See
[licensing and credits](docs/LICENSING.md). This repo is not an official LEGO,
TT Games, Lucasfilm, Marvel, DC or Epic Games project.

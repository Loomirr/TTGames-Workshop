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

**Current candidates:** Character **0.5.16**, CU3 **0.1.25**. This pass adds
classic PC model inspection, CU2 reference scenes and explicit older DAT layouts.
See [validation and remaining gaps](docs/COMPATIBILITY_EXPANSION_2026-10-09.md).

## Game and file support

This lists the file families covered by Workshop, not every extension shipped
with each game. **Partial import** means usable Blender assembly for supported
layouts with known omissions. **Inspection** reads data or references without
building the complete model/scene. No row means every asset in that game is verified.

| Game / platform | File types | Support and how to use it |
| --- | --- | --- |
| LEGO Star Wars: The Video Game (2005), PC | HGP | [HGP addon](formats/hgp/lsw1/README.md): models, native rigs and textures; some headers remain unsupported. Does not cover LSW2/TCS. |
| LEGO Star Wars: The Complete Saga, PC | DAT -3; NU20 GHG/GSC; CU2, AN3, GIZ | [Classic inspection](formats/classic-pc/README.md): raw models/rigs/textures in the character addon; CU2 static references in the cutscene addon; AN3/GIZ CLI inspection. Rigid attachments, costume selection, native shaders and animation playback remain incomplete. Installed tree has local mods. |
| LEGO Batman (2008), PC | DAT -2; NU20 GHG/GSC; CU2, AN3, GIZ | Same [classic inspection](formats/classic-pc/README.md), with installed-DAT or extracted character browsing. Raw Blender models and CU2 reference scenes have explicit omissions; no complete character/cutscene or AN3 playback claim. |
| LEGO Indiana Jones 1, PC | CU2, AN3, GIZ; NU20 GHG/GSC | Same [classic inspection tools](formats/classic-pc/README.md) for reported matching layouts. **No local game validation yet.** Separate from the Xbox prototype. |
| LEGO Indiana Jones 1, Xbox 360 prototype | GHG, GSC, TEX, FNT, DDS | [DDS extractor](formats/nu20/lij1-xbox360/README.md): supported tiled texture allocations, mips and cubemaps. Does not import character meshes. |
| LEGO Marvel Super Heroes, PC | CD, GHG/model GSC, AN4, CU3, DAT | [Character addon](formats/character/README.md): partial models/materials and supported animations; installed or extracted inputs. [CU3 addon](formats/cu3/README.md): partial scene assembly for v16/17/18, with separate camera/track gates. [AN4 CLI](formats/an4/lmsh1/README.md): scalar/BVH research. |
| LEGO Batman 3, PC | CD, GHG/model GSC, AN4, CU3, DAT | [Character addon](formats/character/README.md): partial import/playback; [CU3 addon](formats/cu3/README.md): partial v19 scene assembly. Packed and extracted inputs; native shader/scene gaps remain. |
| LEGO The Hobbit, PC | CD, GHG/model GSC, AN4, DAT | [Character addon](formats/character/README.md): partial import/playback for gated layouts, packed or extracted. Complete cutscene assembly is not enabled. |
| LEGO Marvel's Avengers, PC | CD, GHG/model GSC, AN4, DAT | [Character addon](formats/character/README.md): partial import/playback, packed or extracted. Observed CC8 archive variant supported; complete cutscene assembly not enabled. |
| LEGO Star Wars: The Force Awakens, PC | DAT/HDR (CC8), CU3, GHG/AN4 references | [Archive diagnostics](docs/DIAGNOSTIC_TOOLS.md) and [CU3 reference inspection](formats/cu3/README.md). ANI-E playback, full characters and full scenes are not enabled. |
| LEGO DC Super-Villains, PC | DAT/HDR (CC4), CU3, GHG/AN4 references | [Archive diagnostics](docs/DIAGNOSTIC_TOOLS.md), CU3 inspection and limited [skeleton-transfer research](docs/SKELETON_TRANSFER.md). Not a complete character/scene importer or general native exporter. |
| LEGO Marvel Super Heroes 2 / LEGO The Lord of the Rings, PC | DAT, GHG/AN4 references | [Version-gated archive/character inspection](formats/character/COMPATIBILITY.md). No complete character importer; unsupported compression/animation layouts remain refused. |
| The LEGO Movie Videogame, PC | DAT parent -5; character/cutscene payloads unverified | [PC DAT index GUI/CLI](docs/COMPATIBILITY_EXPANSION_2026-10-09.md): checked paths and file spans. No character or cutscene assembly yet. |
| LEGO Batman 2 / LEGO Star Wars III, PC | DAT -4; character/cutscene payloads unverified | [PC DAT index GUI/CLI](docs/COMPATIBILITY_EXPANSION_2026-10-09.md): checked paths and file spans for installed archives. Does not enable Blender character/animation import. |
| LEGO Jurassic World, PC | DAT parent -7 observed | Diagnostic research only; unresolved hashes and trailing index tables remain refused. |
| LEGO Star Wars: The Skywalker Saga, PC | Later DAT layouts observed | Diagnostic research only; archive and character layouts remain unverified. |
| The LEGO Ninjago Movie Videogame / LEGO Dimensions | Selected GHG / AN4 resources | [Skeleton-transfer diagnostics](tools/skeleton_transfer/README.md) and a private native weapon proof. No general game importer/exporter yet. |
| LMSH: Universe in Peril, Nintendo 3DS | BTGA, FUSE | [Texture / payload tools](formats/btga/3ds/README.md): PNG/DDS conversion and observed USA FUSE decoding; no full character/animation importer. |
| LEGO Fortnite | Exported JSON, GLB, PNG; optional Paks bridge | [Static character profile](formats/fortnite/README.md) in the character addon. External Unreal runtime required for Paks extraction; no animation support and incomplete native shaders. |

Other installed games and handheld editions do not gain importer support merely
because their files share these extensions. Unlisted layouts remain unverified.

**Editing/export:** enabled TT character profiles can write constrained edits
back to matching loose source files. General topology, material, skeleton and
cross-game animation export is not complete. CU3 name editing and face-target
writing have separate hash/layout guards; see [support notes](docs/SUPPORT.md).

See the [game index](games/README.md), [format index](formats/README.md),
[support notes](docs/SUPPORT.md), [project layout](docs/LAYOUT.md) and
[next steps](docs/ROADMAP.md).
The [skeleton transfer planner](tools/skeleton_transfer/README.md) adds
read-only rig/mapping/AN4 checks, item action diagnostics and a rest-relative rotation API. See the
[cross-game transfer pipeline](docs/SKELETON_TRANSFER.md) for the private native
proof, validation stages and remaining export limits.
The [validation review](docs/MERGE_PACKET_REVIEW_2026-10-06.md) records
this implementation pass and its validation limits. The
[BactaTank interoperability study](docs/BACTATANK_INTEROP.md) describes a possible
independent `.bmesh` export path; no BactaTank exporter is enabled yet.
The [latest tool review](docs/TOOL_REVIEW_2026-10-05.md) records the checks,
current limitations and priorities across the components.
The [community reference review](docs/RESEARCH_REFERENCES_2026-10-07.md) records
independent material/face/archive checks and separates external project claims
from our validated coverage. That research review copied no external implementation.
The separate [classic PC contribution](formats/classic-pc/README.md) retains its MIT attribution.
The [minifigure issue patch notes](docs/ISSUE_1_MINIFIGS.md) cover the newer
accessory LOD and LMSH1 arm UV fixes, plus the remaining reported problems.

## Using the tools

Ready-to-use packages are in [builds/](builds/README.md), with download and
installation notes. The packages contain only our tools and their licenses.

Prefer browse buttons over commands? Pick a [separate GUI download](builds/README.md#separate-gui-downloads)
for texture conversion, animation export, archive indexes or face/cutscene
utilities. Each opens directly to its own tool with `Launch.pyw` and works
independently. Python 3.10+ with Tk is required; BTGA also needs Pillow.
The LIJ1 Windows extractor already has its own GUI. The combined
[toolbox](tools/WORKSHOP_GUI.md) remains optional.

Each folder has its own requirements and commands. There is no single install
that enables everything. Blender addons are built from their own folders;
Python tools and the .NET extractor run separately.

You supply your own game files. CU3 scene assembly accepts an installed LB3 or
LMSH1 game folder or an extracted asset tree alongside the selected CU3 file.
It loads supported actors and source cameras, with experimental static stage
geometry from declared level resources. Stage visibility, nested scenes,
props, original lighting, audio and effects still need work.
Game meshes, textures, audio, full Blender scenes, archive keys and proprietary
runtimes are not in Git. On the research workstation those files live under
ignored `local/`; see
[the local workspace guide](docs/LOCAL_WORKSPACE.md).

The character sidebar now exposes import and viewing-copy quality settings.
See [facial shading, head printing and highest-detail selection](docs/SHADING_AND_QUALITY.md)
for the latest corrections and remaining limits.

Character-specific experiments, suit profiles, LOTDK texture mapping and
historical Fortnite projects are also kept local. The reusable Fortnite profile
contains tool code only and keeps its external dependencies separate. This repo focuses on reusable TT file
format tools and importers, rather than character projects.

## Contributing

Keep original inputs intact and make edited copies. Include the exact game,
platform, file version and what was checked when adding support. Preserve
native skeletons and source data, and clearly label guessed or approximate
rendering. More samples help, especially when a file is rejected by the reader.

Existing component licenses stay with their folders. See
[licensing and credits](docs/LICENSING.md). This repo is not an official LEGO,
TT Games, Lucasfilm, Marvel, DC or Epic Games project.

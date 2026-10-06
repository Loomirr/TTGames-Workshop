# Download builds

These packages are built from our tools in this repository. Click a package
below, then use GitHub's **Download raw file** button to save the ZIP.

| Tool | Package | Use |
| --- | --- | --- |
| Character and animation importer 0.5.5 | [Blender addon ZIP](blender/TT_Character_Importer_0.5.5.zip) | LMSH1/LB3/Hobbit/Avengers plus static LEGO Fortnite Paks/export-library browsing; [instructions](../formats/character/README.md) |
| Original LSW1 HGP importer 0.1.3 | [Blender addon ZIP](blender/lsw1_hgp_importer-0.1.3.zip) | Native character meshes/rigs, corrected palette colors, textures, alpha and normals |
| CU3 importer 0.1.14 | [Blender addon ZIP](blender/TT_Cutscene_Importer_0.1.14.zip) | Supported LB3/LMSH1 actors, materials, cameras and experimental static stages, with shared older-accessory fixes; TFA/DCSV reference inspection |
| LIJ1 Xbox 360 prototype extractor 0.1.2 | [Windows x64 ZIP](windows/LIJ1_360_Texture_Extractor-0.1.2-win64.zip) | GHG/GSC/TEX/FNT/DDS inputs; cubemaps, BC5, float and legacy textures |

Only the newest version of each tool is kept in this download folder. Older
packages are archived locally; Git history remains available. Packaging scripts
apply this policy automatically. Checksums and sizes are in [manifest.json](manifest.json).

## Install

### Separate GUI downloads

Each ZIP below is independent. Extract it and open **Launch.pyw** to go straight
to that tool's window. Python 3.10+ with Tcl/Tk is required; only the BTGA tool
needs Pillow. These packages contain their own required Python backends, so
users do not need the toolbox, Blender, or a full repository checkout.

| GUI | Download |
| --- | --- |
| 3DS BTGA texture converter 0.1.2 | [ZIP](python/BTGA_Texture_Converter_GUI-0.1.2.zip) |
| LMSH1 AN4 decoder | [ZIP](python/LMSH1_AN4_Decoder_GUI-0.1.1.zip) |
| LMSH1 experimental BVH exporter | [ZIP](python/LMSH1_BVH_Exporter_GUI-0.1.1.zip) |
| CU3 dependency checker | [ZIP](python/CU3_Dependency_Checker_GUI-0.1.1.zip) |
| Face target decoder 0.1.2 (no extraction log needed) | [ZIP](python/Face_Target_Decoder_GUI-0.1.2.zip) |
| Face target writer | [ZIP](python/Face_Target_Writer_GUI-0.1.2.zip) |
| TFA archive index | [ZIP](python/TFA_Archive_Index_GUI-0.1.1.zip) |
| DCSV archive index 0.1.2 | [ZIP](python/DCSV_Archive_Index_GUI-0.1.2.zip) |
| CU3 name editor | [ZIP](python/CU3_Name_Editor_GUI-0.1.1.zip) |

The LIJ1 extractor above already has its own independent Windows GUI.
To rebuild these packages: `python tools/package_individual_guis.py`.

The Python GUI downloads are small source distributions, not self-contained
Windows EXEs. See each ZIP's README for its inputs, format limits and requirements.
The optional [combined toolbox 0.1.2](python/TTGames_Workshop_GUI-0.1.2.zip) is a separate
tool. The individual downloads above open directly to their own functions.

For the Blender ZIPs, open Preferences and **Install from Disk**, select the ZIP
and enable the importer. LSW1 requires Blender 4.2+; CU3 declares 4.4+. Both
were checked in Blender 5.2.2. Read the component docs for input requirements.

Character 0.5.5 and CU3 0.1.14 include the shared older-accessory reader fixes.
They also correct nearest-detail accessory LOD selection and LMSH1 arm print
UV choice; see [the partial issue #1 resolution](../docs/ISSUE_1_MINIFIGS.md).
The latest builds also preserve evaluated normals through supported Blender
facial helpers and correct verified LMSH1 head-print mapping. The character
sidebar exposes import and preview quality settings; see
[usage and limits](../docs/SHADING_AND_QUALITY.md).
Standalone facial clip linking is a character-addon feature. Face GUI 0.1.2
downloads retain their previously verified target layouts; they have not been
rebuilt with the new character/scene readers. The BTGA 0.1.2 and toolbox 0.1.2
downloads include the strict raw PICA payload-length checks.

CU3 now defaults to **Assemble available scene assets**. Select an extracted
CU3 file and choose its LB3/LMSH1 game folder once; the addon remembers a folder
for each game. Needed companions are cached outside the installation using
the addon's Python readers. **Recovered static environment (experimental)**
also defaults on, loading supported static geometry from declared level GSCs.
Stage visibility and render passes remain approximate; nested scenes, props,
original lighting, audio and effects remain incomplete. TFA reference
inspection does not import character meshes or materials.

For the Windows ZIP, extract it and run `LIJ1_360_Texture_Extractor.exe`, or
drag your files onto that EXE. It is unsigned and self-contained; no separate
.NET installation is needed. Its required framework licenses are included.

You supply your own game files. No package contains game models, textures,
audio, Blender scenes, character projects, LOTDK mapper, Fortnite tools or
external extraction programs. The Windows package contains our own EXE and
documentation/license notices. Dependencies built into that EXE are the
standard .NET Windows desktop runtime, not another game extraction tool.

## Build from source

Use the commands in each component README. To package our addons and an
already freshly published Windows extractor:

```sh
python tools/package_builds.py --blender path/to/blender --dotnet-root path/to/installed/dotnet
```

The script only picks the fixed extractor output from this repo's source build.
It does not collect external programs or game inputs. Source builds remain
available separately under `formats/`.

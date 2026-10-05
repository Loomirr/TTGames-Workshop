# Download builds

These packages are built from our tools in this repository. Click a package
below, then use GitHub's **Download raw file** button to save the ZIP.

| Tool | Package | Use |
| --- | --- | --- |
| Character and animation importer 0.1.0 | [Blender addon ZIP](blender/TT_Character_Importer_0.1.0.zip) | Independent LMSH1/LB3 character browser and CD/GHG/model GSC import, plus supported uncompressed AN4 actions; [instructions](../formats/character/README.md) |
| Original LSW1 HGP importer 0.1.3 | [Blender addon ZIP](blender/lsw1_hgp_importer-0.1.3.zip) | Native character meshes/rigs, corrected palette colors, textures, alpha and normals |
| CU3 importer 0.1.8 | [Blender addon ZIP](blender/TT_Cutscene_Importer_0.1.8.zip) | Supported LB3/LMSH1 actors, materials, cameras and experimental static stages; installed-game loading, live preview and face tools; TFA/DCSV reference inspection |
| LIJ1 Xbox 360 prototype extractor 0.1.2 | [Windows x64 ZIP](windows/LIJ1_360_Texture_Extractor-0.1.2-win64.zip) | GHG/GSC/TEX/FNT/DDS inputs; cubemaps, BC5, float and legacy textures |

Checksums and exact download sizes are in [manifest.json](manifest.json).

## Install

### Separate GUI downloads

Each ZIP below is independent. Extract it and open **Launch.pyw** to go straight
to that tool's window. Python 3.10+ with Tcl/Tk is required; only the BTGA tool
needs Pillow. These packages contain their own required Python backends, so
users do not need the toolbox, Blender, or a full repository checkout.

| GUI | Download |
| --- | --- |
| 3DS BTGA texture converter | [ZIP](python/BTGA_Texture_Converter_GUI-0.1.1.zip) |
| LMSH1 AN4 decoder | [ZIP](python/LMSH1_AN4_Decoder_GUI-0.1.1.zip) |
| LMSH1 experimental BVH exporter | [ZIP](python/LMSH1_BVH_Exporter_GUI-0.1.1.zip) |
| CU3 dependency checker | [ZIP](python/CU3_Dependency_Checker_GUI-0.1.1.zip) |
| Face target decoder | [ZIP](python/Face_Target_Decoder_GUI-0.1.1.zip) |
| Face target writer | [ZIP](python/Face_Target_Writer_GUI-0.1.1.zip) |
| TFA archive index | [ZIP](python/TFA_Archive_Index_GUI-0.1.1.zip) |
| DCSV archive index | [ZIP](python/DCSV_Archive_Index_GUI-0.1.1.zip) |
| CU3 name editor | [ZIP](python/CU3_Name_Editor_GUI-0.1.1.zip) |

The LIJ1 extractor above already has its own independent Windows GUI.
To rebuild these packages: `python tools/package_individual_guis.py`.

The Python GUI downloads are small source distributions, not self-contained
Windows EXEs. See each ZIP's README for its inputs, format limits and requirements.
The older combined toolbox 0.1.0 remains in the build archive; use the separate
downloads above for the current per-tool launchers.

For the Blender ZIPs, open Preferences and **Install from Disk**, select the ZIP
and enable the importer. LSW1 requires Blender 4.2+; CU3 declares 4.4+. Both
were checked in Blender 5.2.2. Read the component docs for input requirements.

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

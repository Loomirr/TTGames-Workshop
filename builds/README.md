# Download builds

These packages are built from our tools in this repository. Click a package
below, then use GitHub's **Download raw file** button to save the ZIP.

| Tool | Package | Use |
| --- | --- | --- |
| Original LSW1 HGP importer 0.1.3 | [Blender addon ZIP](blender/lsw1_hgp_importer-0.1.3.zip) | Native character meshes/rigs, corrected palette colors, textures, alpha and normals |
| CU3 importer 0.1.7 | [Blender addon ZIP](blender/TT_Cutscene_Importer_0.1.7.zip) | Experimental asset-folder scene assembly, companion-file checks, source animation and facial editing/render helpers; full cutscenes remain incomplete |
| LIJ1 Xbox 360 prototype extractor 0.1.2 | [Windows x64 ZIP](windows/LIJ1_360_Texture_Extractor-0.1.2-win64.zip) | GHG/GSC/TEX/FNT/DDS inputs; cubemaps, BC5, float and legacy textures |

Checksums and exact download sizes are in [manifest.json](manifest.json).

## Install

For the Blender ZIPs, open Preferences and **Install from Disk**, select the ZIP
and enable the importer. LSW1 requires Blender 4.2+; CU3 declares 4.4+. Both
were checked in Blender 5.2.2. Read the component docs for input requirements.

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

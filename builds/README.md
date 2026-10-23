# Downloads

Pick your game or task below. Click its ZIP link, then the **Download button
(down-arrow icon) at the top right** of GitHub's file view.

## Blender addons

Keep the ZIP zipped. In Blender, go to **Edit > Preferences > Get Extensions**,
click the **drop-down arrow at the top right**, then select **Install from Disk**.
Choose the ZIP and enable the addon under **Add-ons**. Star Wars 1 and II ZIPs
can also be dragged into the Blender window to install them.

The Star Wars 1 and II addons need Blender 4.2 or newer; the other Blender
downloads need 4.4 or newer. After installation, go to **File > Import**.
These steps follow Blender's [installation guide](https://docs.blender.org/manual/en/4.4/editors/preferences/extensions.html).

| Game or task | Download | What you can do / first steps |
| --- | --- | --- |
| LEGO Star Wars 1, PC | [Download ZIP · 0.1.10](blender/lsw1_hgp_importer-0.1.10.zip) | Import models, rigs, textures, facial shape keys and character layer lists. [Start here](../formats/hgp/lsw1/README.md). |
| LEGO Star Wars II, PC | [Download ZIP · 0.2.1](blender/io_lsw2_hgp-0.2.1.zip) | Import models, rigs, textures, face shapes and animations. Model export is experimental and needs in-game checks. [Start here](../formats/hgp/lsw2/README.md). |
| The Complete Saga / LEGO Batman 1, PC | [Download ZIP · 0.5.31](blender/TT_Character_Importer_0.5.31.zip) | Import models and rigs; costume assembly is incomplete. No animation playback or edited model export. [Start here](../formats/character/README.md#lego-batman-1-and-the-complete-saga). |
| LEGO Batman 2 / Marvel Super Heroes / Batman 3 / The Hobbit / Marvel's Avengers, PC | [Download ZIP · 0.5.31](blender/TT_Character_Importer_0.5.31.zip) | Import characters and view supported animations. Some parts and materials need work; export is limited. [Start here](../formats/character/README.md). |
| Marvel Super Heroes / Batman 3 cutscenes, PC | [Download ZIP · 0.1.37](blender/TT_Cutscene_Importer_0.1.37.zip) | Import supported actors, cameras and some stage geometry. Lighting, effects and other scene features remain incomplete. [Start here](../formats/cu3/README.md#blender-addon). |

The two model rows using version 0.5.31 share **TT Character and Animation
Importer**. Install it once, press **N** in the 3D Viewport, open **TT Character**,
and select your game. Its separate [LEGO Fortnite workflow](../formats/fortnite/README.md)
imports static models; a reported import failure is awaiting investigation.

Check the linked instructions for supported games and export limits. Opening a
model does not mean every part or animation can be exported back to the game.

## Game families

These labels help explain which tools belong together. Select the actual game
in Blender: support depends on its platform and file version too.

| Family | Where to start |
| --- | --- |
| Early Classic — LEGO Star Wars 1 and II | Separate addons above, because their HGP model layouts differ. |
| Classic — The Complete Saga, LEGO Batman 1, LEGO Indiana Jones 1 | TCS/LB1 model import is in the shared download above. For creating characters, start with [BactaTank Classic](https://github.com/AlubJ/BactaTank-Classic). Workshop also has [file inspection tools](../formats/classic-pc/README.md); Indiana Jones 1 has no locally validated Blender workflow here. |
| NXG — including Batman 2, Marvel Super Heroes and The Hobbit | Use the shared character download for those games. Other NXG games do not automatically work; consult [game support](../README.md#game-and-file-support). |
| DX11 — including Batman 3 and Marvel's Avengers | Use the shared character download for those two games. Later DX11 games such as DC Super-Villains do not yet have a complete character importer here. |
| NTT — The Skywalker Saga | No supported Workshop character importer or exporter yet. |

Games can mix families: Batman 3 uses DX11 models and NXG animations. Sharing a
download lets the tools reuse readers while keeping checks for each game and
layout. Separate era names alone would not make those files interchangeable.

## Other file tools

| Task | Download | Instructions |
| --- | --- | --- |
| Extract textures from LEGO Indiana Jones 1 Xbox 360 prototype files | [Windows x64 ZIP · 0.1.2](windows/LIJ1_360_Texture_Extractor-0.1.2-win64.zip) | [Texture extractor](../formats/nu20/lij1-xbox360/README.md) |
| Examine classic PC model, cutscene and animation data from a command line | [Python ZIP · 0.1.3](python/Classic_PC_Inspectors-0.1.3.zip) | [Classic file tools](../formats/classic-pc/README.md) |

## Separate GUI downloads

These tools run in their own window, outside Blender. Extract the ZIP and open
**Launch.pyw**. Most need Python 3.10 or newer with Tcl/Tk (included in the usual
The BTGA converter also needs Pillow.

| GUI | Download |
| --- | --- |
| 3DS BTGA texture converter 0.1.2 | [ZIP](python/BTGA_Texture_Converter_GUI-0.1.2.zip) |
| LMSH1 AN4 decoder | [ZIP](python/LMSH1_AN4_Decoder_GUI-0.1.2.zip) |
| LMSH1 experimental BVH exporter | [ZIP](python/LMSH1_BVH_Exporter_GUI-0.1.2.zip) |
| CU3 dependency checker 0.1.6 | [ZIP](python/CU3_Dependency_Checker_GUI-0.1.6.zip) |
| Face target decoder 0.1.4 (no extraction log needed; optional CLI summary) | [ZIP](python/Face_Target_Decoder_GUI-0.1.4.zip) |
| Face target writer 0.1.3 | [ZIP](python/Face_Target_Writer_GUI-0.1.3.zip) |
| TFA archive index 0.1.6 | [ZIP](python/TFA_Archive_Index_GUI-0.1.6.zip) |
| DCSV archive index 0.1.7 | [ZIP](python/DCSV_Archive_Index_GUI-0.1.7.zip) |
| PC DAT index 0.1.2 (nine explicit game profiles) | [ZIP](python/PC_DAT_Index_GUI-0.1.2.zip) |
| CU3 name editor | [ZIP](python/CU3_Name_Editor_GUI-0.1.1.zip) |

Each tool works by itself. The optional [combined toolbox](python/TTGames_Workshop_GUI-0.1.10.zip)
puts several utilities in one window, but is not required.

For the Windows extractor, extract its ZIP and run
**LIJ1_360_Texture_Extractor.exe**. It needs no separate .NET installation.
The Classic PC inspectors are command-line tools; use the Character addon
if you want to inspect supported classic models in Blender.

Only the newest download of each tool is shown.
[Checksums and sizes](manifest.json) are available for verification.

## Build from source

Use the commands in each component README. To package our addons and an
already freshly published Windows extractor:

```sh
python tools/package_builds.py --blender path/to/blender --dotnet-root path/to/installed/dotnet
```

Source code is under `formats/`. To rebuild the separate desktop tools, run
`python tools/package_individual_guis.py`.

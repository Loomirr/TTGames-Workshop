# LIJ1 Xbox 360 Prototype Texture Extractor

A small drag-and-drop tool for extracting DDS textures from the Xbox 360 LEGO Indiana Jones 1 prototype samples supplied for this project. Version **0.1.0**, Windows 10/11 x64.

## Use it

1. Build the source below, or use an existing private local build. This repository does not include a compiled EXE.
2. Drag `.GHG` / `.GSC` files onto `LIJ1_360_Texture_Extractor.exe`. You can drag several files or a folder at once.
3. The window shows the result for each input. Each gets a new `<filename>_DDS` folder beside it, with the textures and an `Extraction.json` manifest.

You can also open the EXE first and use the buttons or drop files into its window. Leave the output field empty for the default, or choose your own output folder. Folder drops scan subfolders, skipping directory links. If an output folder already exists, a numbered new folder is used.

The tool reads source files without modifying them. It does not download anything or contact a server. The executable includes its .NET runtime, so Python, Blender and a separate .NET install are not needed. It is an unsigned local build.

## What works so far

Tested against these two actual prototype files:

| File | DDS textures | Original mip levels |
| --- | --- | --- |
| `CAPTAIN_KATANGA_360.GHG` | 1024x1024 DXT1, 128x128 DXT1, 512x512 DXT5 | 11, 8, 10 |
| `ICON_ARMYINTELMAN_A_360.GSC` | 256x256 DXT5 | 9 |

These are extracted from the container's texture descriptors, untiled from the Xbox 360 GPU layout, byte-swapped and written as ordinary DDS. **The original compressed blocks and mipmaps are preserved, without recompression.** Alpha is retained. The output can include material masks or other maps as well as body/portrait colors; the extractor does not guess which map is which.

All four DDS files matched a separate Python implementation byte for byte. Pillow successfully decoded all 38 exported mip levels, and the main textures were checked visually. Tests also confirmed unchanged input hashes, numbered repeat outputs, failure on eight malformed/unsupported inputs, and continued extraction of good files in a mixed batch. Launching the GUI with an input path also produced the expected DDS. Explorer's physical drag gesture was not separately automated.

## Current limits

This is a working first version for the **observed prototype format**, not a converter for every TT game or every Xbox build. The parser accepts big-endian NU20 (`02UN`) containers with the observed 180-byte TST0 descriptors, resource flags and tiled packed-mip layout. It supports format codes **1 = BC1/DXT1** and **6 = BC3/DXT5**, power-of-two dimensions from 32 to 8192, and files up to 512 MiB. Both supplied samples use square textures. Rectangular textures follow the same Xbox layout equations but have not been tested on a game sample yet.

Other formats, layouts, flags, dimensions or descriptor structures are refused with an error instead of being guessed. More prototype files are needed to extend support. This does not export models, animations or game-ready replacement containers. Texture identifiers are retained in the JSON manifest; meaningful original texture names were not present in the parsed descriptors.

Conversion completes and validates before writing. An I/O interruption during saving can leave a `.lij1_partial_*` folder, which should not be mistaken for a completed export.

## Command line

```powershell
.\LIJ1_360_Texture_Extractor.exe --cli --out "C:\My DDS" "C:\My Prototype\CAPTAIN_KATANGA_360.GHG"
```

You can pass multiple input files/folders. Exit code 0 means all supplied inputs succeeded; 1 means at least one failed or no files were found; 2 means invalid/missing arguments. Omit `--out` to use folders beside the input files.

## Source and build

The included `Source` folder contains the complete C# parser, DDS writer and Windows Forms interface. Build with a .NET 10 SDK:

```powershell
dotnet publish .\Source\LIJ1TextureExtractor.csproj -c Release -o .\dist
```

`Research/probe.py` is the independent Python reference used during investigation. It is a sample-specific development check, not the end-user converter. `Tests/verify_samples.py` contains the regression checks. Both require Pillow and the two original files; the regression also requires a fresh `Tests/RunOutput` folder. To run them from the extracted package:

```powershell
python .\Research\probe.py "C:\My Prototype Samples"
python .\Tests\verify_samples.py "C:\My Prototype Samples"
```

The two game files themselves are not included. The separate sample DDS archive contains the exported results for inspection.

See `FORMAT.md` for the descriptor, byte order and mip-layout findings. Xbox tiling and packed-mip addressing were cross-checked against Xenia's public implementation; see `THIRD_PARTY_NOTICES.txt` for attribution. DDS headers follow Microsoft's DDS documentation.

AI was used to help investigate the samples, write this tool and check the outputs. It is not an official LEGO, Lucasfilm, TT Games or Microsoft tool. No game files are bundled with the tool.

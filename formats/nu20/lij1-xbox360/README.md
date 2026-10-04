# LIJ1 Xbox 360 Prototype Texture Extractor

A small drag-and-drop tool for extracting DDS textures from the Xbox 360 LEGO Indiana Jones 1 prototype samples supplied for this project. Version **0.1.1**, Windows 10/11 x64.

## Use it

Download [our Windows x64 build](../../../builds/windows/LIJ1_360_Texture_Extractor-0.1.1-win64.zip),
then extract it before running the EXE.

1. Extract the Windows package, or build the source below.
2. Drag `.GHG` / `.GSC` files onto `LIJ1_360_Texture_Extractor.exe`. You can drag several files or a folder at once.
3. The window shows the result for each input. Each gets a new `<filename>_DDS` folder beside it, with the textures and an `Extraction.json` manifest.

You can also open the EXE first and use the buttons or drop files into its window. Leave the output field empty for the default, or choose your own output folder. Folder drops scan subfolders, skipping directory links. If an output folder already exists, a numbered new folder is used.

The tool reads source files without modifying them. It does not download anything or contact a server. The executable includes its .NET runtime, so Python, Blender and a separate .NET install are not needed. It is an unsigned local build.

## What works so far

The original two samples remain verified:

| File | DDS textures | Original mip levels |
| --- | --- | --- |
| `CAPTAIN_KATANGA_360.GHG` | 1024x1024 DXT1, 128x128 DXT1, 512x512 DXT5 | 11, 8, 10 |
| `ICON_ARMYINTELMAN_A_360.GSC` | 256x256 DXT5 | 9 |

These are extracted from the container's texture descriptors, untiled from the Xbox 360 GPU layout, byte-swapped and written as ordinary DDS. **The original compressed blocks and mipmaps are preserved, without recompression.** Alpha is retained. The output can include material masks or other maps as well as body/portrait colors; the extractor does not guess which map is which.

All four DDS files matched a separate Python implementation byte for byte. Pillow successfully decoded all 38 exported mip levels, and the main textures were checked visually. Tests also confirmed unchanged input hashes, numbered repeat outputs, failure on eight malformed/unsupported inputs, and continued extraction of good files in a mixed batch. Launching the GUI with an input path also produced the expected DDS. Explorer's physical drag gesture was not separately automated.

Version 0.1.1 also verifies these five reported GSC files:

| File | DDS textures | Original mip levels |
| --- | --- | --- |
| `ICON_COLONEL_DIETRITCH_360.GSC` | 32x32 DXT1, 256x256 DXT5 | 1, 9 |
| `ICON_THUGGEE_SLAVEDRIVERCHIEF_360.GSC` | 32x32 DXT1, 256x256 DXT5 | 1, 9 |
| `ICON_ENEMY_GUARD_360.GSC` | 256x256 DXT5 | 9 |
| `ICON_ENEMY_PILOT_360.GSC` | 256x256 DXT5 | 9 |
| `INDIANAJONES_ICON_360.GSC` | 64x64 DXT5, recovered legacy layout | 7 |

These seven DDS files match an independent Python reference byte for byte;
Pillow decoded all 45 mip levels and the portraits were checked visually.
The two 32x32 textures are solid gray maps; their material purpose is unknown.
Repeat exports, input hashes, inconsistent secondary metadata rejection and
continued mixed-batch processing were also checked. All five GSCs match files
in the supplied March 20, 2008 prototype ISO byte for byte.

Across the ISO's **757 GHG/GSC containers**, the parser and converter accepted
**437 files, 2,898 textures and 24,609 stored mip levels**. The other 320 files
were refused, including empty texture chunks and unsupported dimensions,
formats, resource flags or container layouts. All 387 files accepted by 0.1.0
still produce byte-identical DDS output. This broad check validates parsing,
allocation bounds and compressed output; it is not a visual check of every
texture or in-game validation. No game files are modified by these checks.

## Current limits

This tool supports **observed prototype layouts**, not every TT game or Xbox
build. The parser accepts big-endian NU20 (`02UN`) containers with 180-byte TST0
descriptors and the verified tiled packed-mip layout. It supports format codes
**1 = BC1/DXT1** and **6 = BC3/DXT5**, power-of-two dimensions from 32 to 8192,
and files up to 512 MiB. Square and rectangular resources occur in the broad
parser/converter check; visual validation remains sample-specific.

Both the original layout flag 1 descriptors and observed layout flag 0
descriptors with matching secondary resource metadata are supported. The
observed 32x32, one-level BC1 allocation of 4 KiB is accepted explicitly.
Unknown duplicate fields or disagreements between descriptors remain errors.

The observed legacy Indiana Jones icon has inconsistent chunk lengths and
mixed-endian texture metadata. A separate, narrowly validated recovery path
uses its secondary payload pointer and checks the following chunk. Recovery
is reported in the window/CLI and `Extraction.json`; check those images.
Other malformed chunk chains are refused. The tool never searches arbitrary
file data for a texture signature or repairs the source container.

Other formats, layouts, flags, dimensions or descriptor structures are refused with an error instead of being guessed. More prototype files are needed to extend support. This does not export models, animations or game-ready replacement containers. Texture identifiers are retained in the JSON manifest; meaningful original texture names were not present in the parsed descriptors.

Conversion completes and validates before writing. An I/O interruption during saving can leave a `.lij1_partial_*` folder, which should not be mistaken for a completed export.

## Command line

```powershell
.\LIJ1_360_Texture_Extractor.exe --cli --out "C:\My DDS" "C:\My Prototype\CAPTAIN_KATANGA_360.GHG"
```

You can pass multiple input files/folders. Exit code 0 means all supplied inputs succeeded; 1 means at least one failed or no files were found; 2 means invalid/missing arguments. Omit `--out` to use folders beside the input files.

## Source and build

The repository's `Source` folder contains the complete C# parser, DDS writer
and Windows Forms interface. Build with a .NET 10 SDK:

```powershell
dotnet publish .\Source\LIJ1TextureExtractor.csproj -c Release -o .\dist
```

`Research/probe.py` is the original sample-specific Python reference, not the
end-user converter. `Tests/verify_samples.py` checks the original pair, and
`Tests/verify_variants.py` checks the five reported GSCs against independent DDS
references. Both regression scripts require Pillow, supplied files and a new
work directory. Keep game data and validation output under ignored `local/`.
To run the original regression from this component directory:

```powershell
python .\Tests\verify_samples.py "C:\My Prototype Samples" --work "C:\My New Validation" --reference "C:\My Reference DDS"
```

For the five GSCs, use `Tests/verify_variants.py` with the same `--work` and
`--reference` options. The old probe writes its references to `SampleOutput`;
run a viewing/reference copy under `local/` when generating game output.

The portable C# checks need no game files or Pillow:

```powershell
dotnet run --project .\Tests\ParserChecks\ParserChecks.csproj
dotnet run --project .\Tests\ParserChecks\ParserChecks.csproj -- --survey "C:\My Extracted Files" "C:\My New Report.json" --convert
```

The first command runs 36 synthetic parser/converter checks. The optional
survey hashes converted DDS data without saving game textures. The game files,
reference DDS files and private ISO sample access script are not included.

See `FORMAT.md` for the descriptor, byte order and mip-layout findings. Xbox tiling and packed-mip addressing were cross-checked against Xenia's public implementation; see `THIRD_PARTY_NOTICES.txt` for attribution. DDS headers follow Microsoft's DDS documentation.

AI was used to help investigate the samples, write this tool and check the outputs. It is not an official LEGO, Lucasfilm, TT Games or Microsoft tool. No game files are bundled with the tool.

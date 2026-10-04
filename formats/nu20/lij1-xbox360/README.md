# LIJ1 Xbox 360 Prototype Texture Extractor

A drag-and-drop DDS extractor for the supplied March 20, 2008 Xbox 360
LEGO Indiana Jones prototype. Version **0.1.2**, Windows 10/11 x64.

## Use it

Download [the Windows x64 package](../../../builds/windows/LIJ1_360_Texture_Extractor-0.1.2-win64.zip),
extract the ZIP, then run `LIJ1_360_Texture_Extractor.exe`.
Drag `.GHG`, `.GSC`, `.TEX`, `.FNT` or `.DDS` files onto the EXE or its window.
Several files or a folder can be supplied together. Folder scans include
subfolders, skip directory links and skip previous extraction folders.

Each input gets a new `<filename>_DDS` directory and `Extraction.json`.
Existing output is preserved by numbering new directories. Choose an output
folder in the window, or leave it empty to save beside each input.
The source files stay unchanged. The self-contained EXE needs no separate
.NET installation, Python, Blender or network connection. It is unsigned.

## Supported textures

| Stored texture | DDS output | Coverage |
| --- | --- | --- |
| BC1 | DXT1 | Standard and observed legacy descriptors |
| BC2 | DXT3 | Legacy descriptors whose GPU word explicitly identifies BC2 |
| BC3 | DXT5 | Standard, legacy, standalone and font textures |
| DXN / BC5 | DX10 BC5_UNORM | Two compressed channels, preserved without reconstructing a normal map |
| RGBA32 float | DX10 R32G32B32A32_FLOAT | Original floating-point values; no color conversion or clamping |
| Six-face BC1 cubemap | DXT1 cubemap | Native face order and all six DDS face flags |
| Existing PC DDS | Unchanged DDS | Observed DXT1/DXT3/DXT5 and BGRA8 files |

Power-of-two dimensions from 1 through 8192 are accepted when the validated
allocation and addressing fit. Original compressed blocks, alpha and declared
mip chains are retained without recompression. Texture identifiers, descriptor
profiles, dimensions, exported mip counts, warnings and output hashes are in
the manifest. The tool does not assign material roles or apply shader swizzles.

The GPU word distinguishes BC2 from BC5 in older serializers: their game-side
format code can both be 4. A format number alone is not enough to identify that
legacy layout. Unknown GPU words and incompatible metadata remain errors.

## Validation and remaining limits

The full **757 GHG/GSC files** from the supplied ISO now process successfully:
**11,182 DDS resources and 92,820 face/mip images**, plus **nine raw allocations**.
Ninety containers contain no texture payload; their manifests correctly report
zero outputs. Twenty-four files report recovery or raw-payload warnings.
All **2,898 DDS outputs** previously accepted by 0.1.1 remain byte-identical.

The other supplied texture files also pass: **344 TEX files, seven Xbox 360 FNT
files and 347 existing PC DDS files** (698 resources, 5,056 exported mip levels).
The ISO archive inventory was checked separately: its 323 TEX members are
byte-identical copies of loose TEX files.

These totals are parser, allocation-bound and output-hash checks, not a visual
check of every texture. Selected extended samples matched an independent
Python conversion for **143 resources / 1,142 face/mip images**. Pillow decoded
1,140 of those images; the two float images were checked byte for byte across
131,072 pixels. Selected cubemap faces, BC2/BC5 maps and font atlases were viewed.
The original two samples and five reported icons have separate regression
checks covering 11 DDS files and 83 mip levels. No in-game validation or
replacement-container writing is claimed.

Two limits are reported explicitly:

- Compact standalone/font GPU objects have no stored mip count. The verified
  base image is exported; the tool does not infer a complete chain from the
  allocation size. Some legacy descriptors likewise contain zero mip/allocation
  metadata; their pointer-bounded base images are exported with warnings.
- Nine 128x64 BC1 resources across three level files declare only 4 KiB, although
  the tiled image requires a 6 KiB address span. Their original allocations are
  preserved as `.x360.bin` with metadata, while the other textures export to DDS.
  Those nine allocations are not claimed as decoded textures.

This is texture extraction for observed prototype layouts. Models, animations,
audio, ISO/archive unpacking, other-platform font/CSC layouts and game-ready
replacement files are outside its scope. Other games or builds may have
different layouts even when their extensions match. Unknown layouts are refused.
An interrupted save can leave `.lij1_partial_*`, which is not a completed export.

## Command line and build

```powershell
.\LIJ1_360_Texture_Extractor.exe --cli --out "C:\My DDS" "C:\My Prototype\C3PO_360.GHG"
```

Files and folders can be mixed. Exit code 0 means all supplied files processed;
1 means an input failed or no files were found; 2 means missing arguments.
Warnings, including raw allocations and base-only exports, also appear in the
window/CLI and manifests. Inspect them before treating an export as complete.

Build the source with a .NET 10 SDK:

```powershell
dotnet publish .\Source\LIJ1TextureExtractor.csproj -c Release -o .\dist
```

Portable synthetic checks require no game files or Pillow:

```powershell
dotnet run --project .\Tests\ParserChecks\ParserChecks.csproj
```

This runs 57 parser/converter checks. The optional
`--survey input-folder new-report.json --convert` arguments hash converted
resources without saving game textures. `Tests/verify_samples.py` checks the
original pair and `Tests/verify_variants.py` checks the five reported GSCs against
verified reference DDS files; each takes a sample folder, `--work`, `--reference`
and optional `--exe`. Both require Pillow and a new work directory.

For independently checking extended sample exports:

```powershell
python .\Tests\verify_extended.py --sources "C:\My Samples" --exports "C:\My Exports" --report "C:\My New Validation\report.json"
```

Keep supplied game data, previews and validation output under ignored `local/`
when working in this repository. No game files are bundled. The original
sample-specific `Research/probe.py` is a development reference, not the shipped
converter. See [FORMAT.md](FORMAT.md) for storage details and references.

AI assisted the research, code and validation. Xbox addressing derives from
Xenia's BSD-licensed equations; attribution is in `THIRD_PARTY_NOTICES.txt`.
This is not an official LEGO, Lucasfilm, TT Games or Microsoft tool.

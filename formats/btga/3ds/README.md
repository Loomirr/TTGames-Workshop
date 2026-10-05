# Universe in Peril 3DS BTGA / FUSE research

The original local investigation verified USA CTR-P-AL5E texture resources.
See [FORMAT.md](FORMAT.md) for the archive and texture layout observations.

## Convert an extracted texture

Install Python 3 and Pillow, then use a new output directory:

```sh
python -m pip install Pillow
python btga_to_dds.py path/to/texture.btga path/to/new-output
```

Input must already be a decompressed BTGA texture record. The tool checks the
observed 56-byte header, dimensions and full mip payload before saving PNGs and
an uncompressed RGBA8 DDS with every original mip. ETC1/ETC1A4 and observed
PICA raw formats are decoded without image generation or recompression.
Vertical flipping follows our original export convention. Sub-tile mips and
unknown headers are rejected. Existing output directories are protected.

BTGA GUI 0.1.2 and the current source decoder also check exact low-level PICA
payload lengths. Direct helper calls now reject short or trailing data instead
of silently filling missing raw pixels. The FUSE helper checks zero-size entry
bounds and negative decoded sizes. These are validation fixes, not additional
ROM or sub-tile layout support.

Run the separate manual, asset-free checks from the repository root:

```sh
python formats/btga/3ds/test_fuse.py
python formats/btga/3ds/test_btga.py
```

FUSE has five standard-library checks; BTGA has six Pillow-dependent checks
covering known pixels in all 14 supported format codes, malformed data,
tile/flip order and stored-mip DDS output. Pixel fixtures do not establish
compatibility with other 3DS games or every archive resource.

`fuse.py` exposes `decompress` and `read_entry` for the observed payload/index
layout. You supply the verified index row, archive offset and archive bounds.
It does not discover RomFS, decrypt ROMs or serve as a complete ROM extractor.

The old build-specific extractor, index files, suit definitions, enhancement
experiments and results are preserved under ignored `local/`. They are not
distributed game assets. Original source atlases can depend on game colors
and masks, so exported images alone are not an exact material preview.

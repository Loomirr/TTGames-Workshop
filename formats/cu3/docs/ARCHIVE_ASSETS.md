# Installed-game companion loading

Available in CU3 importer 0.1.9 (introduced in 0.1.8). Choose **Assemble available scene assets**
(the default), keep **Detect from CU3** for supported LMSH1/LB3 files, and set
**Game or extracted asset folder**. Later imports can leave that field blank
to use the corresponding saved folder in addon preferences. Preferences also
offer an optional **Extracted companion cache** location.

The selected CU3 must already be a standalone extracted file. This workflow
discovers and extracts its companions; the file browser does not browse inside
DAT archives. **Check companion files** uses the same loader without creating
Blender geometry.

The shared asset provider can read the observed PC archives from LEGO Batman 3
and LEGO Marvel Super Heroes. It offers the same lookup interface as an
already-extracted asset tree. A caller supplies the game directory, game
profile and optional cache directory; no game installation path is hardcoded.

Only requested files are extracted. The resource resolver follows the
character definition to its native body, active attachments and declared
costume textures. Native material loading requests the model's texture store
when needed. Exact cutscene and level registry lookups also identify the
selected primary and shared stage resources. With **Recovered static
environment (experimental)** enabled (the default), assembly requests those
GSCs and their textures, then builds supported static draws using native
matrices/material bindings. Named-special draws are excluded. This does not
resolve all stage visibility, nested LED scenes, rigid props, source lights,
audio, effects or every native model/shader layout. See
[scene configuration](SCENE_CONFIGURATION.md).

Simple declared character replacements alter root resource lookup before
dependency loading. The resolver accepts exact mappings and rejects chains
or cycles. The configuration report retains all other commands as unapplied
declarations. **Check companion files** resolves character dependencies and
reports stage associations; it does not decode or build stage geometry.

The index readers have separate version gates:

- LB3: observed legacy DAT index version -6, with explicit name parents.
- LMSH1: observed legacy DAT index version -5, with child/sibling name trees.
- Later archive layouts are separate readers; recognizing their file lists
  does not enable automatic scene assembly for those games.

Uncompressed entries and observed LZ2K chunks are decoded with Python code in
the addon. LZ2K uses canonical Huffman blocks and overlapping LZ references.
The decoder also handles bounded DFLT/ZLIB chunks. Unknown compression is
rejected. There is no bundled or required QuickBMS executable. The archive
layout research retains its reference to Luigi Auriemma's
[ttgames.bms](https://aluigi.altervista.org/bms/ttgames.bms).

Archives are opened read-only. The extraction cache must be outside the game
folder. Its identity includes the game path and each archive's size and
modification time. Cached files have SHA-256 sidecars; modifications are
reported rather than silently reused or overwritten. New cache writes are
atomic. Filenames, table ranges, payload ranges, output limits and compressed
back-references are validated.

Without an explicit cache directory the provider uses
`TTGamesWorkshop/asset-cache` under the user's local application-data directory,
or under `~/.cache` when that directory is unavailable. A fresh cache is an
appropriate way to retry after a damaged/edited cached file is reported.

Validation on the research installs resolved the actor dependency closure for
the LB3 Batcave hub dialogue and LMSH1 Stark Tower intro with no missing
resources or costume textures. Forty-nine resulting cached files matched the
previously extracted reference bytes, totaling 14.4 MB. That verifies archive
extraction and dependency discovery for those samples; the separate Blender
assembly and rendering checks still determine which scene systems work.

The portable companion check also accepts installed game folders:

```sh
python formats/cu3/scripts/check_dependencies.py scene.CU3 --assets "path/to/game" --game LB3 --cache "path/to/cache" --report companions.json
```

Choose a new report filename. TFA/DCSV archive inventory support does not
enable their character/material/camera assembly in this loader.

Asset-free tests:

```sh
python formats/cu3/scripts/test_archive_assets.py
python formats/cu3/scripts/test_archive_v5.py
```

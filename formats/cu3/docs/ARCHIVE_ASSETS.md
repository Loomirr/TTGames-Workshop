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

The verified chunk decoder interprets the two little-endian lengths as
**decoded length, then packed length**. It validates the complete frame list
before invoking a decompressor, limits packed and decoded bytes to 256 MiB per
requested asset, bounds chunk counts, and requires exact decoded lengths.
Whole trailing bytes after TT Deflate/LZ2K streams are rejected; final partial
alignment bytes are allowed. The provider also limits cumulative packed reads
and decoded requests to 1 GiB during its lifetime (cache hits do not consume
that decode budget). The Python provider constructor accepts a lower
`max_total_bytes` limit. Open a new provider for a separate operation when
necessary; this is a resource limit, not a new archive-format claim.

**LOTR mode 3 remains unsupported.** Its observed DFLT header has packed
length before decoded length, and ordinary zlib probes did not establish its
codec. Mode 3 is rejected before decompression, including when synthetic data
would decode as ordinary zlib. No original LOTR specimen was available for
the current safety update.

Archives are opened read-only. The extraction cache must be outside the game
folder. Its identity includes the game path and each archive's file identity,
size and metadata timestamps. Source stamps are checked before
both decoding and cache reuse. Cached files have SHA-256 sidecars; modifications are
reported rather than silently reused or overwritten. New cache writes are
atomic. Filenames, table ranges, payload ranges, output limits and compressed
back-references are validated.

Archive paths now retain their original spelling. Hash lookup uses the format's
separate uppercase/backslash canonicalization. Qualified references require an
exact root-relative logical path; a single matching basename in another folder
does not satisfy one. An unqualified basename found in distinct logical folders
is ambiguous even when payloads are identical. Case-colliding logical names
are diagnosed; exact duplicate logical names across archives can only resolve
after their decoded bytes match. An archive changed after indexing is rejected.

The standalone `archive_index.py`, `archive_index_cc8.py` and
`archive_index_cc4.py` reuse the same bounded readers without Blender. Their
version gates remain separate. The Batman 3 CLI requires a fresh output folder,
retains its index JSON array, and publishes an `archive-manifest.json` alongside
the completed inventory/extraction bundle. The CC readers remain inventory
tools, not decompression support for later games.

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
python formats/cu3/scripts/test_archive_cli_bounds.py
python formats/cu3/scripts/test_pak_preflight.py
python formats/cu3/scripts/test_tt_deflate.py
```

The added safety tests use constructed data only: they cover malformed names,
late frame failures before decode, size/work budgets, archive changes, lookup
ambiguity, unsupported LOTR mode 3, cleanup and successful native-wrapper
round trips. They do not repeat the historical original-file or Blender
validation described above. Stricter framing refusals should be checked
against the user's original specimens before declaring the updated package
validated for those installs.

# Newer PC archive checks, 2026-10-15

The archive reader now accepts two additional **verified index extensions**:
The Force Awakens CC8 v2, and the CC12 v2 layout observed in DC Super-Villains,
Marvel Super Heroes 2 and The LEGO Ninjago Movie Videogame. This removes the
unknown-tail refusal for these specific layouts. It does not enable complete
Blender character assembly or animation playback for those games.

No third-party implementation or game engine code was copied. Installed game
files were opened read-only. Extracted samples and detailed manifests remain
in the ignored local validation workspace.

## Exact format gates

For **kind -8 / version 2**, the existing version-2 name records and 32-bit path
hash mapping are followed by the same suffix framing already established for
Avengers kind -8 / version 1:

- A bounded, NUL-terminated ASCII directory prefix. A nonempty prefix must be
  a complete parent directory of every indexed path.
- Sixteen reserved zero bytes.
- Two `ROTV` tags, each followed by a big-endian file count and exactly one
  opaque 16-byte record per file, in file-table order.
- No bytes may remain after the second array.

For **kind -12 / version 2**, the 64-bit path hash mapping is followed by:

- Eight reserved zero bytes, the bounded shared directory prefix, and sixteen
  reserved zero bytes.
- Four arrays, each with a zero tag and a big-endian file count. Their record
  widths are 16, 16, 1 and 4 bytes, respectively.
- The first two arrays remain opaque. The byte array identifies storage modes
  0, 2 and 6 in the checked originals. Its compression presence must agree with
  the main file table. The final array must reproduce every packed byte length
  from that table exactly.
- Unknown modes, nonzero reserved fields, mismatched counts/sizes, invalid
  prefixes and trailing or missing bytes remain refused.

The main CC12 table has a compression-presence bit, not the complete mode.
Previously it could label mode 6 as mode 2. The validated suffix now preserves
that distinction. **Mode 6 / ZIPX payload extraction remains unsupported**;
it is not dispatched through the DFLT decoder. The opaque 16-byte records are
not treated as checksums, encryption information, offsets or codec selectors.

## Original-file validation

| Installed PC game | Original indexes checked | Indexed entries |
| --- | ---: | ---: |
| The Force Awakens | 19 | 105,620 |
| DC Super-Villains | 20 | 164,756 |
| Marvel Super Heroes 2 | 22 | 183,530 |
| The LEGO Ninjago Movie Videogame | 9 | 69,851 |

Every checked index passed the full existing path, hash and payload-span
checks and the new exact extension grammar. The counts include archive
entries repeated across different DATs; they are not unique characters or
files. Header reads for 25,916 mode-6 entries found `ZIPX` framing. This is
research evidence, not an enabled ZIPX codec.

`ArchiveAssetIndex` also read two CD definitions, two GHG models and two AN4
files from each of TFA, DCSV and LMSH2 into a fresh external cache: 18 successful
archive payload reads using modes 0 and 2. These samples establish extraction,
not complete model or animation support:

- TFA CD version 31 parses. Both sampled Hera Syndulla hair meshes parse as
  MESH 175 with four parts. The sampled Ventress AN4 records still fail the
  animation/name-pointer validation.
- DCSV CD version 38 remains refused. The two sampled face GHGs do not contain
  a currently supported MESH layout. Sampled AN4 v20 records expose ANI-E
  structure, whose pose sampling remains disabled.
- LMSH2 CD version 36 remains refused. Sampled Charlie-27 and Yondu bow meshes
  parse as MESH 175, with 46 and two parts. Sampled AN4s contain ANI-E and one
  ANI-D record; the ANI-D scalar samples were finite at start, middle and end.
  That does not establish body binding or complete animation playback.
- Ninjago was checked at the archive-index/header level only. This pass does
  not add a Ninjago character profile or extend the private weapon proof.

## Constructed regressions and remaining work

The archive CC test selection ran **55 tests: 54 passed and one Windows symlink
test was skipped**. The new tests cover every array header/count, both
reserved regions, directory-prefix safety, truncated/extra bytes, packed-size
disagreement, compression-presence disagreement and retained mode-6 refusal.
Corrupt path tables and out-of-range payloads still fail before suffix parsing.
Diagnostic reports retain bounded metadata rather than whole record arrays.

Remaining work includes a separately verified ZIPX decoder, the later CD/MESH
layouts, ANI-E evaluation and complete character dependency/material assembly.
No Blender visual or in-game fidelity claim follows from this archive pass.

Use the existing [archive diagnostics](DIAGNOSTIC_TOOLS.md) to inspect a DAT or
detached HDR without extracting it. Detached HDRs cannot establish the bounds
of a missing DAT payload. `formats/character/inspect_game.py` can inventory the
existing TFA, DCSV and LMSH2 inspection profiles; refused downstream resources
remain reported as unsupported.

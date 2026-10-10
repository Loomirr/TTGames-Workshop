# TT format research references and independent checks

Reviewed on 7 October 2026. These are research leads, not dependencies. This
pass reviewed repository metadata, READMEs and format documentation. No external
implementation was copied, translated, installed or executed. Private snapshots
and original-file evidence stay under ignored `local/`.

## Community references

Revisions identify reviewed snapshots. Scope descriptions are the projects'
claims, not Workshop support guarantees. License labels are GitHub metadata;
a dash means no SPDX identifier was established, rather than permission to reuse.

| Source | Revision / license metadata | Useful scope and limits |
| --- | --- | --- |
| [GHG-stuff](https://github.com/TheOneQGuy/GHG-stuff) | `b56e66f1c9bd` / — | NXG/DX11/NTT skeleton and skinning work. The README separates skin-weight editing from modified geometry reimport; not proof of a universal GHG writer. |
| [DatLibrary](https://github.com/ArchLeaders/DatLibrary) | `6a57576bb5ef` / GPL-3.0 | Archive library based on the TT Games BMS script. Shared lineage is not independent corroboration. |
| [DATManager](https://github.com/ArchLeaders/DATManager) | `630750b6976e` / — | Newer archive UI. Skywalker Saga requires a separately supplied Oodle DLL; the README also lists QuickBMS/7-Zip dependencies. None were imported. |
| [DATExtract](https://github.com/ArchLeaders/DATExtract) | `0377a97ca606` / — | Archive library, not a complete standalone program; README points to DATManager. |
| [NTT-Dat-Exporter](https://github.com/Divengerss/NTT-Dat-Exporter) | `2c3a7ca2f0a7` / MIT | Work in progress tested on LCU DX11. Codec and LZ2K-distance claims need original-file tests; see below. |
| [TTDAT](https://github.com/mhvuze/TTDAT) | `d1ceacd25f20` / — | LCU PC archive research, separate from model import and other archive variants. |
| [DATOneArchiver](https://github.com/IsaMorphic/DATOneArchiver) | `8001e9254606` / GPL-3.0 | Original LSW1/LSW2 archive extraction/modification/creation. Platform testing varies; not a modern NXG archive writer. |
| [ttextract](https://github.com/pianistrevor/ttextract) | `245f3fd8f8ee` / — | TT extraction CLI; README does not establish a complete per-game/codec matrix. |
| [unlz2k](https://github.com/pianistrevor/unlz2k) | `e904a6670529` / — | Compression research; README format specification remains unfinished. |
| [ttgames-quickbms](https://github.com/xmusjackson/ttgames-quickbms) | `2de532522e45` / — | Description advertises Skywalker Saga extraction. No README available in this review; script implementation was not read. |
| [Tt-Games-quickbms-scripts](https://github.com/linterniGamer/Tt-Games-quickbms-scripts/tree/main/files) | `90e6a90fa55b` / — | Script-version collection with upstream credit. Related copies are not independent format discoveries. |
| [libttdat](https://github.com/xmusjackson/libttdat) | `9ae08e4dfb7a` / AGPL-3.0 | README describes index/file-list support, with compression/extraction still planned. |

## Additional references

| Source | Revision / license metadata | Useful scope and limits |
| --- | --- | --- |
| [JaanDev NXG format notes](https://github.com/JaanDev/lego-tt-nxg-formats) | `820215ce64a8` / MIT | Direct documentation of GHG/GSC sections, skeleton/display/mesh records and materials. Each version still needs original-file evidence. |
| [NuTCrackerV3](https://github.com/JayFrancoe/NuTCrackerV3) | Revision/license not established | Description identifies an NXG_TEXTURES extractor/compiler. No README on the reviewed page; implementation/compatibility not evaluated. |
| [TTGames Explorer Rebirth](https://github.com/AcK77/TTGames-Explorer-Rebirth) | `6e6b4e2917b2` / MIT | Archive/model/texture/shader-collection inspection. README distinguishes unsupported AN4 decompression; browsing a resource is not reconstruction. |
| [BrickBench](https://github.com/BrickBench/BrickBench) | `3d149673e1f7` / — | TCS map editing with experimental LIJ/LB1 work, separate from LSW1 PC and modern NXG/DX11. |
| [OpenSaga](https://github.com/opensagadev/saga) | `a606c391e50b` / GPL-3.0 | Matching decompilation targeting Android x86 TCS. No engine code was read or used; its platform/era do not validate these PC layouts. |

## Material constants: new diagnostic coverage

The [UMTL notes](https://github.com/JaanDev/lego-tt-nxg-formats/blob/820215ce64a8fee2de665499c9c0f4edb20ca9d9/UMTL.md)
suggested examining the interval between texture declarations and the material
name. Independent original-file probes corroborate a 492-byte, 13-sampler block
for LMSH1 UMTL 176/177. Diagnostics now retain its span/hash, sampler values and
finite constant candidates.

Observed values include a normal-layer scalar of 3.0 on Hulkbuster's shoulders,
a glow-related value near 0.421687, and roughness-related values of 0.0/0.05/0.1
on different materials. Field names are candidates; these are not confirmed
Blender normal strengths, emission intensities or roughness inputs. No renderer
behavior changed in this pass.

| Original resources | UMTL | Material records | New block diagnostic |
| --- | --- | --- | --- |
| LMSH1 Hulkbuster | 177 | 14 | Observed layout decoded |
| LMSH1 shared body | 176 | 50 | Observed layout decoded |
| LMSH1 Wolverine face | 176 | 12 | Observed layout decoded |
| LB3 shared body / Alfred face | 202 / 196 | 45 / 10 | Different layouts; unverified spans retained |
| Hobbit shared body / Thrain face | 191 | 43 / 6 | Different layout; unverified spans retained |
| Avengers shared body / Captain America face | 235 / 232 | 26 / 12 | Different layouts; unverified spans retained |

All nine source hashes remained unchanged. This is diagnostic coverage, not
additional shader fidelity. Next steps are later-version alignment and evidence
for parameter units, texture operations, BRDF variants and environment lookup.
A material name alone cannot select a shader branch or replacement candidate.

## LZ2K claim: tested, not adopted

NTT-Dat-Exporter's README says distance code 1 should copy from distance 1.
Workshop currently uses distance 2 for that symbol. A private experiment used
only our own decoder and original face streams, changing only that interpretation.
Both alternatives reached the declared lengths, but produced different bytes.

| Original face | Symbol 1 occurrences | Bytes changed by alternative | Alternative full mesh result |
| --- | --- | --- | --- |
| LMSH1 Wolverine | 26 | 649 | Triangle index exceeds draw vertex count |
| LB3 Alfred | 49 | 370 | Triangle index exceeds draw vertex count |
| Hobbit Thrain | 40 | 360 | Triangle index exceeds draw vertex count |
| Avengers Captain America | 13 | 2,664 | Unsupported native morph target table |

Our existing rule passed full mesh decoding for all four. It remains unchanged,
with an AB-history regression fixture distinguishing distances 1 and 2. This
does not settle LCU or every LZ2K variant: no LCU original was tested. Matching
decompressed lengths alone is insufficient validation.

## Face targets

The decoder now offers a bounded `--summary` report: native part/target IDs,
vertex counts, encodings, source offsets, affected vertex counts and displacement
bounds. It omits editable offsets and cannot be fed to the writer. Detail caps
and omitted counts are explicit.

| Original face | MESH | Parts with targets | Part-target records |
| --- | --- | --- | --- |
| Wolverine | 169 | 14 | 422 |
| Alfred | 175 | 15 | 513 |
| Thrain | 170 | 5 | 90 |
| Captain America | 175 | 20 | 514 |

The 1,539 records include repeated IDs across parts/LODs, not that many distinct
expressions. Original inputs were preserved. Shape offsets are only one layer:
draw/LOD ownership, bones, BSA weights, base-head printing, masks and depth-only
surfaces must agree. Solid viewport appearance is not a fidelity check.
Expression labels, universal timing and exact shading remain incomplete.

The packaged decoder passed summary extraction for all four originals. Native
target no-op writes were byte-identical for each; these are preservation checks,
not in-game editing or visual fidelity validation. The packaged toolbox material
inspector also passed all nine original resources listed above.

## Additional archive samples

Bounded index reads covered 20 DATs in three additional local game folders.
Folder titles are not build identifiers.

- Four LEGO Movie DATs passed the existing explicit little-endian parent `-5`
  reader: 47,783 per-archive entries, storage modes 0/2. The standalone CLI now
  exposes `--index-version -5`, retaining LB3 `-6` by default. This validates
  indexes, not complete characters/cutscenes. LMSH1's different `-5` tree reader
  remains separate.
- Eight Jurassic World indexes start with little-endian `-7`. No new grammar
  or payload support was enabled from that word.
- Eight Skywalker Saga indexes use `.CC40TAD` kind `-13`, version 2. They remain
  refused. A familiar header does not prove entry widths, hashes or codecs.

The CLI additionally indexed 18,078 entries in the sampled Hobbit GAME.DAT.
The same explicit parent-layout option rejected LMSH1's GAME.DAT at path/hash
validation before creating output, corroborating the separate-reader requirement.

New profiles need index/codec validation, followed by definition dependencies,
buffer/display ownership, binds, textures, materials, targets and animation
tests. Archive success alone does not establish downstream model support.

## Repeating the checks

Supply originals and fresh output paths. See [diagnostic commands](DIAGNOSTIC_TOOLS.md),
[character coverage](../formats/character/COMPATIBILITY.md) and
[constrained face editing](../formats/cu3/docs/FACE_GHG_EDITING.md).
Portable fixture tests, original-file decoding, Blender visuals and in-game
validation are separate. This pass does not certify visual fidelity or enable
unrestricted native model writing.

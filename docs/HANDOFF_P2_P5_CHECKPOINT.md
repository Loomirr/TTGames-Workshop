# P2–P5 implementation checkpoint

Updated 6 October 2026. Candidate versions: **Character 0.5.7 / CU3 0.1.16**.

This checkpoint records the safeguards and bounded reader changes implemented
after [P1](HANDOFF_P1_CHECKPOINT.md). Read it alongside the
[remaining handoff](../TTGames_Workshop_Remaining_Handoff.md) and
[master roadmap](../TTGames_Workshop_Master_Roadmap.md). It does not mark the
broader compatibility or visual reconstruction work complete.

The changes apply to the existing supported families. They enable no new game,
platform, general native writer, or complete cutscene reconstruction. Original
game assets were not available for this pass. No in-game checks or installation
into the user's Blender profile were performed. Portable tests, synthetic
Blender checks and original-file validation are separate kinds of evidence;
the final execution record should identify each explicitly.

## P2: shared native sources and bundle publication

The character exporter groups Blender instances by canonical native source
path before producing proposed edits. Relative paths and symbolic-link aliases
resolve to the same source; case normalization follows the host platform.
Every instance in a group proposes the complete native output bytes, including
instances with no edits.

- Identical proposals produce one output file and retain the contributing
  instance names in the report.
- Different proposals reject the export. This includes an edited instance
  paired with an unchanged instance, in either traversal order.
- Compatible-looking changed ranges are not silently combined: every instance
  must agree on the same complete result.
- The P1 consumed-source and companion checks remain in place. Source copies,
  edited payloads and logical output paths are validated before publication.
- A source used as both an edited model and a companion keeps its agreed
  edited payload; a later dependency copy cannot replace it with original bytes.

The shared `bundle_output.py` helper preflights output names and creates a
uniquely owned sibling staging directory. It writes the payloads and manifest,
rereads the full inventory, checks file sizes and SHA-256 hashes, and verifies
that the saved manifest describes that inventory. Only then does it publish
the directory to an absent destination.

Publication uses an explicitly non-replacing operation: Windows `os.rename`,
Linux `renameat2(RENAME_NOREPLACE)`, or macOS `renamex_np(RENAME_EXCL)`. A
concurrent destination creator wins its own directory; the exporter must fail
without replacing it. Unsupported publication operations fail closed. There is
no copy fallback across filesystems and no power-loss durability claim.
Cleanup is restricted to staging whose ownership still matches the current
operation. Existing destinations, unrelated staging and edited drafts are
preserved. An uncatchable process termination can leave staging behind; that
directory is not a completed bundle. Windows and macOS publication branches
still need execution on their target platforms.

Portable tests exercise the real exporter and native byte writers with small
Blender adapters, plus real filesystem publication. They cover identical,
divergent and edited/unchanged instances; path aliases; no-op preservation;
intentional vertex/face edits; failed payload/manifest writes; verification
failure; concurrent creation; cleanup; and retry. The adapters do not establish
behavior in a real Blender scene.

## P3: archive preflight and bounded compression

`pak_reader.py` provides one complete `0x1234567A` PAK preflight for both
`AnimationBank` and the standalone `unpack_pak.py`. Before any member is decoded
or output is created, it validates every name, metadata reference, payload
extent and advertised decoded length. Windows device names, traversal, case
aliases, duplicate outputs, file/directory conflicts, partial payload overlaps
and names embedded inside payload bytes are rejected on every host.

The standalone PAK helper now uses Workshop's existing Python
`Deflate_v1.0` decoder. **QuickBMS is no longer invoked.** Existing `--quickbms`
and `--bms` options remain accepted as documented compatibility arguments with
no effect. The helper requires the shared CU3 source modules, but does not
import Blender. It streams decoded members through the same verified bundle
publisher used by P2 and places `pak-manifest.json` in each completed PAK
folder. See [PAK usage](../formats/an4/lmsh1/README.md#pak-helper).

The bank and per-member packed/decoded limits are 256 MiB; cumulative PAK and
provider limits are 1 GiB. Block/chunk counts are bounded separately from
decoded output. All chunk headers and cumulative lengths are checked before a
decompressor runs, and output must match the declared size exactly. Whole
trailing bytes after TT Deflate and LZ2K streams are rejected; partial final
alignment bytes remain allowed. Nested TT wrappers are not recursively guessed.

Directory input is preflighted as a batch, but publication is **per PAK**. A
later decoding failure can leave earlier, fully verified PAK folders. It does
not leave a completed folder for the failed PAK. Choose a new destination for
a batch retry, or retry the failed archive separately.

The standalone DAT/CC inventory scripts reuse the bounded shared readers while
keeping their version gates separate. Archive logical spelling is retained;
hash canonicalization is a separate operation. Qualified references must match
their full logical path. Different logical directories with the same basename
remain ambiguous even if their bytes match. Source metadata is checked before
decoding and cache reuse, and file identity contributes to cache identity.
Metadata stamps are not a full cryptographic digest of an entire installed DAT.

**LOTR mode-3 DFLT remains rejected.** The observed LOTR header order is packed
length followed by decoded length, whereas the verified generic chunk reader
uses decoded length followed by packed length. Ordinary zlib probes did not
establish LOTR's codec. A synthetic zlib stream that decodes successfully is
not evidence that the game's frame or bitstream is supported. No original LOTR
specimen was available to resolve that work.

The stricter trailing-byte, index-boundary and filename checks need an original
archive regression pass. They are deliberate refusals of unexplained framing,
not a claim that every previously accepted file has been revalidated. More
details are in [archive loading](../formats/cu3/docs/ARCHIVE_ASSETS.md).

## P4: profile, dependency and animation ownership

The four enabled PC character profiles now retain explicit game, platform,
renderer, routing suffixes, actual decoded structure versions and byte-order
metadata. A build that has not been established remains unknown. The profile
does not override a binary reader's layout checks. In particular, LB3's DX11
model path still uses NXG animation naming. Archive path hashes, shader IDs,
consumed-file SHA-256 hashes and tool-generated skeleton identities have
separate meanings and namespaces.

Definition and animation-set dependency reports retain logical paths, source
digests and graph edges. Qualified lookups do not fall back to unrelated
basenames. Iterative graph checks diagnose cycles, including cycles reached
through shared roots or aliases. Explicit inactive-renderer references are
retained as diagnostics without breaking an otherwise valid active path.
Undecoded nested definition fields, unknown inheritance and unrecognized
renderer routing remain outside that closure.

Skeleton selection considers the bounded HGOL/name-table candidates instead of
silently taking the first matching joint count. Native names, hierarchy, bind
matrices, flags, locators, layers and retained opaque fields contribute to
identity. Complete duplicate ownership tables can be deduplicated with all
candidate offsets recorded. Different binds, or identical binds with different
ownership, are ambiguous. Verified display references or a retained complete
identity can disambiguate candidates; joint count alone cannot. Invalid
consumed locators fail instead of turning an unused sentinel into a bone index.

Imported rigs retain resource and skeleton identity. Attachment animation
matching requires a unique actor under the already matched parent, using an
exact declared resource or native root-name association. Only after ownership
is resolved are clip names, joint counts and duration used to validate the
record. Multiple sibling claims and missing/ambiguous matches are reported.
Unresolved attachments remain at their native locators. Older imports without
the retained identity need a fresh import for this matching path.

**AN4 does not contain the bind matrices needed to prove full skeleton
identity.** Native root-name evidence narrows ownership but cannot prove data
that the animation file does not encode. These changes reduce unsupported
guesses; they do not establish every attachment across all games. LOTR reference
inspection can retain explicit AN4 names, but automatic bank/member naming is
not guessed from a DX11 suffix. Additional refusals need original specimens
before any gate is relaxed or support promoted.

## P5: bounded image spans and visible fidelity limits

The new DDS reader sizes supported mip chains, block-compressed images,
cubemaps, DX10 arrays and volumes from their headers. Texture readers use that
proven image span instead of treating a `DDS ` token inside pixel bytes as the
next image. Native preambles and trailers remain separate opaque spans.
Unknown formats and truncated or oversized payloads fail before an image is
exposed.

Numeric legacy FourCC values are ambiguous between D3D9 and DXGI namespaces.
`read_dds` accepts them only with explicit `legacy_d3d9=True` context. Current
generic texture callers do not opt in, so originals containing numeric codes
may newly reject until their enclosing layout establishes that context.
Uncompressed images with unverified padded row pitches also fail closed.
Neither policy has an original-file regression pass in this checkpoint.

Native material reads now check prefix, texture, name and footer spans and
reject overlapping fields or ambiguous final table boundaries. **Material-name
placement is still inferred, and the enclosing TEX/TXTS framing and trailers
are not fully established.** A plausible marker plus bounded DDS data is not
complete proof of a native texture record or an unsupported UMTL layout.

Skin decoding retains raw integer/normalized totals, retained totals and
discarded sentinel-slot weights before producing viewing weights. Duplicate
native influences for the same joint are combined so Blender does not overwrite
an earlier contribution. Reports expose the authored totals and deviations;
no-op native exports preserve original packed bytes. Malformed diagnostic
records fail with scoped format errors.

Normal preservation is now exposed as a runtime capability rather than inferred
from successful addon loading. Missing `GeometryNodeSetMeshNormal` support is
reported as a facial-preview fidelity limitation. Portable capability tests use
test adapters; they do not execute Blender geometry nodes. Any separate Blender
runtime result belongs in the final execution evidence below.

Normal-map channel interpretation, tangent handedness, UV orientation, face
passes, materials, attachment motion, visibility, stage geometry and cameras
still need original-versus-imported visual checks. Use neutral, tilted and
asymmetric examples. A renderer name alone does not establish a green-channel
flip. Depth-only faces require the render helper/compositor; a solid viewport
is not a fidelity check.

## Evidence and remaining work

| Area | Evidence established by the portable tests | Evidence still needed |
| --- | --- | --- |
| P2 source conflicts | Real export proposals/native decoders with synthetic meshes and Blender adapters; identical, divergent, no-op and intentional-edit cases | Representative original imports and real-scene export/reimport on the user's workstation |
| P2 publication | Filesystem writes, hash/manifest verification, failure injection, race/refusal, owned cleanup and retry | Exact target platform/filesystem execution record; no cross-filesystem or power-loss guarantee |
| P3 archives | Constructed unsafe paths/extents, complete-header preflight, bounded decoding, native-wrapper round trips, CLI parity and cache-change cases | Original PAK/DAT comparisons after stricter framing; independently established LOTR mode-3 codec |
| P4 ownership | Constructed profile, graph, renderer, candidate-selection and attachment-claim cases | Original resource/name associations, unresolved nested fields and animation identities not encoded in AN4 |
| P5 spans and diagnostics | DDS size/refusal cases, pixel-marker negatives, material overlap checks, raw weight reporting and no-op byte preservation | Enclosing texture/material record proof and original-file compatibility across each claimed layout |
| P5 rendering | Capability/report behavior is tested separately from loading | Original-versus-imported render comparisons, including facial compositor behavior and asymmetric normal-map tests |

The main portable runner includes the new suites. From the repository root:

```sh
python tools/check_repository.py
```

Focused checks are useful while merging or diagnosing a failure:

```sh
python formats/character/test_source_bundle.py
python formats/cu3/scripts/test_bundle_output.py
python formats/cu3/scripts/test_pak_preflight.py
python formats/cu3/scripts/test_archive_cli_bounds.py
python formats/cu3/scripts/test_archive_assets.py
python formats/cu3/scripts/test_identity_ownership.py
python formats/cu3/scripts/test_dds.py
python formats/cu3/scripts/test_texture_store.py
python formats/cu3/scripts/test_material_flags.py
python formats/cu3/scripts/test_model_validation.py
python formats/cu3/scripts/test_mesh_edit.py
python formats/cu3/scripts/test_preview_capabilities.py
```

Run [the original-file P2 Blender check](../formats/character/check_source_bundle_blender.py)
only in a fresh background Blender session, with the user's own supported
specimen and new output/cache folders outside the installed game. It covers
no-op export/reimport, shared-instance conflicts and a decoded UV edit. The
script is provided for follow-up; its presence does not mean those checks ran.
Keep original evidence, game payloads and scene experiments under ignored
`local/`. Rebuild, back up and install candidate addons on the workstation only
after the relevant checks, preserving preferences and edited projects.

## BactaTank interoperability research

The accompanying [BactaTank Classic interoperability investigation](BACTATANK_INTEROP.md)
documents an independently implementable, destination-specific `.bmesh` path
and its required evidence. It is research, not a working Bacta exporter. It
does not make modern NXG/DX11 GHG files interchangeable with classic PC GHGs,
and no Bacta implementation, bundled addon, runtime or game assets were copied
into Workshop.

## Final execution evidence

Executed on 6 October 2026 from the uncommitted candidate based on
`3c3da56fa18a797b056d475a99d46b35a9df7e03`. The merge packet retains the binary
patch, changed-file hashes and the command logs; no commit or push was made.

| Check actually executed | Result and scope |
| --- | --- |
| Base repository check | Passed: 240 unittest cases in 30 suites before edits, plus repository syntax/config/document/package gates. |
| Updated `python tools/check_repository.py` | Passed: 386 unittest cases in 37 suites (146 additional cases), 159 Python source syntax checks, JSON/project checks, documentation links/encoding, package hashes/CRC/content rules and stale-build policy. |
| Blender package check | Blender 5.2.2 LTS, Linux, build `d13f752e3b9c`: imported 55 modules from each extracted candidate, enabled both addons together, checked defaults/capability reports and unregistered cleanly. |
| Native normal check | Passed on a synthetic noncoplanar mesh; maximum packed-normal error 0.003922, below the stated one-byte tolerance. The pre-existing fixture lacked material metadata and failed on the untouched base too; the fixture now supplies that required metadata. |
| Character preview settings check | Passed using the extracted 0.5.7 package: tilted authored normals, evaluated skinned normals, source-scene isolation, reversible shading, LOD defaults and scene lighting controls. |
| Facial compositor check | CPU-rendered synthetic scene passed pixel checks: the depth mask reveals blue body at center while red detail remains outside it; source vertices and zero-valued targets remain unchanged. |
| Rebuilt GUI backend checks | Six extracted distributions passed isolated backend/module checks without source-tree fallback. These do not open Tk windows or convert original game inputs. |
| Patch review | `git diff --check` passed. The ZIP includes a replay check against the exact base, separate from native/game validation. |

The Blender runtime archive was checked against its official SHA-256 before
use. It and all temporary synthetic render/scene data remain outside the
source and deliverable packages. The host's graphics/socket warnings did not
prevent the successful CPU compositor or package/geometry checks.

Reproduce the asset-free Blender checks from the repository root with a normal
Blender installation. Replace the placeholder paths; the addon directory is
the parent of `io_scene_tt_character` extracted from its candidate ZIP.

```sh
blender --background --factory-startup --python-exit-code 1 --python tools/check_blender_packages.py
blender --background --factory-startup --python-exit-code 1 --python formats/cu3/scripts/test_native_normals_blender.py -- /new/validation/normals
blender --background --factory-startup --python-exit-code 1 --python formats/cu3/scripts/test_face_preview_blender.py -- /new/validation/compositor
blender --background --factory-startup --python-exit-code 1 --python formats/character/check_preview_settings_blender.py -- --addon-directory /extracted/character-addon
```

These are executable checks with generated geometry, not original-file visual
certification. Windows/macOS exclusive publication, original PAK/DAT/GHG/CD/AN4
regressions, Bacta replacement/save/reopen, edited-file gameplay and the user's
installed Blender profile remain untested in this pass.

### Candidate addon hashes

These are the **original packet** hashes. The Windows review refreshed packages
after narrowly verified archive fixes. Current hashes are in the build manifest;
see [the workstation merge review](MERGE_PACKET_REVIEW_2026-10-06.md) for failed
original-character gates and the successful narrower tests.

| Package | Bytes | SHA-256 |
| --- | ---: | --- |
| `TT_Character_Importer_0.5.7.zip` | 179034 | `37e228f61d5d5bad54863ebf9239a3301b902ffdbf232cf5e761e754f4e74f9e` |
| `TT_Cutscene_Importer_0.1.16.zip` | 143117 | `be009c897f04b8e6be52c1f69fe31deb731bd68a215656f2b44f0979572916fc` |

All current package records, including the rebuilt GUI distributions, are in
[`builds/manifest.json`](../builds/manifest.json).

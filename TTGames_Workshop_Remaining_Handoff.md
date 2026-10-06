# TTGames Workshop — remaining implementation handoff

Updated 6 October 2026. Read this alongside the [master roadmap](TTGames_Workshop_Master_Roadmap.md), root README, AGENTS.md and component docs.

## Current checkpoint

**Workstation review update:** this packet and review corrections are included
in the main source update. Portable and synthetic Blender checks pass,
but original shared-body skeleton ownership and Avengers archive suffix gates
currently block the working character/CU3 examples. Keep the installed builds
unchanged. Read [the merge review](docs/MERGE_PACKET_REVIEW_2026-10-06.md) before
promoting the candidate or widening any gate. Thrain's standalone face completed
the original P2 export check; this is not a whole-character certification.

This merge packet starts from repository commit `3c3da56fa18a797b056d475a99d46b35a9df7e03` (Character 0.5.6 / CU3 0.1.15). The new experimental candidate packages are **Character 0.5.7 / CU3 0.1.16**. They have not been installed on the user's workstation or checked against its original game specimens in this pass.

P1's earlier original-file and workstation checks remain recorded in [the P1 checkpoint](docs/HANDOFF_P1_CHECKPOINT.md). The current safeguards and evidence are in [the P2–P5 checkpoint](docs/HANDOFF_P2_P5_CHECKPOINT.md). Do not interpret a portable fixture or a synthetic Blender check as a new original-game or in-game result.

## P2 — shared-source conflicts and output publication

- [x] Group all imported instances by canonical native source before encoding. Compare complete proposed bytes, including unchanged instances; identical edits produce one source file and conflicting edits name their instances.
- [x] Stage the complete bundle in a uniquely owned sibling directory, flush/reread payloads, verify hashes and the manifest, then publish only to an absent destination.
- [x] Exercise identical/divergent mesh and face edits, edited-plus-unchanged instances in both orders, path aliases, existing destinations, failed writes/manifest verification, concurrent destination creation, two real Linux exporters, owned cleanup and retry.
- [ ] Run `formats/character/check_source_bundle_blender.py` with representative original models on the workstation. Confirm no-op byte identity and decoded intentional edits there, then check edited files in game when appropriate.

Publication uses a same-filesystem exclusive directory rename. Platforms without a supported primitive fail explicitly; cross-filesystem atomicity and sudden-power-loss durability are not promised. A stage is removed only when its recorded file identity still belongs to this operation.

## P3 — archive preflight and bounded framing

- [x] Preflight all PAK names, aliases, collisions, table spans and payload extents before decoding or creating output. The unpacker now uses the existing native TT Deflate decoder and does not invoke QuickBMS. Deprecated backend arguments remain accepted but unused.
- [x] Enforce packed/decoded/cumulative limits, bounded chunk counts, cursor progress, exact decoded lengths, and unsupported nested/trailing framing rejection. Standalone readers reuse the bounded core without importing Blender.
- [x] Preserve original path spelling, diagnose ambiguous resources, and detect changed archive identities before decoding or cache reuse. Publish each extracted PAK through the shared verified staging helper.
- [ ] Rerun the stricter readers on original supported archives, especially TT/LZ2K tails, CC index trailers and PAK banks. Multi-PAK CLI publication is per archive, not a transaction across the batch.
- [ ] Investigate LOTR mode-3 DFLT using original specimens. Observed headers and synthetic zlib fixtures do not establish its codec. Mode 3 remains explicitly rejected.

## P4 — identity, profiles and ownership

- [x] Retain selected game, PC platform, renderer, actual structure versions and byte order. Keep unverified build identity unknown and separate archive/shader/source/skeleton hash namespaces.
- [x] Require exact qualified paths, retain logical spelling, filter understood inactive renderer declarations, and diagnose case collisions, ambiguous basenames, dependency cycles and graph limits.
- [x] Coalesce identical complete skeleton/ownership tables with candidate offsets; reject conflicting candidates unless validated display ownership or a retained complete identity selects one. Joint count alone does not choose a skeleton.
- [x] Resolve attachment animation actors under matched native parents using declared resources/native root identities and unique claims, then check clip/count/duration compatibility. Invalid consumed locator indices reject the optional attachment with a named error.
- [ ] Verify these stricter choices on originals and extend only proven nested CD/inheritance/renderer declarations. Unresolved ownership remains diagnostic; AN4 has no bind matrices, so its bind identity cannot be proved by the new matching helper.

LB3 retains DX11 model naming and NXG animation naming. The existing TFA/DCSV/LMSH2/LOTR inspection paths remain separate from enabled character profiles. No new Blender profile was added.

## P5 — proven spans and visual fidelity

- [x] Bound known material prefix, texture-ID, name and footer reads. Reject adjacent unsupported UMTL versions instead of inferring a layout from the filename suffix.
- [x] Calculate DDS mip, cube-face, array, volume and DX10 payload lengths. Ignore header-like bytes inside validated pixel spans; keep native trailer bytes outside exported DDS payloads.
- [x] Retain raw and retained weight totals, sentinel losses and duplicate palette diagnostics before normalization. Merge repeated native joint influences without silently overwriting them in Blender.
- [x] Expose Blender's normal-preservation helper capability and the limitation when it is unavailable.
- [ ] Prove enclosing TEX/TXTS framing and material-name placement from original layouts. Current bounds improve safety but do not establish a complete container grammar. Numeric legacy DDS FourCC and padded uncompressed pitches remain conservative opt-in/rejection cases.
- [ ] Verify normal-map channels, tangent handedness and UV orientation with neutral, tilted and asymmetric original examples. Do not infer a green-channel flip from the renderer name.
- [ ] Continue original-versus-imported face, material, attachment, visibility, stage and camera checks. Depth-only faces require the helper/compositor; solid viewport output is not a fidelity check.

## P6 — broader support after the safeguards

- [ ] Complete one verified game/platform/format family at a time, prioritizing the existing PC profiles and partial LOTR/TFA/LMSH2/DCSV coverage.
- [ ] Require a representative original, a second independent specimen and neighboring unsupported-layout rejection before promoting support.
- [ ] Keep LSW1 PC separate from LSW2/TCS. Console, handheld and prototype work remains separately gated.
- [x] Investigate an independent BactaTank interchange path. [The research report](docs/BACTATANK_INTEROP.md) records the `.bmesh`/`.barm` contract, destination-skeleton constraints and a staged implementation plan. No BactaTank code was reused and no exporter is enabled by this packet.
- [ ] Implement and validate that independent exporter only after resolving destination skeleton mapping, triangle strips, attribute/weight budgets and axis/material limits with generated interoperability fixtures.

Secondary work remains: browser root/profile state and cancellation, Fortnite extractor/cache identity, distinct DS/3DS FUSE framing, and font-record interpretation. This pass does not claim to finish those projects.

## Instructions for the local chat

Review the packet against its exact base commit and merge on a separate branch while preserving local edits. Run `python tools/check_repository.py`, then the supplied package and original-file Blender commands. Keep specimens and private validation evidence under ignored `local/` and choose fresh outputs outside games/caches. Review new ambiguity diagnostics instead of restoring arbitrary fallback selection.

The next priority is original-file regression of the changed safeguards, followed by the unresolved P3/P4/P5 evidence above. Rebuild and install a locally validated addon update only on the workstation, backing up its previous install and preserving preferences/projects. Do not restart P1, mark broad roadmap goals complete from representative checks, or claim in-game validation without running it. Commit/push only when requested; no scheduled checks.

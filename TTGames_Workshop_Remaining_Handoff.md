# TTGames Workshop — remaining implementation handoff

Updated 6 October 2026. Read this alongside the [master roadmap](TTGames_Workshop_Master_Roadmap.md), root README, AGENTS.md and the relevant component docs. This condenses the supplied implementation handoff; it does not replace the broader roadmap.

## Current checkpoint

Last pushed commit: `8487e64` (Character 0.5.5 / CU3 0.1.14). Latest local builds are Character 0.5.6 / CU3 0.1.15, validated and installed, and included in this source update.

- [x] ~~P1: attachment rollback and consumed-dependency provenance.~~ Implemented and checked. See [the detailed checkpoint](docs/HANDOFF_P1_CHECKPOINT.md).
- [x] ~~P1: changed/missing companion rejection before native bundle output.~~ Original-file copied-fixture checks passed for CD, TEX, AS, PAK and loaded AN4.
- [x] ~~P1: package, representative import/export and installation validation.~~ Four enabled game profiles and two CU3 examples passed their scoped checks.

Materials, faces, missing parts and full cutscene reconstruction remain incomplete. No new game profile or general native writer was completed by P1. Native bundle publication is still not transactional.

## P2 — shared-source conflicts and output publication

- [ ] Group Blender instances by canonical native source path before producing edited payloads. The current exporter can overwrite an earlier instance's proposed edits with a later instance's payload.
- [ ] Reject conflicting edits, including an edited instance paired with an unchanged instance of the same source. Identical proposed edits should produce one file.
- [ ] Stage the complete bundle in a uniquely owned sibling directory, verify payload hashes and manifest, then publish to an absent destination. Handle concurrent destination creation and failed writes without leaving a misleading completed bundle.
- [ ] Test identical/divergent instances, duplicate paths, existing destinations, second-payload/manifest failures, concurrent creation, cleanup and retry. Preserve no-op round trips and intentional edit decoding checks.

Start with `formats/character/Addon/io_scene_tt_character/exporter.py` and its native mesh-edit helpers. Do not promise atomic publication across filesystems; clean up only staging owned by this operation.

## P3 — archive preflight and bounded framing

- [ ] Validate all PAK entry names, duplicate outputs, extents and destination paths before invoking a backend or writing output. Review `formats/an4/lmsh1/unpack_pak.py`; malformed input must not invoke QuickBMS.
- [ ] Enforce packed, decoded and cumulative limits, cursor progress, nested compression bounds and exact decoded sizes.
- [ ] Investigate LOTR mode-3 DFLT using original specimens. Observed headers contain DFLT, little-endian packed length and decoded length; the old reader assumes the reverse. Ordinary zlib probes failed. Synthetic zlib fixtures do not establish this game's codec.
- [ ] Keep unsupported framing rejected until independently verified. Enabling mode 3 alone is not a LOTR compatibility fix.

Reuse verified original readers where appropriate; standalone CLI readers should not depend on Blender imports.

## P4 — identity, profiles and ownership

- [ ] Make game/build/platform/renderer and structure version/byte order explicit. Do not conflate TT archive hashing with shader hashing.
- [ ] Resolve attachment animation ownership from verified skeleton/resource identity rather than matching clip labels and joint counts alone.
- [ ] Resolve skeleton candidates through resource/layer ownership. Distinguish identical duplicate bind tables from conflicting skeletons; report candidate offsets rather than silently selecting the first.
- [ ] Follow the active renderer's definition dependency closure, retaining logical paths and spelling. Diagnose cycles, case collisions and ambiguous basenames. Missing inactive renderer assets should not break a valid active path.

## P5 — proven spans and visual fidelity

- [ ] Validate material/texture spans from verified layouts rather than treating marker matches as sufficient evidence. Check DDS mip, face, array and DX10 payload sizes; keep trailers separate.
- [ ] Establish unsupported UMTL layouts from original evidence and negative neighboring-layout tests. A filename suffix is not enough to select byte order or material structure.
- [ ] Preserve raw and retained weight totals and skipped-sentinel diagnostics before normalization.
- [ ] Verify normal-map channels, tangent handedness and UV orientation with neutral, tilted and asymmetric examples. Do not infer a green-channel flip from the renderer name alone.
- [ ] Expose whether Blender supports the normal-preservation helper. Older versions have a fidelity limitation even when imports succeed.
- [ ] Continue original-versus-imported checks for faces, materials, attachments, visibility, stage geometry and cameras. Depth-only faces need the render helper/compositor; solid viewport appearance is not a fidelity check.

## P6 — broader support after the safeguards

- [ ] Complete one verified game/platform/format family at a time, prioritizing the existing PC profiles and partial LOTR/TFA/LMSH2/DCSV coverage.
- [ ] Require representative original samples, a second independent sample and neighboring unsupported-layout rejection before promoting support.
- [ ] Keep LSW1 PC separate from LSW2/TCS. Later console, handheld and prototype work remains separate and explicitly gated.
- [ ] Keep external implementations as licensed references, not copied or translated source. Do not publish game fixtures, extracted assets, runtimes or keys.

Secondary research remains: browser root/profile state and cancellation, Fortnite extractor/cache identity, distinct DS/3DS FUSE framing, and font-record interpretation. These are not completed by P1.

## Instructions for the next chat

Begin with P2 and request the relevant current source files if repository access is unavailable. A normal chat can inspect supplied code and propose patches, but should not claim Blender, original-file, package or in-game checks ran without actual results. Separate hypotheses from verified decoding. Keep private evidence under ignored `local/` and preserve validated scenes and edited drafts.

Do not restart P1 or mark broad roadmap goals complete based on representative checks. Update support notes when coverage changes. Rebuild and install validated Blender addon updates on the workstation, preserving preferences and backing up replaced files under `local/`. Commit/push only when requested; no scheduled checks.

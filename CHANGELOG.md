# Changelog

## Attachment dependency integrity — 6 October 2026

- Character 0.5.6 preserves earlier/shared texture provenance and image/store
  caches after an optional attachment fails; failed new resources are removed.
- Track consumed model, definition, texture, animation-set and loaded animation
  revisions separately from image caching. Verify companions before native
  bundle output; older imports must be reimported for these new baselines.
- Shared model readers retain consumed hashes and reject changes during decoding;
  CU3 0.1.15 includes this guard. No new binary layout is enabled.
- Add original-file attachment rollback/export regressions and synthetic revision
  checks. Instance conflicts and transactional publication remain next steps;
  see the [support notes](docs/SUPPORT.md).

## Facial shading and preview controls — 5 October 2026

- Character 0.5.5 / CU3 0.1.14 retain evaluated custom normals through facial
  clipping and depth bias on Blender versions with Set Mesh Normal support.
- Correct layout-gated LMSH1 CD head-print UVs, reproduced on Axel Alonso and
  Blade. Source geometry and normal-map UV bindings remain intact.
- Add character sidebar import/preview settings, with highest verified native
  LOD as the default and independent controls for normal strength, facial
  clipping, albedo, color display and render samples.
- Preview copies keep source material graphs intact and use their scene lights
  and world. Native shader and facial masking fidelity remain approximate.
  See [checks, usage and limits](docs/SHADING_AND_QUALITY.md).

## Shared structural validation — 5 October 2026

- Character 0.5.4 / CU3 0.1.13 validate decoded geometry, UVs, skin influences,
  bind matrices and selected associations before Blender object creation.
- Reject negative draw/material/bone references and singular transforms with
  stage-labelled errors; quality warnings preserve the original data.
- Include detected native versions and part/warning summaries in import reports.
  No new game layout or character-specific patch is enabled. See the
  [structural compatibility notes](docs/STRUCTURAL_COMPATIBILITY.md).

## TT face and material corrections — 5 October 2026

- Character 0.5.3 / CU3 0.1.12 correct Avengers material texture indexing and
  bounded UV metadata; uncertain modern shader flags remain opaque.
- Apply verified cutout alpha, retain solid beard/mask printing outside facial
  clipping and include root-linked body meshes in compositor depth holdouts.
- Extend verified packed normals to Hobbit/LB3 layouts and bind their actual
  mesh UV channels without changing native coordinates or topology.
- Move character preview buttons above the animation list. Facial rendering
  remains approximate; see [sample checks](docs/FACE_ACCURACY_0.5.3.md).

## Fortnite recipe fixes and Whiplash hair normals — 5 October 2026

- Character 0.5.2 follows declared head materials rather than guessed filenames,
  handles the verified standard-head color selector and checks missing model/map
  companions before import so installed extraction can retry partial output.
- Deduplicates mounted Fortnite package references in the bridge and browser;
  this installation contains 2,376 distinct figure sources. Discovery is not
  tested coverage. Adds a separate static preview scene with the correct profile.
- Character 0.5.2 / CU3 0.1.11 load layout-gated packed LMSH1 surface normal maps,
  reproducing the missing grooves on Whiplash's hair without changing meshes,
  source normals, bones or native vertex payloads.
- Updates the issue and support notes: Whiplash's facial masking and expression
  fidelity remain incomplete, as do Fortnite split arm colors and extra roles.

## Fortnite Paks-folder browsing — 5 October 2026

- Character 0.5.1 accepts the Fortnite installation or Content/Paks folder in
  the same Game folder field as other profiles. Export libraries still work.
- Automatically separates exports into build-specific caches and supplies
  source/output paths to the configured extraction bridge. Private template
  paths remain relative to their original file; key contents are not copied.
- Archive/dependency metadata changes select a new cache. Game files and the
  settings template remain untouched. The external extractor is still required
  for cooked archives; no new model/material coverage is claimed.

## LEGO Fortnite static character profile — 5 October 2026

- Character 0.5.0 adds LEGO Fortnite export-library browsing, generic default
  dataless recipes and supported baked skeletal meshes. Animations stay disabled.
- Reconstructs native plastic LUT colors, layered printing and normal maps;
  retains source shader textures. Unknown selectors/replacement roles fail clearly.
- Adds an optional original .NET installed-game extraction bridge using external
  reviewed Unreal dependencies. No keys, mappings, external tools or runtimes
  are bundled; outputs remain separate from the game. Highest-mip extraction
  rejects unavailable streamed texture payloads instead of silently blurring prints.
- Documentation distinguishes discovery, tested imports and incomplete Unreal
  facial/special shader reconstruction. Character-specific projects remain private.

## Issue #1: minifigure LODs and LMSH1 arm printing — 5 October 2026

- Character 0.4.3 / CU3 0.1.10 select the nearest verified accessory LOD,
  restoring high-detail hair and hats. Unknown LOD layouts fail explicitly.
- Corrected the layout-gated LMSH1 arm-print UV selection without changing
  native UVs or other games' print mappings.
- Added NXG/DX11 LOD and material-role regression fixtures. Source normals,
  topology, skeletons and animation axes are preserved.
- Updated packages and documented partial issue resolution. Head/face,
  mirroring and shading reports still need specific reproductions.
- Toolbox 0.1.2 carries the current shared readers and package links;
  separate GUI versions are independent of the toolbox version.

## General tool review and package updates — 5 October 2026

- Reviewed the existing LIJ1 0.1.2 work, reran its 57 synthetic checks and checked
  packaged C3PO extraction. No duplicate LIJ1 changes or game data were imported.
- Packaged CU3 0.1.9 with the shared accessory-reader fixes; installed-game
  imports and synthetic Blender stage, face, normal and playback checks pass.
- Fixed per-tool GUI test versions and the static-stage hash fixture. Updated
  the toolbox download to 0.1.1, including usable packaged documentation links.
- Added exact raw PICA payload checks and FUSE entry bounds checks, with six
  texture and five FUSE fixtures; BTGA GUI is now 0.1.2.
- Added DCSV index CLI help and protected new-output writing with two checks;
  its independent GUI is now 0.1.2. No new game import profile was enabled.
- Added a general tool review with evidence scopes and prioritized next work.

## Character accuracy and documentation fixes — 5 October 2026

- Character addon 0.4.2 reads verified older static LMSH1 accessories, DISP 16,
  UMTL 163 and TXTS 0, restoring Magneto's helmet. Corrected UMTL 174's shorter
  prefix restores texture indices for other accessories; shader flags remain
  approximate and unknown layouts are rejected.
- Supported standalone BSA face weights now follow loaded clips. Switching to
  a clip without a face track resets keys to Basis. Edited linked facial and
  attachment actions are rejected by native exports rather than lost silently.
- Added portable binary fixtures and an asset-free Blender state/rollback check.
  Actual character validation covers Magneto and facial samples in all four
  enabled games, plus unchanged accessory export/reimport. No new game test.
- Repaired broken Markdown encoding, updated current instructions and package
  links, and added a manual encoding/relative-link check. Newest-only downloads
  and private asset exclusions remain in place.

## LIJ1 prototype texture extraction fixes — 4 October 2026

- Updated the Windows extractor to 0.1.1 with validated layout 0 secondary
  resource descriptors and the observed 32x32 single-level BC1 4 KiB allocation.
- Added bounded recovery for the on-disc legacy Indiana Jones icon's mixed
  byte order and inconsistent chunk lengths, with window/CLI/manifest warnings.
- Verified all five reported GSCs against independent DDS references; retained
  byte-identical output for all 387 previously accepted containers in the ISO.
- Added portable parser checks and regression scripts with explicit output
  paths. Game inputs, reference textures and ISO access remain local.

## LSW1 colors and downloadable builds — 4 October 2026

- Corrected solid LSW1 palette colors to match the texture color-space convention.
- Updated HGP importer to 0.1.3 with original-color metadata and material-role checks.
- Added builds/download instructions for the HGP addon, CU3 addon and our LIJ1
  prototype DDS extractor. No game assets, scenes or external extraction tools.

## First consolidated source snapshot — 4 October 2026

- Added central game/format indexes and per-project documentation.
- Imported CU3 0.1.5 source, including native face rendering and GHG target tools.
- Imported original LSW1 HGP importer 0.1.2 with native normals and face alpha.
- Imported LIJ1 Xbox 360 prototype DDS extractor 0.1.0 and its layout notes.
- Included original Marvel animation decoder/sampler/BVH helpers.
- Added a portable BTGA converter and bounded FUSE payload helper based on the
  verified Universe in Peril 3DS investigation.
- Kept character-specific scripts, suit profiles, LOTDK mapping and Fortnite
  experiments in the private local archive rather than the public repo.
- Kept private game assets, scenes, external dependencies and historical logs
  outside Git. Preserved existing component licenses and AI acknowledgment.
- Added AI working instructions and manual source checks; no CI automation.

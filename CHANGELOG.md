# Changelog

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

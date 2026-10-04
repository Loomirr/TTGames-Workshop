# Changelog

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

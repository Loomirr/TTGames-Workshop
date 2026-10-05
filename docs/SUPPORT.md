# Support and validation

The repository import is a reorganization of existing work, not a claim that
all formats or games are now supported.

- LEGO Fortnite static profile (character 0.5.2): searchable exported recipe and
  baked-model assembly, original plastic LUT colors, layered printing and normals.
  Four Wolverine-family outfits passed offline Blender assembly; Wolverine and
  Peely were extracted from the installed 42.30 build into a fresh cache and
  imported. The deduplicated streamed inventory contains 2,376 figure sources; that
  is not tested import coverage. Runtime facial atlases and special shaders are
  incomplete. The optional bridge uses external Unreal dependencies and rejects
  unavailable full-resolution mips. Version 0.5.2 accepts install/Paks folders,
  creates separate build caches and preserves the private settings template.
  Eleven constructed cache/settings checks pass; installed Blender checks cover
  live Paks indexing, Wolverine/Peely imports and fresh Wolverine extraction.
  A broader 0.5.2 check decodes 41 recipes and imports twelve of fourteen selected
  figures; split arm colors and an unverified neck accessory are explicitly
  rejected. See [the import audit](FORTNITE_IMPORT_AUDIT.md) for exact scope.
  See [setup and limits](../formats/fortnite/README.md).

- Character addon 0.5.3: independent LMSH1/LB3/Hobbit/Avengers character and declared
  animation browsers, supported ANI-D playback, native TT inner decompression,
  matching attachment tracks, separate live/composed face previews and loose native-source
  export. Explicit default/cutscene costume layers and native material role IDs
  fix several missing attachments and costume color assignments. Variable-length
  LB3 facial target records are now read correctly. Five characters were checked
  in Blender 5.2.2, with three actions each and finite evaluated poses/meshes.
  A further four-character Blender check covers Gandalf, Thorin, Killer Croc and
  Hulk with three clips each. Empty conversion-metadata texture stores now load.
  Full roster preflights found 374/467 LMSH1, 280/361 LB3 and 375/417 Hobbit
  definitions passing the probed readers. These counts are not visual certification.
  Recursive attachment configuration, textures, facial timing and all clips are
  not covered by that audit. Existing vertex edits and constrained active ANI-D
  export are available; general topology/material/skeleton writing remains unfinished.
  Version 0.4.1 corrects custom-normal setup order and writes verified normals
  and four-influence skin weights within existing palettes. One edited character
  per enabled game and a static Avengers GSC were exported and reimported.
  Unsupported material/image, rest-bone and loaded-animation edits are rejected
  instead of silently copying their original native data.
  Hobbit MESH 170 face-target writing is enabled for the observed offset layout;
  48 cached faces passed decoded no-op and edit checks. No new in-game test was performed.
  Version 0.4.2 restores verified older static LMSH1 accessories and their
  texture stores, fixes UMTL 174 texture alignment, and links supported
  standalone BSA facial weights to loaded clips. Magneto's helmet, face and
  cape were checked with three idle clips. Facial samples also matched source
  values for Wolverine, B66 Catwoman, Bilbo and Captain America. Black Widow's
  bracelets, Professor X's chair and Sabretooth's backpack passed unchanged
  loose-source export/reimport. Older shader flag meanings and live facial
  masking remain approximate. Facial/attachment action edits are rejected
  on export; their native curves are not rewritten. These changes are bundled
  in the character download. CU3 0.1.9 also packages the shared accessory
  readers; standalone facial clip linking remains a character feature.
  Avengers adds 821/882 parser-ready definitions, sample Blender assembly/playback,
  modern texture/material readers and unpacked-folder round trips. TFA/DCSV/LMSH2/LOTR archive inspection is available, with explicit
  model and animation version limits. See [compatibility](../formats/character/COMPATIBILITY.md).
- Desktop GUIs 0.1.1: nine separate Python/Tk downloads, each checked by launching
  an extracted copy and importing its own backends. No full checkout or common
  toolbox installation is required. Python is required; only BTGA needs Pillow.
  Face decoder 0.1.2 now reads supported GHGs directly; the old plain-text extraction
  log is optional on the CLI and no longer needed in the GUI.
  Face writer 0.1.2 adds constrained MESH 170 target edits, with native-part validation.

- CU3 0.1.12: partial LMSH1/LB3 actor, attachment, material and camera assembly
  from an installed game folder or extracted assets. The addon defaults to
  assembly, detects the verified CU3 versions 18/19 and remembers per-game
  folders. Original Python archive readers load requested companions into an
  external cache; no separate extraction executable is required for those
  supported archives. Live camera playback uses approximate facial depth
  clipping. Experimental static environments load declared primary/shared GSCs
  using native draw matrices and material indices; named-special draws are
  excluded. Stage visibility and render controls remain approximate. Nested
  scenes, props, original lighting, audio, effects and full shader/face accuracy
  remain incomplete. Simple declared character replacements select root
  resources; other registry commands remain unapplied. Native layer-special
  and attachment tint selection reduce overlapping models and incorrect
  accessory colors. Six portable stage tests and a synthetic Blender builder
  check cover native bindings and geometry invariants, not full-scene fidelity.
  TFA versions 22–27 support reference inspection: 426 files were structurally
  checked. Its two private animation examples contain rigs only. TFA/DCSV
  ANI-E playback and full scene assembly remain disabled. Name rebuilding and
  hash/layout-locked face target editing have separate validation scopes.
  The workflow/dependency audit is in [WORKFLOW.md](WORKFLOW.md).
  Version 0.1.9 packages verified older static LMSH1 accessories and UMTL 174
  texture alignment. Synthetic Blender checks cover stage draw invariants,
  normals, composed facial masks, shader helpers and live playback. Full scene
  reconstruction and in-game fidelity remain separate unresolved work.
- LSW1 HGP: original PC character reader; ten headers in the prior local sample
  remain unsupported. Version 0.1.3 corrects palette color-space handling;
  color/material-role checks cover 1,827 records in 139 readable files.
- LIJ1 prototype 0.1.2: all 757 supplied GHG/GSC files process, producing 11,182
  DDS resources / 92,820 face-mip images, nine explicitly raw-only allocations,
  and 90 empty-container manifests. All 2,898 prior DDS outputs are unchanged.
  The 344 TEX, seven Xbox font and 347 existing DDS inputs also pass. BC1/2/3/5,
  float and six-face cubemaps are covered. Compact/zero-metadata objects export
  base images with warnings. Extended Python checks compare 1,142 face/mip
  images, decode 1,140 and check 131,072 float pixels. The original regressions
  cover 83 mips. Selected visuals were checked; this is not in-game validation.
  Other-platform fonts/CSC data and ISO/archive unpacking remain outside scope.
- AN4: observed ANI-D six-channel layouts, constants and packed type-6/7 curves.
  The original standalone BVH workflow targets the verified 63-joint HGOL v10 rig;
  the separate character addon supports additional validated native skeleton layouts.
- 3DS BTGA: observed 56-byte texture header, PICA tiles, stored mips. The FUSE
  helper reads indexed payloads; it does not unpack encrypted ROMs.
  BTGA GUI 0.1.2 rejects short/trailing raw PICA payloads before allocating
  pixels. Six asset-free texture tests cover known raw/ETC pixels, tile/flip
  order, stored mips and DDS bytes; five FUSE command/bounds tests are separate.
  The optional toolbox 0.1.1 is now packaged from the current sources.

Character projects, LOTDK mapping and Fortnite tools are intentionally excluded
from the public source. They remain in the private migrated archive.

Run portable checks manually with `python tools/check_repository.py`.
Blender-dependent and original-file tests are documented in each component.
There are no scheduled checks or CI workflows in this first version.

Public Markdown encoding and relative file links are checked with
`python tools/check_docs.py`, also included in the manual repository check.
This does not verify external URLs or certify support claims. Those claims
require the format, Blender, visual and in-game evidence described above.

The [0.5.3 face accuracy report](FACE_ACCURACY_0.5.3.md) records the four-game
material and facial preview corrections, sample checks and remaining limits.

# Support and validation

Character 0.5.16 / CU3 0.1.25 add LB1/TCS raw model inspection and a separate
classic CU2 reference importer. Missing rigid attachments, overlapping variants,
approximate shaders and unavailable AN3 playback remain explicit limitations.
The PC DAT index tool covers eight selected game/layout profiles.
[Checks and remaining gaps](COMPATIBILITY_EXPANSION_2026-10-09.md).

The repository import is a reorganization of existing work, not a claim that
all formats or games are now supported.

The current experimental candidates are Character 0.5.16 and CU3 0.1.25.
The [7 October reference review](RESEARCH_REFERENCES_2026-10-07.md) adds read-only
LMSH1 material-parameter diagnostics, bounded native face target summaries and
an explicit standalone parent `-5` inventory option validated on four LEGO
Movie DATs. It does not enable a new character profile or change native shader
behavior. The proposed alternate LZ2K distance rule failed original face mesh
checks in all four enabled TT character games; the existing decoder is retained.
The latest shared corrections preserve valid authored normals when another
vertex lacks a usable direction, recognize facial filenames case-insensitively,
and fix scoped animation/texture companion lookups. The new bounded native
variant path resolves both supplied shared bodies; the CC8 v1 ROTV extension
validates all 17 supplied Avengers indexes with their existing entries preserved.
Other unknown variants, storage modes and index suffixes remain rejected. See
[the accuracy review and test scope](CHARACTER_ACCURACY_0.5.9.md).

The preceding 0.5.8/0.1.17
issue follow-up repairs missing preview settings and `SpiderFace` live
grouping, rejects singular skeleton candidates before ownership arbitration,
and adds read-only archive/skeleton/material diagnostics. Material-remap and
native shader reconstruction remain incomplete. No ownership, DDS or archive
format gate has been relaxed. See [issue status](ISSUE_1_MINIFIGS.md) and
[diagnostic tools](DIAGNOSTIC_TOOLS.md).

The preceding 0.5.7/0.1.16 candidates added shared-source/export safeguards,
bounded readers, explicit identity and raw-weight/fidelity diagnostics. The
[workstation review](MERGE_PACKET_REVIEW_2026-10-06.md) found original shared-body
ownership and Avengers index blockers. The specific supplied body/index records
now validate; the subsequent complete-character recovery checks are recorded in
[the recovery report](RECOVERY_2026-10-07.md).
Historical original-file results below remain attached to their stated versions.

Character 0.5.6 adds attachment rollback and consumed companion revision guards;
CU3 0.1.15 adds the shared model revision check. No new profile or shader layout
is enabled. See [support notes](SUPPORT.md).

Character 0.5.5 / CU3 0.1.14 preserve evaluated normals in supported Blender
facial preview helpers and correct layout-gated LMSH1 head-print UVs. Character
sidebar settings expose highest verified LOD selection and independent preview
normal-strength/display controls. These improve selected Blender samples,
without changing current game-profile coverage or establishing full native
shader fidelity. See [shading and quality checks](SHADING_AND_QUALITY.md).

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

- Character addon 0.5.6: independent LMSH1/LB3/Hobbit/Avengers character and declared
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
- Earlier desktop GUI validation (0.1.1): nine separate Python/Tk downloads, each checked by launching
  an extracted copy and importing its own backends. No full checkout or common
  toolbox installation is required. Python is required; only BTGA needs Pillow.
  Face decoder 0.1.2 introduced direct supported-GHG reading; the old plain-text extraction
  log is optional on the CLI and no longer needed in the GUI.
  Face writer 0.1.2 added constrained MESH 170 target edits, with native-part validation.
  See the [current build table](../builds/README.md#separate-gui-downloads)
  for the independently versioned downloads and present validation limits.

- CU3 0.1.14: partial LMSH1/LB3 actor, attachment, material and camera assembly
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
  The current optional toolbox is 0.1.5 and includes the updated shared readers.

Character projects, LOTDK mapping and Fortnite tools are intentionally excluded
from the public source. They remain in the private migrated archive.

Run portable checks manually with `python tools/check_repository.py`.
Blender-dependent and original-file tests are documented in each component.
There are no scheduled checks or CI workflows in this first version.

The [skeleton transfer planner](../tools/skeleton_transfer/README.md) provides
read-only rig/mapping/AN4 inspection and an explicit-axis, rest-relative rotation
API. Seven portable tests cover rest offsets/scale, axis changes, hierarchy
differences, count-only mapping refusal and output protection. The original
Dimensions HGOL 16 donor and a privately decoded recipient reference were also
planned; compact recipient arrays remain rejected as native input by the public
reader. Six additional portable audit tests cover byte order, segment starts,
flags, subframe comparison, explicit edit scope and protected output. Seven
item declaration tests cover literal paths, comments, nested ownership,
references, duplicate/orphan blocks and protected output. This audit inspects
the observed braced text subset; it does not resolve binary action resources.
Cross-game native transplant export is not enabled. A combined private candidate
failed the DCSV runtime test; decoder/Blender results did not certify it. A
subsequent original-motion control ran without a reported crash or broken
weapon motion, but body attacks and grip still need work. The retained
evidence and unresolved validation are separate in
[the transfer notes](SKELETON_TRANSFER.md).

Public Markdown encoding and relative file links are checked with
`python tools/check_docs.py`, also included in the manual repository check.
This does not verify external URLs or certify support claims. Those claims
require the format, Blender, visual and in-game evidence described above.

The [0.5.3 face accuracy report](FACE_ACCURACY_0.5.3.md) records the four-game
material and facial preview corrections, sample checks and remaining limits.

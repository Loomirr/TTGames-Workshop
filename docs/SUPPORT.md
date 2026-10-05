# Support and validation

The repository import is a reorganization of existing work, not a claim that
all formats or games are now supported.

- Character addon 0.3.1: independent LMSH1/LB3/Hobbit character and declared
  animation browsers, supported ANI-D playback, native TT inner decompression,
  matching attachment tracks, separate live face previews and loose native-source
  export. Explicit default/cutscene costume layers and native material role IDs
  fix several missing attachments and costume color assignments. Variable-length
  LB3 facial target records are now read correctly. Five characters were checked
  in Blender 5.2.2, with three actions each and finite evaluated poses/meshes.
  A further four-character Blender check covers Gandalf, Thorin, Killer Croc and
  Hulk with three clips each. Empty conversion-metadata texture stores now load.
  Full roster preflights found 342/467 LMSH1, 280/361 LB3 and 375/417 Hobbit
  definitions passing the probed readers. These counts are not visual certification.
  Recursive attachment configuration, textures, facial timing and all clips are
  not covered by that audit. General mesh/material/animation writing is absent;
  Hobbit MESH 170 face-target writing remains disabled.
  Avengers/TFA/DCSV/LMSH2/LOTR archive inspection is available, with explicit
  model and animation version limits. See [compatibility](../formats/character/COMPATIBILITY.md).
- Desktop GUIs 0.1.1: nine separate Python/Tk downloads, each checked by launching
  an extracted copy and importing its own backends. No full checkout or common
  toolbox installation is required. Python is required; only BTGA needs Pillow.

- CU3 0.1.8: partial LMSH1/LB3 actor, attachment, material and camera assembly
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
  TFA versions 22Ã¢â‚¬â€œ27 support reference inspection: 426 files were structurally
  checked. Its two private animation examples contain rigs only. TFA/DCSV
  ANI-E playback and full scene assembly remain disabled. Name rebuilding and
  hash/layout-locked face target editing have separate validation scopes.
  The workflow/dependency audit is in [WORKFLOW.md](WORKFLOW.md).
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

Character projects, LOTDK mapping and Fortnite tools are intentionally excluded
from the public source. They remain in the private migrated archive.

Run portable checks manually with `python tools/check_repository.py`.
Blender-dependent and original-file tests are documented in each component.
There are no scheduled checks or CI workflows in this first version.

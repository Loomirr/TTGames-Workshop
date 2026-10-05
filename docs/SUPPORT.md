# Support and validation

The repository import is a reorganization of existing work, not a claim that
all formats or games are now supported.

- Character addon 0.1.0: independent install and minifig CD browser, observed
  LMSH1/LB3 native model assembly, and uncompressed standalone AN4 v13/14 actions.
  The packaged addon was checked in Blender 5.2.2 with one character from each
  game and three LMSH1 actions, including clip switching and finite evaluated
  poses. Eight LMSH1 clips match the previous scalar decoder at sampled frames;
  four synthetic checks cover byte order and tree rejection. Face masking,
  smoothing and some costume/material details still differ visibly from the
  game. LB3 standalone `Deflate_v1.0` wrappers are rejected, not decoded.
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
  TFA versions 22–27 support reference inspection: 426 files were structurally
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
  The standalone skeleton reader expects the verified 63-joint HGOL v10 rig.
- 3DS BTGA: observed 56-byte texture header, PICA tiles, stored mips. The FUSE
  helper reads indexed payloads; it does not unpack encrypted ROMs.

Character projects, LOTDK mapping and Fortnite tools are intentionally excluded
from the public source. They remain in the private migrated archive.

Run portable checks manually with `python tools/check_repository.py`.
Blender-dependent and original-file tests are documented in each component.
There are no scheduled checks or CI workflows in this first version.

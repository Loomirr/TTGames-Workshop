# GitHub review, 9 October 2026

Reviewed [issue #3](https://github.com/Loomirr/TTGames-Workshop/issues/3),
[issue #4](https://github.com/Loomirr/TTGames-Workshop/issues/4) and
[PR #5](https://github.com/Loomirr/TTGames-Workshop/pull/5), plus the earlier
minifigure reports. The maintainer subsequently requested publication of this
validated checkpoint. PR #5 is only partially incorporated; its remaining
exporters and archive extraction still need review and validation.

## LMSH1 report

- Character audit model and attachment lookup now uses the same scoped CHARS
  namespace resolver as import. Renderer-inactive attachments are excluded.
  CU3's resource resolver also checks scoped CD paths. Exact paths still take
  priority; missing paths do not silently fall back to unrelated basenames.
- The LMSH1 dependency gate and Blender AUTO dispatch accept CU3 v16/v17/v18.
  Existing camera, animation and resource checks still apply independently.
- BVH export creates an empty export manifest when no scalar clips decoded.
  Existing destinations remain protected. Invalid skeleton and archive-layout
  CLI inputs now produce short errors rather than tracebacks.
- Archive cache temporary filenames no longer repeat the full asset basename.
  Path-length write failures explain how to choose a shorter cache. Windows
  path ownership and traversal checks remain in place. A temporary-name
  collision preserves the existing file. Long catalog test fixture paths were
  shortened without removing the separate plugin-mount test.

The complete installed LMSH1 audit checks **467 definitions, 299 distinct
models, 369 parser-ready definitions**. The remaining 98 include missing
resources, incomplete definitions and unverified mesh/material/skeleton layouts.
These are recorded failures, not proof that 369 characters render correctly.

All 312 installed CU3 files were scanned: 5 v16, 71 v17, 230 v18 and 6 files
outside the accepted envelope. Structural parsing passes 305 files. Camera
decoding passes 35 v17 and 199 v18 files; 67 reject the camera footer, four
reject skeletal curve type 11 and one rejects an actor switch table. Removing
the profile block does not resolve those remaining failures. No camera layout
was guessed to inflate coverage.

## Classic-game contribution

The PR changes 35 files and carries an MIT license credited to Gibby. Changed
source files were extracted into ignored review storage and verified against
their Git blob hashes. Only the reviewed CU2/GIZ inspectors and shared classic
scalar decoding are integrated so far. See [coverage and commands](../formats/classic-pc/README.md).

The remaining contribution needs more work before publication:

- Archive output paths and table extents need bounded validation; extraction
  must not overwrite existing files or race multiple archives into one folder.
- LZ2K must reject exhausted bitstreams and honor bounded output sizes.
- Model/animation glTF exporters need independent visual checks. Node-to-bone
  fallback by array index is not acceptable when ownership is unverified.
- The contributed approximate AN4 reader was not included. It does not replace
  Workshop's separately gated AN4 implementation.
- Unsupported CU2 versions cannot be interpreted as v520. Malformed scalar
  tables, missing constants and incomplete key ranges are refused. Original
  constant-only blocks with a null key pointer remain valid.
- Shell-string commands and external-buffer URI handling need review before
  the remaining utility scripts are added.

Batman 1 and TCS inspection counts are in the component README. TCS's two
rejected AN3 files are the installed `PALPATINE_SITH/IDLE.AN3` and `RUN.AN3`;
the local tree is modified. Its GIZ failures include truncated/placeholder
files and three mismatched pickup record counts. No unknown layout is enabled
on the strength of a file extension alone. Indiana Jones lacks local validation.

## Validation completed in this pass

The repository check passes **584 constructed tests**, source/config checks,
documentation links and package integrity checks. Blender 5.2.2 registers both
new packages independently and together. Fresh character imports of Magneto,
Batman, Thrain and Captain America (AOU) each load an idle animation and produce
a composed-face render. Those images were inspected; their lighting/materials
remain approximate and are not certified against an in-game reference.
The same four characters also import from their extracted companion trees,
with the same model counts and no assembly issues. This checks both input
routes for those samples, not every extracted resource in each game.

All nine independent GUI downloads pass hidden-window launch/backend checks.
The toolbox's six tests pass with its documented Pillow dependency present;
the default workstation Python lacks Pillow, so the conversion tests initially
failed there. No global Python installation was changed. The classic download
also runs all three inspector commands against original Batman 1 files from
an isolated extracted copy and retains its MIT license.

The formerly blocked LMSH1 v17 `grandcentral_midtro_2a_nxg` assembles five model
instances and three cameras, with two unresolved Iron Man attachment identities.
The v18 Stark Tower regression assembles seven model instances and thirteen
cameras. Both render; static environments were disabled to isolate actor and
camera regression. These are incomplete scenes, not new faithful previews.

Whole-definition parser audits now cover all four enabled TT character profiles:

| Game | Definitions checked | Parser-ready | Unique models probed |
| --- | ---: | ---: | ---: |
| LMSH1 | 467 | 369 | 299 |
| LB3 | 361 | 265 | 311 |
| The Hobbit | 417 | 359 | 244 |
| Avengers | 882 | 800 | 447 |

These counts include unused/alternate definitions and explicitly refused layouts.
They measure dependency/model preflight, not a roster of fully accurate imports.
Private manifests retain every failure. Missing dependencies were not suppressed
or substituted with unrelated models.

Character **0.5.15** and CU3 **0.1.24** were installed into the workstation's
Blender 5.2 profile after package checks, with backups outside the profile.
The installed copies load, import Wolverine and play its 146-frame idle clip;
preferences remain byte-identical. Restart an already-open Blender to reload them.

## Remaining priorities

Complete import means models, skeletons, textures, materials, expressions,
animation binding, cameras and source visibility agree with the game. A parser
inventory cannot establish that. Coverage must include whole file inventories,
both packed and extracted lookup, representative visual checks, and explicit
unsupported-layout reports. The goal remains complete per-game coverage;
no current NXG/DX11 or classic reader is certified for every asset variant.

The older face/material reports remain tracked in
[issue #1 notes](ISSUE_1_MINIFIGS.md). Unverified DDS dimensions, material
versions and skeleton ownership remain rejected. The private Jay test 14 and
installed games were not changed by this review.

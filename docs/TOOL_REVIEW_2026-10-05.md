# Tool review — 5 October 2026

This review covers the public components, current downloads and relevant local
validation. The LIJ1 prototype work is already included in the repository;
its existing release does not need to be merged from another checkout.
Private assets, scenes, reports and historical projects stay under ignored
`local/`. Installed games and edited projects were not modified.

## Current tools and evidence

| Component | Current build | Checks in this review | Remaining limits |
| --- | --- | --- | --- |
| Character and animation importer | 0.4.2 | Asset-free facial action switching/rollback; previous native-weight and no-op checks cover Magneto and samples from all four enabled games | Older shader meanings, some faces/attachments and unknown model layouts; no arbitrary material, skeleton or topology export |
| CU3 cutscene importer | 0.1.9 | Packaged default imports from installed LB3 and LMSH1; synthetic normals, stage bindings, holdout compositing, shader helpers and live camera/morph playback | Partial stages/visibility, props, nested actors, source lighting/audio/VFX and exact face rendering; no ANI-E playback |
| Original LSW1 HGP importer | 0.1.3 | Six characters imported from the package; native weights, custom normals, color conversion, bind poses and unchanged source hashes checked | Ten known unsupported headers in the earlier corpus; no animation or native model writer; game shaders remain approximate |
| LIJ1 Xbox 360 prototype DDS extractor | 0.1.2 | 57 synthetic checks; packaged CLI exports C3PO's body and six-face cubemap while preserving the input hash | Nine undersized allocations remain raw; some descriptors provide base images only; no model/animation or replacement-container writer |
| Standalone LMSH1 AN4/BVH utilities | 0.1.1 GUI wrappers | CLI entry points, packaged launcher/backend imports and toolbox dispatch | Original HGOL 10 / 63-joint workflow; BVH transform preview is not equivalent to native gameplay animation; the older PAK helper needs user-supplied external tools |
| 3DS BTGA/FUSE | BTGA GUI 0.1.2 | Six Pillow-dependent texture checks and five standard-library FUSE checks | Observed Universe in Peril records only; no encrypted ROM parsing, index discovery or sub-tile mip support |
| Separate desktop utilities | Per-tool versions in the build index | Nine independent launchers/backends and six toolbox form/worker checks; all test windows hidden | Launching is not format or visual certification; Python/Tk required, with Pillow for BTGA |

The packaged CU3 examples checked here are LB3's Batcave hub dialogue and
LMSH1's Stark Tower intro. They assembled six and seven model instances,
respectively, with cameras and packed images. Imports completing successfully
do not make those scenes exact replicas of game playback. No new scene renders
or in-game export validation were performed in this review; synthetic facial
and shader fixtures were rendered for their numerical checks.

Earlier LIJ1 original-file validation processed all 757 supplied GHG/GSC files
and the TEX/font/DDS samples. That full corpus was not rerun here. This review
reran the synthetic suite and a shipped-EXE C3PO sample. See
[LIJ1 validation](../formats/nu20/lij1-xbox360/README.md) for the raw/base-only
cases and the earlier independent pixel/mip evidence.

## Issues corrected

- Published the shared older-accessory readers in CU3 0.1.9 as well as character
  0.4.2. The standalone character facial clip links remain a separate feature.
- Updated the standalone GUI smoke test to use each tool's actual version;
  it previously searched for removed 0.1.1 face packages.
- Updated the static-stage fixture to supply its source hash baseline in a new
  output folder. The previous fixture omitted the file expected by the current
  builder. This was a stale test, not evidence of an installed-stage failure.
- Direct PICA decoding now checks the exact input length before making pixels.
  Previously a short raw buffer could silently produce zero-valued pixels.
  FUSE also rejects out-of-bounds empty records and negative decoded sizes.
- The DCSV archive-index CLI now has help, argument validation and exclusive
  output creation. It previously treated `--help` as an archive filename and
  could replace an existing JSON report. This does not expand game support.
- Rebuilt the optional toolbox as 0.1.1, BTGA GUI as 0.1.2 and DCSV index GUI
  as 0.1.2. Toolbox documentation keeps available offline links and redirects
  references to omitted repository files to the online source.
- Retained one current download per tool, checked package hashes and excluded
  game data, scenes, private manifests and external extraction programs.

## What to work on next

1. **Current character accuracy.** Resolve older UMTL 172/164 layouts, shared
   texture slots, attachment matching and the remaining face-mask/shader
   differences using unrelated characters. Current roster preflights pass
   374/467 LMSH1, 280/361 LB3, 375/417 Hobbit and 821/882 Avengers definitions.
   These are parser counts, not visual certification. Prioritize documented
   failures before enabling more games.
2. **Cutscene completeness.** Verify visibility and variant selection, then
   nested objects, rigid props and stage render controls against actual shots.
   Compare faces, meshes and materials with game playback before tackling
   original lighting, audio and effects. Keep live preview responsive.
3. **Native editing.** Extend writers separately for facial BSA/attachment
   actions, material/image data and broader geometry changes. Preserve native
   indices and source layout, prove unchanged round trips first, then compare
   decoded edits and test copies in-game. Current export rejection is deliberate.
4. **Unify verified animation paths.** Bring the older desktop AN4/PAK workflow
   onto the bounded compression/bank readers where layouts match, keeping its
   original skeleton gate. Broader BVH or retarget support needs rest-relative
   transform and decoded-pose evidence, not shared file extensions.
5. **Later games and handhelds.** TFA, DCSV, LMSH2 and LOTR remain inspection
   profiles with substantial model/animation gates. ANI-E is a separate task.
   Full 3DS/DS character import comes after the current PC accuracy work.
   [Compatibility notes](../formats/character/COMPATIBILITY.md) list the gates.

## Repeat the manual checks

From the repository root:

```sh
python tools/check_repository.py
python formats/btga/3ds/test_btga.py
python tools/test_workshop_gui.py
python tools/test_individual_guis.py
dotnet run --project formats/nu20/lij1-xbox360/Tests/ParserChecks/ParserChecks.csproj
```

The first command runs 183 standard-library native/archive/package/FUSE/CLI
checks, source syntax/config checks, Markdown encoding/relative links and
package integrity. BTGA additionally needs Pillow; GUI checks need Python/Tk;
the LIJ1 synthetic project needs the .NET 10 SDK. Blender checks are separate,
documented by their component scripts, and used Blender 5.2.2 here.
There are no scheduled checks or automation.

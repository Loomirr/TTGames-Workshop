# Development order

Work through **Early Classic → NXG → DX11 → NTT → Classic**, completing and
testing each game's formats and editing workflow before expanding support.
This is the project strategy, independent of the Blender UI.

The [era development plan](ERA_DEVELOPMENT.md) defines completion criteria,
evidence and remaining work. **Early Classic is active: LSW1 PC first, then
LSW2 PC. No era is complete yet.**

For every game, complete the [shader, face, facial-animation and native-export
requirements](VISUAL_AND_FACE_COVERAGE.md). The goal includes 1:1 recreation;
current approximations stay explicitly incomplete.

Immediate work:

1. Reconcile the full LSW1 release inventory with extracted samples.
2. Build on the [LSW1 ANI/BSA record reader and preserving editor](../formats/hgp/lsw1/docs/ANIMATION_RECORDS.md):
   prove ownership, track mapping and interpolation before native playback.
   Preserve the distinction from later AN3/AN4 families.
3. Resolve remaining model fields, assembly and visual issues, including native
   shaders, face geometry/targets, depth masks and facial playback.
4. Implement and validate native model/animation editing and export, including
   bone additions, part replacement, facial edits and material settings.
5. Repeat the complete audit for LSW2, with original-file and in-game tests.

Existing later-era tools remain available. Regression fixes can continue;
new compatibility expansion follows the era order. Fortnite work is deferred.

Historical [workflow notes](WORKFLOW.md), [support reports](SUPPORT.md),
[LSW1 feedback](LSW1_FEEDBACK_2026-10-20.md) and
[animation coverage](ANIMATION_SUPPORT.md) remain evidence, not completion claims.

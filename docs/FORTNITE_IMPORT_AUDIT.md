# LEGO Fortnite import audit, 5 October 2026

Character 0.5.2 fixes two generic recipe assumptions and duplicate discovery.
The inspected installation is Fortnite 42.30. These are static extraction and
Blender checks, not a complete roster or Unreal shader fidelity audit.

## Reproduced problems

- SwissKale declares `MI_HeadStandard_SwissKale` in `Head Material`. The old
  importer constructed `MI_Head_SwissKale` instead. The importer now follows
  the declared package reference, including its inherited parameters.
- DummeezA's material omits `Color Head ID`; its standard Mutable head uses
  the explicit `Head Standard Color` selector. That selector is now accepted
  for the verified standard head only. Special heads require a material color.
- A failed/partial export could leave its recipe JSON behind, causing the
  browser to skip extraction while required GLBs or maps were still absent.
  Required companions are now checked before import; installed mode can retry
  extraction. Unknown layouts remain errors rather than retry loops.
- Multiple mounted containers contributed duplicate source references. Both
  the extractor index and Blender catalog now deduplicate package paths.
  Earlier figures near 4,400 counted duplicate records; this build contains
  **2,376 distinct figure sources**, not that many verified imports.

## Broader sample

A deterministic sample of 41 recipes, including SwissKale, was decoded with
its referenced material metadata. Sixteen differed from the old guessed head
filename, thirteen declared split upper/lower arm colors, and six used extra
attachment roles. These categories overlap. Metadata success alone does not
establish model/texture conversion or correct assembly.

Full exports were checked on eight additional sources. The selected library
was then checked in Blender against fourteen figures. Source package names
below are codenames, not verified cosmetic display names.

| Source | Result |
| --- | --- |
| SwissKale | Static import and separate preview |
| ArcticCamoSlateA | Static import |
| BandolierB | Static import and separate preview |
| BubblegumB | Static import and separate preview |
| DummeezA | Standard-head selector color; static import and preview |
| PartyTrooperAA | Static import |
| InkHoop | Special head, declared normal map; static import and preview |
| BlackWidowA | Rejected: unverified split arm colors |
| Football20B_E | Rejected: unverified neck accessory role |
| HightowerWasabiA, DesertShadowA, HydroBottle, OliveStomp | Existing Wolverine-family import regressions |
| BananaA | Existing baked Peely import regression |

Checks include finite evaluated vertex positions, no duplicate catalog keys,
source-scene preservation when creating previews, and import rollback on
rejected layouts. Selected previews were visually inspected. Runtime facial
atlases, source material masks and special effects remain incomplete. No
Fortnite animation or cooked asset writing support is added.

## Remaining limits

Split arm color layouts, replacement limbs, capes and other attachment roles
still require independent geometry/material validation. Native shader
selectors cannot safely be ignored just because their files are present.
Missing streamed textures, mismatched mappings/keys, unknown Mutable layouts
and ambiguous exports can also prevent imports. The archive browser is a
discovery list, not a list of certified characters.

See [setup and limits](../formats/fortnite/README.md).

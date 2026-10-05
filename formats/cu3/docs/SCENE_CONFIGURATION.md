# Cutscene configuration and stage dependencies

The importer reads the game's cutscene and level registries to identify
the resources declared by a selected cutscene. The default assembly mode now
builds supported static stage geometry from those exact primary and shared
GSCs. **Recovered static environment (experimental)** controls this step and
is enabled by default. Its visibility and render controls remain approximate;
it does not reproduce complete environments or their original lighting.
Simple declared character replacements also select root actor resources
through the shared dependency resolver.

The reader supports the observed LB3 version 19 and LMSH1 version 18 profiles:

1. Follow `txt_file` includes from `CUT/CUTSCENES_MAIN.TXT`.
2. Match the CU3's internal name to one `cutscene_start` / `cutscene_end` block.
3. Read its explicit `level` declaration.
4. Match that level in `LEVELS/LEVELS.TXT`, retaining its primary `dir`/`file`
   and any `common_dir`/`common_file` or `commonart_dir`/`commonart_file` pairs.
5. Report declared common objects, hidden specials, character replacements and
   the remaining commands with their source filenames and line numbers.

Configuration lookups require exact game-relative paths. A similarly named
file elsewhere does not satisfy a missing reference. Both extracted asset
folders and supported installed-game archive providers can supply the text.
Includes are limited to 32 levels of nesting, 2,048 files and 16 MiB per file;
cycles, path escapes, ambiguous selected blocks and malformed declarations
are rejected.

## Checked associations

| CU3 internal name | Declared level | Shared level declaration |
| --- | --- | --- |
| `1SEWERS_MIDTRO1B` | `1SewersB` | `1SewersB_TECH` |
| `0GAME_INTROC` | `0GameIntroA` | None |
| `STARKTOWER_INTRO` | `5StarkTowerIntro` | None |
| `GRANDCENTRAL_MIDTRO_2A` | `1GrandCentralB` | `1GrandCentralB_TECH` |
| `GRANDCENTRAL_MIDTRO_2B` | `1GrandCentralC` | `1GrandCentralC_TECH` |

These were resolved from the installed games' actual registry files. The
Stark intro also declares `TonyStarkPants` replaced by `TonyStark` and hides
the special `StarkEntranceShop19`. The replacement helper accepts exact bare
resource IDs, rejects duplicate sources and chains/cycles, and changes only
root resource lookup. Source actor names and animation records remain intact;
attachment lookups do not recursively apply substitutions. Native skeleton
compatibility checks still apply to the selected target.

In the tested Stark case, both definitions select the same native minifig
body GHG. `TonyStark.CD` selects the intended outfit and short tousled hair
attachment where `TonyStarkPants.CD` selects an Iron Man helmet. This verifies
the dependency change; Blender appearance and animation remain separate
checks. Hidden-special commands are still reported without being applied.

The tested source registries have unrelated imperfections. LB3 includes a
missing `Cut/Story/CompanyCredits/CompanyCredits.txt`; LMSH1's level registry
contains a stray `level_end` outside a block. The report records these as
unresolved includes or syntax notes and marks the result
`partial_declarations`, while retaining the complete selected blocks.
Missing root registries, incomplete selected blocks and unresolved selected
levels still prevent association. The configuration report's `applied` field
remains false because it describes declarations only. Root-resource
substitutions and stage builds used by assembly are reported separately; this
does not imply the remaining commands were executed.

## Recovered static geometry

The stage reader accepts the observed LMSH1 MESH 169 / DISP 21 and LB3 MESH 175
/ DISP 32 combinations. It checks static/special section boundaries, material
groups, part indices and matrix indices before building geometry. Source
positions, topology, UVs, vertex colors and native affine matrices feed the
shared mesh/material builder.

Only the bounded static draw section is instantiated. Named-special draws are
excluded, including props that would otherwise appear at their storage
positions or inherit the wrong material. Native rendering-control commands
are retained as evidence, without claiming their visibility or render-pass
meaning is decoded. Unknown layouts or commands are reported as unsupported.

The result is labeled **experimental static geometry** in the scene and
import report. It uses an inspection light; original lights are not loaded.
Stage and overall scene reports remain explicitly incomplete. Disable the
static environment option to inspect actors alone.

Six portable `scripts/test_stage_geometry.py` tests cover command bounds,
material ownership and static/special separation. The synthetic Blender check
`scripts/check_stage_blender.py` passed native positions/matrices, UVs,
topology, colors, material bindings, exclusion of named specials, unchanged
source data and rejection before mutation. These do not establish packaged
scene fidelity or in-game matching.

## Remaining scene work

A stage prefix is not a complete rendering recipe. Native LED scene resources
can name further GSCs, such as a separate sky dome or terrain. Their instances,
transforms, layer activation and platform-specific compiled assets still need
to be linked and checked. LED light descriptions and cutscene-specific light
animation layers also need shader and timing validation before being applied.
The remaining cutscene commands include edit lists, clip distances, audio,
screen fades and drawing rules; retaining them in the report does not mean
the importer implements them.

The configuration's portable synthetic tests are
`scripts/test_scene_configuration.py`. They check declared associations,
ambiguity, bounds, missing inputs and source
syntax notes. They do not validate visual fidelity or in-game playback.

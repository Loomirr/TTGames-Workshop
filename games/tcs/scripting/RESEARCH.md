# Testing, evidence and open work

[Guide index](README.md)

## What this documentation validates

This pass inspected installed text assets and performed read-only native code
analysis. It did not launch the game, install a mod, compile the example scripts,
or validate new examples in gameplay. Markdown/link checks are documentation
checks, not language execution tests.

The inspected asset tree is modded. A recursive search found 905 `.SCP` files:
43 under `SCRIPTS` and 862 under `LEVELS`. Additional levels, backups and old
scripts are included. These are inventory counts for the inspected corpus,
**not a clean retail census, active script count or engine limit**. The guide
uses identifiable examples rather than treating every token in that corpus as
a supported command.

## Source map

Paths below are relative to a user-supplied extracted game tree. No game files
or proprietary decompiled implementation are distributed with these notes.

| Evidence | What was inspected |
| --- | --- |
| `SCRIPTS/DEFAULT.SCP` | Empty state structure |
| `SCRIPTS/JEDI.SCP` | Conditions, conjunctions, transitions, timer/action patterns |
| `SCRIPTS/PATROL.SCP` | Formation, trigger and patrol/combat branches |
| `SCRIPTS/GENERALPARTY.SCP` | Conditional shared-script references and fallback |
| `SCRIPTS/NATIVE.SCP` | Indexed named parameters and their use in comparisons |
| `LEVELS/EPISODE_I/NEGOTIATIONS/NEGOTIATIONS_A/AI/LEVEL.SCP` | Messages, trigger queries, sound and path controllers |
| `CHARS/QUIGONJINN/QUIGONJINN.TXT` | Native character properties and animation blocks |
| `CHARS/OBIWANKENOBI/OBIWANKENOBI.TXT`, `CHARS/MACEWINDU/MACEWINDU.TXT`, `CHARS/DARTHVADER/DARTHVADER.TXT` | Stock blue/purple/red choices, category flags and attachments |
| `CHARS/BATTLEDROID/BATTLEDROID.TXT`, `CHARS/BATTLEDROID/BATTLEDROID_SECURITY.TXT` | Categories, animation blocks and a stock redirect variant |
| `CHARS/COLLECTION.TXT` | Purchase prices, area gates, story entries and cheat codes |
| `LEVELS/EPISODE_I/NEGOTIATIONS/NEGOTIATIONS_A/AI/LEVEL2.SCP` | Creature spawning, group options and message decrement |
| `LEVELS/MAP/MAP/MAP.TXT` | Area settings and door grammar |

## Native build identification

The analyzed unpacked PC executable has SHA-256:

```text
6C9C2B35AA9452BA36C4F816A4AE50E3E8DE133971AE1899A20DE102D7E20ADB
```

The addresses below are virtual addresses for this analyzed image with base
`0x00400000`, not file offsets or universally applicable patch locations. A
packed Steam executable, different revision or relocated image needs its own
identification and analysis. This is a research index, not patch instructions.

| Address | Checked finding |
| --- | --- |
| `0x00512F00` | Action-name resolver checks a supplied table, then the core table, stepping by 12 bytes |
| `0x004F8B10` | String comparison used by that lookup folds ASCII letter case |
| `0x0052B3F0` | Condition parser recognizes comparisons, named parameter operands and `OnMacro` |
| `0x0052C000` | Reference parser reads script/return names, nested conditions and Global/Level flags |
| `0x00801720`–`0x00801758` | Top-level dispatch entries include states, parameters, constants, macros, references, derivation and inclusion |
| `0x00801768` | Core condition registration table; 49 entries before its null terminator |
| `0x008019C0` | Core action registration table; 54 entries before its null terminator |
| `0x005157D0` | `SetState` argument and missing-target handling |
| `0x00515890` | `ResetTimer` options and zero default |
| `0x005159A0` | `Idle` duration/frame setup and update behaviour |
| `0x00584640`, `0x00589410`, `0x00585760` | Character redirect detection, loading and animation declaration processing |
| `0x00418FB0` | Identity-dependent shared hilt selection |
| `0x004A4CE0`, `0x004A4FF0` | Force ring drawing and target-dependent placement |
| `0x005DED80` | Native hierarchy registration |
| `0x00630B40` | Model/animation cache construction |
| `0x0062D400`, `0x0062D360` | Loose and bundled animation filename cache paths |
| `0x00547780` | Level reset of animation filename/request counts |

Native evidence does not establish GPU appearance, performance, successful
script binding or save persistence. In particular, a table's handler pointer
is not an argument signature. No decompiler-generated engine source is included.

The color/material, inheritance and capacity chapters also consolidate earlier
native research. Only findings about the original engine and original structures
are carried forward. Reported but unresolved behaviour, such as special hilt
tints, remains explicitly unresolved. Numbers in the capacity table are not
new limits implemented or newly gameplay-tested by this documentation pass.

## A controlled authoring workflow

1. Back up the target script and record game revision, asset changes and area.
2. Establish which resource actually loads. Keep its binding and packaging
   unchanged for the first test.
3. Make one small change with an observable result, using a command already
   working in that context. Avoid testing spawning, assets and new logic at once.
4. Check braces, unique state names, transition targets and reference sources.
5. Check quoted parameter syntax against the same action's working usage.
6. Verify all named resources in the same area: locators, triggers, paths,
   objects, animations, sounds and character registrations.
7. Restart/reload through the relevant loading boundary. Test the intended
   transition, its reverse/reset path and a player who does not trigger it.
8. Record the visible result and any diagnostic text. Keep “file parsed,”
   “state reached,” “action accepted” and “rendered correctly” separate.

For party logic, include player 1, player 2, an AI-controlled actor and a
player-controlled actor where relevant. Test area re-entry and save reload
before claiming persistence. Use an isolated test character/area rather than
changing every base-game definition to diagnose one failure.

## Troubleshooting

| Symptom | Checks that distinguish likely causes |
| --- | --- |
| Editing has no effect | Wrong area/file, packaged copy still selected, script not bound, reference points elsewhere |
| Script stops progressing | Transition target typo, never-true query, missing actor context, native action waiting on unavailable resources |
| State appears to retrigger repeatedly | Transition cycle, unreset condition/message, player remains in trigger, misunderstood action completion |
| Actor slides or freezes | Animation mapping/resource/cache problem; not necessarily condition syntax |
| Actor ignores a jump/combat request | Native category/target restrictions, missing animation, control ownership, wrong state |
| Character exists but portrait is blank | Icon resource registration/loading; unrelated to localization and AI state names |
| Correct name but wrong behaviour | Registration identity, category, inherited resource assumptions, script binding |
| Crash during area transition | Missing/invalid resources, incompatible definitions, native capacity or lifecycle issue; reduce changes before blaming grammar |
| Named effect stays unchanged | Wrong effect component/pass, native hardcoding, unsupported native color selection or incorrect material |
| Shop purchase does not survive reload | Save completion and purchase persistence; a script message is not proof of a committed save |

Do not silently ignore unknown commands in a future validator. Report them
as unresolved unless the selected game/build's registration evidence covers
them. Conversely, a command absent from the small core inventory is not
automatically invalid: gameplay registration tables extend it.

## Remaining research priorities

- Trace all gameplay registration tables and document handler arguments and
  result codes, with positive and negative examples.
- Establish condition priority, conjunction/disjunction evaluation, action
  scheduling, interrupts and reference return behaviour.
- Document `CONST`, macros, `INCLUDE` and `DERIVEFROMSCRIPT` from actual parser
  handlers and representative assets.
- Verify tokenizer escaping, comment forms, name length limits, encoding,
  malformed input diagnostics and duplicate definitions.
- Trace script binding, global/level lookup order and loose/packed precedence.
- Establish timer units, parameter override paths, message lifetime and script
  processor allocation limits.
- Add a portable linter only once its accepted grammar is evidence-backed;
  distinguish warnings about unverified constructs from proven errors.

Contributions should state the game/platform/build, provide a small original
reproducer, and separate static analysis from actual gameplay results. Keep
game assets and private research dumps out of public documentation and commits.

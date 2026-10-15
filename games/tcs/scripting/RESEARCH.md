# Testing, evidence and open work

[Guide index](README.md)

## What this documentation validates

The reference combines script examples with native parser and handler analysis.
Selected paths were also executed in an x86 emulator, with test boundaries
listed below. Complete tutorial examples have not been tested in gameplay.
Link and formatting checks do not validate script execution.

The source map identifies the files used for each observation. A command
appearing in a file does not by itself establish that the native parser accepts
it or that a particular level loads that script. The guide makes no claim to
an exhaustive inventory of retail scripts or every text interface in the game.
The command index covers the four identified SCP registration tables, not
character/level TXT directives or a complete set of argument signatures.

## Source map

Paths below are relative to the extracted game directory. No game files
or proprietary decompiled implementation are distributed with these notes.

| Evidence | What was inspected |
| --- | --- |
| `SCRIPTS/DEFAULT.SCP` | Empty state structure |
| `SCRIPTS/JEDI.SCP` | Conditions, conjunctions, transitions, timer/action patterns |
| `SCRIPTS/PATROL.SCP` | Formation, trigger and patrol/combat branches |
| `SCRIPTS/COMMANDERPATROL.SCP` | `PreviousResult` following a `GotTriggerArea` query |
| `SCRIPTS/GENERALPARTY.SCP` | Conditional shared-script references and fallback |
| `SCRIPTS/NATIVE.SCP` | Indexed named parameters and their use in comparisons |
| `SCRIPTS/GAMORREANGUARD.SCP`, `SCRIPTS/MISSIONTARGET.SCP` | `CanDefend` usage and explicit disabling forms |
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
| `0x0043C830` | Gameplay initialization installs the extended condition/action tables |
| `0x007F6858`, `0x007F7060` | Gameplay tables: 170 condition entries and 207 action entries |
| `0x00512EA0` | Condition-name lookup checks the gameplay table, then the core fallback |
| `0x00512F00` | Action-name resolver checks a caller-provided table, then the core table, stepping by 12 bytes |
| `0x004F8B10` | String comparison used by that lookup folds ASCII letter case |
| `0x0052B3F0` | Condition parser recognizes comparisons, named parameter operands and `OnMacro` |
| `0x0052B9C0` | Action parser recognizes `DoMacro`; an unknown ordinary action is omitted |
| `0x00512850`, `0x00512860`, `0x00512870` | Diagnostic return stubs on the checked parser paths |
| `0x005132F0` | Condition suffix handling for `goto` and `and` |
| `0x0052C880` | Ordered condition evaluation and conjunction short-circuiting |
| `0x0052CC90` | Processor update: timer, actions, references and state conditions |
| `0x00513540` | State parser promotes `Base` to the front of the state list |
| `0x005136C0` | Parameter declarations accept indexes 0 through 3 |
| `0x0052BDF0`, `0x0052BEC0` | Condition/action macro declarations |
| `0x00513990`, `0x00513B30` | Copying condition/action lists during expansion |
| `0x00513820`, `0x00513F20` | Derivation declaration and parent-state/parameter finalization |
| `0x00513010` | Enabled level-script search precedes enabled global-script search |
| `0x0052C000` | Reference parser reads script/return names, nested conditions and Global/Level flags |
| `0x00801720`–`0x00801758` | Top-level dispatch entries include states, parameters, constants, macros, references, derivation and inclusion |
| `0x00801768` | Core condition registration table; 49 entries before its null terminator |
| `0x008019C0` | Core action registration table; 54 entries before its null terminator |
| `0x005157D0` | `SetState` argument and missing-target handling |
| `0x00515890` | `ResetTimer` options and zero default |
| `0x005159A0` | `Idle` duration/frame setup and update behaviour |
| `0x004445C0` | `CanDefend` actor flag update and `false` argument handling |
| `0x0044B360`, `0x005147C0` | `SetMessage` options and numeric/parameter value resolution |
| `0x00442480`, `0x004424B0` | `Message` preparation and numeric read; null cached pointer reads zero |
| `0x00516C70` | `SetParam` name/value pairs and current processor-value updates |
| `0x00516E30`, `0x00516EE0` | One saved return-state slot, pending return and clearing the saved slot |
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

The color/material, inheritance and capacity chapters describe original engine
behaviour and structures. Unresolved behaviour, such as special hilt tints,
is labelled explicitly. Capacity figures are native analysis findings, not
results of an exhaustive gameplay stress test.

## Executed native checks

The 15 October audit used the original instruction bytes in an x86 emulator,
with memory and input objects constructed for each check. No game process was
launched and no installed game files were changed.
The checked parser, scheduler, table, parameter, message, return-state and
`CanDefend` memory ranges match the identified unpacked executable byte-for-byte.

| Check | Result | Boundary |
| --- | --- | --- |
| All four registration tables | 480 rows match native bytes; all 476 distinct kind/name pairs resolve to the expected entry | Gameplay table pointers installed as in the native initializer; no handler behaviour inferred |
| Contributed 37-name inventory | Every exact condition/action name fails lookup, including both case variants of `UnlockDoor` | Positive gameplay/core controls resolve; one analyzed PC build |
| Unknown action between valid actions | `SetDefensive` omitted; valid neighbours retained | Native parser with modeled line/token input |
| Unknown conditions in conjunctions | Leading guard can disappear; a missing final test can join unrelated groups | Native parsed lists and native evaluator; synthetic processor values |
| Condition priority | First successful independent condition/group wins; failed `and` group skips to the next group | Native evaluator; no scene/actor queries needed |
| Action scheduling | Nonzero return advances; zero waits; waiting calls receive update rather than setup flag | Native processor with synthetic action handlers |
| Action interruption and timer | A successful condition interrupts a waiting action; timer accumulates supplied deltas | No claim about real frame rate, pauses or wall-clock units |
| Action and condition macros | Native declaration and expansion copy the expected nodes; condition suffix selects the supplied target | Modeled lexer; not full tutorial text or nested includes |
| `CanDefend` | Setup enables by default; any case-insensitive `false` argument disables; `0` does not disable | Native handler/comparator with a synthetic actor; combat behaviour not exercised |
| `PreviousResult` | Reuses raw fractional query output after a failed comparison or in an `and` group; starts at zero on fresh evaluation | Native parser/evaluator with controlled tokens and a synthetic timer value |
| `SetParam` | Set, `inc=`, `dec=`, default without actor override, case-insensitive names and two pairs; no actor means no change | Native handler/name lookup with synthetic declared slots; numeric literal conversion modeled |
| `SetMessage` | Assignment, fractional increment/decrement, parameter-valued assignment, name-only zero, setup-only update and mixed-option behaviour | Native handler and parameter helper; message service and numeric literal conversion modeled |
| `Message` | Reads the prepared record's float; null record yields zero | Native query with synthetic record; no allocation or binding-lifecycle claim |
| Saved return-state actions | Current/named destination saved; returning requests a pending state and clears the saved destination | Native handlers/state lookup; no nested-reference gameplay test |

Parser checks supply already separated tokens and model numeric literal
conversion. They do not test the full tokenizer, quoting/escaping edge cases,
resource binding, rendering or complete level execution. State promotion,
derivation, include handling and shared-script search order are separately
labelled static findings; they were not added to the emulated test coverage.

The public [execution guide](EXECUTION.md) describes the consequences for script
authors. The [machine-readable index](COMMAND_INDEX.json) records names and
addresses without distributing game code or assets.
The [values and messages guide](VALUES_AND_MESSAGES.md) covers the additional
handler checks. Its message service was modeled, so those results do not extend
to native message allocation, save persistence or all resource-binding paths.

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

The [37-name audit](UNRESOLVED_NAMES.md) includes native lookup checks,
unknown-name parser/evaluator checks and manifest/package checks for
`SetDefensive`. It does not add gameplay validation of the affected levels.

- Document more gameplay handler arguments and result codes, with positive and
  negative examples; the table inventory alone is not an authoring contract.
- Trace nested reference returns, delayed transitions and interactions with
  explicit `SetState`, including actor/level processor differences.
- Validate macros and derivation in complete scripts; establish `CONST` and
  `INCLUDE` scope, loading behaviour and limits.
- Verify tokenizer escaping, comment forms, name length limits, encoding,
  malformed input diagnostics and duplicate definitions.
- Trace binding callers and loose/packed precedence beyond the checked
  level-before-global name lookup.
- Establish timer units, parameter override paths, message lifetime and script
  processor allocation limits.
- Add a portable linter only once its accepted grammar is evidence-backed;
  distinguish warnings about unverified constructs from proven errors.

Contributions should state the game/platform/build, provide a small original
reproducer, and separate static analysis from actual gameplay results. Keep
game assets and private research dumps out of public documentation and commits.

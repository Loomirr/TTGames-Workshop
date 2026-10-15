# Script names without native PC bindings

[Guide index](README.md) · [Command reference](COMMANDS.md)

Audit date: 15 October 2026. Build identification is in
[research evidence](RESEARCH.md#native-build-identification).

## Finding

A contributed inventory identified 37 condition/action names present in SCP
text but absent from the native registration tables. Executing the analyzed
PC build's own name lookup routines confirms that **all 37 rows fail lookup**,
including both spellings in `UnLockDoor/UnlockDoor`.

This is more specific than “there is no function for that behaviour.” The
finding is that these exact names have no binding through the checked native
text-script lookup paths. Related mechanics can exist elsewhere in the engine,
and another build or platform may differ.

A [comparison with original LSW1](LEGACY_COMPARISON.md) now confirms that
sixteen of these names, including `SetDefensive`, had native bindings in that
earlier PC build. Their absence here is a TCS finding, not a claim that the
commands never existed. Developer intent behind their retention remains unknown.

## Tables and validation

The gameplay initializer at `0x0043C830` installs these tables:

| Kind | Gameplay table | Entries | Core fallback table | Entries |
| --- | --- | ---: | --- | ---: |
| Conditions | `0x007F6858` | 170 | `0x00801768` | 49 |
| Actions | `0x007F7060` | 207 | `0x008019C0` | 54 |

The original command reference listed the core tables only. Absence from those
lists alone was insufficient evidence of an unsupported command. This audit
checks both layers; the [gameplay inventory](GAMEPLAY_COMMANDS.md) and
[full index](COMMAND_INDEX.json) now publish both sets of registrations.

The native condition resolver (`0x00512EA0`) and action resolver (`0x00512F00`)
were executed in an x86 emulator with the gameplay table pointers installed
as the native initializer specifies. Each CSV name was submitted to its
corresponding resolver. All returned null. Positive controls resolved:

| Control | Handler | Purpose |
| --- | --- | --- |
| `SetState` | `0x005157D0` | Core action lookup |
| `setstate` | `0x005157D0` | Case-insensitive lookup |
| `Activate` | `0x004442F0` | Gameplay action lookup |
| `CanDefend` | `0x004445C0` | Registered defence-related action |
| `GotOpponent` | `0x005151C0` | Core condition lookup |
| `BlowupBlownup` | `0x00441660` | Gameplay condition lookup |

This executes the real lookup instructions, not a reimplementation of string
matching. Follow-up checks also executed native action/condition parsing with
controlled token input and evaluated the resulting condition lists. They did
not launch the game or execute complete levels, and do not establish gameplay
equivalence between similarly named commands.

## Why repeated names can remain in usable script resources

The text action parser at `0x0052B9C0` handles `DoMacro` explicitly. For an
ordinary action it calls the action resolver. An unrecognized non-brace token
takes a diagnostic branch without allocating an action node, then proceeds to
the next line. The diagnostic functions at `0x00512850`, `0x00512860` and
`0x00512870` are empty return stubs in this build.

Consequently, an unrecognized ordinary action can be silently omitted from the
parsed action list. It does not need a placeholder handler to let parsing continue.
The condition parser at `0x0052B3F0` similarly takes its diagnostic path when
a condition lookup fails instead of constructing the normal condition node.

Do not treat an unknown condition as a guaranteed false condition. Dropping a
test can affect the surrounding transition or conjunction; the resulting
behaviour must be examined in context. Silent parsing is not validation.
Native emulation reproduced a missing leading test removing a guard, and a
missing final test joining two formerly separate condition groups. See the
[worked failure examples](EXECUTION.md#why-an-unknown-condition-is-dangerous).

## `SetDefensive`: 37 occurrences are real

The reported count was reproduced: **37 uncommented occurrences across 13
scripts**, excluding additional-level content. Every one of those 13 scripts
is named in its area's `SCRIPT.TXT`, and each complete script is also present
byte-for-byte in the corresponding `AI.PAK`.

Examples include Maul A `AI/DARTHMAUL.SCP` and Dooku C `AI/DOOKU.SCP` and
`AI/PARTY.SCP`. These contain both bare `SetDefensive` and the `"FALSE"` form.
The package checks rule out the explanation that these are merely commented
examples, unlisted loose files, or text rewritten when placed in those packages.
They establish packaged input, not a fresh runtime trace of every state.

Despite that evidence, `SetDefensive` has no binding in either action table.
When the checked text parser processes it as an ordinary action, it omits it.
Repeated use therefore does not prove implemented behaviour in this PC build.

`CanDefend` is registered, but it is **not a verified drop-in replacement**.
Its handler sets or clears an actor defence flag; the
[checked argument forms](COMMANDS.md#candefend) provide a supported authoring
option when that capability is what the script actually needs.
The LSW1 handler's flag update is now verified, but its full historical combat
semantics and equivalence to TCS behaviour remain unresolved. Do not bulk-replace it
without checking its call sites and the candidate handler's semantics.

## Audited names

Counts below are the contributed inventory's uncommented occurrence counts,
not claims that every containing state executes in gameplay. Case variants
are grouped. Every row has a null native lookup result in this build.

| Kind | Name | Reported uses | Similar registered spelling, if checked |
| --- | --- | ---: | --- |
| Condition | `ObstacleFinished` | 8 | — |
| Condition | `DoorOpened` | 6 | — |
| Condition | `HothBattleWaveCreature` | 5 | — |
| Condition | `GotLocatorInGroup` | 4 | — |
| Condition | `DoorOpenedByPlayer` | 4 | — |
| Condition | `ObstacleChainPhase` | 4 | — |
| Condition | `GadgetActive` | 3 | — |
| Condition | `DoorClosed` | 2 | — |
| Condition | `ObstaclePlaying` | 2 | — |
| Condition | `JustComeFromE` | 1 | — |
| Condition | `PreviousMessage` | 1 | — |
| Condition | `lowupBlownup` | 1 | `BlowupBlownup` |
| Action | `SetDefensive` | 37 | — |
| Action | `AddLocatorGroup` | 27 | — |
| Action | `UnLockDoor/UnlockDoor` | 14 | — |
| Action | `SetObstacleChainPhase` | 13 | — |
| Action | `GetLocatorFromGroup` | 11 | — |
| Action | `SetVisbility` | 10 | `SetVisibility` |
| Action | `LockDoor` | 10 | — |
| Action | `OpenDoor` | 10 | — |
| Action | `ActivateGadget` | 7 | — |
| Action | `ObstacleTriggerSet` | 7 | — |
| Action | `ResetTime` | 5 | `ResetTimer` |
| Action | `SetPlayType` | 5 | — |
| Action | `FollowSpline` | 5 | — |
| Action | `AddLocatorSet` | 5 | — |
| Action | `CloseDoor` | 4 | — |
| Action | `EngageTurret` | 3 | — |
| Action | `FollowSock` | 2 | — |
| Action | `GoToOrign` | 2 | `GoToOrigin` |
| Action | `DisableObstacle` | 2 | — |
| Action | `MakeExplosion` | 1 | — |
| Action | `GoToLoc` | 1 | `GoToLocator` |
| Action | `Wander` | 1 | — |
| Action | `SXetGravityHeight` | 1 | `SetGravityHeight` |
| Action | `SetMesssage` | 1 | `SetMessage` |
| Action | `ThrowThermal` | 1 | — |

Similar spellings are investigation leads, not automatic fixes. In particular,
`lowupBlownup` occurs as a byte suffix inside the string `BlowupBlownup`, but
is not a registered alias. Searching for raw substring bytes would incorrectly
suggest that the misspelled name has a binding. The same caution applies to
prefix matches and strings used only as resource or state names.

## Guidance for script authors

- Check the appropriate gameplay and core tables, not just the core inventory.
- Distinguish exact command names from comments, state names and substrings.
- Verify whether the script is listed and whether the package contains the
  same text before dismissing a suspicious line as unused.
- Use `DoMacro` / `OnMacro` evidence when investigating macros; an ordinary
  unknown action is not automatically resolved as a macro name.
- Treat typos and legacy-looking names as unresolved until their intent and
  surrounding logic have been checked. A plausible spelling is not a safe fix.
- Test observable behaviour. Successful parsing or absence of an error dialog
  does not prove every condition or action was recognized.

These findings do not prove why the names were retained historically. Leftover
authoring content and platform differences remain possibilities for individual
rows. Earlier LSW1 bindings and shared script passages are now established for
the cases in the comparison; they do not establish a motive for retaining them.

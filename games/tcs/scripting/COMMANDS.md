# Command reference

[Guide index](README.md) · [AI language](AI_LANGUAGE.md)

This is a reference to observed usage and a bounded native core, not an
exhaustive list of all gameplay commands. Registration proves that a name has
a handler in the analyzed build; it does not prove the handler works with every
actor, nor establish its arguments. See [evidence](RESEARCH.md).

## Common conditions

The roles below describe their use in the referenced scripts. Arguments, result
domains and edge cases need individual handler checks before extending them.

| Query | Observed role / usage | Evidence example, game-relative |
| --- | --- | --- |
| `GotOpponent` | Test whether an opponent is available; compared with 0/1 | `SCRIPTS/JEDI.SCP` |
| `OpponentIsAThreat` | Distinguish threat handling from following | `SCRIPTS/JEDI.SCP` |
| `OpponentOnSamePath` | Gate engagement on path relationship | `SCRIPTS/JEDI.SCP` |
| `PlayerRange` | Numeric distance threshold in following/combat decisions | `SCRIPTS/JEDI.SCP` |
| `ShouldAttackOpponent` | Gate attack input | `SCRIPTS/JEDI.SCP` |
| `Timer` | Numeric time-related condition, often compared with zero | `SCRIPTS/JEDI.SCP` |
| `PreviousResult` | Feedback used after an operation; do not generalize result codes | `SCRIPTS/PATROL.SCP` |
| `GotTriggerArea` | Select trigger-dependent behaviour | `SCRIPTS/PATROL.SCP` |
| `OpponentInTriggerArea` | Restrict engagement by trigger membership | `SCRIPTS/PATROL.SCP` |
| `BeenAlerted` | Enter an alerted combat branch | `SCRIPTS/PATROL.SCP` |
| `HelpWithTriggers` | Gate party helper behaviour | `SCRIPTS/GENERALPARTY.SCP` |
| `CanFightLikeAJedi` | Gate a shared Jedi script reference | `SCRIPTS/GENERALPARTY.SCP` |
| `CategoryIs "Blaster"` | Query category, rather than character display name | `SCRIPTS/GENERALPARTY.SCP` |
| `OpponentRange` | Compare with a literal or named parameter | `SCRIPTS/NATIVE.SCP` |
| `GotLocator` | Test locator availability before movement | `SCRIPTS/NATIVE.SCP` |
| `EitherPlayerInTriggerArea "name"` | Named trigger condition | Negotiations A `AI/LEVEL.SCP` |
| `EitherPlayerIs "name"` | Named character condition | Negotiations A `AI/LEVEL.SCP` |
| `Message "name"` | Read named level-logic value | Negotiations A `AI/LEVEL.SCP` |
| `ForceComplete "name"` | Query a named Force interaction | Negotiations A `AI/LEVEL.SCP` |
| `MissionMode` | Select mission-specific logic | Negotiations A `AI/LEVEL.SCP` |

Here, Negotiations A means
`LEVELS/EPISODE_I/NEGOTIATIONS/NEGOTIATIONS_A/`. Distances are left in native
game units; the guide does not assert a conversion to metres.

## Common actions

Examples show syntax shapes. Substitute actual resources from the target area;
quoted options are specific to each handler.

| Action | Observed form / purpose | Evidence example |
| --- | --- | --- |
| `Idle` | No quoted argument in basic idle states | `SCRIPTS/JEDI.SCP` |
| `SetState` | `SetState "NextState"`; explicit transition request | `SCRIPTS/JEDI.SCP` |
| `ResetTimer` | `ResetTimer "mintime=-3" "maxtime=-1"`; randomized reset bounds | Pattern in `SCRIPTS/JEDI.SCP` |
| `FollowPlayer` | Numeric quoted argument; other scripts use `"run"` | `SCRIPTS/JEDI.SCP`, `SCRIPTS/NATIVE.SCP` |
| `FollowOpponent` | Numeric quoted argument | `SCRIPTS/JEDI.SCP` |
| `PressActionButton` | Request action input; not a guarantee of a particular move | `SCRIPTS/JEDI.SCP` |
| `FormationMove` | Formation behaviour followed by result-dependent logic | `SCRIPTS/PATROL.SCP` |
| `FollowPath` | `FollowPath "walk"` | `SCRIPTS/PATROL.SCP` |
| `BreakFormation` | Used before entering combat | `SCRIPTS/PATROL.SCP` |
| `GoToLevelPath` | Used before switching to combat state | `SCRIPTS/PATROL.SCP` |
| `EngageOpponent` | Options such as `"goalrange 1.5"` and `"firerange 3"` | `SCRIPTS/PATROL.SCP` |
| `KeepWeaponOut` | Quoted boolean-like value | `SCRIPTS/GENERALPARTY.SCP` |
| `HelpWithTriggers` | Action sharing a spelling with a condition | `SCRIPTS/GENERALPARTY.SCP` |
| `GoToOrigin` | Observed `"waittime=10"` option | `SCRIPTS/NATIVE.SCP` |
| `GoToLocator` | Observed `"wait=0.5"` option | `SCRIPTS/NATIVE.SCP` |
| `ReleaseLocator` | Used on a spawned-actor path | `SCRIPTS/NATIVE.SCP` |
| `SetMessage` | `"name=WorkshopFlag" "value=1"` | Pattern in Negotiations A `AI/LEVEL.SCP` |
| `PlaySfx` | Named sound plus play count and delay options | Negotiations A `AI/LEVEL.SCP` |
| `CnxController` | Named path endpoints, object and animation-frame conditions | Negotiations A `AI/LEVEL.SCP` |

`CnxController` illustrates why an action cannot be understood in isolation:
its `from`/`to` names, `obj`, flags and frame range must match the area. A
syntactically valid copy into another level can still reference nothing useful.
Likewise, a sound name requires the matching sound resource.

## Handler details checked in native code

These details come from the build identified in [research evidence](RESEARCH.md).
They supplement the asset examples without claiming every scheduler path has
been traced.

### `SetState`

The handler at `0x005157D0` uses its first argument as a state name and resolves
it against the current script. Additional arguments are checked for
`KeepBlockedMessages`, which changes a processor flag. The full lifetime and
meaning of blocked messages remain open; ordinary authoring should use the
simple state-name form unless that behaviour is specifically understood.

A missing target enters the native diagnostic path. It is not a request to
create a new state or load a different script. Define every target and avoid
assuming that a target in a referenced script is automatically in scope.

### `ResetTimer`

The handler at `0x00515890` accepts `time`, `mintime` and `maxtime` options.
Without nonzero range options it writes the explicit `time` value; the local
default for that value is zero. This supports both of these forms:

```text
ResetTimer
ResetTimer "time=-4"
```

Supplying nonzero range options selects the range calculation instead. Do not
assume its distribution is identical to `Idle`'s random wait calculation.
Resetting the timer is distinct from waiting for it; use a condition or a
finite wait action as appropriate to the surrounding script.

### `Idle`

The handler at `0x005159A0` has setup and update paths. Setup recognizes a
numeric duration argument, `mintime`, `maxtime` and `frames`. Update either
decrements a frame counter or subtracts the supplied update delta from the
remaining duration, and reports completion when that active counter expires.

The positive frame count is clamped to 255 and stored in one byte. This is an
`Idle` detail, not a global script limit. A bare `Idle` with no active duration
or frame counter does not complete from elapsed time alone on this path.
That is materially different from a finite idle followed by another action.

The handler evidence supports forms such as `Idle "frames=12"` and
`Idle "1.5"`; a new example still needs a game check for the surrounding
scheduler and time scale. Do not assume that “frames” means displayed GPU
frames under every pause or update condition.

## Additional level-logic vocabulary

Negotiations A `AI/LEVEL2.SCP` uses `CreateCreatures` with `locator` or
`locator_set`, `type`, `script`, `max_range_to_player` and `addtoset` options.
It also uses the standalone `off_screen` flag and group-size options. These
are observed argument names, not a complete schema with validated defaults.

The same script initializes named messages with `SetMessage "name=..."
"value=..."` and updates them using `"decrement=1"`. This is useful for
mission counters. It does not establish arbitrary arithmetic expressions or
save persistence. See [recipes](RECIPES.md) for original examples.

## Native core inventory

The following inventory is extracted from the two null-terminated core tables
in the analyzed executable: **49 conditions and 54 actions**. These are core
table counts, **not the game's total command counts or script limits**. The
action resolver also checks a caller-provided table before the core table, and scripts
contain many gameplay-specific names outside this list.

These names are an index for further research. Unexplained names below do not
constitute documented, tested authoring APIs. No argument signatures are inferred
from table membership.

### Core conditions

| Name | Native handler VA |
| --- | --- |
| `PreviousResult` | `0x00000000` |
| `AlwaysTrue` | `0x005149f0` |
| `LocatorRange` | `0x00514a00` |
| `LocatorRangeXZ` | `0x00514a50` |
| `LocatorRangeY` | `0x00514aa0` |
| `Timer` | `0x00514990` |
| `Random` | `0x005149a0` |
| `GotLocator` | `0x00514ae0` |
| `GotLocatorSet` | `0x00514b00` |
| `CurrentLocatorIs` | `0x00514bb0` |
| `InTriggerArea` | `0x00514bd0` |
| `PlayerRange` | `0x00514c30` |
| `NearestPlayerRange` | `0x00514c80` |
| `NearestPlayerXZRange` | `0x00514d50` |
| `InLevelNode` | `0x00514e20` |
| `PlayerInLevelNode` | `0x00514e70` |
| `EitherPlayerInLevelNode` | `0x00514ec0` |
| `NodeRange` | `0x00514f50` |
| `GotTriggerArea` | `0x00514f90` |
| `PlayerInTriggerArea` | `0x00514fb0` |
| `Player2InTriggerArea` | `0x00515010` |
| `EitherPlayerInTriggerArea` | `0x00515070` |
| `BaddyInTriggerArea` | `0x00515100` |
| `GoodyInTriggerArea` | `0x00515130` |
| `OpponentInTriggerArea` | `0x00515160` |
| `GotOpponent` | `0x005151c0` |
| `OpponentIsAThreat` | `0x005151e0` |
| `OpponentOnSamePath` | `0x00515210` |
| `OpponentRange` | `0x00515250` |
| `NearestOpponentRange` | `0x00515270` |
| `YawToOpponent` | `0x00515290` |
| `OpponentBelow` | `0x00515320` |
| `OriginRange` | `0x00515360` |
| `OpponentToOrigin` | `0x005153c0` |
| `PlayerToOrigin` | `0x00515450` |
| `OpponentToLocator` | `0x005154e0` |
| `OpponentToLocatorXZ` | `0x00515530` |
| `OpponentToLocatorY` | `0x00515580` |
| `PlayerToLocator` | `0x005155c0` |
| `NearestPlayerToLocator` | `0x00515620` |
| `OnPath` | `0x00514b20` |
| `PlayerOnPath` | `0x00514b40` |
| `OpponentOnPath` | `0x00514b60` |
| `TimeOffPath` | `0x00514b90` |
| `PathBlocked` | `0x005156f0` |
| `InterruptID` | `0x00515710` |
| `IAm` | `0x00515750` |
| `StuckTime` | `0x00515790` |
| `Param` | `0x005157b0` |

### Core actions

| Name | Native handler VA |
| --- | --- |
| `Idle` | `0x005159a0` |
| `SetState` | `0x005157d0` |
| `ResetTimer` | `0x00515890` |
| `RetreatFromNearestOpponent` | `0x00535e90` |
| `RetreatFromOpponent` | `0x00535d60` |
| `MoveAwayFromPlayer` | `0x00535aa0` |
| `MoveAwayFromPlayer2` | `0x00535c00` |
| `SetCircleDirection` | `0x00515ba0` |
| `Circle` | `0x005350e0` |
| `CircleOpponent` | `0x005356b0` |
| `CirclePlayer` | `0x00535420` |
| `FollowPlayer` | `0x00535000` |
| `MoveAwayFromOpponent` | `0x00535940` |
| `FollowOpponent` | `0x00534f20` |
| `FacePlayer` | `0x00515ca0` |
| `FaceOpponent` | `0x00515e70` |
| `FaceLocator` | `0x0052d220` |
| `IgnoreWallSplines` | `0x005160b0` |
| `CheckWallSplines` | `0x00516120` |
| `NoTerrain` | `0x005161a0` |
| `FlatTerrain` | `0x005162a0` |
| `ShadowTerrain` | `0x00516320` |
| `DontUseShadowTerrain` | `0x005163a0` |
| `DontPush` | `0x00516420` |
| `CanSeeBehind` | `0x005164a0` |
| `RequiresLOS` | `0x00516520` |
| `SetFullPathSearch` | `0x00516590` |
| `SetViewDistance` | `0x00516610` |
| `SetMaxViewHeight` | `0x00516790` |
| `SetMinViewHeight` | `0x005166d0` |
| `SetHearDistance` | `0x00516850` |
| `SetMoveRadius` | `0x00516910` |
| `GoToNode` | `0x00535fc0` |
| `GoToNodeRandom` | `0x00536190` |
| `GoToOrigin` | `0x00536330` |
| `GoToLocator` | `0x00536700` |
| `SetLocator` | `0x0052d310` |
| `SetRespawnLocator` | `0x0052d510` |
| `FollowPath` | `0x00536dc0` |
| `MoveAwayFromNode` | `0x00536fc0` |
| `OverrideAnimation` | `0x00516980` |
| `BlockPath` | `0x0052d6b0` |
| `PathConnectionObstacle` | `0x0052d8f0` |
| `PathConnectionMaxLength` | `0x0052d7c0` |
| `NoLosCheck` | `0x00516220` |
| `ResetToOrigin` | `0x00516ac0` |
| `SetInterrupt` | `0x0052d9c0` |
| `ClearInterrupt` | `0x0052db30` |
| `SetIgnoreAntinodes` | `0x00516b40` |
| `NoShadows` | `0x00516bf0` |
| `SetParam` | `0x00516c70` |
| `SetReturnToState` | `0x00516e30` |
| `ReturnToState` | `0x00516ee0` |
| `NotifyStateChange` | `0x0052dbf0` |

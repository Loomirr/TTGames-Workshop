# How native scripts execute

[Guide index](README.md) · [Language syntax](AI_LANGUAGE.md) · [Command index](GAMEPLAY_COMMANDS.md)

These findings describe the native PC build identified in
[research evidence](RESEARCH.md#native-build-identification). Selected parser,
condition evaluator and scheduler paths were executed in an x86 emulator.
They are not full gameplay tests. The test boundaries are listed below.

## States and actions

The state parser puts a state named `Base` at the front of the script's state
list, using a case-insensitive comparison. Other states are appended. The
processor's ordinary fallback chooses the first state when no current state
is set. `Base` therefore has special handling; its position is not merely an
authoring convention. Explicit initialization, transitions and referenced
scripts can select another state.

Within a state, the processor calls actions in list order. A newly entered
action receives a setup flag; later calls to the same waiting action receive
an update flag. In the checked action loop:

- A zero handler return leaves that action current and stops the action loop
  for this processor update.
- A nonzero return advances to the next action. Several immediately completing
  actions can run in one processor update.
- Conditions are still checked after the action loop. A successful state
  transition can interrupt an action that is waiting.

This explains why a bare `Idle` can keep an actor in a waiting action without
preventing a condition from changing its state. Conversely, placing a waiting
action before a setup command can prevent that later command from running.
Read the specific handler before assuming whether an action completes.

The ordinary update also advances the processor's `Timer` by the supplied
delta. This does not establish a fixed update frequency, wall-clock seconds,
or behaviour across every pause and time-scale path. `SetState` requests a
pending state change; it is not a recursive call to the target state's text.

## Condition order and `and`

The evaluator checks independent conditions or conjunctions in list order.
The first successful condition/group supplies the transition. For example:

```text
Conditions {
    if Timer > 0 goto First
    if Timer > 0 goto Second
}
```

If the timer is positive, `First` wins. `Second` does not override it. Define
both destination states when using such a block in a complete script.

A line ending in `and` joins the next test to its group:

```text
Conditions {
    if GotOpponent == 1 and
    if OpponentRange < 2 goto Nearby
    if Timer > 0 goto Waiting
}
```

Both opponent tests must pass to select `Nearby`. If a test in the group fails,
the evaluator skips the remaining tests in that group and continues with the
next independent group. Here it can still choose `Waiting`.

The inspected suffix parser recognizes `goto` and `and`, not an `or` suffix.
For alternative reasons to enter one state, use separate conditions targeting
that state. Their position still determines priority relative to other tests.
General expression syntax, parentheses and C-style `&&`/`||` are not supported
by this evidence.

## Why an unknown condition is dangerous

An unknown action such as `SetDefensive` is omitted from the action list.
An unknown condition is also omitted, but its neighbours can then acquire
different meaning. It is **not** a condition that simply returns false.

The following fragments are deliberately broken demonstrations, not recipes.
The destinations are illustrative; the native tests inspected the resulting
condition lists and selections.

### A missing leading test removes a guard

```text
if DoorOpened "WorkshopDoor" == 1 and
if Timer > 0 goto Enter
```

`DoorOpened` has no registered condition binding in the analyzed build.
Omitting it leaves the timer test on its own. The transition can succeed
without checking the door.

### A missing final test can join unrelated groups

```text
if Timer < 0 and
if DoorOpened "WorkshopDoor" == 1 goto Enter
if Timer > 0 goto Waiting
```

After the unknown middle line is dropped, the first line still ends in `and`.
It becomes joined to the last line. With a positive timer, the first test
fails and the supposed independent `Waiting` fallback is skipped too.

Both behaviours were reproduced with the native parser and evaluator, using
controlled token input. This is why a linter should flag every unresolved name
and review its whole conjunction, rather than silently removing that line.
See the [37-name audit](UNRESOLVED_NAMES.md) for the affected inventory.

## Registration, preparation and evaluation are different stages

The native lookup returns a registration entry. Finding that entry does not
prove its handler accepts a guessed argument or that the required actor exists.
Conversely, a null direct handler pointer does not necessarily mean the name
is unsupported: the registered `PreviousResult` condition reuses the last
condition query's numeric result within that evaluation. It is not an action
success code. See [values and messages](VALUES_AND_MESSAGES.md#previousresult-means-the-previous-querys-number).

Some conditions also have a preparation callback. For example, `AlwaysTrue`
has a preparation path that supplies a cached value, defaulting to one. Calling
only its evaluator on an uninitialized node is not a valid test of a normally
bound script. The [JSON index](COMMAND_INDEX.json) includes preparation
callbacks so tools can preserve this distinction.

Gameplay registrations are searched before the core fallback. These names
appear in both layers, with different handler addresses:

| Kind | Name |
| --- | --- |
| Condition | `OpponentIsAThreat` |
| Action | `SetLocator` |
| Action | `DontPush` |
| Action | `FollowPlayer` |

When the checked gameplay tables are installed, their entry wins. An analysis
of the core handler alone can therefore describe the wrong implementation for
a gameplay script.

## What the emulated checks establish

The checks execute the original native instruction bytes for name lookup,
action/condition list construction, macro expansion, condition evaluation and
selected processor scheduling. They cover unknown-name omission, both broken
conjunction examples, first-match priority, waiting-action updates and a
condition interrupting a waiting action.

The lexer was replaced with controlled tokens, numeric literal conversion was
modeled, and scheduler-only checks used synthetic action handlers with known
return values. These tests do not validate full text tokenization, actor
movement, resource loading, rendering, save behaviour or complete levels.
Native macro syntax examples in the language guide still need game tests in
their intended loading context.

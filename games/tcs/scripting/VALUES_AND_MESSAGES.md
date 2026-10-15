# Values, parameters and messages

[Guide index](README.md) · [AI syntax](AI_LANGUAGE.md) · [Execution order](EXECUTION.md)

Native scripts have several distinct kinds of values. Choose the one that
matches the job; they do not share a single variable namespace.

| Value | Role | Important boundary |
| --- | --- | --- |
| A condition result | Numeric output of a native query | Meaning and valid range depend on that query |
| `PreviousResult` | Reuses the last evaluated left-hand query result in the current condition list | Not the previous action's return value or a saved comparison boolean |
| `Timer` | Per-processor value advanced by the supplied update delta | Pause behaviour and real-time units need a game check |
| `PARAM` / `SetParam` | Four named parameter slots and their current processor values | Updates require the actor/processor context checked below |
| `Message` / `SetMessage` | Named numeric records used for coordination | Binding, allocation and persistence are separate concerns |
| Saved return state | One remembered destination on the processor | Not a stack of nested function calls |

The native findings below use the build identified in [research evidence](RESEARCH.md).
Selected handlers and evaluator paths were executed in isolation. Complete
example scripts have not been tested in gameplay.

## `PreviousResult` means the previous query's number

The native condition evaluator starts with a numeric result of zero. Evaluating
a condition's left-hand query replaces that result. `PreviousResult` is registered with
no direct query handler, so it keeps the result already held by the evaluator.

Consider this original condition-block fragment:

```text
if PlayerRange < 4 goto Nearby
if PreviousResult < 12 goto Approaching
if PreviousResult >= 12 goto Distant
```

If `PlayerRange` returns 8, the first comparison fails. `PreviousResult` still
contains **8**, not a false/zero boolean, so the second line can select
`Approaching`. Supply all destination states in the containing script.

This reuse is limited to the current condition-list evaluation. It starts at
zero again on a fresh evaluation, and skipped tests do not produce new query
results. It does not preserve the last action's success code or a previous
update's query value. Avoid placing `PreviousResult` first unless that initial
zero is specifically intended.

The stock `SCRIPTS/PATROL.SCP` and `SCRIPTS/COMMANDERPATROL.SCP` use it after
`GotTriggerArea`. Native emulation additionally verified reuse of a fractional
value after a failed comparison and inside an `and` group.

## Updating declared parameters

Declare indexed parameter names at script level:

```text
PARAM 0 WorkshopRange 1.25
PARAM 1 WorkshopCount 2
```

Only indexes 0 through 3 are accepted by the checked declaration handler.
`SetParam` takes separate name/value argument pairs, **not** a `name=value`
option for each parameter:

```text
SetParam "WorkshopRange" "3.5"
SetParam "WorkshopRange" "inc=2"
SetParam "WorkshopRange" "dec=1.5"
SetParam "WorkshopRange" "default"
SetParam "WorkshopRange" "2" "WorkshopCount" "7"
```

The first three lines set, add to and subtract from that processor's parameter
value. The fourth requests its effective default. With no actor-provided
override, the checked case restores the declared `1.25`. Native code also has
an actor-override default path; that path was inspected but not emulated here.
The last line updates two declared names in one action.

The handler matches declared names case-insensitively and writes current
processor values. It does not create another parameter, edit the declaration
shared by all actors, or allocate arbitrary variables. An absent actor,
processor or current script prevents this update on the checked path. Do not
assume an actor-free level controller can use it just because the command is
registered.

Conditions can then compare against the declared name:

```text
if OpponentRange < WorkshopRange goto Nearby
```

Keep pairs complete, names declared and resource/state dependencies valid.
These examples establish literal updates and the shown `inc=`, `dec=` and
`default` forms, not a universal expression syntax for every action.

## Message assignment and counters

`SetMessage` supports these quoted options:

| Option | Checked effect |
| --- | --- |
| `name=WorkshopSignal` | Chooses the named record |
| `value=3` | Assigns a numeric value |
| `increment=1` | Adds to the existing value |
| `decrement=1` | Subtracts from the existing value |

For example:

```text
SetMessage "name=WorkshopRemaining" "value=3"
SetMessage "name=WorkshopRemaining" "decrement=1"
```

These are separate actions: initialize once, then place the decrement at the
event that should consume one count. If run consecutively, this example leaves
the value at two; it does not wait for three events.

Fractional increments/decrements are supported by the handler's floating-point
arithmetic. The numeric helper also resolves declared parameter names:

```text
SetMessage "name=WorkshopRemaining" "value=WorkshopCount"
```

That form reads the current processor parameter value. It is not a reference
to another message called `WorkshopCount`.

Use one of `value`, `increment` or `decrement` per action. They are not an
ordered mini-program. In the checked handler, mixing `increment=1` followed
by `value=5` still selects increment mode and adds five. A name-only action
defaults to assigning zero when it finds the record.

The action updates on its setup call and reports completion even if the
manager is unavailable or lookup yields no record. Completion therefore does
not prove a message was written. The record lookup/allocation service was
modeled in these handler tests; arbitrary name capacity, allocation failure
and load/reset lifetime remain unverified.

### Reading messages and interpreting zero

The query form takes the name directly:

```text
if Message "WorkshopRemaining" <= 0 goto Finished
```

Preparation obtains a record pointer; evaluation reads its numeric value.
A null prepared pointer returns zero. Consequently, **zero does not distinguish
a valid zero-valued message from a query with no bound record**.

For a controlled test, first write a distinctive nonzero value, then test that
exact value in another understood state/processor. Keep script binding and
level resources fixed. Only then introduce countdowns or zero-as-completion
logic. A message is not established save storage; reload persistence must be
tested separately.

## Remembering one return state

`SetReturnToState` remembers the current state when called without arguments.
It also supports a named destination in the current script:

```text
SetReturnToState "state=Resume"
```

`ReturnToState` copies that remembered destination into the pending-state slot
and clears the remembered slot:

```text
ReturnToState
```

A second return with no newly remembered destination requests nothing. Another
`SetReturnToState` overwrites the single slot; there is no nested return stack
on this path. This mechanism is distinct from `ReferenceScript` return handling.

Unlike `SetState`, the `ReturnToState` action reports completion to the action
loop. Later actions in the current list can therefore still execute before
the pending transition is applied. Put it last when the intention is to finish
the current sequence. The handlers and saved/pending fields were emulated;
complete nested-reference and gameplay interactions still need validation.

## Test boundaries

Native tests cover query-result reuse, `SetParam` updates, `SetMessage` option
selection/arithmetic, `Message` record reads and the saved return-state handlers.
Input contexts were synthetic. Parser tests used controlled tokens, numeric
literal conversion was modeled, and the message service returned a controlled
record or no record. The game, its save system and complete level scripts were
not run. See the [check matrix](RESEARCH.md#executed-native-checks).

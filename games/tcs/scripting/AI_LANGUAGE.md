# AI language: `.SCP`

[Guide index](README.md) · [Command reference](COMMANDS.md)

## Execution model

Think of a script as named states with condition tests and action lists. A
condition can request a transition; an action can request a transition with
`SetState`. Actions delegate to native handlers for movement, combat and level
operations. The language is not general-purpose C, Lua or JavaScript.

Actor AI and level scripts have different useful contexts. An actor can have an
opponent, origin, locator or path; a level controller can coordinate messages
and scene objects. A valid command name does not guarantee a meaningful actor
or resource exists in the current context.

**Native, with emulated checks:** actions run in order until a handler waits;
conditions can then interrupt that waiting action. The first successful
condition or conjunction wins. See [execution details](EXECUTION.md) for setup
versus update calls, condition priority and unknown-command pitfalls. Exact
game update frequency and every reference/return interaction remain open.

## State blocks

Observed structure:

```text
state Base {
    Conditions {
    }
    Actions {
        Idle
    }
}
```

The native parser places `Base` first in the state list, and the processor's
ordinary fallback selects the first state when none is current. This does not
mean every loading context enters `Base`: explicit initialization and script
references can select other states.
Braces may appear on the declaration line or the next line. Empty condition
and action blocks occur in the referenced scripts.

Keep state names unique and use consistent spelling for transition targets.
Native state lookup is case-insensitive, but this does not establish the same
rule for resource filenames. State names,
script names and scene object names belong to different namespaces; sharing a
spelling does not link them automatically.

## Conditions and transitions

The common form is:

```text
if <condition> [argument] <comparison> <value> goto <state>
```

For example:

```text
if GotOpponent == 0 goto Waiting
if OpponentRange < 2 goto Nearby
if Message "WorkshopSignal" == 1 goto Respond
```

`GotOpponent`, `OpponentRange` and `Message` are native queries, not variables
declared by these lines. The quoted argument selects a named message in the
last example. Each query defines its own accepted argument and result meaning.

**Native:** the condition parser recognizes `=`, `==`, `<`, `>`, `<=`, `>=`
and `!=`; `=` and `==` select the same comparison kind. Prefer `==` in new
examples to make comparisons visually distinct from configuration assignments.
Numeric comparisons include fractional values in the referenced scripts.

### Conjunctions

The referenced scripts chain tests by ending a line with `and`:

```text
if GotOpponent == 1 and
if OpponentRange < 2 goto Nearby
```

Retain the repeated `if`; this is not C's `&&` syntax. The transition belongs
at the end of the chain. Do not insert a transition midway through a chain.
The inspected suffix parser recognizes `goto` and `and`, not `or`. Use separate
conditions with the same destination for alternatives, remembering that the
first successful group wins. Arbitrary parenthesized expressions, C-style
operators and general expression precedence are not established here.

### Result and timer queries

`PreviousResult` reuses the most recent condition query's numeric result in the
current evaluation. It does not hold the previous action's success code or the
boolean outcome of the previous comparison. A fresh condition-list evaluation
starts that result at zero. See [values and messages](VALUES_AND_MESSAGES.md#previousresult-means-the-previous-querys-number)
for a worked example and native checks.

`Timer` is often compared with zero after `ResetTimer` receives a negative
starting value, including randomized negative bounds. That is an observed
delay pattern. Do not turn it into a guaranteed real-time duration without
checking the update path, pause behaviour and time scale.

## Actions and arguments

Observed forms include an action with no arguments, a quoted positional
argument, and multiple quoted option strings:

```text
Idle
SetState "Waiting"
FollowPlayer "0.75"
ResetTimer "mintime=-3" "maxtime=-1"
SetMessage "name=WorkshopSignal" "value=1"
```

The contents of a quoted string are interpreted by that action's native
handler. Observed action arguments use `key=value`, `key value` and standalone flags.
These are not proven interchangeable. For example, `SetState "Waiting"`
does not establish that `SetState "state=Waiting"` is accepted.

**Native:** action lookup checks a caller-provided registration table, then a core
table. Core entries are 12 bytes in the analyzed 32-bit build. The lookup's
comparison routine folds ASCII letter case. That establishes case-insensitive
action-name lookup on this path, not universal case insensitivity for filenames,
resource names or every parameter parser. Keep existing spelling conventions.

An unknown ordinary action is not necessarily a visible parse error. In the
analyzed PC build, the text parser takes an empty diagnostic path and omits
the action node. Unknown conditions can also be omitted; this must not be
interpreted as a guaranteed false test. See the [37-name audit](UNRESOLVED_NAMES.md)
before relying on a command solely because it appears in a script file.

Adding a line such as `MyNewAction` does not implement an engine feature.
Use registered handlers and the native macro facilities. Likewise, an existing action may still require a particular actor
category, animation, target type or scene resource.

## Script parameters

Observed declaration and use:

```text
PARAM 0 WorkshopNearRange 1.25

state Base {
    Conditions {
        if OpponentRange < WorkshopNearRange goto Nearby
    }
    Actions {
        Idle
    }
}

state Nearby {
    Conditions {
        if GotOpponent == 0 goto Base
    }
    Actions {
        FaceOpponent
    }
}
```

The declaration supplies an index, a name and a numeric default. `NATIVE.SCP`
uses this pattern for two combat distances. **Native:** the declaration handler
accepts indexes **0 through 3**, and condition operand lookup checks those four
named parameter slots. This is a script-parameter limit, not the capacity of
every script-related pool. These declarations do not establish arbitrary
mutable variables.

`SetParam` can update those declared values on an actor's current processor.
Its name/value pairs and context requirements are documented in
[updating declared parameters](VALUES_AND_MESSAGES.md#updating-declared-parameters).

Constants and macros also exist in the native parser vocabulary; they are
listed under advanced constructs below. Parameters are not the only named
values the implementation can resolve.

## Referencing shared scripts

Observed structure, with original state names:

```text
state DelegateCombat {
    ReferenceScript {
        Script=Jedi
        Source=Global
        ReturnState=Waiting
        Conditions {
            if CanFightLikeAJedi == 1
        }
    }
    Conditions {
        if GotOpponent == 0 goto Waiting
    }
    Actions {
        FollowPlayer "0.9"
    }
}
```

This fragment also needs a `Waiting` state in its containing script. The nested
conditions gate a reference and therefore need not contain `goto`. The parent
state's transition conditions are a separate block.

`GENERALPARTY.SCP` uses multiple references to delegate to behaviours such as
`Jedi`, `Blaster` and `NoWeapon`. `ReturnState` names a return destination;
precisely when the runtime returns or interrupts a reference still needs tracing.
Do not assume this is textual inclusion or a conventional synchronous function
call with a local stack.

**Native:** the reference parser recognizes `Script`, `ReturnState`,
`Conditions` and `Source`. It distinguishes `Global` and `Level` source flags.
When neither flag is set it enables both. The inspected script lookup searches
the enabled level list before the enabled global list. Use an explicit source
when relying on a particular script. Some callers can request a global
`default` fallback; do not assume every missing reference does so.

## Worked pattern: a message latch

This original example illustrates a trigger, a named message and a distinct
state for a one-time state progression. It requires an existing area trigger
named `WorkshopZone`. It is not a complete level setup.

```text
state Base {
    Conditions {
        if EitherPlayerInTriggerArea "WorkshopZone" == 1 goto Signal
    }
    Actions {
    }
}

state Signal {
    Conditions {
    }
    Actions {
        SetMessage "name=WorkshopEntered" "value=1"
        SetState "Finished"
    }
}

state Finished {
    Conditions {
    }
    Actions {
    }
}
```

Other logic can query `Message "WorkshopEntered"`. Do not assume messages
persist in a save or across area transitions. Choose unique mod-prefixed names
and test reset behaviour. The separate terminal state avoids deliberately
cycling back to the trigger while the player remains inside it.

## Comments and text conventions

The referenced files contain `//` line comments, semicolon comments and `/* ... */`
blocks. Their presence is asset evidence; full tokenizer edge cases have not
been exhaustively checked. Prefer simple ASCII identifiers, plain quotes and
the surrounding file's encoding/line endings. Do not assume Unicode names,
escaped quotes or nested block comments are supported.

When analyzing files, remove comments with quote awareness before counting
commands. Words inside comments and disabled experiments are not valid evidence
of a supported command. A naive split on `//` or `;` can also damage a quoted
argument.

## Native macros

Macros copy lists of actions or conditions during parsing. They do not create
new native handlers. Declare them before use in the containing script; the
inspected parser resolves against macros already defined there.

An action macro contains actions directly, without an extra `Actions` block:

```text
ACTIONMACRO WorkshopStartTimer {
    ResetTimer "time=-2"
}

state Base {
    Conditions {
        if Timer > 0 goto Ready
    }
    Actions {
        DoMacro WorkshopStartTimer
        Idle
    }
}

state Ready {
    Conditions {
    }
    Actions {
        Idle
    }
}
```

Use `DoMacro WorkshopStartTimer`, not a bare `WorkshopStartTimer` action.
An ordinary unknown action is not automatically a macro invocation.

A condition macro contains conditions directly. The invocation supplies the
transition suffix, which is applied to the last copied condition:

```text
CONDITIONMACRO WorkshopCloseOpponent {
    if GotOpponent == 1 and
    if OpponentRange < 2
}
```

Inside a state's `Conditions` block, use:

```text
OnMacro WorkshopCloseOpponent goto Nearby
```

Define `Nearby` in the same script. Native declaration and expansion were
checked with controlled token input; these complete teaching examples have not
been gameplay-tested. Macro arguments, recursion and cross-file scope are not
established. Do not assume C-preprocessor substitution rules.

## Constants, derivation and inclusion

The `CONST` handler reads a name followed by a numeric value. Constants provide
another source for named condition operands; they are separate from the four
indexed `PARAM` slots. Constant lifetime across nested parsing needs more work,
so this guide does not promise file-wide or project-wide constant scope.

`DERIVEFROMSCRIPT` recognizes a block with `Script=...` and `Source=Global` or
`Source=Level`. Native finalization copies parent states whose names are absent
from the child. A child state with the same case-insensitive name takes
precedence as a whole state; its actions are not automatically appended to the
parent state's actions. Empty child parameter slots can inherit parent names
and defaults. This is static parser/finalizer evidence, not gameplay validation
of arbitrary inheritance chains.

`INCLUDE` reads a following name and invokes nested script loading. Complete
path resolution, loading precedence, recursion limits and interaction with
constant/macro scope remain unverified. Do not substitute C's `#include` syntax
or assume it is equivalent to `ReferenceScript` or `DERIVEFROMSCRIPT`.

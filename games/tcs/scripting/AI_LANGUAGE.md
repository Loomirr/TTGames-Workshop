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

**Open:** exact update frequency, condition priority when multiple tests pass,
action completion/yield rules, and transitions during a running action. Do not
assume every action runs once, every action runs every frame, or each action
waits for the previous one to finish. Preserve a working script's ordering
until the relevant handler/runtime path is understood.

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

`Base` is a common starting state in the referenced scripts. It is a convention worth
preserving, not evidence that it is the first state entered in every loading
context: scripts also contain states such as `InActive` and `Activate`.
Braces may appear on the declaration line or the next line. Empty condition
and action blocks occur in the referenced scripts.

Keep state names unique and match transition targets exactly. State names,
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
Arbitrary parenthesized expressions, C-style operators and general expression
precedence are not established here. The supported semantics of `or` remain
open in this guide.

### Result and timer queries

`PreviousResult` is used after native operations in the referenced scripts. Treat it
as operation-dependent feedback; this guide does not establish a universal
success code for every action.

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
uses this pattern for two combat distances. **Native:** the inspected condition
parser checks four parameter-name slots when resolving a right-hand operand.
This is evidence about that lookup path, not a claim that every script-related
storage pool has the same capacity. Avoid inventing arbitrary mutable variables
or increasing indexes beyond verified support.

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
When neither flag is set it enables both; the search order when both are enabled
is not established here. Use an explicit source for predictable authoring.

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

## Advanced constructs awaiting authoring documentation

The native top-level dispatch table includes `CONST`, `CONDITIONMACRO`,
`ACTIONMACRO`, `DERIVEFROMSCRIPT` and `INCLUDE`, alongside `STATE`, `PARAM` and
`REFERENCESCRIPT`. The condition parser also recognizes `OnMacro`.

These are real parser vocabulary, but this guide does not yet establish their
complete declaration syntax, scope, recursion rules, precedence or loading
behaviour. Do not substitute a C preprocessor's `#include`/`#define` syntax.
Further examples and handler tracing should extend this section without
presenting guessed syntax as usable instructions.

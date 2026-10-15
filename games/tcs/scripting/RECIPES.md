# Native authoring recipes

[Guide index](README.md)

These are original examples assembled from observed native syntax. They have
not been executed as new scripts in-game. Use them in an already understood
binding and supply every named resource; they are not complete replacement levels.

## Recolor a working saber

In the character definition that supplies its effective properties, replace
the existing `streak` assignment with one of `blue`, `green`, `red` or `purple`.
For example:

```text
streak=green
```

Keep working animation, category and attachment settings. Do not add a new
color word and expect the palette to grow. See [colors and effects](COLORS_AND_EFFECTS.md)
for the blade, trail, light and reflection checks.

## Price a new character using the native shop

After registering a complete character, add its intended collection entry:

```text
collect "WorkshopKnight" buy_in_shop 18000
```

To gate a different character behind an existing area completion:

```text
collect "WorkshopGuard" area_complete "negotiations" buy_in_shop 9000
```

These belong in `CHARS/COLLECTION.TXT`. They are not character-TXT properties.
Check shop capacity before adding many entries, and confirm persistence after
an actual save/reload. Keep names unique and verify their registered file stems.

## A cosmetic variant using a redirect

The stock security Battle Droid redirects to the regular Battle Droid and
overrides display/icon properties. Following that structure, a definition in
the compatible directory can begin:

```text
txt_file="battledroid"
icon="workshop_guard_icon"
```

Add a valid `name_id` using an unused ID from your localization tables. This
fragment does not supply the portrait asset or change the model's textures.
Retain the expected model/resource arrangement for the variant. If adding a
new animation, follow the collection-stage rules in [character authoring](CHARACTERS.md)
rather than placing a new clip only in this override.

## A simple opponent-aware actor state machine

This example changes from idle to facing an opponent and returns when the
opponent is gone. It does not spawn the actor or establish an opponent itself.

```text
state Base {
    Conditions {
        if GotOpponent == 1 goto Watching
    }
    Actions {
        Idle
    }
}

state Watching {
    Conditions {
        if GotOpponent == 0 goto Base
    }
    Actions {
        FaceOpponent
    }
}
```

Use an existing actor binding with a known opponent-selection path. If the
state never changes, inspect `GotOpponent` and control ownership before
changing the facing action.

## Named-message coordination

One processor can publish a numeric value with:

```text
SetMessage "name=WorkshopRemaining" "value=3"
```

The native mission scripts also use `decrement`:

```text
SetMessage "name=WorkshopRemaining" "decrement=1"
```

A condition can test it:

```text
if Message "WorkshopRemaining" == 0 goto Finished
```

Place the decrement in a state reached once for the intended event. A repeated
transition can decrement more than once, and an equality-to-zero test can then
miss completion. Decide whether the intended logic permits a `<= 0` guard;
do not hide accidental duplicate events by changing the comparison alone.
Message lifetime and persistence across loads remain unverified.

## Spawn at a named locator

The following action form is observed in area mission scripts, with the
resource names replaced for this example:

```text
CreateCreatures "locator=WorkshopSpawn" "type=WorkshopGuard" "script=WorkshopGuardAI"
```

Before using it, supply a valid registered character, an appropriate script
binding/source and an actual locator in the area. `locator` is not an XYZ
position string. `type` is not the localized display name.

Negotiations A `AI/LEVEL2.SCP` also uses `locator_set`, `max_range_to_player`,
`addtoset`, `off_screen`, `mingroupsize` and `maxgroupsize`. Preserve their
observed quoted option form. Their complete defaults, selection rules and
failure behaviour are not established here; begin with a single known locator
and a single known character before building random group spawning.

Do not put a spawn action in a deliberately repeating cycle without a count
or termination condition. The resource limits in [icons and capacities](ICONS_AND_LIMITS.md)
are not lifted by script-generated actors.

## Wait before a state transition

The native `Idle` handler accepts a quoted numeric duration argument:

```text
state PauseBeforeNext {
    Conditions {
    }
    Actions {
        Idle "1.5"
        SetState "NextPhase"
    }
}
```

Provide `NextPhase` elsewhere in the same script. This illustrates a finite
idle rather than bare `Idle`, whose native handler does not complete by time
alone when no duration/frame count is active. The exact time scale and scheduler
behaviour still need a game check in the target context; `1.5` is not presented
as a measured wall-clock delay.

## Verify an area interaction without rebuilding the level

Start from an existing working script and change only a numeric threshold or
an existing stock choice. Keep scene names, asset packaging and bindings fixed.
Once that edit is observable, introduce a uniquely named message or new state.
Only then add a new scene resource or character.

This separates three otherwise identical-looking failures: the edited file
was never loaded, the condition was never true, or the action lacked its resource.
Record the exact area and loading sequence with each test.

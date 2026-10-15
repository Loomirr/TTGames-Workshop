# Connecting scripts, characters and levels

[Guide index](README.md)

## Loading and binding

Shared behaviours are present under `SCRIPTS/`; area behaviours are present
under the area's `AI/` directory. Packaged resources such as `AI.PAK` can also
participate in loading. Finding a loose file does not prove that it is
the resource used by a particular installation or loading path.

Before editing, identify the actor or level processor that uses the script,
the matching area and the file actually resolved at runtime. Preserve an
existing working binding while testing a small change. Do not assume dropping
an arbitrary new `.SCP` into a directory starts it, or invent an `ai_script=`
character property without confirming its parser support.

Area files named `LEVEL.SCP`, `LEVEL1.SCP`, `PARTY.SCP` and named actor scripts
are observed. Their names alone do not prove automatic discovery rules or the
number of supported level processors. `ReferenceScript` explicitly selects a
script and source; level scripts also use `AddScriptProcessor` and
`CreateCreatures` with `script=` options. Their complete signatures, lifetime
and loading order remain outside the verified core reference.

Verify archive-versus-loose precedence for the resource and loading path being edited.
Keep extraction/packaging changes separate from script changes so a failed
load can be diagnosed without also changing gameplay logic.

## Character registration is not AI scripting

An illustrative new registration in `CHARS/CHARS.TXT` is:

```text
char_start
    dir "WorkshopGuard"
    file "WorkshopGuard"
char_end
```

This describes the character directory and file identity. It does not provide
model, animation, sound or icon assets, and it does not run a new state machine.
The character must have compatible resources and a valid definition.

Collection declarations such as the following belong in `CHARS/COLLECTION.TXT`,
not in an SCP `Actions` block:

```text
collect "WorkshopGuard" buy_in_shop 0
```

The number after `buy_in_shop` is the purchase price in the observed native
collection format. Here it is zero. Stock entries use positive prices, and
may also specify `area_complete "area_name"` and `cheat_code "code"`. See
[characters and collection](CHARACTERS.md) for gates and persistence.

Use a free localization ID in `STUFF/TEXT/ENGLISH.TXT` and match the character's
`name_id`. Avoid copying a fixed numeric ID from another mod; collisions can
display a different name while the underlying character identity is unchanged.
Other installed languages need their own corresponding text entries.

## Character `.TXT` properties

Observed character definition vocabulary includes:

| Area | Examples | Meaning / dependency |
| --- | --- | --- |
| Presentation | `name_id`, `icon` | Text ID and icon resource name |
| Visible geometry | `layers_special`, `layers_high`, `layers_medium`, `layers_low`, `layers_dead` | Model layer choices; indices depend on the model |
| Placement | `weapon_locator`, `weapon_locator_2`, `helmet_locator`, `head_locator` | Model-specific locators; not arbitrary coordinates |
| Movement | `walk_speed`, `run_speed`, `jump_speed`, `air_gravity` | Movement parameters; do not remove native eligibility gates |
| Category | `jedi` | Bare category flag observed in a Jedi definition |
| Combat visuals | `streak`, `streak_1_locators` | Streak selection and attachment information |
| Sound | `sfx_die`, `sfx_hurt` | Named sound resources |
| Animation mapping | `anim_start`, `action`, `speed`, `blend_in`, `blend_out`, `anim_end` | Per-animation blocks linking named animations/actions |

These examples were inspected in `CHARS/QUIGONJINN/QUIGONJINN.TXT`. This is not
a complete character property schema, and arbitrary new properties are not
automatically supported. An animation name must resolve to compatible animation
data. Changing a name cannot create missing motion or repair a skeleton mismatch.

### Why a jump or weapon command can do nothing

An AI script requests native behaviour. The character's categories, animations,
model attachments and native gameplay restrictions still participate. Increasing
`jump_speed` does not establish that a restricted droid can enter a jump state.
Changing a streak does not establish that the blade material, reflected blade,
dynamic light and hilt texture all use the same color selection.

Distinguish these layers when testing:

1. Was the script loaded, and did its condition reach the action?
2. Did native gameplay accept the requested action for this actor and target?
3. Were the required animation, model and locator resources available?
4. Did each rendering pass use the intended material/effect?

Likewise, adding more registrations does not automatically increase model,
animation, icon, shop or save capacities. Those are separate systems. No limit
increase is implemented by the documentation in this repository.

## Level `.TXT` settings

The inspected cantina area definition uses directives such as `max_obstacles`,
`max_force`, `max_force_objects`, `music`, `farclip_pc` and `nearclip_pc`, followed
by `settings_end`, with subsequent `door_start` / `door_end` blocks.

These use a different grammar from SCP state blocks. A door block's `spline`,
`level` and `1_way` entries describe an area connection. They are not native
AI actions to paste into `Actions { ... }`. Allocation settings should not be
treated as unlimited-capacity switches: related native arrays and resource
budgets may impose additional bounds.

Named triggers, locators, path connections, Force objects and obstacles must
exist in the level's resources. A script name string does not create the
corresponding gizmo or scene object. Use the appropriate binary inspection
tools to check resources, while respecting their documented coverage limits.

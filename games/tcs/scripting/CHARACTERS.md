# Native character authoring

[Guide index](README.md) · [Colors](COLORS_AND_EFFECTS.md) · [Capacities](ICONS_AND_LIMITS.md)

Character TXT files configure native systems. They are not AI programs, and
their animation blocks do not use the SCP state grammar. Examples here are
small editing fragments, not complete character definitions.

## Identity and registration

A character involves several independent names:

| Identity | Where it is used | Frequent mistake |
| --- | --- | --- |
| Registered file stem | `file` in `CHARS/CHARS.TXT`, collection entries | Using the display name instead |
| Directory | `dir` in the registration | Assuming every character has a unique directory |
| Display text ID | `name_id`, localization tables | Reusing another mod's ID |
| Icon object name | `icon` in the character TXT | Using a texture filename instead of the expected object name |
| Animation name | `anim_start` | Declaring motion that has no compatible resource |
| Native action name | `action` inside an animation block | Inventing an action name to add new gameplay |
| Script state name | SCP `state` / `goto` / `SetState` | Treating it as a character property |

Several stock definitions share directories and underlying resources. A new
registration is not a request to duplicate every resource, but all references
must still resolve. Preserve existing registration order when working with
saved progress; numeric identity and name-based references are not interchangeable.

An original registration fragment:

```text
char_start
    dir "WorkshopKnight"
    file "WorkshopKnight"
char_end
```

The corresponding definition belongs under `CHARS/WorkshopKnight/` and must
have the named file stem. This fragment does not create model or animation files.
Use compatible resources from your own game installation and distribute only
material you have permission to distribute.

## Definition structure and properties

Assignments, bare flags and animation blocks all occur in native definitions.
Do not normalize every line to one invented grammar. For example, the stock
Battle Droid uses bare `droid`, `baddie` and `blaster` flags; Vader uses `jedi`,
`baddie`, `choke` and `resist_zap`.

| Property group | Observed native fields | Authoring guidance |
| --- | --- | --- |
| Identity | `name_id`, `icon`, `variant` | Keep display, portrait and variant identities distinct |
| Health / dimensions | `hit_points`, `radius`, `miny`, `maxy`, `scale` | Preserve compatible dimensions before tuning gameplay |
| Locomotion | `acceleration`, `tiptoe_speed`, `walk_speed`, `run_speed` | Speed does not create a missing locomotion animation |
| Jump / fall | `jump_speed`, `jump_2_speed`, `jump_speed_double`, `air_gravity`, `water_gravity` | Native action eligibility still applies |
| Combat movement | `move_delay`, `lunge_jumpspeed`, `slam_jumpspeed`, `slam_gravity` | Test the corresponding native move, not only walking |
| Layer sets | `layers_special`, `layers_high`, `layers_medium`, `layers_low`, `layers_dead` | Indices are specific to the model; check all distance/death states |
| Attachments | `weapon_locator`, `weapon_locator_2`, `weapon_shoot_locator`, `helmet_locator`, `hand_locators` | Keep indices within the actual model's locators |
| Head / cloak | `head_locator`, `head_joint`, `cloak_joint`, `cloak_joint2`, `hair_layer_index` | Bone, layer and locator numbers are different domains |
| Effects | `streak`, `streak_1_locators`, `shadow_locators` | Preserve attachment and rendering dependencies |
| Audio | `sfx_die`, `sfx_hurt`, `sfx_misc` | Resolve actual sound resources; a string alone adds no sound |

Evidence: the stock-named Qui-Gon, Obi-Wan, Mace Windu, Darth Vader and Battle
Droid definitions listed in the [source map](RESEARCH.md#source-map). The table is an observed vocabulary,
not a promise that every property is applicable to every category or model.

## Categories are not independent ability checkboxes

Changing a native category can affect several behaviours at once: AI selection,
interactions, movement, combat, targeting and animation selection. For example,
`CategoryIs "Blaster"` is used to choose shared party AI. A category change can
therefore alter AI even when the author intended only a new weapon interaction.

`choke` is a real stock flag. It is not evidence of an unrestricted ability to
choke every humanoid: native target selection and receiving animations still
matter. Similarly, `jedi` is not a generic promise that arbitrary melee weapons
will render or behave correctly.

The native weapon-streak route includes Jedi logic and identity-specific
Magnaguard/Royal Guard routes. Supplying streak locators to an unrelated
character does not establish that it enters one of those routes. Imperial
panel interaction also checks native actor flags. This guide does not invent
separate TXT toggles for these checks.

Claims about arbitrary vehicle driving, generic bullet types, Ewok rock
projectiles, Geonosian weapon selection and arena Jedi counts remain research
questions until their native handlers are documented. Treat filename/tag
substitution as a broad behaviour change, not a clean independent capability.

## `txt_file` and animation collection

Stock variants use redirects such as `txt_file="battledroid"` or
`txt_file="clone"`. Some referenced definitions use the whitespace form instead of
`=`. Preserve a known working form for the target parser.

The native loader follows `txt_file` before collecting animations. A later
override pass can update an animation already collected, but introducing a
new `anim_start` only in the derived override did not add a new clip on the
inspected path. This explains an important failure mode: ordinary inherited
animations work, but a newly declared action has no animation entry.

When adding a genuinely new clip, put it in the definition collected initially,
or use a complete definition without a redirect and supply its dependencies.
Keep the original action coverage when making a complete definition. This is
not a reason to flatten every simple cosmetic variant.

Native evidence: redirect detection at `0x00584640`, loader at `0x00589410`,
and animation declaration processing at `0x00585760`, in the build identified
in [research evidence](RESEARCH.md). This finding concerns animation collection;
it is not a complete specification of inheritance for every property.

## Animation declarations

Illustrative mapping for a compatible animation resource:

```text
anim_start="workshop_idle"
action="idle"
blend_in=0.1
blend_out=0.1
anim_end
```

`anim_start` identifies the animation; `action` maps it to a native action.
The example requires an actual compatible resource. It does not generate an
AN3 file. Do not rename a file from a different rig and expect retargeting.

Observed per-animation fields also include `speed`, `cycle`, `frame`,
`frame1` through `frame4`, `bsa`, and flags such as `gun_off`, `no_headturn`
and `can_play_backwards`. Stock locomotion blocks use `footsteps 4frames`.
The meaning of numbered event frames is action-dependent: do not label all
`frame1` values as a universal hit or sound event without tracing that action.

`bsa_default` and per-animation `bsa` settings occur in the same definitions.
Their presence does not establish that arbitrary BSA/AN3 resources can be
interchanged. Keep compatible resource naming and settings until the relevant
animation path is understood.

If an actor slides, first check idle/walk/run resources and action mappings,
then check the shared filename cache. A model loading successfully does not
prove its animations loaded. If only one new action is missing, check redirect
collection before assuming the whole cache is exhausted.

## Collection, price and unlock gates

The native collection file is `CHARS/COLLECTION.TXT`. It is separate from the
character definition. These are original examples of observed forms:

```text
collect "WorkshopKnight" buy_in_shop 25000
collect "WorkshopGuard" area_complete "negotiations" buy_in_shop 12000
```

`buy_in_shop` is followed by the purchase price. An `area_complete` gate refers
to the game's area identity, not its localized title. Stock entries also use
`story` and `cheat_code "..."`; some initial characters have a bare `collect`
entry. Do not add all flags indiscriminately: they represent different routes
to availability.

Use one intended collection declaration per new identity and inspect existing
entries before appending. Listing a character, making it eligible for purchase,
buying it, unlocking it in Free Play and saving that state are different steps.
A zero-price entry still needs testing through its intended unlock path.

Keep prices within established native usage until the price parser and all
consumers have been checked. This guide does not claim arbitrary integer ranges.
Likewise, choose unused cheat codes and localization IDs rather than copying
values from another character.

## Saves and persistence

Native save storage has fixed character availability and shop-purchase fields.
Text registration does not enlarge them. Do not infer persistence merely
because a character appears during the current session.

Test a purchase, wait for an actual native save to complete, quit, and reload
the same slot. A purchase made while standing in the cantina is not proof that
a save has been written. Keep backups when changing collection ordering or
registrations; test both existing progress and a fresh save where practical.

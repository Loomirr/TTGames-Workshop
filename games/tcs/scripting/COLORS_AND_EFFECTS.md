# Native lightsabers, streaks and Force effects

[Guide index](README.md) · [Character definitions](CHARACTERS.md)

## Selecting a stock lightsaber color

The native character definition uses `streak` for the stock color selection.
The four observed stock choices are:

| Value | Stock example definition |
| --- | --- |
| `blue` | `CHARS/OBIWANKENOBI/OBIWANKENOBI.TXT` |
| `green` | `CHARS/QUIGONJINN/QUIGONJINN.TXT` |
| `red` | `CHARS/DARTHVADER/DARTHVADER.TXT` |
| `purple` | `CHARS/MACEWINDU/MACEWINDU.TXT` |

For a character already configured with a working native saber, change the
existing assignment in its TXT, for example:

```text
streak=purple
```

Replace the original assignment rather than relying on duplicate-key priority.
Keep the character's working weapon and streak locators. This is a stock color
selection, not a new palette entry. Writing `streak=orange`, a hex value or an
RGB tuple is not a documented way to add a fifth native saber color.

This reference establishes the native four-color system and stock usage. Test
the edited character in the actual game; the recipe is not a new gameplay
validation of every character/scene combination.

## Streak locators and visual components

The inspected Jedi definitions commonly include:

```text
streak_1_locators=6,7
```

Those numbers are model-specific endpoints. They are not universal defaults
for every rig. Copying them to another model can attach an effect incorrectly
or reference unsuitable data. `weapon_locator` and `weapon_locator_2` are
separate attachment declarations.

A visible saber involves several components:

| Component | Why it matters |
| --- | --- |
| Blade geometry/material | Its core is not just the motion trail |
| Camera-facing glow | Bright additive rendering can hide a dark surface |
| Motion streak | Can have the expected color even when the blade is wrong |
| Dynamic light | Affects surroundings independently of the apparent blade |
| Hilt | Selected separately from the blade |
| Reflected rendering | Must be checked independently of the main view |

Native render research found an untextured white core in the blue saber
material and camera-facing glow geometry. Setting a color to black does not
make an opaque black core in additive rendering: adding black contributes no
light. A black-centered, white-edged weapon is therefore not provided by a
simple extra `streak` name or ordinary RGB edit.

Material, geometry and particle changes belong to asset authoring, not the
SCP grammar. Matching a trail or dynamic light is not sufficient evidence that
all relevant material and reflection paths match.

## Hilt selection and reported hilt colors

Native selection at `0x00418FB0` chooses shared hilt parts by character identity:
Darth Maul uses part 18; Count Dooku uses part 19 when available; the ordinary
route uses part 17. Blade selection is a later, separate operation.

The inspected shared scene contains `LightSabreHandle` and `BentLightSabre`.
Those two objects use the same material in the inspected asset. That supports
a hardcoded geometry distinction; it does **not** establish a separate
character-specific texture tint for Dooku. The report of special Palpatine hilt
coloration also remains unresolved. One inspected Palpatine identity reference
was mission logic, not a hilt renderer.

There is no verified character TXT directive here for selecting an arbitrary
hilt mesh, replacing its texture per character or assigning a hilt RGB color.
Editing a shared material may affect every character using it. Separate shared
asset edits from per-character text changes in your test plan.

## Force effects are several rendering systems

Native Force visuals include particles and camera-facing ring meshes. Changing
one does not automatically recolor the other. An idle target highlight and an
effect while manipulating an object may follow different paths.

The native ring draw routine at `0x004A4CE0` draws two counter-rotating meshes;
`0x004A4FF0` computes target-dependent placement, radius, pulse and ring family.
Inspected ring parts include green, red, blue and purple pairs. The blue and
purple pair shares material/texture data: vertex color carries the difference.
Consequently, looking only for a differently colored texture can miss the
source of the hue.

The existence of those asset variants does not establish a character TXT
property that freely chooses any Force color. No native per-character RGB
directive for Force rings or lightning has been verified in this guide.
Lightning is also distinct from saber `streak`; changing the latter is not a
general lightning-color setting.

## Native-only testing checklist

1. Start with a character whose native saber/action already works.
2. Change one existing stock color assignment.
3. Inspect the blade while still, its motion streak, nearby lighting and a
   reflection where the level provides one.
4. Check drawing/sheathing, attack animations and both player slots if relevant.
5. If editing an asset, check another character sharing it for unintended changes.
6. For Force effects, inspect idle highlighting and active manipulation separately.

The addresses above apply only to the build identified in
[research evidence](RESEARCH.md). They explain native behaviour; they are not
instructions to alter executable code.

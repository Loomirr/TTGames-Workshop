# Facial animation: playback checks and remaining limits

Facial animation does play in Blender for supported clips. We did not reproduce
a general playback failure in this pass. The reported failure did not identify
a game, character or clip, so these checks cannot establish its cause.

We did find a confusing case: an imported face can have a valid, **constant
expression** throughout the clip. The body moves while the facial controls stay
still. That is different from failing to load a facial track.

## What the new status means

Each newly imported clip now records a facial-playback summary, available in
its `TT AN4 report` in Blender's Text Editor:

| Status | Meaning |
| --- | --- |
| `animated` | At least one imported face mesh has changing expression weights. |
| `static` | Facial tracks loaded, but their expression weights stay constant throughout the clip. |
| `absent` | No facial tracks loaded. A matched actor may have no facial track, or the imported character may have no face attachments. |
| `unavailable` | The reader could not safely match or decode the facial track. The report contains the reason. |

The report counts mesh tracks, not expressions or characters: one face can
contain several meshes. It separates animated and static meshes and retains
attachment ownership or decoding notices. A loaded body animation does not
automatically mean its face animation loaded too.

These diagnostics do not relax the checks on actor matching, frame counts,
target IDs or supported animation layouts. They do not add facial export.
The summary is also stored on the Blender action as `tt_facial_playback`;
`tt_animation_report` identifies that action's report text. The rig retains the
latest report name. Older saved actions need reimporting to gain these fields.

## Original-file checks

Current source was tested in **Blender 5.2.2 LTS** with isolated preferences and
user-owned files. Every imported face-target weight was compared with the
source animation at every integer frame. Evaluated mesh movement was checked
separately. This did not assess rendered shader quality or in-game export.

| Game and character | Selected clip | Frames | Face mesh tracks | Result |
| --- | --- | ---: | ---: | --- |
| LMSH1 Wolverine | `Wolverine_VO / Idle` | 146 | 7 | All seven have changing weights and evaluated mesh movement. |
| LB3 1966 Catwoman | `2BatCaveFightA / BrainiacMindControl_Stunned` | 105 | 5 | All five match a constant source expression. The separate hair animation remains unmatched and is reported. |
| The Hobbit Bilbo Baggins | `BilboBaggins_Default / idle` | 351 | 5 | All five have changing weights and evaluated mesh movement. |
| Avengers Captain America | `CaptainAmerica_Default / Idle` | 39 | 5 | Four animate; one stays constant. Values and evaluated movement agree with that distinction. |

All **114,746 sampled target values** matched within `6e-8`. The LB3 clip's
source face block has 106 samples, with one permitted extra end sample. All
53 controls remain constant; controls 31 and 32 are approximately 0.62. Nothing
is being dropped merely because its face does not change during playback.
The animation browser's `Idle` entry in that case refers to a conditional
level clip, not a Catwoman-specific idle animation.

The same four cases passed again after adding diagnostics. Asset-free Blender
checks also cover changing weights, a constant expression, a missing source
face track, and preserving the rejection of an incompatible duration. Public
test entry points are:

```text
formats/character/check_face_playback_blender.py
formats/character/check_face_diagnostics_blender.py
```

Their module instructions describe the command arguments. The original-file
check requires a user-supplied cases JSON and an extracted addon package; no
game files are included. Reports can contain local paths, so review them before
sharing. Local runs and logs are under ignored
`local/validation/face-playback-20261021/`.

## Playback and export are different

The current AN4 body exporter does **not** write edited face or attachment
animation curves. It rejects changed linked actions rather than exporting the
old expression without notice. That is an export limitation even when the same
face animation plays correctly in Blender.

Likewise, baking a control rig or fixing AN4 compression does not add support
for an unknown facial layout. Current facial playback requires a compatible
actor, duration and target IDs. Supported scalar layouts include observed
53-control faces and LB2's separate 37-control layout; that does not mean all
games' faces are enabled.

## If your face still does not move

Check the selected clip's status and `TT AN4 report`, then include the game,
character, actual clip/set name, addon version and report when reporting the
problem. State whether it happens in Blender, after replacing a file in-game,
or both. A screenshot and the frame number help distinguish missing movement
from a masking/shading problem. Do not upload proprietary game assets to the
repository.

AI assistance was used for the diagnostics and checks. No in-game facial
export test or new rendered-fidelity claim is made by this report.

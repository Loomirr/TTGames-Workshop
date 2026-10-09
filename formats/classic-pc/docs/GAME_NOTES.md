# How the games work, from their data

Notes taken while studying LEGO Batman (2008) and LEGO Indiana Jones 1 (2008), with a little from LEGO Star
Wars: TCS. Everything is read from the games' own data files unless it says otherwise. Where something is
an interpretation or was not found, it says so.

Units: the games work in metres, Y up.

## Character definition files

`chars\<name>\<name>.txt`: keyword flags, `key=value` numbers, then one `anim_start ... anim_end` block per
animation. Shared ability sets are in `chars\ability_*.txt`.

| Value | Batman | Indiana Jones |
|---|---|---|
| `run_speed` / `walk_speed` / `tiptoe_speed` (m/s) | 1.6 / 0.4 / 0.1334 | 1.4 / 0.6 / 0.2816 |
| `jump_speed` | 1.9 | 1.9 |
| `air_gravity` | not stated | -5.0 |
| `acceleration` | 10 | 10 |
| `radius`, `miny`, `maxy` | 0.1, 0, 0.42 | same |
| `hit_points` | 4 | 1 (how that becomes four hearts was not looked at) |
| `turn_rate` | not stated | 1.0 |
| `lunge_speed` | not stated | 1.5 |
| `slam_jumpspeed` / `slam_gravity` | goon files only | 3 / -15 |

The 42 cm `maxy` is the collision height, not the model's height: the minifig model stands about 37 cm.

Abilities are keywords in the same file: `hero`, `zipup` (grapple points), `got_batarang`,
`combat_roll can_direct_land`, `tightrope_tilt`, `fight_sequential` (the combo runs `fight1` .. `fight6` in
order), and in Indy `has_whip`, `phobia "snakes"`, `wall_jump off`, `tightrope_walk`.

### Animation blocks

Each block has `action=`, optional `fpsec=` (playback frames per second; 30 if absent), `blend_in=` /
`blend_out=` (seconds), `cycle=off`, `footsteps` with footfall frames, and nested
`effect_start ... effect_end` (a sound at a frame).

**`speed=` is forward movement in metres per second, not a playback rate.** The character moves at that
speed while the animation plays, until `frame_stop`. A recoil has a negative speed (-0.435). Reading it as
a rate gives wrong timings: Batman's `fight1` has `frame_hit=12`, `frame_settle=15`, `speed=0.84`, no
`fpsec`, so the hit lands at 12 / 30 = 0.400 s while he lunges forward at 0.84 m/s.

Other examples from `chars\batman\batman.txt`: run `fpsec=28` with footfalls at frames 3 and 12 (a 19-frame
cycle, 0.68 s); side-step `speed_x` of plus or minus 0.25, `frame_stop=11`, `fpsec=32`, `blend_out=0.2`.

The punch animation files hold two 45-bone sets (90 nodes): attacker and victim. Taking the first as the
attacker is an assumption.

## The minifig model and skeleton

- Studied hero model: 8 textures, 14 materials, 104 meshes, 45 bones.
- Hierarchy: `character` (root) -> `Hips` -> `LeftUpLeg` -> `LeftLeg` -> `LeftFoot` -> `LeftToeBase` (and
  right); `Hips` -> `Spine` -> `Spine1` -> `Head`; `Spine1` -> `LeftShoulder` -> `LeftArm` -> `LeftForeArm`
  -> `LeftForeArmRoll` -> `LeftHand` -> `LeftWeapon` (and right); `Spine1` -> five four-bone cape chains.
- Bind-pose joints in cm above the feet: hip 10.7, upper spine 20.4, shoulder 24.6 (6.1 out), elbow 19.6,
  hand 16.2 (9.6 out), neck 27.0. The bind pose is not a T-pose: the arms hang at the sides.
- **The body is skinned, not rigid pieces.** Share of weight: hands follow the hand bone 86%, forearm-roll
  14%. Legs and hips: upper legs 54%, feet 23%, lower legs 21%, toes 3%. Torso and arms: spine 42%, spine1
  32%, upper arm 18%, forearm 5%, forearm-roll 4%. Knees, ankles and elbows bend and the torso flexes.
- The same file also holds rigid single-part meshes (leg, arm, torso, hips, head) in their own local space,
  taken to be the loose pieces a character breaks into (not confirmed).
- The original's arm is about a third longer than a real LEGO arm, and the standing pose has the whole
  figure turned 22 degrees with bent knees and elbows.
- Goons use their own 25-bone skeleton (`character, upperTorso, leftLeg ... head`) with shared animations in
  `chars\commonanims\goon_*.an3`. Same file format, same Z mirror.

## Camera

Each level area's `.txt` holds several `sock_start ... sock_end` blocks: camera zones, each with its own
numbers. LEGO Batman has 481 blocks in 118 area files, about four per area. An area is never one camera
setting.

| Key | Usual values | Meaning |
|---|---|---|
| `cam_dist_to_target_xz` | 3.0 to 4.5 m; 2.0 in tight interiors | horizontal distance |
| `cam_dist_to_target` | up to 12 m for big set pieces | distance |
| `cam_y_offset` | 0.8 to 1.5 m (extremes 0.4 and 6.5) | height above the target |
| `campos_seek` | 5.0 in nearly every block, both games | position follow rate |
| `cam_blend_time` | 1.0 | seconds to blend between zones |
| `cam_x_offset` / `cam_z_offset` | up to several metres | camera shifted sideways or along the path |
| `cam_rail_offset` | | the camera rides a rail |
| `move_angle` | -90 in 13 of 15 | the view turned for that zone |
| `cam_look_ratio_y`, `cam_lateral_ratio`, `cam_pullback_ratio`, `offset_blend_y_ratio` | 0.7 to 0.8, plus or minus 0.2, 0.3 to 0.5, 0.65 to 1.0 | not understood |

Indy uses the same keys; its cameras sit lower and closer on average (`cam_y_offset` most often 1.0 to 1.2,
`cam_dist_to_target_xz` 3.5).

LEGO Batman level 1 street (`gothamstreets_a`): main zone distance 4.5, height 1.5, look ratio 0.72; side
zones distance 3.7, height 1.35. Field of view is not in these files; measured roughly from a screenshot it
is about 40 degrees vertical in play. Cutscene cameras all carry a 54.1 degree lens.

Not found: where each zone's area is defined (probably `_cam_pc.gsc` or the `.ai2` trigger areas) and each
zone's heading.

Scale check from the street scene's objects: a van is 62 x 30 x 42 cm, a traffic light 81 cm, a street lamp
104 cm. Vehicles are toy-sized against the minifig.

## Studs and the HUD

- Pickups are `GizmoPickup` records in the area's `.giz`: name, position, type letter, flag.
- The True Hero target is `story_coins` in the level `.txt` (38,000 for Batman's first level).
- True Hero bar (from play): ten studs, each a tenth of the target, turning gold left to right with the one
  in progress partly gold. It is hidden at 0 and appears with the first stud.
- The stud icon beside the count takes the colour of the last stud picked up.
- HUD art is in `stuff\things_pc.gsc` in both games (heart, portrait rings, four stud colours of 32 spin
  frames each, ten side-on studs for the bar). The HUD's layout is in the program, not in a data file.
- `stuff\status\hero_*.gsc` are full-screen end-of-level images, not the in-game HUD.
- PC default keys in both games: WASD move, U jump, H attack, K swap character.

## Enemy AI

Behaviour is plain-text state-machine scripts, `.scp`. Global ones are in `scripts\` (listed in
`scripts\script.txt`); each level area adds its own in `<area>\ai\`. A state has `Conditions`
(`if <test> goto <state>`), `Actions`, and can hand over to another script with `ReferenceScript`. The
tests and actions themselves (`GotOpponent`, `AttackOpponent`, `FollowPlayer` ...) are built into the
program.

**Batman's basic goon:** a level script (level 1's `startinggoons.scp`: neutral until
`NearestPartyRange < 1.75`, then side "baddie") hands over to global `goon.scp`, which sets
`SetHitPoints "min=1" "max=2"` and hands over to `goonnogun.scp` if the character has `prefers_brawling`,
else `goonwithgun.scp`.

`goonnogun.scp`:

| State | Actions | Leaves when |
|---|---|---|
| Start | no weapon, one attacker at a time | spawned -> ApproachPlayer; else -> IdleGotNoOpponent |
| IdleGotNoOpponent | `GoToOrigin "waittime=10"` | `GotOpponent` -> Fight; a player in its trigger area -> ApproachPlayer |
| ApproachPlayer | `FollowPlayer "run"` | `GotOpponent` -> Fight; `Timer > 10` with no opponent -> Idle |
| Fight | `AttackOpponent "goalrange=0.1"` | no opponent -> Idle; `OpponentRange < 0.2` -> TimeAttack |
| TimeAttack | `AttackOpponent "goalrange=0.1"` | `Timer > 3` -> Backoff |
| Backoff | `MoveAwayFromPlayer 1.5` | `OpponentRange > 1.5` -> Fight; `Timer > 4` -> Fight |

Also in the scripts: "one attacker at a time" queuing (`SetUseOneAtOnce`, `SetAtOnceRowDistance 1.25`).
Goon body numbers (`chars\henchman\r_goon.txt`): run 1.6, walk 0.455, same radius and height as the heroes.
View range comes from `viewrange=` in the character file or the level's AI file; the goon files do not set
it and the built-in default was not found (other characters set 1.2, 2 or 20).

**Indy's differences:** `goon.scp` picks gun or no-gun by `GotGun`. Its `goonnogun.scp` has no timed burst
and no back-off; it adds `BackOffScared` (`MoveAwayFromOpponent "1" "face"` while
`OpponentJustPickedUpWeapon`) and gives up the approach after 3 s if the party is under cover. Indy-only
scripts: `attack` (`EngageOpponent` goalrange 1.5, firerange 3), `defend` / `block`, `patrol`, `noweapon`,
`citizenfight`, and creature scripts (`monkey`, `spider`, `bug`, `indysnake`).

## The computer-controlled partner

`scripts\hero.scp` and `generalparty.scp`, in both games:

- Base: `FollowPlayer "0.75"`; with an opponent -> Fight.
- Fight: `AttackOpponent "goalrange=0.1"`; no opponent -> Base; opponent further than 4 m from the player
  (Indy: 3 m) -> Caution; Batman only: closer than 0.5 m to the player -> Backoff (`MoveAwayFromPlayer 1`
  until more than 1 m away).
- Caution: keep following; back to Fight when the opponent is within 2.5 m of the player.
- `generalparty.scp` wraps this: with a gun it uses the `blaster` script instead; Indy adds
  `HelpWithCarry` and `HelpWithTriggers` (the partner helps carry objects and stands on switches).

## Puzzles: the flow-box model

`*.git`, plain text, one per level area (115 in Batman, 90 in Indy, 166 in TCS).

- A level's logic is a flow chart of **FlowBoxes**. A box holds gizmos (by Type and Name), a **Condition**
  or an **Action**, and links to child boxes. When a box is satisfied, its children fire.
- Conditions combine their inputs: `All` (797 in Batman / 437 in Indy), `Any` (179 / 104), `Loop`
  (185 / 159), `None` (85 / 94), `Exactly 1`, `Exactly 2`; some `MonitorInputs`. Timer boxes add delays
  (`Timer`, `RandomTime`, `RandomOutputChance`).
- Gizmo flags seen on every type: `StartInvisible`, `FinishedInvisible`, `FinishedDeactive`, `OutputOnly`,
  `Reverse`.
- Gizmo census (Batman / Indy): `blowup` breakable 4,013 / 2,226; `GizObstacle` animated set piece
  3,458 / 2,409; `NuSpecial` 999 / 291; `GizmoPickup` 553 / 136; `GizBuildit` 505 / 231; `MiniCut`
  262 / 121; `Lever` 191 / 84; `Ledge` 116 / 81; `Message` 84 / 67; `Spinner` 46 / 43; `PushBlocks`
  42 / 33; `Grapple` 24 / 58; `SecurityDoor` 19 / 54; `Techno` 18 / 22; `GizTurret` 25 / 19; `Plug`
  20 / 148; `Tube` 61 / 8.
- Batman only: `Shard` 594, `Attracto` 44, `Panel` 36, `TightRope` 24, `Signal` 23, `Torp Machine`,
  `BombGenerator`. Indy only: `GizDig` 111, `Puzzle` 44, `Teleport` 26, `Whipper` 18, `ZipUp` 9.
- Commonest chains: breakable -> breakable, breakable -> set piece, breakable -> condition -> action,
  breakable -> build (148 / 67), build -> set piece (178 / 96), lever -> set piece, plug -> set piece,
  dig -> set piece, breakable -> pickup (218 in Batman).
- Actions (a sample): `PlayObstacle "FORWARD" "name=..." "STAYOPEN"`, `SetGizmoVisibility`,
  `ActivateGizmo`, `SetVisibility`, `ActivatePartEffect`, `SetAIMessage "Name=..." "increment=1"`,
  `GoThroughDoor`, `TurnOnFlowBox`, `HitBlowup "name=..." "damage=100"` (Indy), `SetPickupVisibility`,
  `PlayCutscene`, `CompleteLevel`.

`level_anatomy.py` turns one area's `.git` and scene into its puzzle chains and a floor plan.

## Cutscenes

A cutscene is `cut\...\<name>_pc.cu2` plus a scene of its own (`levels\...\<name>\<name>_pc.gsc`), at 30
frames a second. Each character's performance is a whole-skeleton animation made for that character's own
skeleton (Batman's has 45 nodes like his play animations, Robin's 37).

LEGO Batman's level 1 intro (`gothamstreets_intro`) is 980 frames (32.7 s): six shots joined by plain cuts
at frames 1, 100, 180, 250, 615 and 725. Cameras are locked off (one drifts 0.7 cm in twelve seconds), all
with the same 54.1 degree lens. One camera shakes for seven frames when a wall blows in: a decaying
side-to-side jolt, 33 cm down to 3.

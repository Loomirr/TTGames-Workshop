# Animation export for LEGO Indiana Jones and LEGO Star Wars: TCS

Work of 2026-10-08. Nothing committed, nothing pushed. All scratch scripts and game-derived exports are in
`scratchpad\agent_anim\` (exports under `before\`, `after\`, `all\`). Every number below says what it was measured on.

## Result in one paragraph

`anim_export.py` now writes real clips for all three games. The cause of "0 clips" was never the upper-case names
(Windows opens them either way): it was (1) the fixed LEGO Batman file names (`stand_pc.an3` and so on; TCS has
`IDLE.AN3`, no `_PC`), (2) shared animations living in `chars\commonanims`, and (3) for Indiana Jones himself,
animation files with 29 nodes on a 50-bone skeleton, which the old rule skipped. `chars\batman` in default mode
still gives byte-identical `.gltf` and `.bin`. The Z mirror holds in all three games. The one unreadable file is a
real animation in an older, unrelocated layout and now reads (8,013 of 8,013).

## 1. How each game says which file plays for which action (measured)

Same scheme in all three, read from every character listed in each game's `chars.txt`
(LEGO Batman 287 characters / 5,635 blocks, Indiana Jones 207 / 11,434, TCS 281 / 3,030):

```
anim_start="<file name without _pc.an3 / .AN3>"
action="<what the game asks for>"        ; idle, run, walk, tiptoe, jump, fall, land, build, pulllever, push ...
fpsec=<frames per second>                ; absent in about half the blocks
anim_end
```

- `anim_include="<file>.txt"` pulls in more blocks; the included file lies in the `chars` folder itself
  (`ability_*.txt`, `IndianaJones_SharedAnims.txt`). 1,211 include lines over the three games (not split per game).
- The file is in the character's own folder, else in `chars\commonanims`. Blocks resolved that way:

| game | own folder | commonanims | only in some other folder | nowhere |
|---|---|---|---|---|
| LEGO Batman | 2,273 | 3,250 | 89 | 23 |
| Indiana Jones | 2,889 | 8,455 | 49 | 41 |
| TCS | 2,778 | 226 | 24 | 2 |

  No block names a path; "only in some other folder" (e.g. Batgirl's `sonar_land`, present only in `chars\batman`)
  is treated as not found. Whether the game finds those is not known.
- File naming: `<anim>_pc.an3` lower case in the two 2008 games, `<ANIM>.AN3` in TCS.
- The eleven role actions (idle, run, walk, tiptoe, jump, fall, land, build, takehit, pulllever, push) exist under
  the same action names in all three. Indiana Jones has no `takehit` action at all (0 of 110 characters with
  blocks); TCS has it for 5 of 158. So those games give 10 role clips, not 11.
- Several characters share one folder (`chars.txt`: `dir` + `file`). A skin's `.txt` often has no blocks
  (LEGO Batman 127, Indy 123, TCS 128 characters have none of their own). That the game then uses the folder's
  main character's blocks is a GUESS; the tool does it and says so in its help.
- Which block wins when a name or action repeats (Indy `pulllever`: 11 characters) is a GUESS: the later one
  (includes come first in the files, the character's own blocks after).
- Playback rate: `fpsec=` of the block, 30 where absent (reported as "placeholder" in the notes).

## 2. Z mirror per game (measured)

Test as documented in the code: at frame 0, each node's translation against the bone's bind offset, for bones whose
bind z is more than 2 mm, over every character/animation pair with equal or fewer nodes.

| game | z = minus bind | z = plus bind | z neither (animated) | x or y differ (animated) |
|---|---|---|---|---|
| LEGO Batman (284 characters) | 20,201 | 0 | 691 | 949 |
| Indiana Jones (207) | 53,735 | 0 | 50 | 1,731 |
| TCS (281) | 13,280 | 0 | 11 | 373 |

The same mirror applies to all three; the code is unchanged there. A second, weaker test on the exported idle clips
(bone positions at frame 0 against the rest pose and against its mirror image, in the root's frame) agrees for the
lopsided skeletons (Indy camel 5 cm from rest against 57 cm from the mirror image, horse 0.9 / 36, elephant 7 / 94;
TCS gonk droid 0.05 / 18) and cannot tell for symmetric minifigs (13 of 16 Batman, 16 of 18 Indy, 15 of 20 TCS
characters nearer the rest pose; the misses are near-ties). Not checked on a skinned mesh by eye.

## 3. What changed

`anim_export.py`
- Reads the blocks (with includes) and finds files in any case, with or without `_pc`, in the folder then `commonanims`.
- Default mode, same clip names (`A_TT_Idle` ...): the LEGO Batman file name is used when the folder has it and the
  `.txt` names it; otherwise the `.txt`'s animation for the action. Where they disagree the note says so.
- `--all`: every animation the `.txt` names plus every unnamed `.an3` in the folder; clips carry the animation's own
  name (lower case, no prefix); `.animations.json` also gets `action` and `file`.
- `--multi`: files holding several copies of the skeleton give one clip per copy that fits (`name`, `name_set2` ...).
- `--char <name>`: another model/`.txt` of the same folder (needed for `marion`, `belloq`, `enemysoldier`, `willie`
  ..., which have no model named after the folder and crashed before).
- `--strict`: the old node-count rule. `--set` recipes keep the old rule unless they say `"loose_node_count": true`.
- New node-count rule: node i drives bone i; fewer nodes leave the last bones at rest, extra nodes are left out.
  The note gives how far the frame-0 offsets are from the skeleton's, so a doubtful one can be spotted.
- No arguments prints the help and exits 1; a folder with no skeleton or no model says so instead of crashing;
  a one-bone skeleton with a two-node file no longer crashes.

`an3.py`: reads the `5INA` file (section 5); `info` no longer crashes on files with fewer than 14 nodes; usage on no arguments.
`skeleton_export.py`, `gizmo_export.py`, `format_report.py`, `extract_game.py`, `mem_tool.py`, `nxg.py`, `ttpak.py`:
print the docstring and exit 1 when run bare (all nine verified: exit 1, nothing on stderr). Nothing else changed in them.

### Changes to LEGO Batman output (read this)
- `chars\batman`: `.gltf` and `.bin` byte-identical to before. `.animations.json` differs in two notes only.
- `chars\robin`: 10 clips became 11 (TakeHit added, from `takehit_high`), and **Build now plays at 30 fps instead of 32**.
  The old 32 came from an `fpsec` line belonging to a commented-out block after `build`; the old reader gave such stray
  lines to the block before. Same cause changes 3 more of 242 role clips in the game: `crocodile` walk 36 -> 30,
  `killercroc` run 21 -> 28, `t-rex` fall 30 -> 60 (the new value is the block's own in each case).
- Other Batman characters gain clips (Joker 8 -> 10, Nightwing 4 -> 11, Policeman 0 -> 11) through the action lookup
  and the new node-count rule. In 7 of 232 roles the `.txt`'s animation replaces a leftover file of the Batman name
  (e.g. Nightwing Run: `run1`, not `run`).
- Kept on purpose: Batman's `A_TT_TakeHit` is still the file `takehit`, although the `.txt` uses that file for
  action `recoil` and plays `takehit_high` for `takehit`. Other code depends on the current clip, so it was not
  changed; the note now states it.

## 4. Before and after

62 exports per mode (20 Batman, 20 Indy, 22 TCS; minifigs, skins, animals, vehicles, props). All 62 pass the structural
check (accessor ranges inside views and buffer, 2 channels per bone, rising times, unit quaternions, finite values)
and all 62 import in Blender 5.2 (`--background --factory-startup`), one armature each, actions = clips, every
evaluated pose finite (3 frames per action).

| mode | game | characters | with clips | clips = Blender actions | poses evaluated, all finite |
|---|---|---|---|---|---|
| default | LEGO Batman | 20 | 18 | 162 | 486 |
| default | Indiana Jones | 20 | 19 | 125 | 375 |
| default | TCS | 22 | 21 | 157 | 471 |
| `--all --multi` | LEGO Batman | 20 | 20 | 1,488 | 4,464 |
| `--all --multi` | Indiana Jones | 20 | 20 | 2,833 | 8,499 |
| `--all --multi` | TCS | 22 | 21 | 758 | 2,273 |

Default mode per character (bones, clips before, clips after; "n/a" = `--char` did not exist, the folder crashed or gave the wrong model):

| game | character | bones | before | after |
|---|---|---|---|---|
| Batman | batman | 45 | 11 | 11 |
| Batman | robin | 37 | 10 | 11 |
| Batman | joker / catwoman / alfred / nightwing | 25 / 25 / 28 / 28 | 8 / 7 / 8 / 4 | 10 / 11 / 10 / 11 |
| Batman | harleyquinn / penguin / bane / batgirl | 36 / 25 / 25 / 54 | 9 / 7 / 9 / 8 | 11 / 11 / 11 / 11 |
| Batman | manbat / killercroc / policeman_1 | 46 / 25 / 28 | 6 / 7 / 0 | 10 / 11 / 11 |
| Batman | henchman --char p_goon | 25 | n/a | 11 |
| Batman | jackinabox / penguingoon / umbrella / tank | 30 / 18 / 2 / 6 | 1 / 1 / 2 / 0 | 2 / 5 / 3 / 1 |
| Batman | whip / glide_pack | 21 / 2 | 0 / 0 | 0 / 0 (9 / 4 with `--all`) |
| Indy | indianajones | 50 | 0 | 10 |
| Indy | indianajones --char hansolo / youngindy | 28 / 29 | n/a | 10 / 10 |
| Indy | marion_bar / belloq_jungle / enemysoldier_desert / willie_singer (`--char`) | 38 / 28 / 28 / 38 | crash | 10 each |
| Indy | shortround / thuggee / salah | 28 | 8 / 1 / 9 | 10 / 10 / 10 |
| Indy | camel / elephant / horse / crocodile / indysnake / bat | 41 / 32 / 25 / 27 / 23 / 10 | 2 / 2 / 2 / 1 / 1 / 1 | 3 / 3 / 3 / 2 / 2 / 2 |
| Indy | monkey / colonelvogel_tank / giraffe | 50 / 42 / 28 | 6 / 0 / 0 | 7 / 2 / 1 |
| Indy | whip | 21 | 0 | 0 (32 with `--all`) |
| TCS | bobafett, obiwankenobi, hansolo, princessleia, darthvader, yoda, chewbacca, stormtrooper, landocalrissian, jarjarbinks, snowtrooper (`--char`) | 25 to 37 | 0 | 10 each |
| TCS | darthmaul / grievous | 31 / 37 | 0 | 11 / 9 |
| TCS | battledroid / destroyer / r2d2 / gonkdroid | 14 / 21 / 12 / 7 | 0 | 5 / 5 / 3 / 3 |
| TCS | atat / bantha / tauntaun / xwing | 29 / 20 / 49 / 10 | 0 | 3 / 3 / 4 / 1 |
| TCS | 2_1b | 13 | 0 | 0 |

`--all --multi` clip counts: Batman 157, Robin 158, Indiana Jones 317, Han Solo (Indy) 316, Enemy soldier 294,
Marion 259, Short Round 247, Yoda 69, Darth Maul 72, Obi-Wan 68, Boba Fett 50, R2-D2 12. Full list in `agent_anim\final_table.txt`.
Not found on disk in `--all`: 12 animations (Batman set), 24 (Indy set), 4 (TCS set); listed as skipped in each `.animations.json`.
The whole `--all` run of 62 characters takes about 70 s, three at a time.

## 5. The one failing file (measured, one file)

`LEVELS\EPISODE_IV\DEATHSTARESCAPE\DEATHSTARESCAPE_INTRO\DEATHSTARESCAPE_INTRO.AN3`, 204 bytes. It is a real
animation, not truncated, in a different container:
- bytes 0..3: `AC 00 00 00` = offset 172 of a fix-up table; the tag `5INA` follows at byte 4 (all other TCS files: `4INA` at byte 0);
- the header is the usual one, but each pointer is relative to its own position (constants: field at 44 holds 52 -> 96;
  key types: 48 + 64 = 112; node flags: 56 + 112 = 168), and 0 means none;
- the fix-up table at 172 holds 7 entries that point exactly at the header's seven pointer fields (28, 40, 44, 48, 52, 56, 60);
- it also carries its name, `deathstarescape_intro`, at byte 64.

So it is an unrelocated build of the format (the loader would normally fix the pointers up). Content: 2 nodes, 40 frames,
no curves, 8 constants: two things standing still at (2.03, 1.53, -0.30) and (-3.34, 1.30, -0.32), scale 1. `an3.py`
now reads it. With curves this layout is untested: no such file exists in the three games.
After the change: 8,013 of 8,013 files open and give finite first and last frames (4INA 2,910; 5INA 1; 6INA 2,156; 8INA 2,946).

## 6. Node-count census (measured: every character/animation pair of every `chars.txt` entry)

| game | same as skeleton | more nodes | fewer nodes | exactly double | other whole multiple | file not found |
|---|---|---|---|---|---|---|
| LEGO Batman | 4,191 | 1,221 | 16 | 15 | 4 | 111 |
| Indiana Jones | 10,057 | 966 | 247 | 0 | 0 | 89 |
| TCS | 2,683 | 227 | 66 | 1 | 2 | 26 |

- So the old rule skipped 1,237 (Batman), 1,213 (Indy) and 293 (TCS) pairs outright, plus doubles that did not fit.
- "More" is mostly a prop or two after the skeleton (26 on 25, 29 on 28) or a second, different skeleton (64 on 28:
  policeman and victim). "Fewer" is mostly Indiana Jones: 224 of his animations have 29 nodes on 50 bones (the other 21 are the whip).
- Do the first nodes really belong to the skeleton? Frame-0 offsets within 3 cm of the bind (cape, coat, hair, tail left out):
  more: Batman 970 of 1,221, Indy 869 of 966, TCS 168 of 227; fewer: 15 of 16, 202 of 247, 53 of 66. For comparison the
  same test passes only 3,380 of 4,182 (Batman), 7,503 of 10,056 (Indy), 2,158 of 2,675 (TCS) of the equal-count pairs
  (short characters and stance shifts fail it), so the test cannot reject a file; it is printed in the note instead.
- Whole multiples, skeletons of 2 bones or more: Batman 15 doubles (both copies fit in all 15) and one x4 (`generic_gun_in`
  on Robin, all 4 fit); TCS one x3 (`gunin` on Lando, all 3 fit); Indy none. `--multi` exports them: in the 62-character
  run 9 doubles, the x4 and the x3 came out as 25 clips. In a double, which copy is the attacker stays an assumption.
- Not done: exporting the second, DIFFERENT skeleton of a two-character file (64 on 28). That needs the partner's model.

## 7. Still open

1. Nobody has looked at an Indy or TCS clip on a skinned body. Everything above is numbers (finite, structurally valid,
   mirror test); a wrong bone order in a "more / fewer nodes" clip would pass all of it. Worst notes seen: Nightwing's
   idle (64 nodes on 28 bones, offsets 7.3 cm off). Read the note before trusting such a clip.
2. Skins without blocks using the folder's main `.txt`, and "later block wins", are guesses (section 1).
3. TCS `2_1B` (and the other 127 TCS characters without blocks) get nothing or the main character's set; how the game
   animates a character with no blocks and no files (2-1B) was not found.
4. Half the clips play at the 30 fps placeholder (TCS: 647 of 758 in the `--all` run), because the block has no `fpsec`.
   The engine's real default was not looked up.
5. `speed=`, `frame_stop`, `cycle`, `blend_in/out`, footstep frames are read by nobody here; only name, action, fpsec.
6. `.bsa` files beside most animations were not examined.
7. The `--set` path could not be run (no `anim_sets.json` is shipped and I may not write one into the tools folder);
   it was kept on the old node-count rule and only checked by reading.
8. `nu20.py` was being edited by another agent during these runs; the numbers are from its state at the time.
9. Robin's Build rate change (32 -> 30) is a fix of a reader bug but does change an existing clip: say if the old
   value should be kept.

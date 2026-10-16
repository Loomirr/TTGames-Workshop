# P1/P2 parity audit

Goal: P3/P4 behave like P1/P2 everywhere. Method (16 October 2026): every function
of the unpacked executable that reads party slots 0/1 (`0x93D7F0`, `0x93D7F4`), loops
over them (ends at `0x93D7F8` or after 2 players), reads the pausing player
(`0x802AF8`), the control entries of players 0/1 or their purses was listed: **217
functions**, of which **160** treat P1 and P2 together (the others only mean "the
leading player"). Arrays indexed by a character's player number (`char+0x280`, 2/3 for
P3/P4) were checked for 2-wide sizes, since those are written out of range.

Status: **done** (patched), **v0.40** (this pass), **open** (found, not changed yet),
**checked** (no change needed). Addresses are function starts unless noted.

## Visible: portraits, HUD, menus

| Area | Where | What P1/P2 do | Status |
| --- | --- | --- | --- |
| HUD portraits, hearts, studs | `0x4B9110` loop | Corner portrait, ring, hearts, stud counter | done (second pass, red/purple rings, purses) |
| Counter pulse when hurt | `0x879358` (2 floats), `0x4B78CC` loop | Counter shakes while the character's hit timer runs | v0.40 (4 wide; P3/P4 used P1/P2's) |
| Multiplier icon timer | `0x879360` (2 words), `0x46AC0D`, `0x4B784B` | Animated "x2" icon | v0.40 (4 wide; P3/P4 wrote over `0x879364`) |
| Multiplier marker bits | `0x87B924` bits 0/1 | Doubled count shown per player | v0.40 (P3/P4 read their own bits) |
| Pause: dim others, "PAUSED" by the pauser | `0x4B9282`, `0x4B95DD` | Only the pausing player's portrait stays bright | v0.40 (P3/P4 compared as P1/P2) |
| Computer-controlled corner | `0x4B9931` | Dimmed portrait and flashing join prompt | v0.40 (native path; outside hubs only while a free pad is connected) |
| Pad-light race counters | `0x951250`, `0x476010` | "n/m" per player in that mode | open (2-player scoring; P3/P4 show nothing) |
| Pause menu options per player | `0x494516`, `0x495F91`, `0x4960CC` | Option tables indexed by the pausing player | open (P3/P4 read P1's / outside 2 entries) |
| Results screen | `0x483C70` | P1/P2 stud totals | done (banked); P3/P4 counters not drawn: open |
| Character select, shop, Control Configuration, door menu, loading screen | see PATCHES.md | | done |

## Players in the world

| Area | Where | What P1/P2 do | Status |
| --- | --- | --- | --- |
| Drop-in/out, swap onto a character | `0x427EE2`, `0x427CD0`, `0x428419` | | done |
| Camera framing | `0x40AF85` | Frames the human pair | done (farthest human pair); other loops in `0x40AF85`, `0x40AA90`, `0x40AB20` open |
| Keep players on screen / pull back | `0x40EBF0`, `0x4104F0`, `0x411980`, `0x411C00`, `0x413890` | Players pushed back toward the view | open (P3/P4 can leave the view) |
| Regroup with the partner | `0x499170`, `0x427B40`, `0x427BCD`, `0x41A4D0` | A lost player reappears at the other player | open (P3/P4 have no partner) |
| Players' average position | `0x55E340` (16 callers) | Objects use the human players' centre | open |
| "Is a player" checks | `0x408370` (thermal detonator), `0x40A2A0` | P1/P2 treated as players | open (P3/P4 count as computer characters there) |
| Both P1 and P2 human required | `0x575C20` | Some objects react only when both are human | open |
| Other P1/P2-only checks | about 100 functions, e.g. `0x56E460`, `0x59BD40`, `0x498590`, `0x55EAA0` | Not yet identified | open (to be read one by one) |
| Script targets `player`, `player_2` | `0x43C220`, `0x4543E0` | Level scripts address P1/P2 by name | open |
| Studs: pickup, flight, purses, True Jedi, banking | `0x46B1D0`, `0x46AF20`, `0x4B71A0` | | done; `0x46C4F0`, `0x46D270` open |
| Vehicle levels, pod race | `0x434A20`, `0x43E530`, `0x4D9FA0`, `0x4DC310`, `0x4DCA80` | | open |
| Level-specific scripts | laser gates `0x4C8E40`, disco `0x4E0D6F`, gunship `0x4E2770`, ceiling collapse `0x4E3EA0`, door fight `0x4E4480`, emperor fight `0x4EAF1A`, mine cart `0x4EBDA0`, pillars `0x4DE740` | Triggers react to P1/P2 | open |
| Pause, control entries, cutscene skip | `0x54B0B0`, `0x55C120` | | done |

## Out-of-range writes (P3/P4 index 2/3 into 2-wide arrays)

| Array | Writer | Effect | Status |
| --- | --- | --- | --- |
| `0x879360` words | `0x46AC0D` | Overwrote the stud sound timer `0x879364` | v0.40 (moved, 8 wide) |
| `0x880584` floats ("Techno" state timer) | `0x4CCC60`, every human character | P4 overwrote the first field of the state record `0x880590` | v0.40 (moved, 8 wide) |
| `0x88A534`/`0x88A53C`, `0x800214`/`0x80021C` | `0x4E6D40` | | checked (native guard: players 0/1 only) |
| `0x951250` | `0x476010` | | checked (native guard) |
| `0x88A648` | `0x4EA8E0` | Out-of-range read only | checked |
| `0x876C98` | `0x43E530` | | checked (8 wide) |

## Next passes

1. Players in the world: keep-on-screen, regroup, players' centre, "is a player"
   checks (gameplay; each needs in-game testing).
2. Results screen P3/P4 counters and the pause-menu option tables.
3. Vehicle levels and level-specific scripts, level by level.

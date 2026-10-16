# Patch list

Patch v0.48. All addresses are virtual addresses in the unpacked Steam
executable (image base `0x400000`). `M_BASE` is the mod area: memory allocated by
the DLL, or in the executable build a `.mod` section at the next aligned
address after the last section (`0x2A8E000` when Steamless keeps `.bind`).

## Mod area (0x8000 bytes, RWX)

The DLL allocates this area at run time, with one zero page in front of it
(the game reads the port table at index -1, `0x50FB65`); the executable build appends it as a
section named `.mod`. The hook code is position-dependent, so `build_dll.py`
assembles it at two base addresses and records every 32-bit field that
changes: absolute references get the base added, and relative jumps or calls
into game code get it subtracted. Patched game code is recorded the same way.
A simulation of the loader is compared with the executable build at several
bases.

| Offset | Content |
| --- | --- |
| `+0x000` | Port-to-device table, 4 entries of 12 bytes `{?, device, active}` |
| `+0x040` | Gamepad pointers for ports 0..3 |
| `+0x0C8`..`+0x0E4` | Mod state (camera selection, skip arm, HUD pass) |
| `+0x100` | Hook code (up to `+0x1F00`) |
| `+0x3000` | More hook code (section `.text2`) |
| `+0x1F00` | P3/P4 stud purses, HUD and ring state |
| `+0x1F60` | HUD counter pulse (8 floats), multiplier icon timer (`+0x1F80`, 8 words), HUD swap state (`+0x1F90`..`+0x1FA8`) |
| `+0x1FB0` | "Techno" state timer (8 floats, moved from `0x880584`) |
| `+0x1F40` | Pointer to the loader's `ring_material` helper (DLL only) |
| `+0x1F44`, `+0x1F48` | Current level, frames since it started |
| `+0x1F4C` | Pointer to the loader's `party_watch` logger (DLL only) |
| `+0x2600` | Free Play select: P3/P4 copy of the per-player arrays (78 bytes) |
| `+0x2680` | Free Play select: P3/P4 control entries (2 x `0x60`) |
| `+0x2740`.. | Free Play select pass, return addresses, device scan output |
| `+0x2780` | Camera lists |
| `+0x2900` | FPU save for portrait draws |
| `+0x2980` | Control Configuration: input repeat state for 4 players, page offset, header strings |
| `+0x2800` | Debug text buffer (research builds only) |

## Port table relocation

The game keeps a 3-entry port table at `0x297E040`. 41 instruction operands
that point into `0x297E040..0x297E063` are rewritten to the 4-entry table in
`.mod`. The list is in `src/build.py` (`RELOCS`).

## Hooks

| Name | Address | Original bytes | Replacement |
| --- | --- | --- | --- |
| H1 port table init | `0x4F4992` | `89 1D 30 EF 91 00` | jmp; also initialises entry 3 |
| H2 port reset | `0x4F4C2A` | `89 0D` (+ relocated operand) | jmp; also resets entry 3 |
| H5 frame update | `0x54B0E4` | `55 89 6C 24 14` | jmp; runs cutscene-skip check, gives slots 2/3 their control entry and pad, calls the controller update for slots 2/3 |
| H6 drop-in loop | `0x4285C8` | `83 FB 02` | immediate 2 → 4 |
| H7 drop-in device mask | `0x42807D` | `51 E8 5D C8 0C 00` | jmp; excludes devices already used by ports 0..3 (except P3/P4's own port); P3/P4 accept XInput devices only; nobody joins while a cutscene skip is active; P3/P4 cannot join in a level's first 120 frames, during a cutscene or in a cutscene level |
| H8 pad for port 2 | `0x6DC392` | `8B 74 24 78 85 F6 74 0E` | `mov esi, M_PADS+8` |
| H8 pad for port 3 | `0x6DC3A8` | `8B B4 24 80 00 00 00 85 F6 74 0E` | `mov esi, M_PADS+12` |
| HUD character | `0x4B9266` | `8B 34 AD F0 D7 93 00` | jmp; second pass reads party slots 2/3 |
| HUD loop end | `0x4B9C62` | `83 FD 02 0F 8C F5 F5 FF FF` | jmp; after P1/P2, repeat the loop for P3/P4 with the Y position mirrored |
| HUD ring | `0x4B92C1` | `F6 86 FC 01 00 00 80` | jmp; P3/P4 use the blue ring `0xA6` |
| HUD portrait | `0x4B9479` | `E8 B2 23 0A 00` | jmp; arm the red (P3) or purple (P4) ring material (recoloured texture) |
| Menu corner portraits | `0x496729`, `0x496880`, `0x47B34D`, `0x47B62B`, `0x49745F`; `0x47BEF9` | `call 0x55B830` (P2's corner) | call `menu_corner` / `sel_corner`: P2's portrait, then P3/P4's under P1/P2 with the HUD cross-fade |
| P2 joins the select | `0x4773DA` (`fs_loopend`), `0x476EE8` | `mov edx,0x9253B0` | `p2_join`: F2 (loader `key_f2`, mod `+0x1F5C`) or START on a free XInput pad; `p2_feed` fills control entry 1 from P2's pad; `fp_party` makes slot 1 human |
| Lineup without an absent P2 | `0x47C593`, `0x47C7F1`, `0x47C978` | | list P1 + roster; index 1 is an ordinary entry |
| Switch portrait ring | `0x4BC08B`, `0x4BC284`; `0x56174C`, `0x561840` | | P3/P4 effects get a copied icon entry/node; drawn with the red/purple ring material |
| Grid hidden cells | `0x47C2D1`, `0x47C34F` | `call 0x594C30` | `grid_list`: list `0x879B80` = P1, P2 if active, P3/P4 if active |
| Cursor skips the other player | `0x47719B`, `0x4771E0`, `0x477244` | `movzx reg, word [idx*2+0x87B6C4]` | 0xFFFF (nothing to skip) when that player is not active |
| Grid ring of an inactive player | `0x477843`, `0x47789E` (`fs_portrait`) | | no ring when `0x87B6C8[p]` is 0 |
| HUD P3/P4 pass state | `0x4B9C62` (loop end) | | `hud_swap` around the P3/P4 pass: counter pulse, multiplier icon timer and bits, pausing player, join text, pad-light counters |
| HUD pulse array | `0x4B7139`, `0x4B791F`, `0x4B792D`; loop end `0x4B7939` | `0x879358`; `cmp esi,8` | operands → `+0x1F60`; loop covers party slots 0..3 |
| HUD multiplier icon timer | `0x46AC0D`, `0x4B784B`, `0x4B785E`, `0x4B788E`, `0x4B973E`, `0x4B97B2`; `0x4B78C1` | `0x879360` | operands → `+0x1F80`; jmp `hud_icon_timers` advances entries 2/3 too |
| "Techno" timer | `0x4CCDAE`, `0x4CCDC7`, `0x4CCDD5`, `0x4CDCE9`; `0x4CDCDE` | `0x880584`; `cmp al,1 ; jne` | operands → `+0x1FB0`; `cmp al,3 ; ja` |
| Portrait ring draw | `0x55B8FC` | `E8 0F 73 FF FF` | call; ring drawn with `[0x9738F0]` = armed copy |
| Stud pickup | `0x46B209` | `0F BE 9F 80 02 00 00` | jmp; a human in slot 2/3 owns the stud (hub levels: folded to 0/1) |
| Stud flight target | `0x46B391` | `83 FB 01 D9 05 E0 C2 7F 00` | jmp; studs fly to the collecting player's counter, P3/P4 at the bottom |
| Stud arrival owner | `0x46B07D` | `84 C0 74 08 3C 01 0F 85 FB 00 00 00` | `cmp al,3 ; ja` - owners 0..3 credited |
| Hub stud type array | `0x46AF80` | `0F BE 8E FD 00 00 00` | jmp; owner index clamped to 0/1 for the 2-entry array `0x7FC374` |
| Party restore | `0x41FBAC` | `8B 15 84 37 80 00` | jmp; a carried-over P3/P4 stays human only if its port has a device |
| Purse init | `0x41FE40` | `A1 F4 D7 93 00` | jmp; P3/P4 purses carry over or reset with P1/P2's |
| True Jedi sum | `0x4B7606` | `8B 0D F4 D7 93 00` | jmp; `[0x87B994]` = P1+P2+P3+P4 studs |
| Results banking | `0x483D94` | `80 3D DC A6 87 00 02` | jmp; add P3/P4 studs to the P1/P2 snapshot once |
| HUD counter row | `0x4B9A7B`, `0x4B9B60` | `D9 05 E4 C2 7F 00` | `fld [M_CTRY]`: 0.075 for all players (native 0.045) |
| Select grid loop end | `0x4773DA` | `81 FA 70 54 92 00` … `0F 8C 1E FB FF FF` (24 bytes) | jmp; after P1/P2, P3 joins, then the loop runs again for P3/P4 |
| Select grid start | `0x476E76` | `89 1D 64 95 87 00` | jmp; place the P3/P4 cursors |
| Select menu init | `0x47BB5C` | `89 1D FC 9A 87 00` | jmp; clear the P3/P4 state |
| Select confirm | `0x4772C3` | `E8 98 D6 11 00` | call; refuse a character another player has picked |
| Select cursor draw | `0x47C2E5`, `0x47C362`, `0x47C55E` | `call 0x477630` | call; draw P1/P2 cursors, then P3/P4 |
| Select cursor ring | `0x477843`, `0x47789E` | `call 0x55B830` | call; P3/P4 cursor rings red/purple |
| Select portrait loop end | `0x47C1F8` | `83 C6 01 83 FE 02 0F 8C 27 FD FF FF` | jmp; big portraits and names again for P3/P4 |
| Select portrait other check | `0x47BFCC` | `80 BB C8 B6 87 00 00` | jmp; P3/P4 keep their side position |
| Select portrait ring | `0x47C144` | `E8 E7 F6 0D 00` | call; P3/P4 rings red/purple |
| Select portrait positions | `0x47BF9E`, `0x47BFB7`, `0x47C004` | `fld [0x755174]`, `fld [0x7532B8]`, `fld [0x7FC310]` | operand → patch variables: centre x ±0.4 (±0.8 for P3/P4), corner y 0.745 (-0.745) |
| Select layout values | `0x47BFE2`, `0x47C112`, `0x47C1C8`, `0x47C19A` | `fld [0x7F9358]`, `[0x7F9354]`, `[0x7F935C]`, `[0x7532C4]` | operand → patch variables: portrait size, portrait y, name y, name scale (2x2 layout) |
| Select reveal list | `0x476A48` | `5F 5E 5D 5B 59` | jmp; P3/P4 picks first in `0x8795A8` |
| Roster, second branch | `0x489327` | `A1 C4 B2 87 00` | jmp; add P3/P4 picks |
| Party list | `0x41FA84` | `33 C0 66 83 7D 00 FF` | jmp; Free Play: slots 2/3 = P3/P4 picks; Cantina: + Leia, Antilles |
| Cantina load list | `0x47AABC` | `66 C7 05 94 D5 93 00 FF FF` | jmp; copy `0x879520` + Leia, Antilles to a larger list |
| Cantina load list pointer | `0x48AF61`, `0x48AFB0` | `0x879520` | → the larger list |
| Drop-in swap candidates | `0x428419` | `BD F8 D7 93 00` | jmp; P3/P4 never swap; P1/P2 consider slots 4..7 |
| Loading screen loop end | `0x48BEF2` | `03 F7 83 FE 02 0F 8C 63 FE FF FF` | jmp; second pass with Leia/Antilles |
| Loading screen ring | `0x48BED6` | `E8 55 F9 0C 00` | call; P3/P4 rings red/purple |
| Loading screen y | `0x48BE7B`, `0x48BEC4` | `fld [0x75A21C]`, `fld [0x75A218]` | operand → patch variables (±0.29 for the 2x2 grid) |
| Select prompt device | `0x4B7A80` | `push ebp ; call 0x4F48E0 ; push eax ; call 0x6D67F0 ; push ebp ; call 0x6D6340` | jmp; port + 0 or + 2 |
| Select prompt y | `0x4B7A92`, `0x4B7B0A` | `fld [0x7532B4]`, `fadd qword [0x751660]` | operands → patch variables (0.7, 0.4 for P3/P4) |
| Door menu prompts | `0x47B426`, `0x47B9EC`, `0x4968C0`, `0x4C780E` | `call 0x4B79A0` | call; then P3/P4 corner portraits and prompts (ports 2/3) |
| Drop-out offered | `0x495929`, `0x495B55` | `call 0x55F1A0` | call; any two human players |
| Off-screen join | `0x428401` | `83 7C 24 14 00 74 11 E9 21 FF FF FF` | jmp; P3/P4 join their character where it is |
| Select prompt pass | `0x47C477` | `83 C4 38 5F 5E` | jmp; recompute prompts from the P3/P4 arrays and call `0x4B79A0` again |
| Reveal start position | `0x47C8B5` | `BE A7 00 00 00` | jmp; P3/P4 picks start at the P3/P4 corner |
| Reveal ring | `0x47CA0E` | `E8 1D EE 0D 00` | call; P3/P4 picks red/purple |
| Free Play roster | `0x489278` | `83 3D C8 A9 87 00 00` | jmp; add P3/P4 picks to the roster |
| Free Play party | `0x414E71` | `C7 05 7C 5F 85 00 00 00 00 00` | jmp; party slots 2/3 = P3/P4 picks, human |
| Camera pair 1 | `0x40B6FE` | `8B 34 95 F0 D7 93 00` | jmp; choose the human pair furthest apart |
| Camera pair 2 | `0x40B8B7` | `8B 14 8D F0 D7 93 00` | jmp; same, second gather loop |
| Shop opens for P3/P4 | `0x47CFAA` | `8B 0D F0 D7 93 00` | jmp; counter test for party slots 0..3 |
| Shop input | `0x4C1196` | `81 FD 78 54 92 00 0F 8C 0E FF FF FF` | jmp; also control entries 2/3 of a human P3/P4 |
| Toggle target | `0x487CAA`, `0x487CDB` | `85 ED 56 57 74 2B`, `B9 F0 D7 93 00` | jmp; in the Cantina skip slots 2/3 |
| Cheat codes | `0x4C4714` | `83 C4 04 33 F6` | jmp; ALLCHR / STUD1M before the native code hashes |
| Story characters with the cheat bit | `0x5949C4` | `8B 0D 6C 13 95 00` | jmp; flag 0x80 counts as owned |
| Control Setup players | `0x493CB6` | `6A 02` | `push 4`: the pause menu's Control Configuration covers 4 players |
| Control Setup draw | `0x4234A5` | `E9 86 F2 FF FF` | jmp; columns 2/3 drawn as a second page (fields swapped with 0/1 for the draw, headers "Player 3/4") |
| Control Setup input | `0x4218AE` | `8B 7C 8C 1C 85 FF` | jmp; players 2/3 navigate with their own pads |
| Control Setup input state | `0x4218B4`..`0x4219CC` (11 operands) | `0x856858`/`0x856860`/`0x856868` | operands → mod area `+0x2980` (4 players) |
| Control Setup devices | `0x421A53`, `0x421B46` | `call 0x6D9510` | call; no keyboard for players 2/3 |
| Control Setup presets | `0x421AA9`, `0x421FE7`, `0x422048`; `0x422065` | `call 0x6D95B0`; `8B 7E 38 33 ED` | call / jmp; players 2/3 use the default layouts of players 0/1 |
| Control Setup binding names | `0x422EFB`, `0x422FF1`; `0x422E93`, `0x422EB8` | `call 0x6D9670`; `call 0x6D68E0` | call; player + 2 on the second page |

## Behaviour notes

**Device changes (v0.46).** `WM_DEVICECHANGE` (`0x6DE443`)
schedules three re-enumerations 2 s apart (`0x6D5950`, run from `0x6DAA87` →
`0x6DA200`). The enumeration callback `0x6D9DF0` called `0x6D5080`, a WMI-based
"is this an XInput device" check, for every listed device. The loader replaces
that call (`0x6D9E11`, checked before writing) with `is_xinput()`, which matches
the product GUID's vendor/product id against Raw Input HID devices named with `IG_`.

**Control ownership (H5, `fix_owner`).** When a human is in party slot 2 or 3,
the patch gives that character control entry 2/3 (`0x9253B0 + k*0x60`) and
pad k. If another character already holds that entry, the entries are swapped.
Without this, the joined character kept a non-human control entry and either
ignored input or ran in one direction.

**Stud purses.** P1/P2 purses are 16-byte records at `0x855F38`; P3/P4 get two
more at `M_BASE+0x1F00`, assigned to their character each frame. In normal
levels a collected stud only adds to the collector's purse, so the True Jedi
value (`0x4B71A0`, sum of P1+P2) and the results screen snapshot (`0x483C70`,
`0x87A6AC`/`0x87A6B0`) are extended to include P3/P4.

**Cutscene skip.** While a cutscene plays (`[0x951BE0]`, entry `[0x951BE8]`),
a new START press from any device sets the finished bit `0x1000` in the
cutscene player's flags (`player+0x88`), the same bit playback sets at the end
(`0x508747`), and stops the cutscene audio stream group `0x10` with
`0x694030(0x10, 0)` on the stream manager `0x924DF8`. The cutscene manager
(`0x57EF50`) then runs its normal ending. A cinematic can be several chained
scenes, so the skip stays active: each cutscene that starts next is finished
and silenced too, until none has played for 90 frames with START released.
While the skip is active nobody can drop in, and P3/P4 cannot join during
the first 120 frames of any level (level change detected through
`world+0x128`). In v0.13/v0.14 the skip press joined P3 as the next level
started; that P3 had no port device, so the real P3 pad then joined as P4
(In-game). Cause: the skip press joined P3 in the cutscene level (the drop-in
runs before the skip check in a frame); the level end saved slot 2 as human
and the next level's party setup (`0x41FB90`, saved slot state
`0x93D510 + slot*0x10`, human flag at `+6`) restored it while the ports were
reset. v0.16 blocks P3/P4 joins during cutscenes and in cutscene levels, and
the party restore keeps P3/P4 human only when `0x4F48E0(slot)` returns a
device. v0.9 called
`0x57A5B0`, which completes the chapter; v0.10 finished one scene only.

**Camera.** The native camera gathers at most two players. The hook builds a
list of human characters, picks the pair with the largest distance, and feeds
that pair to the native code. It falls back to vanilla behaviour when
`[0x7F3B14] != -1` or when no human is in slots 2/3.

**Ring colours.** There are only four ring icons (`0xA5` green, `0xA6` blue,
`0xA7` neutral, `0xA8` gold), and the neutral and gold rings are used by the
game. Icon colour comes from the texture: the material set routine
`0x608000` binds the texture (`+0xB8`) and render states; the diffuse colour is
used only by untextured materials (`0x600F20` packs it to `+0xC8`). Each scene
material has a render record (`+0x3C`) that resolves its material by index
when it executes (`0x5E030C`), so a material copy that shares the blue record
still draws the blue texture (v0.12–v0.14 in-game).

v0.15: the loader (`ring_material`, `ring_tid` in `loader.c`)
1. makes a managed copy of the blue ring's D3D texture with remapped colours
   (hue set to red 0° or purple 280° with HSV value and saturation kept;
   DXT1/3/5 endpoints recoloured with the block mode kept, or
   A8R8G8B8/X8R8G8B8 texels; v0.15 swapped R/B, which gave orange), wraps it in a copy of the
   game's texture object (hash cleared, reference count -1 so it is never shared
   or freed by a scene) and registers it with `0x5E5270`;
2. creates a dynamic material with the engine (`0x5E4D40(1)`, as the game does
   for its own override material at `0x62F970`), copies the blue ring's
   settings into it except the pool fields and render record, sets the new
   texture id and finalises it (`0x5E4B00`). The engine assigns dynamic
   materials their own render record (`0x5DE440`).
For P3/P4 the HUD draws the blue ring with that material through the per-draw
material override `[0x9738F0]` (read by the icon draw at `0x5F11D0`), for the
ring draw only and only once the record exists. No game data is changed. The
executable build has no helper and draws blue rings for P3/P4.

**Free Play character select (v0.18).** Menu `0x12` (update `0x476DA0`, draw
`0x47BB70`) shows the character grid in state `[0x879564] = 1`. The native
code keeps two-entry per-player arrays: character `0x87B6C4` (word), active
`0x87B6C8`, cell `0x87958C`, ready state `0x87955C` (0 choosing, 1 picked,
2 ready), timer `0x879B0C`, animation `0x879538`, and stick-repeat state
`0x87B56C`, `0x87B570`, `0x87B584`, `0x87B58C`, `0x87B5A4`, `0x87B5B4`,
`0x87B5B8`, `0x87B6D0`. The grid loop (`0x476EE1`..`0x4773EC`) runs players
0/1 with control entries `0x9253B0 + p*0x60`; a player's cursor skips the
other player's character (`(p-1)&1`). When every active player is ready it
calls `0x476840(P1, P2)`, which builds the Free Play roster (`0x489150`,
`0x87A840`, up to 48) and stores the first two picks at `0x93D590`.

The patch keeps a copy of those arrays for P3/P4 (`M_BASE+0x2600`). After the
P1/P2 loop it exchanges the arrays with the copy and runs the same loop again
with two private control entries filled from the P3/P4 gamepads (buttons
`+0x70`/`+0x78`, left stick `+0x92`/`+0x93` as `0x54AE40` does). The ready
count is shared, so the select ends when all four are ready. The grid cursor
draw `0x477630` is run a second time the same way, with the ring drawn red or
purple through the ring-colour override. P3/P4 are in the select when their
port has a connected pad; a START press on a free XInput pad claims port 2 or 3
(`0x6D9120`, `0x4F47F0`).

Each frame the P3/P4 pads are read with `0x6D6020(pad, 0)` (as `0x54AE40` does
for a human slot; 0.18 skipped it, so the cursors did not move) and their
portrait scale `0x879538` is moved toward 1 with `0x54FAD0` (as `0x4775CD`
does for P1/P2). The big portrait and name loop of the draw function
(`0x47BF29`..`0x47C1FE`, which lerps each portrait from its corner to the
centre by that scale) is run a second time for P3/P4 with the corner y
mirrored and the centre x moved to ±0.8.

When the grid finishes, the P3/P4 picks are added to the roster after
P1/P2's. On the level change the party save `0x414D40` copies the roster into
the saved slots (`[0x855F7C] = 1`); the patch then sets slot 2/3 to the P3/P4
picks with the human flag (`0x93D510 + slot*0x10`, `+6`). A P3/P4 whose port
has a device is human when the Free Play level starts. In Free Play the native
party has only P1 and P2's characters (`0x4892F4`), so before v0.18 P3/P4
could not join a Free Play level.

**2x2 select layout (v0.20).** The big portrait loop computes x =
lerp(centre x, corner x, W), y = lerp(`[0x7F9354]` 0.35, corner y, W), size =
lerp(`[0x7F9358]` 0.35, `[0x804FB0]` 0.16, W), where W goes 0 → 1 as a pick
flies to the corner; the name is drawn at x = centre x, y = `[0x7F935C]`
(top edge), scale `[0x7532C4]`. On screen the portrait centre y equals y and
the ring radius is about 0.6 × size. With P3/P4 the patch uses size 0.25, top
row y 0.55 (names at 0.385), bottom row y 0.15 (names at -0.015), scale 0.36.

**Free Play party (v0.20).** `0x489150` rebuilds the roster when a Free Play
level loads and may cut the party list `0x93D590` to P1/P2 (`0x4892F4`), so
P4 was missing in 0.19. The P3/P4 picks are added to the roster in both
branches whenever Free Play is active, and party setup `0x41F940` reads a
copy of its list with the picks in slots 2/3.

**Cantina (v0.20).** `0x47AA30` builds the Cantina load list `0x879520` (P1
and P2's characters `0x802BD8`/`0x802BDC`, then the hub's extra characters; room
for 6) and the party list `[P1, P2]`. Character ids by name are in the table
at `0x7F1B80` ({name, &id}): `quigonjinn` `0x7F185C`, `obiwankenobi`
`0x7F1860`, `princessleia` `0x7F1864`, `captainantilles` `0x7F1870`. The
starting pair `0x7F1808`/`0x7F180A` is Qui-Gon and Obi-Wan.

**Door menu and loading screen (v0.21).** A level door opens menu `0xF` or
`0x10` (`0x47AA00`); menu `0xF` (draw `0x4967B0`) is the Story/Free Play
choice. The screen with the two large portraits shown while the Cantina loads
is drawn by `0x48BD60`..`0x48BEF7` inside the loading loop, for P1/P2's
Cantina characters `0x802BD8`/`0x802BDC`.

**Drop-in swap (v0.21).** After a join, if the joined character is off screen
or busy, `0x428419`..`0x428523` searches party slots 2..7 for a computer
character near the screen and swaps the player onto it with `0x487CA0`.

**Mirrored pads (v0.23).** Raw devices `0x917000 + dev*0x84`: `+0x10` buttons
held, `+0x14` pressed (copied to the pad's `+0x70`/`+0x78` by `0x4F49B0`).
`mirror_mask` excludes devices 0..3 without a port whose `+0x10` is non-zero
and equal to that of a device with a port.

**Text (`0x50D910`).** 16 arguments: string, x, y, 1.0, three scales, side
flags (the HUD passes 2 for the left player and 8 for the right; the select
names pass 1), r, g, b, a float, 2, 0, 0, alpha (0..128).

**Loading icons (v0.24).** While `[0x93B28C]` is set (loading screen) the
portrait routine takes icons from the loading set: name `[[0x951BB8] +
ring*8 + 4]`, looked up in scene `[0x924880]` with `0x5CF5B0(scene, out,
name, 1)` (out = {scene, ?, node}, the same layout as the level's icon table).

**Pause and drop-out (v0.26).** The per-frame controller loop handles START
for players 0/1: with the game running, after a list of checks it calls
`0x55C120(player)` (pausing player `[0x802AF8]`, menu `[0x8037FC]`); while
paused, the pausing player's START resumes (`0x55C560(1)`, `0x55C600`). The
pause menu adds Drop Out when `0x55F1A0` is true and drops the slot whose
control entry belongs to the pausing player with `0x427CD0(slot, 1, 0, 0)`.
The H5 hook applies the same START handling to a human P3/P4 after their
controller update.

**Control Configuration (v0.27).** The menu at `0x7F2900` and the input
engine keep every per-player field for 4 players, so opening it for 4 players
is enough for device selection, binding, dead zone, reset and accept (accept
saves each player's table into its device record). Two things were 2 wide:
the menu's input repeat state (moved to the mod area, with players 2/3 read
from their own pads) and the draw, which lays out exactly two columns. For
the draw the hook swaps the fields of columns 2/3 with 0/1, sets the player
count to 2, adds 2 to the player argument of the binding lookups and copies
the "Player 1/2" headers with the last digit changed to 3/4, then restores
everything. LEFT/RIGHT walk the columns 0..3 natively, so moving right from
Player 2 flips to the Player 3/4 page.

**Idle P3/P4 controller update (v0.28).** `0x54B0B0` calls `0x54AE40` for
control entries 0/1 every frame; for a computer-controlled player it clears
the entry and keeps only START (mode 3). The h5 hook did this for entries 2/3
only while P3/P4 were human, so after a drop-out the entry and its pad (pads
are read only through `0x6D6020` in that function) kept the last frame's
buttons. `idle_update` now runs it for a computer-controlled P3/P4 whose
entry still holds the mod's pad.

**HUD parity (v0.40).** The HUD loop reads per-player state for players 0/1. The P3/P4
pass runs the same loop with ebp = 0/1, so `hud_swap` exchanges that state with
P3/P4's before the pass and back after it. A computer-controlled P3/P4 now takes the
native path of a computer-controlled P2 (dimmed portrait, flashing prompt from
`[0x800A6C]`/`[0x800A70]`, swapped to "Press START to join"); `p34_prompt` shows it in
hub levels, or while enough XInput pads without a port are connected. The previous
Cantina-only `hud_grey` drawing is removed. See [AUDIT.md](AUDIT.md).

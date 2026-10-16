# Four-player patch: version history

Every test build from the first research version to the current one, newest
first. Each entry says what changed and why; the [README](README.md) status table
says what was tested in game.

## 0.48 — 16 October 2026

- Fixed the long freeze when Jolee Bindo loads (Cantina visitor or Free Play pick).
  The 0.47 watchdog showed the loading thread busy inside D3DX while the main thread
  waited on the loading screen. Jolee's model says its first texture is 0x08000800 x
  0x08000000 pixels; the DDS inside is 2048x2048. The game passes the record's size to
  `D3DXCreateTextureFromFileInMemoryEx` (`0x6020B6`), which scaled the picture up to
  the device maximum and recompressed it. The loader now corrects texture records
  whose width/height disagree with their DDS header in the `_gen` model copy (cube
  maps and other layouts are left alone). Of the 21 test characters only Jolee is
  affected.

## 0.47 — 16 October 2026

- Diagnostics for the long freeze after returning to the Cantina. The 0.46 log
  showed a 31 s freeze while Jolee Bindo walked in (122 files opened, none of the
  time in the mod's own code). A freeze is now recognised by the game's message
  pump stopping (`PeekMessageA`), so long stays in menus are no longer logged as
  pauses. During a freeze a watchdog thread notes every 0.5 s where the main and
  loading threads are and the last file opened through the mod.

## 0.46 — 16 October 2026

- Connecting or disconnecting a controller no longer freezes the game. On every
  device change the game lists all input devices three times, 2 s apart, and asked
  for each device whether it is an XInput pad with a WMI query (`0x6D5080`, called
  from `0x6D9E11`), which takes a long time per device. The loader answers the same
  question from the Raw Input device list instead (also faster at start-up).
- The game opens files on two threads (the Cantina brings visitors in on a loading
  thread). The 4p_mods lookup now lets one thread at a time through and makes the
  other wait; before, the second thread was sent to the .DAT and did not find a
  custom character's file.
- 4p_mods is listed once into an in-memory index instead of one or more disk
  lookups per opened game file (up to 43 for an icon).
- `4p_mod.log` records every pause of 1 s or more between frames with what the mod
  did during it, to find what is left of the pause when returning to the Cantina.

## 0.45 — 16 October 2026

- P3/P4 portraits of computer-controlled characters (Leia and Antilles in the
  Cantina) are shown only while a pad could join them, everywhere: the Cantina HUD,
  the loading screen into the Cantina (back to the two-portrait layout when neither
  could join), the door menus and the Free Play select corners. The characters
  themselves are unchanged; joined players are always shown.

## 0.44 — 16 October 2026

- P2 joins the Free Play select with F2 on the keyboard (P1 and P2 share it, so
  P1's keys activated P2 in 0.43) or START on a free XInput pad; its prompt reads
  "Press F2 or START to join".

## 0.43 — 16 October 2026

- Free Play lineup: a P2 that is not in the select is left out (P1, then the
  roster), as for P3/P4.
- P2 can join the Free Play select: START on its own device, or on any device no
  port owns (before P3/P4 are offered the press). It then picks like the others and
  is human in the level.
- "Press START to join" beside the corner of every player who can still join the
  select (P2; P3/P4 while a free pad is connected).
- The portrait ring shown over a character when a player switches to it is red/purple
  for P3/P4 (was blue/green).

## 0.42 — 16 October 2026

- Free Play select: the grid leaves out the characters under the players' cursors
  (list `0x879B80`). It listed P1 and P2 always; now P1, P2 only while in the
  select, and P3/P4 while in it. P3/P4's hovered character no longer stays in the
  grid under their cursor, and a P2 that is not in the select leaves its character
  in the grid (0.41 left a hole there).
- Cursors skip another player's character only while that player is in the select,
  so P2's hub character can be picked while P2 is out.

## 0.41 — 16 October 2026

- Menus draw P1/P2's corner portraits themselves, so they never disappear. P3/P4's
  are now drawn right after P2's in every such menu (door menus, including the
  phase where the menu fades in, and the Free Play select), instead of with the
  menu prompts, which are not drawn while a menu fades in.
- Coming from gameplay, P3/P4 cross-fade from their bottom HUD corners to their
  menu places under P1/P2 (0.25 s); while a menu shows them, the HUD does not.
- Free Play select: a player who is not in the select (P2 included) shows no ring
  on the grid, as P3/P4 already did.

## 0.40 — 16 October 2026

- P1/P2 parity audit ([AUDIT.md](AUDIT.md)): 160 functions that treat
  P1 and P2 together, grouped by area with status.
- HUD: P3/P4 now use their own per-player HUD state instead of P1/P2's: counter
  pulse when hurt and multiplier icon timer (both moved to 4-wide arrays), multiplier
  marker bits, and the pausing player (only the pauser's portrait stays bright, with
  "PAUSED" by it, as for P1/P2).
- A computer-controlled P3/P4 is shown like a computer-controlled P2 (dimmed portrait
  and flashing join prompt) through the game's own code; outside hub levels only
  while a free XInput pad is connected. Replaces the Cantina-only grey portraits.
- Fixed two out-of-range writes by P3/P4: the multiplier icon timer overwrote the stud
  sound timer, and the "Techno" state timer (`0x880584`) let P4 overwrite a state
  record.

## 0.39 — 16 October 2026

- Custom character icons no longer come and go in Free Play: base pictures sit in
  `stuff\things.gsc` (permanent heap), but a custom character's icon file was
  only loaded into the level heap while that character was in the party or the
  Cantina, and the Free Play grid resolves pictures at level load from whatever
  was loaded. Every custom icon file is now loaded once right after
  `things.gsc` (`things_load` at `0x48AAD4`) into a heap of the loader's own,
  and `0x55B6C0` (icon file of character n) returns it for custom characters.
- Models named differently from their .txt (`T3-M4_PC.GHG` next to
  `T3_M4.TXT`) are served under the name the game asks for; T3-M4 had no model.
- Models exported with Maya namespaces (`MaceWindu_SE_019:head`, Jolee Bindo)
  get the namespaces cut out of their node name table in a
  `4p_mods\_gen\models` copy; the game froze loading Jolee Bindo.

## 0.38 — 16 October 2026

- Custom character icons, found the real cause: an icon .GSC names its two
  pictures in its NTBL chunk (`<name>1` = locked silhouette, `<name>` = colour
  picture), and the KotOR pack's icon files all still say `anakin_jedi_icon`.
  The loader now renames every occurrence of the inside name (node names and
  path) to a unique same-length name in the `_gen\icons` copy and points the
  character's `icon=` at it, so the game's own lookup finds the right picture.
- Removed 0.37's `icon_resolve` fallback: it picked the first node (the
  silhouette) and handed the Cantina spawner a material array where a node was
  expected, which is the likely cause of the freeze when a custom character
  (Jolee Bindo) walked into the Cantina.

## 0.37 — 16 October 2026

- Custom character icons: 0.36's renamed copies were served (log) but still
  not found, so the texture name inside these icon files is not the file's
  path. Icons added by character files are now resolved by owner: when the
  name lookup (`0x5CF5B0`) fails in a character's own icon file and that
  character owns the icon being looked up, the file's first texture is used
  (`icon_resolve` at `0x419F4C`, `0x57A112`, `0x55B9E6`).

## 0.36 — 16 October 2026

- Custom character icons: the game finds an icon texture by the name stored
  inside the icon .GSC ("...\\Icons\\<name>_PC.gsc"). Several community packs
  reuse another icon file without renaming it inside (Canderous Ordo's says
  anakin_jedi_icon), so the icon never resolved (In-game 0.35: same 13 blank).
  Such files are copied to `4p_mods\\_gen\\icons\\` with the inside name
  replaced by a unique name of the same length, and the character's icon= is
  set to it.
- Character .txt choice also accepts a model named with other separators
  (T3_M4.TXT with T3-M4_PC.GHG).
- The served-file log skips animation files.

## 0.35 — 15 October 2026

- Custom character icons: the icon file is found by the `icon=` name in the
  character's .txt as well as by file name. Community packs name them
  differently (icon="bastila_icon" with BASTILA_SHAN_ICON_PC.GSC,
  icon="canderousordo_icon" with CANDEROUSORDO_PC.GSC); the folder's .GSC
  (preferably one with ICON in the name) is used. In-game 0.34: 13 of 21
  icons blank although all were registered.
- Folders with several .txt files (TEST.TXT, leftovers): the character .txt
  is the one with a matching <name>_PC.GHG, named like the folder, not TEST
  (0.34 loaded Zaalbar's folder as TEST).

## 0.34 — 15 October 2026

- Icons for custom characters: the icon table (static, 750 entries at
  `0x7F44F8`) was full after about six custom characters (log 0.33: the 7th
  and later had icon index -1). It is copied to the mod area with room for
  0x800 entries (`0x4CA160`, references `0x419F21`, `0x419F41`, `0x4C9E2F`,
  `0x4CA77C`), and the icon name space grows from 8000 to 0x6000 bytes.
  The mod area grows to 0x8000 bytes (table at `+0x4000`).

## 0.33 — 15 October 2026

- Custom characters were in the character list and the Free Play grid but
  locked (In-game 0.32: the slot gave the error sound; log: owned 0, flags 0).
  A `collect` line without criteria does not unlock a character by itself.
  Custom characters without a price now get the owned and available flags
  (`[0x93B288]` |= 3; 2 with a price), every frame because a loaded save
  replaces the flags.
- 4p_mod.log lists the files served from 4p_mods and the table entries of
  the custom characters (name, text, icon, flags, owned).

## 0.32 — 15 October 2026

- Game file overlay: any file placed as `4p_mods\<game path>` in the game
  folder is opened instead of the copy in the .DAT archives (hook on
  `0x4FA3F0`, the open used for all game files; `file_hook` in the loader).
- Custom characters: every folder in `4p_mods\chars\` with a character .txt
  (community format) is added to the game. The loader merges chars\chars.txt,
  chars\collection.txt and the language file (stuff\text\<language>.txt)
  from the game's copies plus the custom characters into `4p_mods\_gen\`,
  gives each character a free text id (from 352) and rewrites its name_id,
  and finds `stuff\icons\<icon>` in the character folders. Optional
  `4p_char.ini`: `name=`, `price=` (shop). Limits: 340 characters (319 used by
  the game), 100 shop items (88 used). See MODS_README.txt.
- The research build's file log and list dump are removed.

## 0.31 — 15 October 2026

- Cantina visitors: the animation-name table is the limit (spawn log 0.30:
  0x3FF of 0x400 used while 36 MB of the level heap were still free). It now
  has 0x1000 entries (`0x4CA48C`), so about four times as many unlocked
  characters can walk in.
- Cantina: if P1/P2 end up controlling Leia or Antilles (slot 2/3 human with
  no device on port 2/3 and control entry 0/1) they are moved back to their own
  character (`hub_guard`). Party log 0.30: after leaving the shop a keyboard
  press joined P2 onto Leia, which looked like P3 had joined and then made the
  pad join as P4.

## 0.30 — 15 October 2026

- Diagnostics only: 4p_mod.log gets a `spawn` line whenever the Cantina's
  character loading limits change (animation-name table used/max, level heap
  free in 64 KB units, scene objects, character count), to find which limit
  stops more unlocked characters from walking in.

## 0.29 — 15 October 2026

- Cantina shop: P3/P4 can open it at the counter (`0x47CFAA`, slots 0..3
  instead of 0/1) and control it (`0x4C1080` reads control entries 2/3 for
  a human P3/P4).
- Character toggle: in the Cantina, P1/P2 no longer switch onto Princess
  Leia / Captain Antilles (`0x487CA0`). Elsewhere, a P3/P4 slot that P1/P2
  switched onto keeps its control entry: `fix_owner` only treats slots 2/3
  as P3/P4 when their port has a device (party log 0.28: P1 toggled onto
  Antilles and P4 appeared to join).
- Cheat codes in Enter Code: `ALLCHR` unlocks and buys every character and
  vehicle (character flags `[0x93B288]` |= 0x83; the 0x80 bit also unlocks
  story characters through `0x594960`; shop bought bits `0x86E4A8`),
  `STUD1M` adds 1,000,000 studs (`[0x86E4DC]`).
- Mod area grows to 0x4000 bytes: hook code continues in a second area at
  `+0x3000` (section `.text2`).

## 0.28 — 15 October 2026

- Control Configuration: the relocated input repeat state kept the 2-player
  spacing, so player 2/3 entries overwrote the previous/output buttons of
  players 0/1 (In-game 0.27: every cursor move skipped several rows). The
  arrays are now 4 wide (`+0x2980` floats, `+0x2990` previous, `+0x29A0` output).
- Computer-controlled P3/P4: control entries 2/3 are updated every frame like
  0/1 (`0x54B0D0`), instead of only while human. A dropped-out P3's entry
  and pad kept the buttons of the drop-out frame (In-game 0.27: the character
  kept jumping and P3, then P4, rejoined by themselves; party log).

## 0.27 — 15 October 2026

- Control Configuration (pause menu > Control Setup) covers players 3 and 4:
  LEFT/RIGHT past Player 2 shows a second page with Player 3 / Player 4.
  Change Device, button bindings, dead zone, Reset To Defaults, Accept and
  Cancel work per player. Controllers only: keyboards stay with P1/P2.
- The menu object (`0x7F2900`) and the input engine already keep 4 players
  (per-player binding tables `+0x6358 + player*0x80`); the pause menu now
  opens it for 4 players (`0x493CB6`), the draw shows two columns at a time,
  and the menu's input repeat state moves to the mod area (it was 2 wide).

## 0.26 — 15 October 2026

- P3/P4 can pause with START and resume with START, with the same conditions
  the game checks for P1/P2 (`0x54B195`..`0x54B33A`, pause `0x55C120(player)`).
- Drop Out is offered in the pause menu whenever at least two players are
  human (was: P1 and P2 both human, `0x55F1A0`), so P3/P4 can drop out; the
  native drop-out (`0x427CD0`) works on any party slot.

## 0.25 — 15 October 2026

- Door / chapter menus (Replay Story, Free Play, Challenge; menus 0x10, 0x11,
  0xF and the prompt call at `0x4C780E`): P3/P4 corner portraits under
  P1/P2's (faded while computer-controlled) and Back/Select prompts for a
  joined P3/P4.

## 0.24 — 15 October 2026

- P3/P4 join their own character even when it is off screen. 0.21–0.23
  skipped the native "swap onto a nearby party member" without joining, which
  left P3's port claimed and Leia computer-controlled (party log; In-game:
  Leia kept shooting while P3 pressed buttons).
- Mirrored pads: confirmed working (party log on 0.23: P3 joined alone).
- Loading screen: the ring colour comes from the loading icon set
  (`[0x93B28C]`, `[0x951BB8]`, `[0x924880]`), so P3 slides in red from the
  start instead of appearing late.
- Faded (alpha 0.75, as P2) portraits for P3/P4 while not joined: Cantina HUD
  and the Free Play select corners, which are now always shown.
- Free Play select: P3/P4 prompts drawn under P1/P2's (the prompt base y is
  also `fadd qword [0x751660]` at `0x4B7B0A`).

## 0.23 — 15 October 2026

- Double join: the party log of 0.22 showed one START press joining P3 with
  XInput device 0 and P4 with device 1 in the same frame: one physical pad
  presented as two devices (a real pad and a virtual copy). A pad without a
  port whose held buttons equal those of a pad that has one is now ignored
  for joining (drop-in and the Free Play select).
- Free Play select: P3/P4 corner portraits under P1/P2's, with their own
  Exit/Select prompts (a second run of `0x4B79A0` for ports 2/3); centre
  portraits moved inward (x ±0.25).
- Select reveal: P3/P4 picks keep their red/purple rings and fly in from the
  P3/P4 corner portraits, as P1/P2 do.
- Cantina: computer-controlled Leia/Antilles keep the red/purple rings and
  show "Press START to join".
- Loading screen: P3/P4 are drawn only with their red/purple ring; in the
  2x2 layout the portraits are smaller (×0.8) and spread wider (x ×1.5). The
  0.22 x constants only moved where the slide started and were removed.

## 0.22 — 15 October 2026

- Crash entering a level door (In-game, `4p_mod.log` on 0.21): the door menu
  reads the port table with index -1 (`0x50FB65`, port `[0x29758F9]` = -1).
  The original table is inside `.data`, so that read is harmless; the
  relocated table started the DLL's allocation and the read faulted. The DLL
  now keeps a zero page in front of the mod area.
- Drop-in: a pad that another slot is in the middle of joining with is
  excluded for the other slots (P3's START still activated P3 and P4, In-game).
- Cantina: dimmed P3/P4 portraits with the neutral ring for Leia and Antilles
  while nobody plays them.
- P3/P4 portraits are not drawn until their red/purple ring is ready (the
  loading screen briefly showed blue/green rings).
- Loading screen: wider spacing in the 2x2 grid.
- `4p_mod.log` lists changes of party slots 0..3 and ports 0..3.

## 0.21 — 15 October 2026

- Crash when a level door opened its Story/Free Play menu (In-game report on
  0.20): the 0.20 "intro portrait" hook was on menu 0xF, which is that door
  menu, not the loading screen. Removed.
- Cantina loading screen: Princess Leia (P3) and Captain Antilles (P4) are
  drawn with P1/P2 in a 2x2 grid.
- Drop-in: a joining P3/P4 is no longer moved onto another computer-controlled
  party member when their character is off screen, and P1/P2 no longer take
  over P3/P4's slots that way (In-game: P3's START activated P3 and P4 in the
  Cantina).
- The DLL writes the first exceptions (code, address, registers, return
  addresses) to `4p_mod.log`.

## 0.20 — 15 October 2026

- Free Play select with P3/P4: big portraits in a 2x2 layout (P1/P2 on top,
  P3/P4 below, a lone P3 or P4 centred), smaller, above the grid.
- P3/P4 corner portraits at the bottom corners of the select.
- P3/P4 picks are shown first among the characters revealed after everyone is
  ready.
- Free Play levels: P3/P4 picks are added to the roster in both roster
  branches and whenever a Free Play level loads, and the level's party list
  is extended with them (0.19: P4 and their character did not appear,
  In-game).
- Cantina: Princess Leia and Captain Antilles are loaded and join the party as
  slots 2/3, so P3/P4 can drop in there; the level intro portraits show
  P3/P4 at the bottom corners.

## 0.19 — 15 October 2026

- Free Play select: P3/P4 pads are read each frame (0.18 showed their cursors
  but they could not move or pick, In-game).
- P3/P4 big portraits and names in the select, at x = -0.8 / +0.8 beside
  P1/P2, animating in from the bottom corners (0.18 drew them at size 0
  because their portrait animation never advanced).

## 0.18 — 15 October 2026

- Free Play character select for P3/P4: START on a free XInput pad joins the
  grid, the cursor has a red (P3) or purple (P4) ring, and the select ends
  when every joined player is ready. A character picked by one player cannot
  be confirmed by another. P3/P4 start the level as their picked character in
  party slots 2/3. Untested.
- A P3/P4 whose port already has their pad can drop in again with it.
- Unused debug logger, windowed-mode helpers and icon dump are left out of
  the normal build.

## 0.17 — 15 October 2026

- P1/P2 stud counters have the same gap above the hearts as P3/P4 (0.075).

## 0.16 — 15 October 2026

- Ring texture recolour shifts the hue (red 0°, purple 280°) and keeps
  brightness; 0.15 showed the custom texture in-game but orange.
- Phantom P3 after a cutscene skip: no P3/P4 joins during cutscenes or in
  cutscene levels, and a P3/P4 restored at level start without a controller
  is dropped (In-game report on 0.15).

## 0.15 — 15 October 2026

- P3/P4 rings: draw with an engine-created dynamic material that gets its own
  render record and the recoloured texture (0.14 created the texture but drew
  through the blue material's record, so the ring stayed blue in-game).
- P3/P4 cannot join during the first 2 s of a level, which stops the cutscene
  skip press from creating a P3 without a controller (In-game report on 0.14).

## 0.14 — 15 October 2026

- P3/P4 rings use a recoloured copy of the blue ring texture made at run time
  (0.12/0.13 material tints showed blue/grey rings in-game). Untested.
- A cutscene skip can no longer drop in a player: joining is blocked while the
  skip is active and START is held (In-game report on 0.13).
- Add a DXT1 recolour transparency fuzz test.

## 0.13 — 15 October 2026

- Cutscene skip covers every chained scene of a cinematic and stops the
  cutscene audio (In-game report: 0.10 skipped one scene, audio kept playing).
- P3/P4 rings: 0.12 drew a blue copy (In-game); 0.13 tints a copy of the grey
  neutral ring through the diffuse and packed colours. Untested.

## 0.12 — 15 October 2026

- P3's ring is red and P4's purple, drawn from copies of the blue ring
  material through the engine's per-draw material override. 0.11 recoloured
  the neutral and gold rings, which the game also uses; 0.12 leaves them
  unchanged. Untested in-game.
- Record the icon material layout and the unused colour override.

## 0.10 — 15 October 2026

- The `dinput8.dll` loader works on the Steam executable (In-game); it patches
  on the game's `DirectInput8Create` call and logs to `4p_mod.log`.
- Cutscene skip now ends only the playing cutscene through the game's own
  finished flag; 0.9 completed the whole chapter.
- P3/P4 get their own stud counters; True Jedi and the results screen include
  them. The bottom HUD stud counter has more space above the hearts.
- Document the cutscene manager, level types and stud purse flow. See the
  [patch notes](PATCHES.md).

## First version — 15 October 2026

- Add a source-built executable patch for TCS PC (Steam) that adds players 3
  and 4: drop-in on XInput pads, control routing, HUD for P3/P4 and a gold
  P4 ring are tested in-game.
- Cutscene skip with START, P3/P4 stud pickup into the partner's purse and a
  camera that frames the furthest human pair are implemented but untested.
- Distribute the patch as a `dinput8.dll` proxy that patches the game in
  memory after SteamStub decrypts it; the Steam executable is not modified.
  Loader patch data is checked against the executable build; in-game loading
  is not yet tested.
- The builder verifies every original byte and rejects packed executables. No
  game executable or DRM unpacker is included. See the
  [patch notes](README.md).

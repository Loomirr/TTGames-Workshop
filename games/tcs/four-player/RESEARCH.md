# Native research notes

Steam PC build, linker date 2009-10-01. Addresses are virtual addresses in the
unpacked executable. Entries marked *(inferred)* are not fully confirmed.

## Executable

- SteamStub v2.0 wrapper (`.bind`). Original entry point `0x6E74A2`.
  Use Steamless to unpack; this repository does not include an unpacker.
- `.text`, `.rdata` and `.data` file offsets equal their RVAs in the unpacked
  image.

## Players and party

| Address | Meaning |
| --- | --- |
| `0x93D7F0` | Party slots, 8 character pointers |
| `0x93D818` | Party count |
| `0x93D810` / `0x93D814` | P1 / P2 character pointer (set by `0x55E410` from party 0/1) |
| `[0x93D504]`, `[0x93D500]` | Character array base and count, stride `0x10D8` |

Character fields:

| Offset | Meaning |
| --- | --- |
| `+0x80/+0x84/+0x88` | Position |
| `+0x1FC` bit `0x80` | Human-controlled flag |
| `+0x280` | Party slot |
| `+0x7FC` | Stud purse pointer |
| `+0x800` | `0x630`-byte per-player struct |
| `+0xCA4` | Control entry pointer; player index = `(ptr-0x9253B0)/0x60` |

- `0x487CA0` character swap refuses human targets.
- Party setup `0x41F940`: in carry-over mode (`[0x93D81C]`) each slot's human
  flag, hearts and character come from the saved slot state
  `0x93D510 + slot*0x10` (`+0` studs, `+4` character, `+6` human, …).
- `0x41FDC0` purse setup loops two slots only: `0x855F38+slot*0x10` for
  `+0x7FC`, `0x876E78+slot*0x630` for `+0x800`.

## Input

| Address | Meaning |
| --- | --- |
| `0x9253B0` | Control pool, 64 x `0x60`; `+0` gamepad ptr, `+0x5A` allocated |
| `0x297E040` | Port-to-device table, 3 x 12 `{?, device, active}` |
| `0x80051C` | Ports processed by auto-assign (2) |
| `0x917000` | Raw devices, 14 x `0x84`: 0-3 XInput, 4-9 DirectInput, 10-13 keyboard halves |
| `[0x2975144]` | Engine input object; per-device bindings at `dev*0x17C+0x4EA2` |

| Function | Meaning |
| --- | --- |
| `0x4F41F0(port, 0)` | Create a gamepad; engine init tags `0xE..0x11` are ports 0..3 |
| `0x4F49B0` | Read pad |
| `0x4F47F0(port, dev)` | Claim a port for a device |
| `0x427EC0` | Drop-in (player loop `cmp ebx,2` at `0x4285C8`) |
| `0x54B0B0` | Per-frame controller update; calls `0x54AE40(slot)` for two slots |
| `0x54AD40` | Pause check |
| `0x6D9120(mask, 0x1A, &a, &b, 1)` | Scan for a button; returns device or -1 |
| `0x6D74E0` | Device poll |

## Levels and cutscenes

- World struct `[0x802C54]`; current level at `+0x128`.
- Level flags `level+0x64`: `0x20` intro, `0x40` mid-level cutscene,
  `0x80` outro.
- Level records: `[0x951B78]`, stride `0x130`; `+0x62` index. Chapter (area)
  `world+0x12C`: level list `+0x60` (int16), count `+0x7D`.
- Level types from `levels.txt` (`0x578A7E`): `intro_level` `0x20`,
  `midtro_level`/`cutscene_level` `0x40`, `outro_level` `0x80`,
  `status_level` `0x400`, `test_level` `0x200`.
- `0x57A580(index)` requests a level; `0x57A5B0(world)` requests the chapter's
  status (results) level unless a next level is pending (`[0x951B80]`).
- `[0x93B2A4]` != 0 in Free Play (outros are skipped by redirecting to the
  status level).
- `0x574E20() != -1` when a menu is open. Pause is refused in cutscene levels
  (`0x54ADFA`).

## Cutscenes

- Manager `world+0x2AB0` {entries, count}; `0x57C970(mgr, name)` finds one.
  Entry: `+0x4` player, `+0x50` flags (`0x1` main, `0x1000` level's own),
  `+0x5C` playback speed, `+0xEC` next level index, `+0x104` chained cutscene.
- Current cutscene: `[0x951BE0]` playing, `[0x951BE8]` entry (`0x57CE40`).
- Player: `+0x88` flags (`0x2` started, `0x1000` finished - `0x500210`),
  `+0x90` time, `+0x98` step this frame.
- `0x57EF50(world)` per-frame update; at the end of the main cutscene it sets
  the next level (`entry+0xEC`), queues a chained cutscene or resumes play.
- Stream manager `0x924DF8` (thiscall): `0x694240(group, track)` load,
  `0x696900(group, 1)` play, `0x694100(group)` pause, `0x6941A0(group)`
  resume, `0x694030(group, fade)` stop, `0x694DB0(group, volume)` volume.
  Cutscene audio is group `0x10`, track `entry+0x18C`.
- `0x652FB0`/`0x653000` pause and resume the music.

## HUD

- `0x4B9110` draws the player HUD; loop `ebp = 0..1` from `0x4B9260` to
  `0x4B9C65`.
- Position in -1..1 with +Y up. P1/P2 Y is the local `[esp+0x1C]` (about
  0.745); X is `±[0x7FC31C]` (0.775). `[0x7FC318]` (0.16) is the portrait
  size, not a position.
- Ring icon ids: `0xA5` green, `0xA6` blue, `0xA7` neutral, `0xA8` gold.
  `0xA4` appears unused *(inferred)*.
- Icon table `[world+0x2AC0]`, 16-byte entries `{scene, 0, node, flags}`.
  The icon scene has a material array at `+0xC` (count `+0x10`, 0x154).
  Ring materials: `0x14F` neutral, `0x150` gold, `0x151` blue, `0x152` green;
  each material is `0x2C4` bytes. Ring nodes are `0xD0` bytes (`+0xB0` parts,
  `+0xB4` name, `+0xB8` part count 4).
- `0x55B830` draws portraits; `0x552C10` draws 3D icons.
- Ring node: `+0xB0` parts (`{count, &material index, &geometry index}`),
  `+0xB4` name, `+0xC0` node index. Material record (`0x2C4`): `+0x38` index,
  `+0x3C` render record, `+0x74`/`+0xB8` texture id, `+0x120` RGBA tint,
  `+0x128` second colour. Blue tint `00 0D FF FF`, green `0E FF 00 FF`;
  neutral and gold use white with their own textures.
- `0x5CFB50`/`0x5CFB90` set global alpha/colour overrides for icon draws; only
  alpha reaches the renderer (`0x5FD220`).
- Material override: `[0x9738F0]` replaces every primitive's material in
  `0x5F0F00` (via `0x5E5020` when the vertex format `+0x1F0` differs);
  `[0x9738F4]` is a table keyed by material `+0x9A`. Material pool
  `[0x96E560]`, count `[0x971590]`; `0x5E4B20` allocates, `0x5E4F30` makes a
  cached variant, `0x601030` finalises one.
- Textures: table `[0x97157C]` (id n -> entry n-1), capacity `[0x96E570]`;
  `0x5E5270(obj, 0)` registers in the first free slot. Texture object: `+0`
  width, `+4` height, `+8` 16-byte hash (sharing key, `0x5E5390`), `+0x18`
  reference count, `+0x1C`/`+0x20` file data, `+0x24` `IDirect3DTexture9*`
  (`0x5F8E50` creates it with D3DX `0x715730` from the file in memory). Device
  `[0x29765CC]`. Scene unload `0x5EF880` frees only the scene's own ids.
- Dynamic materials: `0x5E4D40(1)` creates one in the pool and lists it in
  `0x973E50` (count `0x973E4C`, max 600); `0x5DE440` later gives listed
  materials a render record; `0x5E4B00` finalises (`0x601030`).
- Render record (`material+0x3C`): `+0` context, `+4` material index; the
  command stream finds its material as `[[record]+0x50][record+4]`. The generic
  record `0x973E70` switches material with MTL commands (`0x5DE2D0`).
- Material set `0x608000`: texture `+0xB8`, vertex declaration `+0x2BC`, render
  states (`0x601360`, wrapper `0x6E5340`). Diffuse floats are not used.
- Render commands (debug names at `0x5E0664`): `0x80` MTL, `0x81` TXTRLOAD,
  `0x82` GEOMCALL, `0x83` MTXLOAD, `0x84` TERMINATE, `0x8C` TRANSFORM_REF,
  `0x8E` END ITEM, `0x93` GEOMCALL2D, `0x94` LIGHTS, `0x9A` CAMERA …
- Portrait `0x55B830(char, x, y, z, size, ring, …)` draws the ring
  (`0x55B8FC`) and then the face (`0x55BA8F`).
- Free Play character select picks the ring at `0x47C96D` in `0x47BB70`:
  player 0 → `0xA6`, 1 → `0xA5`, otherwise `0xA7`. The grid cursors are
  drawn by `0x477630(grid, flag, …)` (ring `0xA6`/`0xA5` by player).

## Menus

- Menu table `0x7FADF4`, 0x1C-byte entries `{draw, update, ?, -1, 0, id, exit}`.
  Menu `0x12` (draw `0x47BB70`, update `0x476DA0`) is the Free Play character
  select; state `[0x879564]` 0 intro, 1 grid, 2 back, 3/4 start the level.
- Grid struct (`0x855F24`, `0x855ED0`, `0x855EA4`): `+0` cells (0x1C bytes,
  `+0` character), `+4` columns, `+6` count. `0x594250(char, cells, count)`
  finds a character's cell; `0x594960(char)` != 0 when it is unlocked.
- Per-player arrays: see PATCHES.md (Free Play character select).
- `0x489150(c1, c2, level, …)` builds the Free Play roster `0x87A840`
  (count `[0x87B2C4]`); `0x4890E0` (char in `edx`) adds one.
- `0x414D40(8)` saves the party for the next level into `0x93D510` (slot
  state) and `0x93D590` (characters); with `[0x855F7C] = 1` the characters
  come from the roster, with 2 they are kept.
- `0x917000 + dev*0x84`: `+0` connected, `+4` owning port.
- `0x6D67A0(dev)` != 0 for the keyboard devices 10..13.
- Control Configuration: object `0x7F2900`, open `0x4234B0(players, ...)`,
  update `0x421720`, draw `0x422730`. `+4` players, `+0x38` selected column,
  `+0x3C`/`+0x4C`/`+0x5C` device per player (current / at open / last),
  `+0x78`/`+0x88` dead zone (4 wide each). The pause menu opens it with 2
  players (`0x493CB0`), the main menu with 1 (`0x493D70`). Navigation input:
  pads of players 0/1 passed as arguments, repeat state `0x856858` (2 wide),
  focus player `[0x29758F9]`.
- Input engine `[0x2975144]`: per-player binding tables `+0x6358 + p*0x80`
  (32 actions x 4 bytes, cleared for 4 players at `0x6DA560`), player device
  `+0x6558 + p*4`; `0x6D5D90(dev, load, p)` copies device ↔ player table;
  accept saves with load = 0, then `0x6DA550`. Keyboard devices 10..13 map
  by player in `0x6D9510` (players 2/3 would give 14/15).
- Cantina shop: in-level menu 0xD, opened at `0x47D09E` when slot 0/1 is human at
  the counter; input `0x4C1080` (control entries, menu snapshot `0x87B6C8`);
  update `0x4C6E90`. Lists `[0x880478]` characters (type 1, count
  `[0x8800D8]`), `[0x880480]` extras (type 2), item 0x74 bytes (`+0x60` id,
  `+0x62` type, `+0x63` bought, `+0x64` price); bought bits `0x86E49C` +
  type*12 style (`0x86E4A8` characters, `0x86E4B8` extras, `0x86E4C8` extras
  enabled); purchase `0x4C2730`, `0x4C2660`; studs `[0x86E4DC]`.
- Enter Code: 6 characters at `0x7FCBF4` (A-Z, 0-9), hash `0x650430`, table
  `0x8801D0` (characters then extras, built at `0x4C1880`); extra codes are
  in the exe at `0x7F3DA8` (0x20-byte entries), character codes come from the
  game data.
- Characters: flags `[0x93B288]` = `0x86E5C0` (1 owned, 2 available),
  collection `[0x95587C]` (count `[0x955878]`, 0x1C bytes); `0x594960(char)`
  owned (story characters via `0x574D00` and `[0x95136C]`), `0x594A90(char)`
  buy. `0x487CA0(char, target)` moves a player onto a computer-controlled
  party member (character toggle, drop-in swap).
- Cantina visitors: `0x419FB0` (from the Cantina update `0x47CDD0`) loads one
  random owned character at a time (async `0x4FECF0`, callback `0x419E90`,
  then `0x4BDE10`) while: no load is pending (`[0x7F23A4]`, `[0x7F23A8]`),
  scene objects `[0x9739B8]` <= 0xFD (array of 256 at `0x9739BC`, fatal
  beyond), the level heap has about heap/6.75 free (`[0x7EF020]` = 40 MB of the
  150 MB main heap `[0x7EF01C]`, which is allocated before DirectInput8Create,
  i.e. before the patch), and the animation-name table has room
  (`[0x29130E4]`: +0x2C used, +0x14 max = 0x400 from `0x4CA48C`, entries 0x34
  bytes at +0x24). Spawn log 0.30: this table fills first (0x3FF) with 36 of 40 MB
  of the level heap free and about 100 scene objects. 0xE9 (`0x4CA491`) is the
  number of animation types, the size of per-character animation arrays.
- Built-in presets `0x824FC0` (24 x 0x9C: name, device id `+0x40`, player
  `+0x5E`); pad presets are for player 0, keyboards for 0/1.

## Studs

- `0x46B1D0` stud pickup accepts slot 0/1 only (`ebx` at `0x46B209`). The slot
  picks the flight target (HUD counter), the owner byte and the multiplier bit
  `1<<slot` in `0x87B924`.
- `0x570BB0()` != 0 in hub levels; there studs go to shared counters and
  `0x7FC374[owner]` (2 entries; `0x7FC37C` is a HUD float).
- True Jedi value `[0x87B994]` = P1+P2 purses (`0x4B75E2`); results screen
  `0x483C70` snapshots purses to `0x87A6AC[2]` and banks their sum.
- Purse (16 bytes): `+0` studs, `+4` flash timer, `+8` stud icon type,
  `+0xA` combo, `+0xC` combo timer. `0x4877D0` swaps purses on character swap.
- Flying stud stores its owner at `+0xFD`; arrival callback `0x46AF20` adds to
  `0x93B298` (level total) and `0x85EA74` (True Jedi meter *(inferred)*).
- Death drop `0x416CED` → `0x46C6E0`; requires `char+0x7FC`.

## Camera

- `0x40ADE0`, called from `0x492575`. The gather loop `0x40B6FE..0x40BA2B`
  collects at most two players into stack arrays.
- `[0x7F3B14] != -1` selects a different camera mode; the patch does not
  change it.

## Display

- D3D present parameters at `0x2976700`; `Windowed` at `0x2976720`, from
  byte `0x2976C24`. Window size variables `0x82647C..0x826488`.
- Forcing windowed mode produced no visible window. Unsolved.

## Open questions

- How the results screen shows per-player studs (`0x87A628` struct; values
  at `+0x84`/`+0x8C` are written but not read by name).
- Drop-in marker over the character (likely the same icon table).
- Whether the hub (Cantina) party has room for P3/P4 drop-in.

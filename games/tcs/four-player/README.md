# TCS PC four-player patch

Research revision: 16 October 2026 (patch v0.48). Parity audit: [AUDIT.md](AUDIT.md);
version history: [HISTORY.md](HISTORY.md).

A patch for the Steam PC release of LEGO Star Wars: The Complete
Saga (app 32440) that adds local players 3 and 4. It is built from source
against the user's own copy of the game. This folder does not contain the
game executable, a patched executable or a DRM decrypter.
Players install a single `dinput8.dll`; the executable stays unmodified.

## Status

Evidence labels: **Native** = confirmed by reading the executable's code;
**In-game** = tested on real hardware; **Untested** = built, not yet played.

| Feature | State | Evidence |
| --- | --- | --- |
| P3/P4 drop-in with START on XInput pads 3/4 | Works | In-game |
| P3/P4 control routing (own control entry and pad) | Works | In-game |
| No duplicate join from the same physical pad | Works (XInput only for P3/P4) | In-game |
| P3/P4 HUD portrait, hearts and stud counter (bottom of screen) | Works | In-game |
| HUD rings: P3 red, P4 purple | Works | In-game |
| P3/P4 HUD uses their own state (hurt pulse, multiplier icon, pause dimming) | Implemented (v0.40) | Untested |
| P3/P4 portraits stay through menu transitions (cross-fade from the HUD) | Implemented (v0.41) | Untested |
| Computer-controlled P3/P4 corner: dimmed portrait and join prompt, as P2 | Implemented (v0.40; hubs, or while a free pad is connected) | Untested |
| Results screen counters for P3/P4 | Not started (P3/P4 studs are added to P1/P2) | - |
| Skip Story Mode cutscenes with START | Skips the whole cinematic and its audio (In-game) | In-game |
| No phantom P3 join after a skip | Fixed in v0.16 | In-game |
| P3/P4 own stud counters | Works | In-game |
| P3/P4 collect studs | Works | In-game |
| P3/P4 studs count toward True Jedi and the level total | Implemented | Untested |
| More space between stud counter and hearts (all players) | P3/P4 work; P1/P2 since v0.17 | In-game (P3/P4) |
| Camera frames the two humans furthest apart | Works | In-game |
| Drop-in marker over the character in P3/P4 colour | Not started | - |
| Free Play character select for P3/P4 | Picking works (v0.19, In-game); v0.20: 2x2 portraits, corner portraits, reveal | Untested |
| P3/P4 start Free Play levels as their picks | v0.19: only P3 (In-game); v0.20 fixes the party list | Untested |
| P3/P4 in the Cantina (Princess Leia, Captain Antilles) | Characters appear (v0.20, In-game); v0.21 fixes the double join, adds them to the loading screen | Untested |
| P3/P4 pause and drop-out | v0.27: drop-out left P3 jumping and rejoining by itself; v0.28 fix | Untested |
| Cantina shop for P3/P4 (open and control) | Implemented (v0.29) | Untested |
| Cheat codes ALLCHR (all characters/vehicles bought) and STUD1M (+1,000,000 studs) | Implemented (v0.29) | Untested |
| P3/P4 controller configuration (Control Setup, second page) | Works (v0.27); v0.28 fixes cursor skipping | In-game |
| DLL loader on the Steam executable | Works (patches on `DirectInput8Create`) | In-game |
| Windowed mode | Attempted; window does not appear | In-game (failed) |
| P2 joins the Free Play select (F2 on the shared keyboard, or START on a free pad) | Implemented (v0.44) | Untested |
| "Press START to join" beside every player who can still join the select | Implemented (v0.43) | Untested |
| Free Play lineup leaves out players who did not join | Implemented (v0.43) | Untested |
| Character-switch portrait ring red/purple for P3/P4 | Implemented (v0.43) | Untested |
| P3/P4 portraits of computer characters only while a pad could join them (also the Cantina and its loading screen) | Implemented (v0.45) | Untested |
| No freeze when a controller is connected or disconnected | Implemented (v0.46: XInput check without WMI) | Untested |

If one controller shows up twice in Windows (for example a pad plus a Steam
Input or DS4Windows virtual copy), the copy cannot join as another player
while it mirrors a joined pad.

A DirectInput pad (for example a raw DualSense) has no control bindings unless
the game's own configuration assigns some, so it cannot join as P3/P4. Use an
XInput pad or an XInput wrapper such as DS4Windows.

## Installing (players)

The patch is distributed as `dinput8.dll`. It does not modify any game file.

1. Copy `dinput8.dll` into the game folder, next to `LEGOStarWarsSaga.exe`.
2. Start the game from Steam as usual.

To uninstall, delete `dinput8.dll`. The DLL only works with the unmodified
Steam executable. If the game code is not what it expects (another version,
or an executable that is already patched), it shows a message and the game
runs without the mod.

## Building

Requirements: Python 3, GNU binutils for i386 (`as`, `ld`, `objcopy`, `nm`)
and LLVM (`clang`, `lld-link`, `llvm-dlltool`). On Windows use WSL, or MSYS2
with `mingw-w64-i686-binutils` and set `BINUTILS_PREFIX=i686-w64-mingw32-`;
LLVM's Windows installer provides the other tools.

The builder needs an unpacked copy of the executable to read and record the
original bytes of every patched location:

1. Copy `LEGOStarWarsSaga.exe` and remove the SteamStub wrapper from the copy
   with [Steamless](https://github.com/atom0s/Steamless). The builder checks
   the original entry point (`0x6E74A2`) and rejects a packed executable.
2. Build:

   ```
   python src/build_dll.py LEGOStarWarsSaga.unpacked.exe dinput8.dll
   ```

   Any mismatch with the expected original bytes stops the build.

`--research` adds a one-shot dump of the player icon materials to
`4p_icons2.bin` in the game folder. It is only for continuing the ring-colour
work.

`src/build.py` produces a standalone patched executable from the same sources
instead. It is kept for research; a patched executable is not distributable.

### How the DLL works

The game imports `DINPUT8.dll`, so Windows loads the DLL from the game folder
before the game starts. At that point SteamStub has not yet decrypted the game
code. The DLL applies the patch on whichever comes first: the game's call to
`GetSystemTimeAsFileTime` (the C runtime's first import call after the
original entry point), or its call to `DirectInput8Create` (engine start-up at
`0x6DC13C`, before the port table and gamepads are initialised). On the Steam
executable only the second trigger fires; the first import call does not reach
the replaced entry (In-game, from `4p_mod.log`). It then checks
every original byte, allocates the mod area, copies and relocates the hook
code and applies the patches. `DirectInput8Create` is forwarded to the system
`dinput8.dll`. Progress and errors are written to `4p_mod.log` in the game
folder. The log also lists every pause of a second or more between frames,
with the files opened through the mod during it.

## Playing

- P1 and P2 join as usual. P3 and P4 join by pressing START on the third and
  fourth XInput controllers.
- P3/P4 take over a non-human party member, as P2 does.
- The P3/P4 HUD appears at the bottom-left and bottom-right of the screen.
- During a Story mode cinematic, any player's START skips all its scenes and
  the cutscene audio; the game continues as if they had played to the end.
- Free Play character select: P3 and P4 join the grid with START on their
  pad (if they are not in it already) and pick with the same buttons as
  P1/P2. Their cursors have red and purple rings. The level starts when every
  player in the grid is ready; a character already picked by another player
  cannot be confirmed. P3/P4 then start the level as the characters they
  picked.
- In the Cantina the party has four characters: Qui-Gon Jinn and Obi-Wan
  Kenobi for P1/P2, Princess Leia and Captain Antilles for P3/P4 (computer
  controlled until P3/P4 press START).
- If the game crashes, `4p_mod.log` in the game folder records where.
- Each player has an own stud counter. At the results screen P3's studs are
  added to P1's line and P4's to P2's, so the level total includes everyone.

## Files

- [AUDIT.md](AUDIT.md): every native function that treats P1/P2 specially, and
  whether P3/P4 are covered.
- [HISTORY.md](HISTORY.md): every test build and what it changed.
- [PATCHES.md](PATCHES.md): each hook, its address, the original bytes and
  what the replacement does.
- [RESEARCH.md](RESEARCH.md): native addresses and structures found while
  building the patch, and open questions.
- [src/hooks.s](src/hooks.s): hook code (GNU as, Intel syntax).
- [src/build_dll.py](src/build_dll.py) and [src/dll/loader.c](src/dll/loader.c):
  DLL builder and runtime loader.
- [src/build.py](src/build.py): shared patch definition and executable builder.
- [src/test_dll_data.py](src/test_dll_data.py): checks the DLL patch data
  against the executable build at several load addresses.
- [src/test_dxt_recolour.py](src/test_dxt_recolour.py): fuzz test that the
  DXT1 ring recolour keeps transparency.

## Limits

- Only the Steam PC build analysed here is supported (linker date 2009-10-01).
  Other builds are rejected by the byte checks.
- The patch has been played on one machine with two to three players. Four
  simultaneous players have not been tested.
- Split screen is not affected. The camera still frames two players; it now
  picks the pair that is furthest apart.

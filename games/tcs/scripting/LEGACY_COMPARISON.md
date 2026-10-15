# Comparing inherited script names with LSW1

[Guide index](README.md) · [TCS unresolved names](UNRESOLVED_NAMES.md) · [LSW1 overview](../../lsw1/README.md)

Some names without TCS PC bindings also occur in the original 2005 PC game's
scripts. This comparison asks whether they are inherited commands, rather than
assuming that every line in a shipped script remains callable in a later game.
LSW1 and TCS are treated as separate engines/builds throughout.

## Native finding

**Sixteen of the 37 audited names have native bindings in the inspected LSW1
PC executable, but not in the inspected TCS PC executable.** `SetDefensive` is
one of them. This supports the explanation that older command text survived
after its bindings changed between the games.

The LSW1 initializer installs its gameplay tables, and the native resolvers
search those tables followed by the core fallbacks. Executing those original
setter and lookup instructions in an x86 emulator produced these bindings:

| Kind | Name | LSW1 native handler |
| --- | --- | --- |
| Condition | `ObstacleFinished` | `0x00436C70` |
| Condition | `DoorOpened` | `0x00436C00` |
| Condition | `DoorOpenedByPlayer` | `0x00436C20` |
| Condition | `ObstacleChainPhase` | `0x00436CB0` |
| Condition | `GadgetActive` | `0x00436D00` |
| Action | `SetDefensive` | `0x00438CA0` |
| Action | `UnLockDoor` / `UnlockDoor` | `0x004419F0` |
| Action | `SetObstacleChainPhase` | `0x00441C50` |
| Action | `LockDoor` | `0x004419C0` |
| Action | `OpenDoor` | `0x00441A50` |
| Action | `ActivateGadget` | `0x00441C00` |
| Action | `SetPlayType` | `0x00439D40` |
| Action | `FollowSpline` | `0x0043CFD0` |
| Action | `CloseDoor` | `0x00441A20` |
| Action | `FollowSock` | `0x0043D6A0` |
| Action | `MakeExplosion` | `0x004403F0` |

Case variants of `UnlockDoor` count as one audited row. All other rows in the
37-name inventory failed the checked LSW1 lookup too. These are lookup results,
not gameplay validation of all sixteen handlers.

### `SetDefensive` was more than a leftover name

The original LSW1 handler was also executed against a synthetic actor context.
On its setup call, it sets actor flag bit `0x4` at offset `0xF10`. An argument
equal to `false`, case-insensitively, clears that bit. No arguments, `"TRUE"`
and `"0"` enable it; a later update call leaves it unchanged. The lookup also
resolves lowercase `setdefensive` to the same entry.

Thus LSW1 contains both the name binding and executable flag-changing behaviour.
The test does not establish every combat consequence of that flag. TCS's
`CanDefend` changes a different-build actor field; it remains **unproven as a
drop-in replacement** for every inherited `SetDefensive` call.

The reverse example matters too: LSW1's installer includes a backup script
mentioning `CanDefend`, but that name fails lookup in this LSW1 build. TCS does
register it. `PreviousMessage`, `ResetTime` and `JustComeFromE` also occur in
LSW1 script material despite failing both builds' checked lookup. Original
script presence was never sufficient evidence of command support.

## Original script evidence

The inspected LSW1 disc installer identifies 1,199 SCP file records. Their
original paths were reconstructed from its `File`, `Component` and `Directory`
tables. All 1,199 extracted files were present at the expected sizes. CAB member
names with numbered suffixes identify different files; they must not be
collapsed by basename when counting commands.

After removing comments with quote awareness, `SetDefensive` occurs 113 times
across that installer material. Of these, **25 occurrences in 11 files** are
outside directories named as backups in the original installer. This is source
coverage, not a claim that all 25 statements execute in gameplay.

The comparison also finds matching script passages containing `SetDefensive`:

| LSW1 source path | Corresponding TCS source path | Matching passage after whitespace/comment normalization |
| --- | --- | ---: |
| `Levels/Episode_I/Chapter_07/Maul_F/AI/DarthMaul.scp` | `LEVELS/EPISODE_I/MAUL/MAUL_F/AI/DARTHMAUL.SCP` | 87 lines |
| `Levels/Episode_III/Chapter_04/Grievous_A/AI/Grievous.scp` | `LEVELS/EPISODE_III/GRIEVOUS/GRIEVOUS_A/AI/GRIEVOUS.SCP` | 48 lines |
| `Levels/Episode_II/Chapter_07/Dooku_C/AI/Dooku.scp` | `LEVELS/EPISODE_II/DOOKU/DOOKU_C/AI/DOOKU.SCP` | 31 lines |

Each listed passage includes at least one `SetDefensive` statement. These are
matching portions, not claims that the complete files are identical. They
support inherited script text across the two games; source text alone does
not establish the earlier command's binding or explain why it was retained.

## Limits of the historical conclusion

Original source material can preserve both working commands and already stale
lines. Nineteen of the TCS audit's 37 names occur somewhere in the inspected
LSW1 SCP material; sixteen resolve and three do not in the checks above. The
remaining names cannot be assigned an origin merely because LSW1 and TCS share
other scripts.

Nothing in these files proves that developers deliberately kept commands
“just in case,” lacked time to remove them, or intended every old script to
remain active. Those are possible explanations, not established history.
LSW2 has not been checked in this comparison.

## Source identification

The inspected original-disc installer inputs have these SHA-256 hashes:

| File | SHA-256 |
| --- | --- |
| `LEGO_STA.MSI` | `384631AE05C0A9A95C2F872189C5BED86A07A909CA3770D967957CD989569F54` |
| `DATA.CAB` | `30704E8FF95BCF3284A364ACDEE62362534A5E38C447A4439D3B9B9B211DB268` |

The disc executable has SHA-256
`49F74D802596B72B8DA24B76F98F249DFDB370D5607FA7E65E3A19BEB833D473`.
It is wrapped by SecuROM, but the relevant tables, setter thunks, lookup loops
and handler remain inspectable. No game startup or protection bypass was used.

| LSW1 native evidence | Address / layout |
| --- | --- |
| Gameplay table installation callsite | `0x03B00E8C` |
| Action/condition setter entry points | `0x004E5E40`, `0x004E5E50` |
| Action/condition resolver bodies | `0x03AFBAA0`, `0x03AFB3E2` |
| Gameplay actions | `0x007695E0`: 145 entries, **8-byte rows** |
| Core actions | `0x00777C38`: 40 entries, **8-byte rows** |
| Gameplay conditions | `0x00769190`: 91 entries, 12-byte rows |
| Core conditions | `0x00777A60`: 38 entries, 12-byte rows |

These are virtual addresses for that LSW1 executable, not TCS addresses or
portable patch locations. In particular, do not apply TCS's 12-byte action-row
layout to LSW1. Emulation used original instructions with synthetic memory
contexts and asserted completion of every native call; no gameplay test was run.

Paths in the comparison are game-relative. No disc images, scripts, executable
code or decompiled implementation are distributed with this documentation.

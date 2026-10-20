# LEGO Star Wars II: The Original Trilogy — PC

Contributor validation in [PR #7](https://github.com/Loomirr/TTGames-Workshop/pull/7) used one Steam PC install (depot 32321): `lego_data/game.dat`,
1,093,580,474 bytes, plus loose audio and movies outside the archive.
This edition is separate from LSW1 and The Complete Saga; no reader for
either is assumed to cover it.

## Archive index (DAT -1)

```text
python formats/cu3/scripts/archive_index_classic.py "path/to/lego_data/game.dat" "new-index.json" --game LSW2
```

Read-only paths and file spans, like the other classic layouts. The index
differs from LB1's -2 in three ways:

- No path hash table and no 8-byte trailer: the index ends after the names.
- File offsets are plain byte positions (no shift, no low byte in the flags).
- Every entry observed is stored (flags 0, packed size equals size).
  Non-zero flags are refused because no compressed -1 entry was seen.

Without hashes, a leaf's file ordinal cannot be cross-checked against its
path. The reader instead refuses overlapping file spans, as well as the
duplicate ordinals, tree cycles and out-of-extent spans it already rejects.
A changed character inside a name string cannot be detected in this layout.

The contributor reports on that install: 8,136 file entries in 487 folders below the root. Every span is
2,048-byte aligned, ends before the index and matches, byte for byte, the
file extracted from it. The extracted `chars` folder (5,187 files) is also
byte-identical to an independently supplied copy of that folder. The -1
profile refuses all 34 installed LB1, TCS, LB2, LMSH1 and LIJ1 archives
tried, and their own layouts index exactly as before.

## Other files

The contributor measured these on files extracted from the archive above with a
separate reader; Workshop does not extract classic archives.

| Files | Count | Result |
| --- | ---: | --- |
| AN3 (`4INA`) | 2,440 | All pass the [classic AN3 inspector](../../formats/classic-pc/README.md), sampled at first/middle/last frames |
| CU2 (75 version 517 in `cut/`, one version 516 in `levels/episode_v/ending/`) | 76 | All pass the classic CU2 inspector. None has a companion stating `fpsec`, so every rate is the labelled 30 FPS assumption. `cut/episodeii/` holds only four leftover `.txt` scripts with no CU2 |
| HGP characters | 259 | 255 begin with their own length followed by `NU20`; both the LSW1 HGP reader and the classic NU20 reader refuse them. The other four use the LSW1 layout and read with the LSW1 reader; they look like leftovers (`chars/chewbacca/_chewbacca.hgp`, `chars/yoda/_yoda.hgp`, `chars/palpatine/walk.hgp`, `chars/obiwankenobi/tpm/obiwankenobi.hgp`) |

The separate experimental [LSW2 HGP addon](../../formats/hgp/lsw2/README.md)
now reads this character layout and writes separate source-format copies,
including added bones/parts. Version 0.2.1 has synthetic and Blender integration
checks; the upstream original-file counts are separately labelled and have not
been repeated here. No in-game export validation is claimed. Inspector passes
are layout checks, not skeleton ownership, playback or visual fidelity.
Levels (`.nup`, `.ter`, `.rtl` and others) were not examined.

Workshop integration checks exercise the constructed layout and malformed-input tests. LSW2 is not installed on the integration workstation; the original-file counts above have not been independently repeated here.

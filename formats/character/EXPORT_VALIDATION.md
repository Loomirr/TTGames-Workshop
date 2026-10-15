# Native character export checks

The character addon writes loose native source files into a new folder. It
does not replace an installed character, rename a character slot, or write DAT
archives. Copying the exported files into a mod remains a separate operation.

## What edits are checked

Existing vertex positions, UVs, vertex colors, normals, palette-limited skin
weights and existing facial target coordinates have constrained native writers.
They preserve topology, native bindings and opaque file data. Position edits
must stay inside the original bounds. Facial Basis coordinates cannot change.
Repeated facial-offset runs cannot be split without a future stream rebuilder.

Native shader graphs, painted/replaced images, new geometry, removed draws,
new skin palettes, rest skeleton changes and character-definition rewrites are
not supported. Object placement and evaluated modifiers remain preview-only.
This is not yet an arbitrary Blender-to-game character exporter or a new-slot
character creator. [The main instructions](README.md#export-loose-native-files)
describe the supported workflow and separate animation writer.

## Preventing omitted edits

Fresh imports record their model instances and native draw membership. Export
rejects removed/detached attachments, deleted/duplicated draws, newly added
meshes, reparented geometry and changed native draw bindings. Renaming Blender
objects does not change this identity. Complete copies of a model remain
allowed, provided every instance proposes the same native bytes; the existing
shared-source conflict check still rejects different proposals.

Export also requires leaving Edit Mode, so Blender has committed pending mesh
edits before the writer reads its data. An import from an older addon lacks the
assembly inventory: its export report explicitly marks this check unavailable
and asks for reimport. An import that already omitted an unsupported attachment
keeps that omission in the export report. Its bundle contains consumed
resources, not a complete dump of every dependency named by the character.

Windows publication now uses extended paths internally. A valid destination
path no longer fails solely because the private staging suffix takes a native
animation-set filename past the legacy path limit. Logical exported filenames,
path validation, source ownership, hash verification and exclusive publication
are unchanged. Other applications may still have their own long-path limits.

## Reproducible checks

Run `test_export_inventory.py` with normal Python for the assembly-loss tests.
The shared bundle-output suite also tests a Windows path longer than 260
characters, successful publication and cleanup after a forced verification
failure. Neither suite includes proprietary fixtures.

For your own original files, run the separate Blender checker in a fresh
background process:

```text
blender --background --factory-startup --python check_edited_blender.py -- cases.json new-output-folder
```

Each case supplies `source`, `assets` and `game`, as in `check_blender.py`.
Use `--addon-directory extracted-addon` to test a private unpacked candidate,
or omit it to test the single current build. `--features position,uv` selects a
smaller subset; the default checks all six supported edit classes. An optional
`--cache-directory` can reuse an existing extraction cache; outputs still go
to a fresh separate folder, and consumed source hashes are verified.

For every edit, the checker verifies changed decoded native data, unchanged
file size, topology and palettes, untouched original sources, and reimports
the loose character with the same mesh count and no additional attachment
omissions. It also rejects unsupported assembly/material/topology changes
before publishing output and checks an unchanged live-preview copy.

The October 15 original-file pass verified all six edit classes for these
samples in Blender 5.2.2:

| Game | Character | Decoded edits and loose reimport |
| --- | --- | --- |
| LEGO Marvel Super Heroes | Black Panther | Six classes passed; its pre-existing cape-top decoding omission remains |
| LEGO Batman 3 | Batman | Six classes passed |
| LEGO The Hobbit | Dwalin | Six classes passed |
| LEGO Marvel's Avengers | Captain America (Age of Ultron) | Six classes passed |

These 24 checks validate native editing and Blender reimport for the sampled
layouts. A final candidate check also passed, for each of these four games:
six unsupported-edit rejections before publication, another position edit and
loose reimport, and a byte-identical export from the live facial preview copy.
The final run used a longer output root to exercise Windows staging paths.

These are not in-game tests, whole-roster coverage or proof of native shader
fidelity. Game assets, exported sources and detailed local reports are kept
outside the public repository.

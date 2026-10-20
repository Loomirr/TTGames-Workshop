# Loose character clone building blocks

`definition_patch.py` provides one building block for private character clones:
checked, equal-length string edits in **uncompressed LMSH1 PC StreamInfo 25**
definitions. It uses the shared definition reader's parsed field extents and a
required source SHA-256. Unknown bytes remain unchanged. It does not replace
every matching byte sequence or write DAT archives.

This is not yet a complete new-character creator. Character identity can live in
folder names and roster/project records rather than a CD name field. New roster
entries, collection/unlock/localization records, model copies, attachment
dependencies and animation bindings must be prepared and checked separately.
Changing `Skeleton Name` does not rename bones or prove the game can resolve the
new model. Never redirect to a modified shared model without an isolated copy.

## Use

Inspect the source with the shared definition reader. Its `objects` contain
`offset`, `class`, `fields` and `field_spans`; spans use **decompressed definition
byte offsets**, not compressed file offsets. This writer refuses compressed
inputs. Make a JSON plan with the exact source hash and intended fields:

```json
{
  "game": "lmsh1",
  "source_sha256": "REPLACE_WITH_SOURCE_SHA256",
  "edits": [
    {
      "object_offset": 1234,
      "class": "Character Definition",
      "field": "Skeleton Name",
      "expected": "SUPER_MINIFIG",
      "replacement": "PILOT_MINIFIG"
    }
  ]
}
```

The offset above is illustrative; obtain it from the actual source. Both string
lengths must match exactly, including ASCII encoding. This intentionally avoids
unverified block relocation, internal pointer changes and stream rebuilding.

```text
python tools/character_clone/definition_patch.py source.cd plan.json new-copy.cd
python tools/character_clone/test_definition_patch.py
```

The output must not exist. Choose a separate loose mod staging directory outside
the game and retain originals. The tool verifies the edited fields by decoding
again and checks that bytes outside their extents are identical. These checks
prove a constrained decoded round trip, not engine compatibility or new-slot
registration. Test the complete loose mod in-game separately.

## Packed character text

LMSH1 PC also loads character text from `chars/charstxt.fpk`. A new loose TXT
alone did not supply the runtime name in the private new-slot test. The guarded
`fpk_append.py` helper adds one TXT member to the observed uncompressed
`0x1234567A` bank. It requires the source SHA-256 and an explicit existing donor
member, preserves sorted lookup order, and checks every original payload remains
byte-identical. Compressed or non-character banks, duplicate/unsafe paths and
existing output files are refused. It does not write DAT files.

```text
python tools/character_clone/fpk_append.py charstxt.fpk new-character.txt new-charstxt.fpk --game lmsh1 --name chars/minifigs/newcharacter/newcharacter.txt --donor chars/minifigs/tonystark/tonystark.txt --source-sha256 REPLACE_WITH_SOURCE_SHA256
python tools/character_clone/test_fpk_append.py
```

The header checksum is validated and rebuilt as `0x12345678` plus the sum of
all bytes except the checksum field at offsets 12 through 15, modulo 2^32.
This matched 81 original LMSH1 banks in the private audit. Other header and donor
entry metadata are retained. In the stock text bank, the entry word historically
labelled `crc` by the reader has only three values, which decode as adjacent DOS
timestamps; it is not a measured content or path CRC. General metadata rebuilding
remains unimplemented. Preservation checks establish structure, not acceptance
by the game.

A private skeleton redirect needs its complete runtime resource chain: the CPJ
skeleton record must resolve a CPD, whose model reference must resolve the GHG
and matching texture/shader companions. A GHG by itself imported in Blender but
did not make the new native character work. The child attachment skeletons and
shared animation resources must still resolve too. CC4 dependency/preload
metadata remains opaque; equal-length typed-field edits do not rebuild it.
Keep those original dependencies available and test the complete package in-game.

## Validation

Six asset-free tests cover parsed field edits, opaque-tail preservation, wrong
hash/game/owner/value, unknown fields, length changes, NUL/non-ASCII replacements,
overlapping edits, truncation and compressed-input refusal. A private original
Tony Stark CD sample also decoded after an equal-length skeleton-name edit;
all bytes outside the parsed field remained identical. In-game validation of
that identity redirect is pending.

Five asset-free FPK tests cover sorted insertion, original payload and metadata
preservation, malformed extents, path collisions/traversal, wrong hash/profile,
invalid payloads, header checksums and exclusive CLI output. A private 708-member LMSH1 bank was
extended and decoded with its existing members unchanged; native validation of
the new entries is pending. These helpers are not a universal new-character tool.

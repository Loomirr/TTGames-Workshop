# Inspect original models and archive indexes

The 0.5.10 / 0.1.19 recovery also verifies observed HGOL 12/17 trailers, morph-skin face variants and renamed cape LOD draws. See [recovery checks](RECOVERY_2026-10-07.md).

These read-only tools collect evidence for the shared-body skeleton, archive
and material problems recorded in the [workstation review](MERGE_PACKET_REVIEW_2026-10-06.md)
and [minifigure issue](ISSUE_1_MINIFIGS.md). They work without Blender and do
not require a successful character import. Supply your own original files.
No diagnostic inspector here modifies, extracts or repacks a game archive.
The separate parent-index CLI below can optionally extract supported CU3
companions; that is a separate operation from index inspection.

Run the commands from the repository root with Python 3.10 or newer. Replace
the example paths with your own. Create a new folder under ignored `local/`
for each investigation; reports never replace an existing file or link.
Keep generated reports local until you choose to share them. Source paths,
hashes and decoded metadata are included, but model/texture payloads are not.

## Shared-body skeletons

Use an extracted, uncompressed GHG. The display check uses the existing
mesh/display readers; it does not build Blender geometry. Verified counted
native variant selection always requires mesh/display ownership evidence,
including when the optional report detail is omitted.

```text
python formats/cu3/scripts/inspect_skeleton_candidates.py "path/to/BODY.GHG" --with-display --output "local/my-new-check/body-skeleton.json"
```

The report records all parsed HGOL/name-table candidates, binding and ownership
identity groups, exact consumed field spans, hashes, differing field paths and
structural display compatibility. It also identifies adjacent, overlapping and
contained interpretations. A marker inside an opaque field remains a candidate:
its position alone does not establish whether it belongs to another resource.

`selection.outcome` is the result to inspect: `selected`, `ambiguous` or
`rejected`. Successfully writing a report is not a successful model import.
If display decoding fails, `display_check` says so. Ordinary single-resource
selection can remain limited to skeleton structure, but the new counted-group
route cannot select without its required context. An optional `--expected-nodes` check runs only
after identity selection and never chooses a candidate by joint count.

The default detail limit is 64 candidates/name tables and 32 differing paths.
Truncation is explicit. Identity grouping and selection still use all parsed
candidates within the existing scanner limits, including candidates omitted
from the displayed detail. The report omits bone names, matrix values and
opaque payload bytes. Section boundaries describe reader consumption. For a
verified counted HGOL 10/16 group, `selection.native_variant_group` additionally
records the native ownership proof and selected base. Candidate offsets,
cross-layer remaps, summary rows and nested unmapped entries are each bounded
with explicit total/omitted counts; the internal proof still uses all entries.

Character 0.5.8/CU3 0.1.17 reject singular bind matrices before candidate
arbitration using the same validity check already required by model assembly.
That prevents an invalid candidate from making a valid candidate ambiguous.
Character 0.5.9/CU3 0.1.18 additionally recognize the counted group established
by the supplied LMSH1 NXG and LB3 DX11 originals. They validate the complete
group, native joint/metadata remaps and every sibling's mesh/display/skin
associations before selecting its unique zero-threshold identity base. They
retain original matrices and cross-layer associations. Candidate order and
joint count are not selectors. Unexplained conflicting identities still stop
import, and retained identity cannot hide an invalid sibling. Standalone reads
recheck the source hash after collecting ownership context. See the
[original-file evidence](CHARACTER_ACCURACY_0.5.9.md).

## Avengers and other CC archive indexes

Point the inspector directly at one installed-game DAT, or an existing detached
HDR index. It reads only the bounded declared index, not the entire DAT.

```text
python formats/cu3/scripts/inspect_archive_cc.py "path/to/GAME.DAT" "local/my-new-check/archive-index.json"
```

| Report status | Meaning |
| --- | --- |
| `complete` | The known index structure validates completely. Payload codecs, textures and game support were not tested. |
| `unsupported_suffix` | Known tables validate, followed by bytes whose grammar is unverified. Extraction remains blocked. |
| `invalid_prefix` | A known header, name, path/hash, override or extent check failed. The reported suffix must not be treated as the sole problem. |

The command exits with code 2 for the latter two statuses after saving the
diagnostic report. This is an expected refusal to interpret an unverified
layout. A detached HDR cannot verify DAT payload extents, which the report
states explicitly.

For unsupported layouts, suffix reports include kind/version, table spans, byte count, offsets, SHA-256,
at most 64 sample bytes, and up to 16 `ROTV` marker observations. The words
following those markers are observations in both byte orders, not decoded
lengths or pointers. No pointer is followed and no extraction entries are
returned by the diagnostic API. Neither all-zero suffixes nor familiar-looking
markers are accepted as padding.

The verified kind -8/version 1 extension used by all 17 supplied Avengers
indexes is now decoded: a bounded terminated common-directory prefix, 16 zero
bytes and two counted `ROTV` arrays of 16-byte per-file records ending exactly
at the index boundary. Complete reports include bounded spans, counts and hashes.
The reader preserves each entry's two opaque records without assigning them a
checksum or codec meaning. This grammar does not accept other unknown suffixes,
enable unsupported storage modes or certify DAT payload extraction.

The known path/hash mapping is now checked before a suffix refusal is reported.
Source metadata is compared on the same open handle before and after the index
read, preserving the Windows metadata correction from the workstation review.

## Material and character-definition declarations

Use an extracted GHG or GSC and, when available, its matching character CD.
This path reads declarations without selecting a skeleton or importing a model.

```text
python formats/cu3/scripts/inspect_material_declarations.py "path/to/MODEL.GHG" --definition "path/to/CHARACTER.CD" --output "local/my-new-check/materials.json"
```

Omit `--definition` to inspect only the native material table. The report
retains native material roles, texture and UV selectors, surface declarations,
shader controls and decoded CD objects with completeness information. Input
snapshots and report detail are bounded; original hashes make comparisons
repeatable. Unsupported readers remain unsupported.

For characters with `Source Material Resource File` declarations, add
`--remap-library "path/to/MATERIAL_REMAP_CHARACTER_NXG.GSC"` alongside
`--definition`. This compares each declared material name against the supplied
library, retaining every same-named candidate with its texture/UV selectors and
shader fields. Missing names and duplicate candidates are explicit. The
comparisons also list differing decoded shader flags, variant pointers and
texture bindings in candidate order; equal fields do not prove native shader
equivalence. Differences cover only the reported candidates if detail is capped.
Library paths are chosen by you; the command does not follow paths from the CD or prove
that the chosen library belongs to it. No candidate is selected or applied.
The library snapshot is hashed, and unknown table versions remain rejected.

Each reported material now includes a `parameter_block` span/hash. Only the
observed UMTL 176/177, 492-byte, 13-sampler block is decoded into sampler values
and finite constant candidates. Other layouts remain `unverified_layout`;
invalid values also leave the block uninterpreted. Candidate field names do
not establish Blender shader units or behavior. No constants are applied to
materials by this inspector. See the [reference review and original-file
checks](RESEARCH_REFERENCES_2026-10-07.md).

This is a declaration inventory. It does not create a shader, load textures,
prove a CD belongs to that model, or determine whether a material was rendered
correctly. In particular, decoded fields are not evidence of working native
material remaps, metallic/emission translation or additional normal encodings.

An actual Blender import has a separate `material_capabilities` report in its
material notices. That report can distinguish fields successfully used by the
current shader from fields left unapplied. It also distinguishes an unbound
surface declaration from a verified normal binding that failed to load/apply.
The offline inventory does not make those renderer claims.

For issue #1, useful inputs include the model/CD declarations for Tony, Iron
Man Mark 6 and Hulkbuster, and the face/base-head resources for Vulture and LB3
Alfred. These are investigation targets from the issue, not newly validated
characters. Compare exact source hashes, game/platform and layout versions;
do not copy a shader/UV rule between games based only on a similar screenshot.

## Face target summaries

Use a supported extracted, uncompressed face GHG. The ordinary decoder writes
an editable offset companion; `--summary` instead produces a small diagnostic:

```text
python formats/cu3/scripts/decode_face_targets.py "path/to/FACE.GHG" --summary --output "local/my-new-check/face-summary.json"
```

It preserves native part/target IDs, source record offsets, vertex counts,
encodings, affected vertex counts and source-space displacement bounds. It does
not label expressions, sample BSA/AN4 curves or evaluate masks/renderer output.
Part and target detail caps include omission counts. Repeated targets in LODs
are counted as separate part-target records, not unique expressions.

The summary uses `tt.face-target-summary.v1` and cannot be used as an editable
companion by the native writer. Omit `--summary` for the usual
`tt.relative-position-targets.v1` offset payload. No extraction log is required.
See [face GHG editing and its constraints](../formats/cu3/docs/FACE_GHG_EDITING.md).

## Explicit parent-index DAT inventory

The existing standalone script defaults to LB3's observed `-6` parent layout.
For the observed Hobbit/LEGO Movie `-5` parent layout, select that version
explicitly and choose a new output folder:

```text
python formats/cu3/scripts/archive_index.py "path/to/GAME.DAT" "local/my-new-check/parent-index" --index-version -5
```

This writes an entry list and manifest, extracting no payloads by default.
The manifest records the selected index version. Original checks validated
all four LEGO Movie DAT indexes (47,783 per-archive entries), not their full
character/cutscene pipelines. Every file still passes the known name, path/hash
and extent checks. A `-5` first word is not sufficient: LMSH1 uses a different
tree/hash layout and remains on its separate reader. `-7`, CC families and
other unknown layouts remain rejected here.

Optional `--extract-cutscenes` uses the existing bounded storage-mode 0/2
decoder to write separate CU3/declared companion copies. Extraction success
does not prove those files are supported by the Blender importer. Installed
archives are never edited or repacked.

## Follow-up validation

Keep the existing ownership, path and DDS/archive checks until the reports
establish a specific grammar or association. After a supported correction,
rerun the matching original-file import and native export/edit checks in a
fresh output folder, then compare rendered appearances separately. A camera
import or an operator returning `FINISHED` does not establish actor recovery.
The two previously tested cutscenes still need nonzero, correctly owned actors
before their original-file regression can pass.

BactaTank export remains a separate independent proposal in
[BACTATANK_INTEROP.md](BACTATANK_INTEROP.md). These diagnostics contain no
BactaTank implementation and do not enable `.bmesh` or classic-game GHG writing.

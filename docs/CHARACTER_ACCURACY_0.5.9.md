# Character accuracy follow-up: 0.5.9 / CU3 0.1.18

Character **0.5.9** and CU3 **0.1.18** restore automatic skeleton selection for
the supplied original LMSH1 NXG and LB3 DX11 shared bodies, and accept the
verified additional layout in all 17 supplied Avengers archive indexes. They
also correct four reproducible defects in the shared character code. The fixes
are validated against the original bytes and bounded regression fixtures;
configured-character appearance and in-game behavior still need separate tests.
No whole-roster or exact in-game rendering claim is made.

## Corrections and evidence

### Preserve valid authored normals within a mixed part

The model builder previously applied authored normals only if every vertex in
the part had a usable direction. One zero or near-zero direction discarded all
the valid directions in that part, including when the missing direction belonged
to an unused vertex. This could replace intended surface shading with Blender's
geometric normals.

The builder now applies each valid direction with the existing inverse-transpose
transform. It supplies Blender's zero-vector automatic-normal sentinel only for
vertices without a usable source direction. The existing direction threshold,
finite-value checks and format gates are unchanged. It does not alter native
normal bytes, weld geometry or invent a normal-map encoding.

The Blender regression independently constructs bounded MESH 169, 170 and 175
payloads with float and packed directions. Eighteen cases cover a used missing
direction, an unused missing direction and an entirely missing set, including
nonuniform scaling. They compare each imported corner to its authored or
automatic reference, preserve positions/topology/source data, and exercise the
actual vertex-edit and patch writer for byte-identical unchanged export. The
new mixed-direction case fails on the preceding implementation. Blender 5.1.2
and 5.2.2 pass the corrected checks; a separate review reran the 5.2.2 cases.

**Apply by reimporting.** Opening a saved blend or recreating its preview does
not reconstruct import-time normals. This is a demonstrated importer defect,
but the original Hulkbuster shoulder has not yet been tested against it.

### Recognize facial assets independent of filename case

Asset lookup accepts case differences and preserves the actual source spelling.
The face helper instead required uppercase `FACE_` or exactly `SpiderFace`.
An otherwise identical extracted file named `face_example.ghg` or
`spiderface.ghg` therefore missed the facial mask/depth setup.

The shared predicate now compares filename stems without a case distinction,
while retaining the original provenance value. Live and composed helpers use
that predicate. It accepts the same facial-name families; it does not classify
unrelated head or body meshes as animated facial surfaces.

Portable tests cover qualifying and unrelated names and missing/non-string
metadata. Actual Blender checks compare six case variants through clipping,
shape-target changes and corner-normal preservation, with unchanged source
meshes/materials. Recreate the preview from the original imported scene to
apply this helper correction. These constructed checks do not establish that
Vulture or Alfred's original reported defect is resolved.

### Keep declared loose animation lookup in its proper directory

The animation catalog compared an animation-set directory with candidate clip
directories case-sensitively, unlike its asset provider. For example, a set in
`Anims/` and its declared clip in `ANIMS/` could lose their sibling relationship.
An unrelated clip with the same basename could then make a valid lookup fail.

Directory scope now follows the provider's case-insensitive logical paths.
Case aliases of one full logical path still go through the provider's identity
checks; distinct scoped paths remain ambiguous. Bank-member root precedence,
bone ownership and animation transforms have not changed.

Tests use the actual archive asset provider with constructed index/definition
fixtures. They verify the correct same-directory clip wins over an unrelated
basename, true ambiguities remain rejected, and case aliases retain provider
content checks. No original AS/AN4 grammar was inferred from these fixtures.

### Resolve the existing texture fallback for explicit external models

The file importer accepts a specifically selected model outside the chosen
asset root. Its material resolver attempted to make that source relative to
the root without handling the outside-root case. The resulting exception
prevented the existing companion lookup from running and could leave albedo
or a supported normal texture missing.

The resolver now uses the exact provider-relative companion when it exists,
then the previously supported provider basename lookup. A model outside the
root reaches that same checked fallback. It does not search unselected folders,
prefer an arbitrary duplicate, or alter texture encodings and material roles.

Six new tests use a real extracted-asset provider and a bounded constructed
TXTS/DXT5 fixture. They cover the outside-root model, exact sibling precedence,
ambiguous companions, unavailable companions, constructor-level albedo/normal
loading and the resulting missing-binding diagnostic. The new cases fail on
the preceding implementation and pass after the correction.

## Restore native shared-body selection from original ownership records

Historical Character 0.5.6 selected the first compatible skeleton. The stricter
reader correctly noticed that the original LMSH1 shared body contains three
different valid resources, with 63, 63 and 41 joints; the LB3 body contains four,
with 63, 63, 41 and 41. It could not yet prove how those resources belonged
together, so 0.5.8 refused the import. The bones had not disappeared: the missing
piece was interpretation of their enclosing native resource group.

The two complete originals establish counted HGOL 10 and 16 groups, bounded
trailers, explicit joint and metadata remaps, and one unique base resource with
zero threshold, identity joint mapping and empty metadata remapping. The new
`native_variants.py` reader validates that complete group, including each
sibling's display ownership, layer metadata, rigid associations and skin
palettes, before selecting its declared base. Character and CU3 model loading
pass their already decoded mesh/display data through the same proof.

Selection does not use candidate order, joint count, triangle count, approximate
matrix equality or an assumption that similarly named layers are identical.
Native cross-layer mappings and unmapped entries are retained. An explicitly
retained resource identity cannot bypass validation of a malformed sibling.
Unknown layouts and unexplained conflicting ownership still stop import.
Standalone skeleton reads gather the same required context and recheck the
original source hash; diagnostic output bounds every evidence list without
discarding the full internal ownership evidence.

### Original model checks

Both supplied files now follow the ordinary automatic `load_model` /
`create_model` path in Blender 5.2.2, without injecting a chosen candidate:

| Original shared body | Native base offset | Joints | Mesh objects | Vertices | Triangles |
| --- | ---: | ---: | ---: | ---: | ---: |
| LMSH1 `super_minifig_nxg.ghg` | `0x11e8f8` | 63 | 54 | 15,146 | 17,432 |
| LB3 `super_minifig_dx11.ghg` | `0x11ab54` | 63 | 51 | 11,495 | 12,096 |

Recovered geometry, UVs, byte colors, skin influences and observed normals match
an independently assembled reference for each base. Unchanged native export is
byte-identical, and the originals' contents and filesystem metadata remain
unchanged. All seven resource variants were also structurally audited. Separate
temporary copies exercised 31 refusal checks per original, including malformed
counts/remaps, nested or extra resources, invalid unselected skinning, retained
identity bypass attempts and a source change between reads. All 62 were refused.
The portable native-variant suite adds 24 bounded constructed tests.

These originals are shared bodies, without their matching character definitions,
textures or animations. This establishes the cause and correction of the reported
skeleton exception; it does not certify a complete Vulture, Iron Man or Alfred
render. Small existing Blender normal-encoding differences also remain: the
selected DX11 base has a maximum vector difference of about 0.00845 at a few
corners. A separate reduced NXG variant retains a local head fan shading
limitation. Neither observation justifies changing native topology or normal
bytes. The mixed-normal correction above affects a reduced NXG resource and is
not evidence that the reported Hulkbuster shoulder is fixed.

## Accept the verified Avengers index extension

All 17 supplied original Avengers indexes use CC kind -8, version 1 with one
additional structure: a terminated common-directory prefix, 16 zero bytes and
two counted `ROTV` tables, each containing one 16-byte record per file. The reader
now accepts precisely that bounded structure and requires the complete suffix
to end at the declared index boundary. Other suffix layouts remain unsupported.

The 9,003,256 original index bytes now parse successfully, preserving all
**93,570** pre-existing file entries and their paths, offsets, sizes and flags.
Both extra records are retained per entry as opaque bytes; their checksum,
compression or other semantics are not guessed. Independent byte slicing
verified the records, and all 102 original-index corruption checks were refused.
Ten new portable tests cover the supported grammar and its refusal boundaries.

The eight-byte DAT headers also match their declared index spans and original
archive sizes. No DAT payloads were supplied or extracted. Storage mode 6 remains
unsupported; the supplied listings contain 6,932 such entries, with none among
the model, texture or animation resource types used by the current Character
dependency route. Successful index parsing is therefore useful access progress,
not proof that every archive member, Avengers character or cutscene works.

The earlier Windows report recorded four passing package/preview checks, two
blocked shared bodies and 17 blocked indexes. This follow-up resolves those
specific body and index refusals against the subsequently supplied originals;
the earlier report itself remains a record of the previous build.

## Game coverage and next comparisons

| Area | Current scope | Remaining evidence |
| --- | --- | --- |
| LMSH1 PC NXG | Original shared body now selects and builds its native base; CU3 v18 remains a separate scene workflow. | Fresh complete Vulture and Tony/Mark 6 imports, textures, facial animation and the reported material cases. |
| LB3 PC DX11 | Original shared body now selects and builds its native base; CU3 v19 remains a separate scene workflow. | Fresh Alfred import, facial layers, head-print seam and actor recovery in the earlier blocked cutscene. |
| The Hobbit PC NXG | Shared corrections apply behind the existing definition/archive/layout gates. | Local import of a familiar character such as Bilbo or Gandalf, including skinning and declared attachments; no new Hobbit body supplied in this pass. |
| Avengers PC DX11 | All 17 supplied indexes parse; the original payload codecs were not exercised. | Local installed-game character import, textures, declared attachments and the named costume's materials. |
| LEGO Fortnite | Separate static exported JSON/PNG/GLB/recipe path | Its separate assembly/material dependencies and original exported samples; this TT pass does not establish Fortnite rendering accuracy. |
| Original 2005 LSW1 PC | Separate HGP addon | Independent HGP import checks; this pass does not change that reader. |

No further game files are needed for the corrected refusals above. Start with
fresh imports in the candidate build. If another supported character encounters
a different refused layout, retain its exact error and request only the specific
resource needed to investigate it.

TFA, DCSV, LMSH2 and LOTR archive/reference tools do not constitute enabled
full character profiles. LIJ1 prototype and 3DS texture tools also do not imply
character import support. Historical parser-ready counts describe their earlier
versions, not current complete or visually accurate roster coverage.

## Repeating the Blender regression

Use a fresh output directory with the matching source checkout:

```text
blender --background --factory-startup --python-exit-code 1 --python formats/cu3/scripts/test_native_normals_blender.py -- NEW_OUTPUT_FOLDER
blender --background --factory-startup --python-exit-code 1 --python formats/cu3/scripts/check_face_live_groups_blender.py
```

The repository's portable suite also exercises the new face-name, animation
scope and material-companion fixtures. Package loading, preview-setting recovery
and source-isolation checks remain separate from original-file import,
interactive visual comparison and in-game validation.

For visual reports, record game/outfit, import version, preview version, clip,
frame and a matching before/after angle. A baseline import opened with candidate
preview code can test explicit preview actions; it does not rebuild the saved
materials, normals, geometry or rig. Native material remaps, metallic/emission
semantics, all facial expression timing and complete scene lighting remain open.

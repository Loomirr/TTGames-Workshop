# BactaTank Classic export interoperability research

Reviewed 6 October 2026 against BactaTank Classic source commit
`5576652dfd08b83e985db4317329e7f310c59e46`.

## Feasible target and current status

An independently written **`.bmesh` exporter for replacing a mesh inside an
existing BactaTank Classic model** is a plausible next feature. The supported
destination should initially be a verified PC model from **The Complete Saga,
LEGO Indiana Jones: The Original Adventures, or LEGO Batman: The Videogame**.
Those are BactaTank's documented editable families. Its documented support does
not include original LSW1, LSW2, modern NXG/DX11 characters or console models.
[Reference 1](#references)

The intended workflow would be: import a supported source into Workshop, prepare
one mesh for a particular destination character, export a `.bmesh`, then use
BactaTank's existing mesh-replacement operation on a copy of that destination
`*_PC.GHG`. The destination's `.barm` is a skeleton reference for skinned work.
Modern GHG data cannot become a classic PC GHG by changing its filename, suffix
or version word. The interchange file does not reconstruct an entire classic
character definition, material system, native header or animation bank.
[References 1, 2, 5](#references)

**This packet provides the interoperability investigation, not a working Bacta
exporter.** No Bacta executable, reference `.bmesh`/`.barm`, destination GHG or
gameplay test was available for this pass. The field descriptions below come
from read-only documentation and consumer/producer inspection. They are not a
claim that an independently generated replacement has loaded correctly.

No BactaTank functions, Blender addon modules, strip-generation code, libraries,
DLLs or assets were copied, translated, installed or included in Workshop. A
future implementation must be written independently from the field contract and
validated against independently produced files.

## Which format version matters

The published format page shows **0.4** and ends at an unfinished Mesh section.
It cannot serve as a complete writer specification. At the reviewed commit, the
application's `.bmesh` producer writes **0.5**, and the bundled Blender addon
also selects 0.5. The application handles 0.4 and 0.5 through the same newer
reader and has a separate legacy 0.3 path. Some comments, menu labels and the
addon directory still say 0.3 or 0.4. Those labels are not reliable version gates.
[References 3, 4, 7](#references)

A new exporter should target one explicitly tested version, initially 0.5,
and record the tested Bacta executable version separately. Unknown versions
must be rejected by Workshop's own validation rather than relying on the
consumer's permissive legacy fallback.

## Neutral `.bmesh` field contract

The inspected Blender producer writes NUL-terminated UTF-8 strings. Numeric
fields are used as little-endian values in the supported Windows workflow;
several bundled Python packing calls rely on host byte order instead of stating
it explicitly. An independent writer should state byte order explicitly and
verify it against a reference file. The application creates a byte-aligned
buffer, so alignment padding should not be inferred between these sections.
[References 4, 7](#references)

This table describes the 0.5 structure accepted by the inspected consumer. It
does not specify a general-purpose serialization API.

| Section | Fields in order | Required interpretation |
| --- | --- | --- |
| Header | `BactaTankMesh` string, `PCGHG` string, 32-bit float version | Use the selected 0.5 contract. Validate exact tags and version independently. |
| Bone names | `Bones` string, 32-bit count, that many strings | Names describe the complete armature order for Blender interchange. The application discards these names during mesh replacement. |
| Mesh header | `Mesh` string, unsigned 32-bit vertex count, unsigned 32-bit strip primitive count, eight signed 8-bit bone links | Bone links address the destination model's bone table. They are not arbitrary source joint IDs. |
| Attribute declaration | `MeshAttributes` string, 32-bit attribute count, that many strings | Only the recognized attributes listed below have payload readers. This is not an arbitrary extensible attribute stream. |
| Vertex payloads | `Vertices` string, followed by a tag and the complete array for each declared supported attribute | Arrays follow the consumer's fixed order, not interleaved vertex records. |
| Indices | `Triangles` string and unsigned 16-bit indices | The number of indices is the stored strip primitive count **plus two**. It is not three times a triangle count. |
| Shape payloads | `DynamicBuffers` string, unsigned 32-bit buffer count, one array of three 32-bit floats per vertex per buffer | These are ordered buffers without target names or native target IDs. Destination slot semantics must be established separately. |

The producer and consumer disagree on signedness for some positive count fields;
an initial writer should require nonnegative, bounded counts below the signed
32-bit limit. The practical limits on indices and bone links are much smaller.
The bundled addon also emits variant spellings for two section tags, while the
application reads past these strings without checking them. That permissiveness
does not justify inventing tags or treating arbitrary trailing data as valid.
Use the application's canonical tags and require exact file consumption in our
independent validator. [References 4, 7](#references)

### Supported vertex arrays, in consumer order

Each row applies to every exported vertex. A row is present only when its name
is declared in the attribute list. [Reference 4](#references)

| Attribute | Bytes per vertex | Contract and remaining check |
| --- | --- | --- |
| `Position` | 12 | Three float32 coordinates. Destination axes, units and bind space must be established. |
| `Normal` | 4 | Three unsigned bytes mapped from `[0,255]` to `[-1,1]`, plus a retained fourth byte. This is lossy compared with float normals. |
| `ColourSet1` | 4 | Four unsigned color bytes. Confirm color-space use against the destination material. |
| `ColourSet2` | 4 | A second four-byte color array. |
| `UVSet1` | 8 | Two float32 values. Workshop and the Bacta addon use different Blender-facing V conventions. |
| `UVSet2` | 8 | A second float32 pair. The `.bmesh` reader does not implement arbitrary additional UV arrays. |
| `Tangents` | 4 | Four packed directional/handedness components. Their exact basis and fourth-component use need a normal-map test. |
| `BlendIndices` | 4 | Four signed bytes referencing the mesh's eight-link palette. The documented usable skinning has only three influences. |
| `BlendWeights` | 4 | Four unsigned bytes decoded as normalized fractions. Do not assume that four serialized slots imply four usable influences. |

The global application has additional vertex attribute names, but the inspected
`.bmesh` reader only handles the subset above. A modern source with UV3/UV4,
extra shader attributes or more layers cannot be exported by appending unknown
arrays. Target-required channels must be mapped explicitly; unsupported data
needs an actionable rejection or an explicitly chosen conversion policy.

### Triangle strips are a compatibility gate

The consumer reads `strip_primitive_count + 2` indices and installs the mesh as
a strip. A normal triangle-list writer would therefore consume the wrong number
of bytes and shift the following dynamic-buffer section. The bundled addon
generates stitched strips, but its strip algorithm must not be reused for this
project. An independent implementation can begin with a straightforward strip
representation using degenerate connectors, followed by an independent decode
that proves triangle membership and winding are unchanged. A more compact
strip generator is optional after correctness is established.
[References 4, 5, 7](#references)

The consumer's index field is unsigned 16-bit: an individual index can represent
0 through 65,535. The documentation's 65,565 vertex figure is inconsistent with
that field width. Vertex splitting for UV seams and corner normals counts toward
the exported index range. The bundled Blender exporter currently packs these
indices as signed 16-bit, introducing an additional 32,767 maximum positive
index on that re-export route. Neither numerical field width proves all boundary
values work throughout Bacta and the target game. An initial verified profile
should use conservative limits and include boundary cases before raising them.
[References 2, 4, 7](#references)

## Skeleton identity and classic skinning limits

The documented practical ceiling is **seven usable palette bones per mesh and
three influences per vertex**. Eight link bytes and four weight slots exist in
the file, but the documentation warns about the eighth link and fourth influence.
A writer should reject excess influences or propose a separate, quantified
conversion. Silently keeping the strongest three weights would change deformation
and repeat an existing class of skinning errors. [Reference 2](#references)

The more serious issue is identity: the application **does not remap the embedded
bone names to the destination skeleton**. It uses the signed link indices and
substitutes bone zero for links greater than the destination's bone count. An
export could therefore appear to load while attaching vertices to the wrong
bones. Workshop should require an explicit destination bone map, retain the
destination skeleton fingerprint in an adjacent report, and reject missing,
ambiguous or out-of-range targets before writing. Matching bone count or display
labels alone is insufficient. Nonnegative signed 8-bit destination indices are
limited to 0 through 127; unused sentinels need their own validation.
[Reference 4](#references)

### What `.barm` provides

The inspected armature exporter writes `BactaTankArmature`, `PCGHG`, float32
version 0.4, a `Bones` section and a signed 32-bit bone count. Each record contains
a name, a signed 32-bit parent index and sixteen float32 matrix values. The
application exports its accumulated bone matrices, not just the local bind
matrix array. These records can identify a particular destination's order,
hierarchy and retained transforms. [Reference 6](#references)

The bundled Blender importer uses translation values to construct short Blender
bones; that import alone does not establish complete rest-pose orientation and
scale preservation. Workshop should retain all matrix values and validate their
meaning independently. A `.barm` reader can initially provide identity and
preflight diagnostics without pretending it has solved modern-to-classic
retargeting. `.barm` is a destination reference for this work, not proof that a
new skeleton can be installed through `.bmesh`. [References 6, 7](#references)

## Fidelity and ownership that the file does not solve

| Area | Consequence for an independent exporter |
| --- | --- |
| Coordinate systems | Position, normal, tangent and dynamic-buffer paths show different component/sign handling. Use an asymmetric reference mesh, axes and known unit distances to establish one explicit conversion. |
| Object and bind transforms | Preserve the original Workshop scene. Build a separate export representation and establish the destination rest space; do not assume baking the visible pose produces a valid skinned replacement. |
| Materials and textures | A `.bmesh` does not install a complete shader, material or texture tree. The existing destination material and its native vertex layout govern the replacement. Modern packed/layered materials need separate conversion. |
| Facial targets | Buffer order has no native target IDs. Preserve the destination's existing count and slot meaning, including blank slots. Do not map modern numbered targets to classic slots by array position. |
| Dynamic-buffer capacity | The target header has retained capacity constraints. Bacta warns about mismatched buffer counts and increased vertex counts for morph-bearing replacements. These should be hard preflight limits for the initial Workshop profile. |
| Whole characters | One `.bmesh` addresses one replacement mesh. Attachments, layers, skeletons, visibility, definitions, animations and new native header structures remain separate concerns. |

The UV and shape-buffer differences are evidence that a direct copy of Workshop
vertex/target values is unsafe. They do not establish a universal axis matrix
for every source game. Normal-map parity requires neutral, tilted and asymmetric
texture examples in both the destination viewer and the target game.
[References 2, 4, 5, 7](#references)

## Staged independent implementation plan

1. **Capture a reference contract.** Export one small static `.bmesh`, one skinned
   `.bmesh`, and the exact destination `.barm` from a known Bacta executable. Keep
   executable version, input hashes, target game/build and exported slot identity
   in ignored `local/`. Obtain a second independent example before enabling a
   profile publicly. Inspect an asymmetric shape to establish axes and winding.
2. **Implement independent validation first.** Validate exact tags, selected
   version, count bounds, file consumption, finite attributes, strip indices,
   target palette bounds and destination skeleton identity. Construct small
   independent fixtures and reject neighboring/unsupported layouts. A fixture
   generated and read only by our own code establishes internal consistency,
   not Bacta compatibility.
3. **Enable a static subset.** Export one mesh with positions, normals, UV1 and
   a compatible destination material. Split vertices deliberately for corner
   data, generate strips independently, decode the output, then publish the
   verified file and its report using Workshop's owned-staging safeguards.
   Include every transformation and omitted channel in the report.
4. **Add bounded skinning.** Require the target `.barm` fingerprint and a reviewed
   source-to-target map. Validate rest-space conversion, seven-bone palettes,
   three-influence rows and quantization. If partitioning into several meshes is
   needed, require enough existing destination slots and review the resulting
   assignments; partitioning does not create new native slots automatically.
5. **Validate the real destination.** Import the generated `.bmesh` with the
   stock consumer, replace a copied target mesh, save and reopen the copied GHG,
   then test it in the target game. Check deformation and material behavior,
   not just successful parsing. Repeat on a second sample for that profile.
6. **Investigate facial buffers separately.** Establish target slot identity,
   coordinate/basis conversion and existing header capacities before writing
   targets. Shape names, target order and blank slots are not interchangeable
   across generations.

A useful first implementation can be deliberately small: a structurally valid
static mesh replacement for one proven destination family. Broader cross-game
character conversion should remain gated by the destination evidence above.

## References

All source references are pinned to the reviewed commit. The repository was
inspected read-only; the bundled addon was read for field contracts without
executing or installing it.

1. [BactaTank Classic README: supported games, platform and model limitations](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/README.md).
2. [Mesh editing documentation: replacement workflow, palette/influence limits and shape capacity](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/docs/editing/meshes.md).
3. [Published format specification: incomplete 0.4 description](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/docs/technical/bacta-format-documentation.md).
4. [BactaTankBMesh consumer/producer: field types, array order, strip count and palette behavior](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/scripts/BactaTankBMesh/BactaTankBMesh.gml).
5. [BactaTankMesh replacement and dynamic-buffer checks](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/scripts/BactaTankMesh/BactaTankMesh.gml).
6. [BactaTankArmature serialization and accumulated matrices](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/scripts/BactaTankArmature/BactaTankArmature.gml).
7. [Bundled Blender addon 3.2.0](https://github.com/AlubJ/BactaTank-Classic/blob/5576652dfd08b83e985db4317329e7f310c59e46/datafiles/bactatank-blender-addon-v3.2.0.zip): `export_bactatank.py` and `import_bactatank.py` were inspected for version, string/scalar encoding, field order, skinning and coordinate conventions. No addon source or strip-generation implementation is included in this project.

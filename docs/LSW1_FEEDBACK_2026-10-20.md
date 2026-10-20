# Original LSW1 PC feedback pass

20 October 2026. HGP importer candidate **0.1.6**. AI assistance was used.
This covers the original 2005 PC release, not LSW2/TCS or console HGP layouts.

## Confirmed corrections

| Report / case | Change and evidence |
| --- | --- |
| Young Anakin has no hair | AUTO now adds the independent highest-detail hair family. Goggles and lower hair alternatives remain separate. |
| Bodyguard has no head | AUTO includes the independent `TT4_Head` component with the selected body. |
| Miscellaneous pods / empty body layers | AUTO checks for actual geometry before selecting a high-detail name and falls back to a nonempty body. Known common bits, hoses and energy-binder sets are included; broken pieces and cutscene alternatives stay separate. |
| Some droids overlap multiple bodies | Native joint coverage and observed detail names distinguish a complete default body from a default head/accessory set. A complete default body is no longer overlaid with its lower-detail replacement. |
| Panaka mouth / Imperial Officer shading | Zero-area strip triangles remain in the topology but cannot join Blender's smooth-normal fans. This restores adjacent authored custom normals that Blender otherwise corrupts. |
| Geonosian Fighter / Gungan Bongo canopy | The fourth packed vertex byte is preserved as authored opacity. Observed alpha-blended surfaces multiply it with texture alpha, or with 1 for untextured glass. Native RGB bytes are retained for inspection and do not recolor materials. |

AUTO remains an inspection assembly based on observed native layer conventions,
not a reconstruction of gameplay layer switching. Numeric layer choices 0–31
and `HGP.layer_meshes(index)` provide explicit inspection. Imported roots and
meshes retain selected layer indices/names.

Rigid normal transforms now use the inverse transpose. A synthetic nonuniform
attachment check establishes perpendicularity; the inspected original rest
frames are effectively orthonormal. Bone names, hierarchy, bind matrices,
weights, source positions, topology and UVs are not cosmetically rewritten.

## Other reports and remaining limits

| Report | Current finding |
| --- | --- |
| Wookie, Geonosian, Destroyer, Droid Starfighter, Darth Sidious fail | These original files import in the current reader. The observed header variants were enabled in 0.1.5; the old unsupported-header message is not reproduced. |
| Clonewalker lies down | The checked original stands upright with the current native bind assembly. No pose correction was introduced. |
| Clone / EP3 variants / Stormtrooper hands | Native geometry appears once, weights normalize and the Blender rest/evaluated mesh matches the source. No incorrect bone mapping was demonstrated; the reported visual difference remains open. |
| Clone ARC missing section | The supplied original imports its selected native geometry. The expected missing section is not independently identified; animation/visibility assembly is not reconstructed. |
| Clone EP3 Sand UVs | Imported loop UVs match the original `(u, 1-v)` within float32 rounding, exactly in the audited Sand sample. No guessed UV shift was applied. |
| Geonosian Fighter missing texture | Both declared embedded DDS images load and are connected. The other ten material slots are natively untextured; canopy opacity was the confirmed omission. |
| Dooku's two speeders / dark rear corner | The two source files are byte-identical. Forty-four cyan faces have authored normals opposing their winding; raycasts locate the dark wedge on those faces. The cyan material and UVs are correct, and diffuse-only rendering is uniform. The lighting discrepancy remains unresolved; no global flag or replacement normals were guessed. |
| Scarred Jedi Anakin lacks eyes/mouth | His default layer is empty, body layers have no separate facial overlay geometry, and the head image contains scars only. A declared shared/external facial assembly would need separate evidence; another character's face is not silently substituted. |
| Obi-Wan eyebrows | Original texture variants contain different eyebrow artwork. A universally correct replacement or offset is not established. |
| Bob / LightSabre / Walk / Kamino Android odd content | Original file names do not guarantee a complete character or weapon. Some contain partial/alternate model exports. Explicit layers remain available; arbitrary missing bodies or animation frames are not synthesized. |

Ten observed nonopaque parts use a separate additive-looking material mode 2.
They retain the existing approximation; this pass enables ordinary vertex
opacity only for the existing modes 1/10. Native refraction, additive effects,
facial morph playback and game animation/visibility still need work.

Further normal-fan isolation is accepted only when the actual failed-corner set
strictly decreases with no newly failed corners. The previous shading flags are
restored otherwise. Three extremely skinny pod triangles still yield problematic
Blender corner normals in the broader corpus. Long pod hose chains also expose Blender
bone-frame orthonormalization differences. These remain reported separately
from finite/normalized skin weights and successful import; no whole-game visual
perfection or edited-file gameplay is claimed.

## Validation

The original MSI's read-only file/directory tables identify **157 HGP inputs**,
including same-named files in different folders and three cabinet members whose
internal keys do not end in `.hgp`. The source files were copied into a new
ignored validation tree with their declared logical paths. Originals, games and
saves were not changed.

- All 157 imported in isolated Blender **5.2.2 LTS**, with packed textures,
  source face/vertex order, native weights, loop UVs and stored opacity checked.
- Native opacity census: 6,784 unique primitive parts across every native layer;
  84 nonopaque parts in 41 files, of which 74 use the enabled ordinary blend mode
  and ten use the separate mode 2.
- Eighteen original-file assembly checks cover source names, hierarchy, rest
  transforms, normalized weights, neutral deformation and custom normal
  directions, plus synthetic nonuniform normal-transform and fan-rollback regressions.
- Six header/layout tests, eleven layer-selection tests and two packed-alpha
  primitive tests exercise accepted inputs and malformed table/index cases.
- Actual Cycles renders compare the confirmed shading and opacity cases; a
  broader reported-asset gallery was rendered. These are Blender checks, not
  in-game or frame-matched fidelity verification.

Reproduce with user-owned inputs and new private output paths:

```text
python formats/hgp/lsw1/tests/check_header_layouts.py
python formats/hgp/lsw1/tests/check_layer_assembly.py
python formats/hgp/lsw1/tests/check_vertex_opacity.py
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_corpus_blender.py -- path/to/Chars path/to/new-report
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_assembly_blender.py -- path/to/flat-inputs path/to/new-assembly-report
```

Use a writable `TEMP`/`TMP` directory for tests in restricted Windows sessions.
Preserve edited scenes, install the new ZIP and reimport to receive the fixes;
existing saved Blender materials are not rewritten automatically.

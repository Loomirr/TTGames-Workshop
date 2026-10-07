# LEGO Batman 3: Beyond Gotham — PC

Use the [CU3 tools](../../formats/cu3/README.md) for structure inspection,
source skeletal animation, instance/record name editing and face target work.

The separate [character and animation addon](../../formats/character/README.md)
0.5.9 supports installed or unpacked character browsing, searchable native
clips and verified standalone facial BSA playback. It also restores native
skeleton selection for the supplied original LB3 shared body; see the
[0.5.9 evidence and remaining visual checks](../../docs/CHARACTER_ACCURACY_0.5.9.md).

In earlier validation, B66 Catwoman's default idle
matched source facial weights at three sample frames, and its composed preview
was inspected. This does not certify every LB3 face or material. See
[compatibility](../../formats/character/COMPATIBILITY.md).

The Batman-to-Green-Lantern menu cutscene replacement was tested by the user
in-game and replaced Batman successfully. This establishes that specific test,
not universal replacement compatibility. Multiple instances and inner record
names can refer to the same character; use the family replacement planner.

The private V5 sewer scene improves depth masks, facial targets, source normals
and several body proxies. Rendering, environments and some shots remain
approximate; it is not a fully faithful game replay.

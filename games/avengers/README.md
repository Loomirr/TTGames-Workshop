# LEGO Marvel's Avengers, PC

Use the separate [character and animation addon](../../formats/character/README.md)
with the **LEGO Marvel's Avengers** profile. Version 0.4.0 accepts installed
archives or unpacked asset folders, browses character definitions and searches
their declared animation sets. Supported ANI-D clips play on native skeletons.

Captain America, Thor, Hawkeye, Black Widow, Iron Man Mark 7 and Hulk AOU were
checked in Blender. A roster preflight found 821 of 882 definitions parser-ready;
this does not establish complete rendering or playback for every character.
See the [compatibility report](../../formats/character/COMPATIBILITY.md) for
the sample checks and remaining layout, material and attachment limits.

The loose-source exporter writes separate native files, including supported
existing vertex and face-target edits. Experimental active AN4 export preserves
unchanged clips and rejects edited poses that cannot be represented safely.
The tested Captain America idle contains recovered shear, so modified export
is currently rejected. Original games and archives remain untouched.

Avengers CU3 scene assembly, ANI-E playback and general topology, weight,
material and skeleton writing are not enabled by this character support.

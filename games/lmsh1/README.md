# LEGO Marvel Super Heroes — PC

- [CU3 cutscenes and names](../../formats/cu3/README.md).
- [AN4 skeletal animation](../../formats/an4/lmsh1/README.md).
- [Character and animation addon](../../formats/character/README.md), version
  0.5.9: installed/unpacked character browsing, native attachment loading,
  supported facial BSA playback and constrained loose-source export.

The current candidate restores native skeleton selection for the supplied
original LMSH1 shared body. See the [0.5.9 evidence and remaining visual checks](../../docs/CHARACTER_ACCURACY_0.5.9.md).

Earlier character checks restored Magneto's helmet and verified three idle
clips with facial and cape tracks. Older static accessory and texture-store
readers, plus corrected UMTL 174 texture alignment, improve other characters
too. That earlier roster preflight passed 374/467 definitions; this is parser coverage,
not a claim of exact rendering for all characters. See
[compatibility](../../formats/character/COMPATIBILITY.md) for remaining layouts
and material/face limits. The current CU3 0.1.18 download has separate scene/animation coverage.

The portable AN4 subset has narrower coverage than the private research
pipeline. Character-specific rigs, animation galleries, audio, suit work and
retargeting drafts stay local. See [the local guide](../../docs/LOCAL_WORKSPACE.md).

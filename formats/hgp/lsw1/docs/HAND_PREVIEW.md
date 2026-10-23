# Clone hands in the import preview

Version 0.1.10 corrects the visible wrist/hand overlap in six original rigs:
Clone, Clone EP3, EP3 Pilot, EP3 Swamp, EP3 Walker and Stormtrooper.

Leave **Correct Known Preview Poses** enabled when importing. It moves the hands
out to the observed preview positions using pose translations. Native mesh
vertices, weights, hierarchy and bind matrices stay unchanged. A mesh-only
import bakes the same display displacement into its new Blender mesh.

For source bind inspection or before applying a complete animation, disable
that option and re-import. On an existing rig, clearing the two hand bones'
location channels removes this correction. This is a display pose, not full
ANI playback or a native-file repair. The same option retains the earlier
Jango helmet-facing correction.

## Why the hands overlapped

The six rigs share the same complete native skeleton fingerprint. Their hand
local X translations are approximately +0.02333813 and -0.02333814. The original
Clone Idle and Walk ANI records have constant values +0.04633813 and -0.04633814
at the corresponding hand tracks. The original Sand Trooper also contains those
longer translations in its bind matrices. Its skeleton differs and receives no
extra offset. Qui-Gon has separate elbow-length bones providing the additional
length instead.

The display correction changes only the two hand translations by approximately
+0.023 and -0.023 in their native parent spaces. It is selected by a fingerprint
of every bone name, parent, local matrix and inverse bind matrix, not by a file
name or bone count. Edited or unknown skeletons do not match. This does not
establish arbitrary ANI track ownership or reproduce the rest of an idle clip.

## Checks

The original-file regression checks all 157 model skeletons: exactly the six
listed above match. For each affected model it compares corrected armature
vertices against independently calculated offsets from the original Idle ANI,
checks mesh-only parity, and verifies unchanged source coordinates, topology and
rest matrices. Changed names, hierarchy or bind matrices reject the profile.
Clone and Stormtrooper before/after renders were inspected; the gray wrist
intrusion into the hand opening is removed in the checked views. This is not a
frame-matched in-game animation validation.

```text
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_hand_preview_blender.py -- path/to/Chars path/to/Clone/Idle.ani path/to/new-report
```

AI assistance was used for the original-file analysis and implementation.

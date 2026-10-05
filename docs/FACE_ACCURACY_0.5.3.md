# Face and material checks: Character 0.5.3 / CU3 0.1.12

This pass addresses issue #1's follow-up examples from LMSH1, The Hobbit,
LEGO Batman 3 and LEGO Marvel's Avengers. LEGO Fortnite was excluded.

## What changed

- Avengers UMTL 232/234/235 records contain eighteen texture references. The
  reader previously consumed the first as an unknown prefix, shifting the
  remaining references. Captain America AOU consequently used a red texture
  for the eyes and lost the mask artwork. UV metadata is now read at the
  observed offsets with bounds checks; unverified shader flags remain opaque.
- Native alpha-tested printing now uses its texture alpha and decoded alpha
  reference, even when the material is not alpha blended. This removes opaque
  rectangles from face artwork such as Axel Alonso's beard.
- Live and composed previews distinguish solid beard/mask printing from masked
  mouth/eye detail. Solid printing is no longer cut away by facial depth masks.
  Root-linked body meshes also participate in compositor holdouts, removing
  differently shaded rectangular patches.
- Verified DXT5 packed surface normals now cover selected Hobbit/LB3 layouts.
  Material UV selectors resolve to the mesh's actual packed UV attributes,
  including the third pair, without renaming or rewriting source coordinates.
  This restores details such as Thrain's beard grooves.
- Preview controls appear above the animation list. Reimport and create a fresh
  preview to obtain the new material and draw-order metadata.

## Validation

Blender 5.2.2 imported these sixteen CDs from read-only installed archives:

| Game | Samples |
| --- | --- |
| LMSH1 | Axel Alonso, Whiplash, Wolverine, Magneto |
| The Hobbit | Thrain, Bilbo Baggins, Gandalf, Thorin |
| LB3 | Alfred, Batman, Superman, Sinestro |
| Avengers | Captain America AOU, Black Widow AOU, Iron Man Mark 43, Thor AOU |

All sixteen assembled without model-import issues and passed material UV
binding checks. Static shape targets began at zero. Preview copies preserved
source coordinates and topology; unchanged native vertex exports changed zero
bytes. Fourteen loaded a declared idle clip and evaluated finite preview
vertices at three frames. Iron Man and Thor had no resolved idle in this
catalog check, so their preview/export checks used the static pose instead.
Their animation coverage is not claimed; archive ambiguity and unresolved
animation companion notices remain separate from successful mesh assembly.

Composed renders of the four reporter-named characters were inspected.
Synthetic Blender checks cover printing/mask separation, root-linked solid
holdouts, preview isolation and unchanged Basis data. These are selected sample
checks, not an exhaustive roster audit or in-game validation.

The repository fixture/documentation/package suite passed. The CU3 import
operator also assembled the LB3 Batcave hub intro (six actor instances, four
cameras) and LMSH1 Stark Tower intro (seven actor instances, thirteen cameras)
with packed textures and no import-report issues. This checks assembly, not
complete scene fidelity. Both addons loaded from the installed Blender profile;
fresh Axel Alonso and Captain America live previews were rendered there.

The sampled skinned body LOD tables already selected their highest-detail
parts. For example, Thrain's body head uses 404 triangles rather than its
356/224/72-triangle alternatives. Missing normal-map detail can make these
meshes look smoother. No global subdivision, welding or normal replacement
was added.

## Remaining limits

The native shader is not fully reproduced. Preview depth offsets follow draw
order as an approximation; live clipping can still have jagged edges and
view-dependent differences. Raw imported face layers are not a fidelity check:
use the character preview in camera view, or the composed preview for closer
inspection. Native expression timing and material remaps remain separate work.

Other packed normal encodings, including the observed Avengers format-3/DXT1
body layout, are not enabled by guessing. Storm's older UMTL 172 hair remains
unsupported. The X-axis report still needs an asymmetric in-game comparison.
TFA/DCSV inspection profiles are not promoted to full character importers by
these changes. Existing scenes and installed game files are not rewritten.

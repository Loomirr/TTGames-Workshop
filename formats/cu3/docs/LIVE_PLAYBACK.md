# Live Blender playback

Addon 0.1.6 adds **N → TT Cutscene → Cutscene playback → Make live camera
preview copy**. It makes a full scene copy, keeps the original compositor scene,
and configures EEVEE for viewing. This operates on an already assembled scene;
it does not automatically extract missing meshes, materials or cameras.

Press **Space** in the 3D View to play/pause. **NumPad 0** restores the source
camera. Material Preview uses the scene lights and world; overlays are hidden
in the viewing copy. Frame dropping is enabled so a slow frame does not slow
the timeline indefinitely. This cannot guarantee a particular viewport FPS.

Verified `tt_colour_write_mask=0` facial meshes are retained as evaluated
dependencies. Geometry Nodes raycast towards the source camera after morphs
and skinning, then remove occluded subdivided detail polygons. Camera switches
follow scene camera markers, including after saving and reopening. Static
source faces with no masks still use their existing materials normally.

This is a **camera-dependent approximation**. Mask edges can be less smooth
than a composed render; free orbit is useful for inspecting meshes, but the
mask calculation still uses the source camera. Perspective and orthographic
cameras are supported. Unknown camera types fail and the partial viewing copy
is removed. Changing marker bindings after setup requires a fresh preview copy.

The viewing modifiers do not change stored vertex order, Basis, target
coordinates, bones or native export bindings. Masks keep their original
animation. Hidden helper collections affect display, rather than stripping
out the source data. Do not apply those modifiers when exporting native faces.

Research V7 scene copies include live stages and face controls. The complete
composed V6 movie is retained as **00 - Watch complete composed cutscene** for
smooth viewing without rendering again. It is a fixed cache: edits appear in
the live scene, but require rebuilding the movie to update cached playback.
Marvel's live Part A and Part B retain separate source timelines. The LB3 live
timeline samples the existing edit's source-frame ranges; the original source
stage is retained separately.

Select an inspection armature to edit **Target** and **Strength** through the
panel or Object Properties → Custom Properties. Target IDs are native numeric
IDs, not invented expression names. The native face editor's verified export
collection remains separate from the original scene.

Manual synthetic regression:

```sh
blender --background --factory-startup --python-exit-code 1 --python scripts/check_live_preview_blender.py
```

This covers copied meshes/keys, animated clipping, camera-cut driver remapping,
unchanged original geometry and rollback for unsupported cameras. Actual
viewport capture and original-file scene checks are separate private tests.

In 0.1.12, solid beard/mask printing stays outside camera-ray facial clipping.
Verified packed normal maps and native alpha cutouts improve selected source
materials. Create a fresh preview after reimporting; existing saved previews
are not rewritten. The draw-order depth offsets remain approximations.

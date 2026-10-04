"""Manually exercise the actual addon operator with user-supplied source assets."""
import sys
from pathlib import Path
import bpy

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / 'Addon'))
import io_scene_lego_cu3

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if len(args) != 3:
    raise SystemExit('Usage: blender --background --factory-startup --python scripts/check_blender.py -- scene.CU3 source.GHG ExactActorName')
cutscene, skeleton, actor = args
io_scene_lego_cu3.register()
try:
    result = bpy.ops.import_scene.lego_cu3(filepath=str(Path(cutscene).resolve()), mode='SKELETONS',
        skeleton_path=str(Path(skeleton).resolve()), actor_filter=actor)
    assert result == {'FINISHED'}
    rigs = [obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE']
    assert rigs and all(rig.animation_data and rig.animation_data.action for rig in rigs)
    for frame in (bpy.context.scene.frame_start, bpy.context.scene.frame_end):
        bpy.context.scene.frame_set(frame)
        for rig in rigs:
            for bone in rig.pose.bones:
                import math
                assert all(math.isfinite(value) for row in bone.matrix for value in row)
    print(f'BLENDER_CHECK_PASSED: {len(rigs)} source rig(s), Blender {bpy.app.version_string}', flush=True)
finally:
    io_scene_lego_cu3.unregister()

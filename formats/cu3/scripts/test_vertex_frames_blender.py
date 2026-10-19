"""Blender regression: native frame playback and linear animation storage.

blender -b --factory-startup --python-exit-code 1 --python this.py
"""
from pathlib import Path
import sys
import types
import bpy
from mathutils import Matrix

package = types.ModuleType('frame_test_core')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from frame_test_core.native_model_blender import add_vertex_frames

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('Frame regression')
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
obj = bpy.data.objects.new('Frame regression', mesh)
bpy.context.scene.collection.objects.link(obj)
frames = [[(0, 0, i), (1, 0, i), (0, 1, i)] for i in range(80)]
add_vertex_frames(obj, frames, Matrix.Identity(4))
for frame in (0, *range(1, 81), 90):
    bpy.context.scene.frame_set(frame)
    expected = min(79, max(0, frame - 1))
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    assert all(abs(v.co.z - expected) < 1e-5 for v in evaluated.data.vertices), frame
    assert sum(k.value for k in mesh.shape_keys.key_blocks[1:]) == 1, frame
action = mesh.shape_keys.animation_data.action
bag = action.layers[0].strips[0].channelbag(mesh.shape_keys.animation_data.action_slot)
assert sum(len(c.keyframe_points) for c in bag.fcurves) <= 3 * len(frames)
print('VERTEX_FRAME_PLAYBACK_CHECK_PASSED', len(frames))

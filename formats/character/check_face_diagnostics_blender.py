"""Asset-free checks for facial playback status and unchanged refusal behavior.

blender --background --factory-startup --python-exit-code 1 --python
formats/character/check_face_diagnostics_blender.py -- extracted-addon-folder
"""
from pathlib import Path
import sys
from types import SimpleNamespace

import bpy

sys.path.insert(0, str(Path(sys.argv[sys.argv.index('--')+1]).resolve()))
import io_scene_tt_character as addon
addon.register()
from io_scene_tt_character.importer import facial_actions

child = bpy.data.objects.new('Face', bpy.data.armatures.new('Face'))
bpy.context.scene.collection.objects.link(child)
mesh = bpy.data.meshes.new('Face surface')
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 0, 1)], [], [(0, 1, 2)])
obj = bpy.data.objects.new('Face surface', mesh)
bpy.context.scene.collection.objects.link(obj)
obj.parent = child
obj.shape_key_add(name='Basis')
key = obj.shape_key_add(name='TT_Target_017')
key.data[0].co.x += 1

def values(frame):
    sample = [0.0] * 53
    sample[17] = frame / 2
    return [sample]

morph = SimpleNamespace(frames=3, curves=53, sample=values)
source = SimpleNamespace(morph_animation=lambda actor: morph)
actor = {'records': [{}]}
tracks = facial_actions(source, actor, child, 3)
assert tracks[0]['facial_status'] == 'animated'
for frame in range(1, 4):
    bpy.context.scene.frame_set(frame)
    assert abs(key.value - (frame-1)/2) < 1e-6

morph.sample = lambda frame: values(1)
tracks = facial_actions(source, actor, child, 3)
assert tracks[0]['facial_status'] == 'static'
for frame in range(1, 4):
    bpy.context.scene.frame_set(frame)
    assert abs(key.value - 0.5) < 1e-6

before = set(bpy.data.actions)
old_action = obj.data.shape_keys.animation_data.action
notices = []
assert facial_actions(SimpleNamespace(morph_animation=lambda actor: None), actor,
                      child, 3, diagnostics=notices) == []
assert notices[0]['status'] == 'absent'
assert set(bpy.data.actions) == before
assert obj.data.shape_keys.animation_data.action == old_action

# Adding a status message must not make previously rejected durations valid.
morph.frames = 8
try:
    facial_actions(source, actor, child, 3)
    raise AssertionError('Mismatched facial duration was accepted')
except ValueError:
    pass
assert set(bpy.data.actions) == before
assert obj.data.shape_keys.animation_data.action == old_action
print('FACIAL_DIAGNOSTICS_CHECK_PASSED: moving, constant, absent, refusal preservation')

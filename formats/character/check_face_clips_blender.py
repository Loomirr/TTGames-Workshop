"""Asset-free Blender check for facial clip binding, switching and rollback.

Run after building the addon:
blender --background --factory-startup --python-exit-code 1 --python
formats/character/check_face_clips_blender.py -- output/facial-check
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZipFile
import bpy

root = Path(__file__).resolve().parents[2]
output = Path(sys.argv[sys.argv.index('--')+1]).resolve()
output.mkdir(parents=True, exist_ok=False)
packages = list((root/'builds/blender').glob('TT_Character_Importer_*.zip'))
if len(packages) != 1:raise ValueError('Build one current character addon first')
with ZipFile(packages[0]) as archive:archive.extractall(output/'addon')
sys.path.insert(0, str(output/'addon'))
import io_scene_tt_character as addon
addon.register()
from io_scene_tt_character import importer
from io_scene_tt_character.animation_export import action_fingerprint, check_linked_actions
from io_scene_tt_character.preview import create_preview

rig = bpy.data.objects.new('Body', bpy.data.armatures.new('Body'))
child = bpy.data.objects.new('Face', bpy.data.armatures.new('Face'))
bpy.context.scene.collection.objects.link(rig)
bpy.context.scene.collection.objects.link(child)
child.parent = rig
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
bone=rig.data.edit_bones.new('Root');bone.head=(0,0,0);bone.tail=(0,0,1)
bpy.ops.object.mode_set(mode='OBJECT')
faces = []
for i in range(2):
    mesh = bpy.data.meshes.new('Surface');mesh.from_pydata([(0,0,0),(1,0,0),(0,0,1)],[],[(0,1,2)])
    obj = bpy.data.objects.new('Surface '+str(i),mesh)
    bpy.context.scene.collection.objects.link(obj);obj.parent=child
    obj.shape_key_add(name='Basis');obj.shape_key_add(name='TT_Target_017').value=0
    faces.append(obj)

def sample(frame):
    values=[0.0]*53;values[17]=.7
    return [values]

morph = SimpleNamespace(frames=3, curves=53, sample=sample)
source = SimpleNamespace(morph_animation=lambda actor:morph)
actor = {'records':[{}]}
tracks = importer.facial_actions(source,actor,child,2)
assert len(tracks)==2
body = bpy.data.actions.new('Body clip')
slot = body.slots.new('OBJECT',rig.name)
bag = body.layers.new('Body').strips.new(type='KEYFRAME').channelbag(slot,ensure=True)
curve = bag.fcurves.new('location',index=0)
curve.keyframe_points.add(2);curve.keyframe_points.foreach_set('co',[1,0,2,0])
body['tt_facial_actions']=json.dumps(tracks)
clip=rig.tt_clips.add();clip.action=body;clip.slot=slot.identifier;clip.frames=2;clip.fps=30
rig.tt_clip_index=0;bpy.context.scene.frame_set(2)
assert all(abs(o.data.shape_keys.key_blocks['TT_Target_017'].value-.7)<1e-6 for o in faces)
check_linked_actions(body)

# An unsupported duration fails before any actions or bindings are changed.
morph.frames=5
before = set(bpy.data.actions)
try:importer.facial_actions(source,actor,child,2);raise AssertionError('Unsupported duration accepted')
except ValueError:pass
assert set(bpy.data.actions)==before
morph.frames=3

# A failure after the first surface must restore both earlier bindings/values.
previous=[o.data.shape_keys.animation_data.action for o in faces]
original=importer.animate_shape_keys
calls=0
def fail_second(*args):
    global calls
    calls+=1
    if calls==2:raise RuntimeError('Injected late facial failure')
    return original(*args)
importer.animate_shape_keys=fail_second
try:
    try:importer.facial_actions(source,actor,child,2);raise AssertionError('Failure was swallowed')
    except RuntimeError:pass
finally:importer.animate_shape_keys=original
assert set(bpy.data.actions)==before
assert [o.data.shape_keys.animation_data.action for o in faces]==previous
assert all(abs(o.data.shape_keys.key_blocks['TT_Target_017'].value-.7)<1e-6 for o in faces)

blank = rig.tt_clips.add();blank.action=body.copy();blank.action['tt_facial_actions']='[]'
blank.slot=slot.identifier;blank.frames=2;blank.fps=30
rig.tt_clip_index=1
assert all(o.data.shape_keys.animation_data.action is None for o in faces)
assert all(o.data.shape_keys.key_blocks['TT_Target_017'].value==0 for o in faces)
rig.tt_clip_index=0
scene = create_preview(bpy.context,rig)
copied=[o for o in scene.objects if o.get('tt_preview_source') in {f.name for f in faces}]
assert len(copied)==2 and all(o.data.shape_keys.animation_data.action in previous for o in copied)

# Native writers must reject edited linked actions, including duration edits.
previous[0].use_frame_range=True;previous[0].frame_end=4
try:check_linked_actions(body);raise AssertionError('Edited linked action accepted')
except ValueError:pass
(output/'results.json').write_text(json.dumps(dict(padded_end_sample=True,rollback=True,
    clip_switch=True,preview_links=True,edited_companion_rejected=True),indent=2))
print('FACIAL_CLIP_BINDING_CHECK_PASSED')

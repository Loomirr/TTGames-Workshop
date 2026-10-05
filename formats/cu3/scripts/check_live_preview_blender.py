"""Blender-only camera-cut/morph/rollback check with synthetic geometry."""
import bpy,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Addon'))
import io_scene_lego_cu3 as addon
addon.register();bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=2);detail=bpy.context.object
detail['source_model']='FACE_FIXTURE';detail['tt_colour_write_mask']=15
detail.shape_key_add(name='Basis');target=detail.shape_key_add(name='TT_Target_003');target.value=0
for point in target.data:point.co.x+=2
original=[tuple(v.co) for v in detail.data.vertices]
bpy.ops.mesh.primitive_plane_add(size=1,location=(0,0,0.1));mask=bpy.context.object
mask['source_model']='FACE_FIXTURE';mask['tt_colour_write_mask']=0
original_mask=[tuple(v.co) for v in mask.data.vertices]
bpy.ops.mesh.primitive_plane_add(size=1,location=(0,0,.2));printing=bpy.context.object
printing.name='Native cutout printing';printing['source_model']='FACE_FIXTURE';printing['tt_colour_write_mask']=15
printing['tt_native_alpha_test']=5;printing['tt_native_draw_order']=0;printing['tt_native_cast_shadows']=False
excluded=bpy.data.collections.new('Excluded variant fixture');scene.collection.children.link(excluded)
bpy.ops.mesh.primitive_cube_add(location=(10,0,0));variant=bpy.context.object
for collection in list(variant.users_collection):collection.objects.unlink(variant)
excluded.objects.link(variant);bpy.context.view_layer.layer_collection.children[excluded.name].exclude=True
bpy.ops.object.camera_add(location=(0,0,3));first=bpy.context.object;scene.camera=first
first.rotation_euler=(0,0,0);first.data.type='ORTHO';first.data.ortho_scale=3
bpy.ops.object.camera_add(location=(3,0,3));second=bpy.context.object;second.data.type='ORTHO'
for frame,camera in [(1,first),(5,second)]:scene.timeline_markers.new(str(frame),frame=frame).camera=camera
assert bpy.ops.scene.tt_live_preview(detail_level=2)=={'FINISHED'}
live=bpy.context.scene
assert live!=scene and live.get('tt_live_preview')
copy=next(o for o in live.objects if o.type=='MESH' and o.get('tt_colour_write_mask')==15 and o.get('tt_native_alpha_test')!=5)
copyprint=next(o for o in live.objects if o.get('tt_native_alpha_test')==5)
assert not copyprint.modifiers.get('TT live facial clipping')
assert copyprint.modifiers.get('TT facial depth bias') and not printing.modifiers
copymask=next(o for o in live.objects if o.type=='MESH' and o.get('tt_colour_write_mask')==0)
assert copy.data!=detail.data and copy.data.shape_keys!=detail.data.shape_keys
assert [tuple(v.co) for v in detail.data.vertices]==original
assert not detail.modifiers and copy.modifiers.get('TT live facial clipping')
assert not mask.modifiers and copymask.modifiers.get('TT facial depth bias')
assert not copy.modifiers.get('TT facial depth bias')
assert [tuple(v.co) for v in mask.data.vertices]==original_mask
assert [tuple(v.co) for v in copymask.data.vertices]==original_mask
assert copymask['tt_preview_depth_bias']==.001
assert copymask.hide_get() and copymask.users_collection[0].hide_render
assert next(c for c in live.view_layers[0].layer_collection.children if c.name.startswith('Excluded variant fixture')).exclude
def faces(frame):
 live.frame_set(frame);bpy.context.view_layer.update()
 return len(copy.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
neutral=faces(1);assert 0<neutral<16,neutral
nodes=copy.modifiers[-1].node_group
assert all(n.inputs['Object'].default_value in live.objects.values() for n in nodes.nodes if n.type=='OBJECT_INFO')
switch=next(n for n in nodes.nodes if n.type=='SWITCH')
faces(5);assert switch.inputs['Switch'].default_value is True
live.frame_set(1);copy.data.shape_keys.key_blocks['TT_Target_003'].value=1
assert faces(1)>neutral,'Mask evaluation must follow target deformation'
assert detail.data.shape_keys.key_blocks['TT_Target_003'].value==0
# An unsupported camera must remove all partially created data.
bpy.context.window.scene=scene;scene.camera.data.type='PANO'
for marker in list(scene.timeline_markers):scene.timeline_markers.remove(marker)
stores=('scenes','objects','node_groups','actions','shape_keys')
before=tuple(len(getattr(bpy.data,name)) for name in stores)
try:
    bpy.ops.scene.tt_live_preview()
except RuntimeError as error:
    assert 'perspective or orthographic' in str(error)
else:raise AssertionError('Unsupported camera was accepted')
assert bpy.context.scene==scene and before==tuple(len(getattr(bpy.data,name)) for name in stores)
addon.unregister()
print('LIVE_PREVIEW_CHECK_PASSED: independent copy, animated morph clipping, camera cuts, preserved Basis, unsupported-camera rollback')

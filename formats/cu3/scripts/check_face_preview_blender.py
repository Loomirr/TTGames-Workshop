"""Blender regression check for static weights and depth-mask layer setup."""
import bpy,sys
from pathlib import Path
from mathutils import Matrix
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'Addon'))
import io_scene_lego_cu3 as addon
from io_scene_lego_cu3.morph import add_shape_keys
addon.register()
bpy.ops.mesh.primitive_cube_add();face=bpy.context.object;face.name='Native face fixture';face['source_model']='FACE_FIXTURE';face['tt_colour_write_mask']=15
original=[v.co.copy() for v in face.data.vertices]
targets=dict(vertex_count=len(original),targets=[dict(id=3,offsets=[[.25,0,0]]*len(original)),dict(id=7,offsets=[[0,.125,0]]*len(original))])
add_shape_keys(face,targets,Matrix.Identity(4))
assert all(k.value==0 for k in face.data.shape_keys.key_blocks if k.name.startswith('TT_Target_'))
assert max((v.co-w).length for v,w in zip(face.data.shape_keys.key_blocks['Basis'].data,original))<1e-7
bpy.context.view_layer.update();evaluated=face.evaluated_get(bpy.context.evaluated_depsgraph_get())
assert max((v.co-w).length for v,w in zip(evaluated.data.vertices,original))<1e-7
face.data.shape_keys.key_blocks['TT_Target_003'].value=.5;bpy.context.view_layer.update();evaluated=face.evaluated_get(bpy.context.evaluated_depsgraph_get())
assert max(abs((v.co-w).x-.125) for v,w in zip(evaluated.data.vertices,original))<1e-7
bpy.ops.mesh.primitive_plane_add();mask=bpy.context.object;mask['source_model']='FACE_FIXTURE';mask['tt_colour_write_mask']=0
before=[v.co.copy() for v in mask.data.vertices]
assert bpy.ops.scene.tt_facial_preview()=={'FINISHED'}
assert bpy.context.scene.get('tt_face_preview')
assert len(bpy.context.scene.view_layers)==2
assert mask.modifiers.get('TT facial depth bias')
assert max((v.co-w).length for v,w in zip(mask.data.vertices,before))==0
assert mask.visible_shadow is False
addon.unregister()
print('FACE_PREVIEW_REGRESSION_PASSED: zero static defaults, weighted target geometry, registration, depth layers, source coordinates unchanged',flush=True)

"""Preview isolation, authored-normal preservation and reversible view controls."""
import sys, argparse
from pathlib import Path
import bpy
from mathutils import Vector

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--addon-directory',type=Path,required=True,help='Directory containing the extracted io_scene_tt_character addon package')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
sys.path.insert(0,str(args.addon_directory))
import io_scene_tt_character as addon
addon.register();bpy.ops.wm.read_factory_settings(use_empty=True)
from io_scene_tt_character._core.face_preview import depth_bias_modifier
from io_scene_tt_character._core.face_live import clip_details
from io_scene_tt_character.preview import create_preview
from io_scene_tt_character.preview_settings import apply_settings

scene=bpy.context.scene
assert scene.tt_mesh_detail=='HIGHEST' and scene.tt_face_detail==4
assert not addon.TTCHAR_OT_apply_preview.poll(bpy.context)
rig=bpy.data.objects.new('Native fixture root',None);scene.collection.objects.link(rig)
bpy.ops.mesh.primitive_plane_add(size=2);detail=bpy.context.object;detail.parent=rig
detail['source_model']='FACE_FIXTURE';detail['tt_colour_write_mask']=15
for p in detail.data.polygons:p.use_smooth=True
expected=Vector((.6,0,.8));detail.data.normals_split_custom_set_from_vertices([expected]*4)
original=[tuple(v.co) for v in detail.data.vertices]
mat=bpy.data.materials.new('Source fixture');mat.use_nodes=True;detail.data.materials.append(mat)
p=mat.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(.2,.4,.8,1)
normal=mat.node_tree.nodes.new('ShaderNodeNormalMap');mat.node_tree.links.new(normal.outputs[0],p.inputs['Normal'])
bpy.ops.mesh.primitive_plane_add(size=.7,location=(0,0,.1));mask=bpy.context.object;mask.parent=rig
mask['source_model']='FACE_FIXTURE';mask['tt_colour_write_mask']=0;mask.hide_render=True
# Unmasked fixture first proves that subdivision cannot replace tilted authored
# normals with the flat plane's geometric normal, then clipping checks topology.
bpy.ops.mesh.primitive_plane_add(size=.1,location=(5,0,.1));far=bpy.context.object
bpy.ops.object.camera_add(location=(0,0,3));scene.camera=bpy.context.object
depth_bias_modifier(detail,.001,camera_only=False)
clip_details(detail,[far],scene,level=4)
bpy.context.view_layer.update()
evaluated=detail.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
assert len(evaluated.vertices)>len(detail.data.vertices)
assert max((n.vector-expected).length for n in evaluated.corner_normals)<.001
assert [tuple(v.co) for v in detail.data.vertices]==original
# create_preview removes old helpers and builds fresh camera-dependent helpers.
view=create_preview(bpy.context,rig)
copied=next(o for o in view.objects if o.get('tt_preview_source')==detail.name)
viewmat=copied.data.materials[0]
assert viewmat!=mat and viewmat.node_tree!=mat.node_tree
assert addon.TTCHAR_OT_apply_preview.poll(bpy.context)
view.tt_preview_normals=False;view.tt_preview_shading='ALBEDO'
apply_settings(bpy.context,view)
vp=next(n for n in viewmat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
assert not vp.inputs['Normal'].is_linked
assert next(n for n in viewmat.node_tree.nodes if n.type=='OUTPUT_MATERIAL').inputs['Surface'].links[0].from_node.name=='TT preview alpha'
view.tt_preview_normals=True;view.tt_preview_shading='LIT';view.tt_face_detail=2
view.tt_preview_normal_strength=.35
apply_settings(bpy.context,view)
vn=next(n for n in viewmat.node_tree.nodes if n.type=='NORMAL_MAP')
assert abs(vn.inputs['Strength'].default_value-.35)<1e-6
assert normal.inputs['Strength'].default_value==1
view.tt_preview_normal_strength=1
apply_settings(bpy.context,view)
assert vn.inputs['Strength'].default_value==1
assert vp.inputs['Normal'].is_linked
assert next(n for n in viewmat.node_tree.nodes if n.type=='OUTPUT_MATERIAL').inputs['Surface'].links[0].from_node==vp
modifier=copied.modifiers.get('TT live facial clipping')
assert next(n for n in modifier.node_group.nodes if n.bl_idname=='GeometryNodeSubdivideMesh').inputs['Level'].default_value==2
assert [tuple(v.co) for v in detail.data.vertices]==original
assert p.inputs['Normal'].is_linked and mat.node_tree.nodes.get('TT preview albedo') is None
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        assert area.spaces.active.shading.use_scene_lights and area.spaces.active.shading.use_scene_world
# The captured values must be the evaluated skin normals, not rest-pose data.
bpy.ops.object.armature_add();arm=bpy.context.object
arm.pose.bones[0].rotation_mode='XYZ';arm.pose.bones[0].rotation_euler.y=.4
bpy.ops.mesh.primitive_plane_add(size=2);skinned=bpy.context.object
for polygon in skinned.data.polygons:polygon.use_smooth=True
skinned.data.normals_split_custom_set_from_vertices([expected]*4)
group=skinned.vertex_groups.new(name=arm.data.bones[0].name);group.add(list(range(4)),1,'REPLACE')
skinned.modifiers.new('Native skin fixture','ARMATURE').object=arm
bpy.context.view_layer.update();baseline=[n.vector.copy() for n in skinned.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.corner_normals]
assert (baseline[0]-expected).length>.1
clip_details(skinned,[far],view,level=3)
bpy.context.view_layer.update();result=skinned.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
assert max((n.vector-baseline[0]).length for n in result.corner_normals)<.001
addon.unregister()
assert not hasattr(bpy.types.Scene,'tt_face_detail')
print('PREVIEW_SETTINGS_PASSED: normals retained, source isolation, reversible shading, LOD defaults and scene lighting')

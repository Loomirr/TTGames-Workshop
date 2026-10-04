"""Facial render setup for imported meshes carrying native material metadata."""
import bpy
from .face_preview import depth_mask_material,depth_bias_modifier,setup_layers

def face_objects(scene):
    return [o for o in scene.objects if o.type=='MESH' and
            (o.get('source_model','').startswith('FACE_') or o.get('source_model')=='SpiderFace')]

class SCENE_OT_tt_facial_preview(bpy.types.Operator):
    bl_idname='scene.tt_facial_preview'
    bl_label='Prepare native facial render layers'
    bl_options={'REGISTER','UNDO'}

    @classmethod
    def poll(cls,context):
        return bool(face_objects(context.scene)) and not context.scene.get('tt_face_preview')

    def execute(self,context):
        scene=context.scene;objects=face_objects(scene)
        masks=[o for o in objects if o.get('tt_colour_write_mask')==0]
        if not masks:
            self.report({'ERROR'},'No verified native colourWriteMask=0 metadata. Decode material records first; material names alone are insufficient.')
            return {'CANCELLED'}
        if getattr(scene,'compositing_node_group',None) or getattr(scene,'node_tree',None):
            self.report({'ERROR'},'This scene already has a compositor. Use a scene copy with an empty compositor.')
            return {'CANCELLED'}
        if any(any(o.name in other.objects for other in bpy.data.scenes if other!=scene) for o in objects):
            self.report({'ERROR'},'Face objects are shared across scenes. Make a full scene copy before preparing render layers.')
            return {'CANCELLED'}
        collection=bpy.data.collections.new('TT native facial surfaces');scene.collection.children.link(collection)
        for obj in objects:
            # The validation above requires scene-local objects.
            for owner in list(obj.users_collection):owner.objects.unlink(obj)
            collection.objects.link(obj)
            if obj in masks:
                obj.data=obj.data.copy();obj.data.materials.clear();obj.data.materials.append(depth_mask_material())
                for polygon in obj.data.polygons:polygon.material_index=0
                depth_bias_modifier(obj)
        context.view_layer.update();setup_layers(scene,collection)
        scene.render.engine='CYCLES'
        self.report({'INFO'},'Facial passes prepared. Render with F12; Solid/Workbench cannot display depth-only masks.')
        return {'FINISHED'}

class VIEW3D_PT_tt_facial_preview(bpy.types.Panel):
    bl_label='Native facial preview'
    bl_idname='VIEW3D_PT_tt_facial_preview'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='TT Cutscene'
    @classmethod
    def poll(cls,context):return bool(face_objects(context.scene))
    def draw(self,context):
        if context.scene.get('tt_face_preview'):
            self.layout.label(text='Native depth masks configured.',icon='CHECKMARK')
            self.layout.label(text='F12: composed face. Live copy: playback panel.')
        else:self.layout.operator(SCENE_OT_tt_facial_preview.bl_idname)

CLASSES=(SCENE_OT_tt_facial_preview,VIEW3D_PT_tt_facial_preview)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)

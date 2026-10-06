"""Facial render setup for imported meshes carrying native material metadata."""
import bpy
from .face_preview import face_objects,prepare_render
from .geometry_normals import normal_preservation_status

class SCENE_OT_tt_facial_preview(bpy.types.Operator):
    bl_idname='scene.tt_facial_preview'
    bl_label='Prepare native facial render layers'
    bl_options={'REGISTER','UNDO'}

    @classmethod
    def poll(cls,context):
        return bool(face_objects(context.scene)) and not context.scene.get('tt_face_preview')

    def execute(self,context):
        try:prepare_render(context.scene)
        except ValueError as error:
            self.report({'ERROR'},str(error));return {'CANCELLED'}
        self.report({'INFO'},'Facial passes prepared. Render with F12; Solid/Workbench cannot display depth-only masks.')
        return {'FINISHED'}

class VIEW3D_PT_tt_facial_preview(bpy.types.Panel):
    bl_label='Native facial preview'
    bl_idname='VIEW3D_PT_tt_facial_preview'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='TT Cutscene'
    @classmethod
    def poll(cls,context):return bool(face_objects(context.scene))
    def draw(self,context):
        if not normal_preservation_status()['supported']:
            self.layout.label(text='Facial preview normals are approximate.', icon='ERROR')
            self.layout.label(text='This Blender lacks normal preservation.')
        if context.scene.get('tt_face_preview'):
            self.layout.label(text='Native depth masks configured.',icon='CHECKMARK')
            self.layout.label(text='F12: composed face. Live copy: playback panel.')
        else:self.layout.operator(SCENE_OT_tt_facial_preview.bl_idname)

CLASSES=(SCENE_OT_tt_facial_preview,VIEW3D_PT_tt_facial_preview)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)

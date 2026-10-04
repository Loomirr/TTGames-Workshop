"""Quick access to live camera playback and existing composed movie caches."""
import bpy
from bpy.props import StringProperty, IntProperty
from .face_live import prepare_live, copy_layer_flags


def show_scene(context, scene):
    context.window.scene = scene
    area = context.area
    if area is None:return
    if scene.get('tt_preview_kind') == 'CACHE':
        area.type = 'SEQUENCE_EDITOR'; area.spaces.active.view_type = 'PREVIEW'
    else:
        area.type = 'VIEW_3D'
        space = area.spaces.active; space.region_3d.view_perspective = 'CAMERA'
        space.shading.type = 'MATERIAL'; space.shading.use_scene_lights = True; space.shading.use_scene_world = True
        space.overlay.show_overlays = False; space.show_region_ui = True


class SCENE_OT_tt_live_preview(bpy.types.Operator):
    bl_idname = 'scene.tt_live_preview'
    bl_label = 'Make live camera preview copy'
    bl_options = {'REGISTER', 'UNDO'}
    detail_level: IntProperty(name='Mask edge detail', default=3, min=0, max=4)

    @classmethod
    def poll(cls, context):return bool(context.scene.camera) and not context.scene.get('tt_live_preview')

    def execute(self, context):
        original = context.scene
        # All modifications happen on a full copy, including geometry modifiers.
        stores = ('scenes', 'objects', 'collections', 'meshes', 'armatures', 'cameras', 'lights', 'node_groups', 'materials', 'worlds', 'actions', 'shape_keys')
        before = {name: set(getattr(bpy.data, name)) for name in stores}
        try:
            bpy.ops.scene.new(type='FULL_COPY')
            scene = context.scene; scene.name = original.name + ' / live preview'
            copy_layer_flags(original.view_layers[0].layer_collection, scene.view_layers[0].layer_collection)
            report = prepare_live(scene, self.detail_level)
            show_scene(context, scene)
            self.report({'INFO'}, f'Live copy: {report["detail_parts"]} masked detail parts. Space plays; NumPad 0 restores source camera view.')
            return {'FINISHED'}
        except (ValueError, RuntimeError, KeyError, TypeError) as error:
            context.window.scene = original
            created = {item for name in stores for item in getattr(bpy.data, name) if item not in before[name]}
            bpy.data.batch_remove(ids=created)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class SCENE_OT_tt_show_preview(bpy.types.Operator):
    bl_idname = 'scene.tt_show_preview'; bl_label = 'Open viewing scene'
    scene_name: StringProperty()

    def execute(self, context):
        scene = bpy.data.scenes.get(self.scene_name)
        if scene is None:
            self.report({'ERROR'}, 'Viewing scene no longer exists'); return {'CANCELLED'}
        show_scene(context, scene)
        return {'FINISHED'}


class VIEW3D_PT_tt_playback(bpy.types.Panel):
    bl_label = 'Cutscene playback'; bl_idname = 'VIEW3D_PT_tt_playback'
    bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = 'TT Cutscene'

    def draw(self, context):
        layout = self.layout
        layout.label(text='Space: play / pause. NumPad 0: camera.')
        layout.prop(context.scene, 'sync_mode', text='Playback')
        if context.scene.get('tt_live_preview'):
            layout.label(text='Live mask approximation; source camera only.')
        else:layout.operator(SCENE_OT_tt_live_preview.bl_idname)
        for scene in bpy.data.scenes:
            if scene.get('tt_preview_kind') in {'LIVE', 'CACHE'}:
                op = layout.operator(SCENE_OT_tt_show_preview.bl_idname, text=scene.name,
                                     icon='SEQUENCE' if scene.get('tt_preview_kind') == 'CACHE' else 'VIEW_CAMERA')
                op.scene_name = scene.name
        rig = context.object
        if rig and rig.get('tt_manual_face_controller'):
            layout.prop(rig, '["Target"]', text='Native target ID')
            layout.prop(rig, '["Strength"]', text='Strength')
        layout.label(text='Movie caches stay unchanged after edits.')


CLASSES = (SCENE_OT_tt_live_preview, SCENE_OT_tt_show_preview, VIEW3D_PT_tt_playback)
def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
def unregister():
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)

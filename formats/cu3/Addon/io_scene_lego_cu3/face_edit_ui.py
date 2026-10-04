"""Export verified editing collections as separate native face GHG copies."""
from pathlib import Path
import json
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper
from .face_edit import patch_targets
from .face_edit_blender import edited_companion


class EXPORT_SCENE_OT_tt_face_targets(bpy.types.Operator, ExportHelper):
    bl_idname = 'export_scene.tt_face_targets'
    bl_label = 'Export edited face GHG copy'
    filename_ext = '.GHG'
    filter_glob: StringProperty(default='*.GHG;*.ghg', options={'HIDDEN'})
    source_ghg: StringProperty(name='Original face GHG', subtype='FILE_PATH')
    source_morph: StringProperty(name='Original target companion', subtype='FILE_PATH')
    collection_name: StringProperty(name='Editing collection')

    def invoke(self, context, event):
        self.source_ghg = context.scene.get('source_ghg', '')
        self.source_morph = context.scene.get('source_morph', '')
        self.collection_name = context.scene.get('editing_collection', '')
        source = Path(self.source_ghg)
        self.filepath = str(Path(bpy.data.filepath).parent / (source.stem + '_Edited.GHG'))
        return super().invoke(context, event)

    def draw(self, context):
        self.layout.prop(self, 'source_ghg')
        self.layout.prop(self, 'source_morph')
        self.layout.prop(self, 'collection_name')
        self.layout.label(text='Existing shape targets; save to a new GHG copy.', icon='INFO')

    def execute(self, context):
        try:
            source = Path(bpy.path.abspath(self.source_ghg))
            morph = Path(bpy.path.abspath(self.source_morph))
            output = Path(bpy.path.abspath(self.filepath))
            collection = bpy.data.collections.get(self.collection_name)
            if not collection:
                raise ValueError('Choose a verified native face editing collection')
            original = json.loads(morph.read_text())
            edited = edited_companion(collection.all_objects, original)
            raw, report = patch_targets(source.read_bytes(), edited)
            outputs = [output, output.with_suffix('.edited.morph.json'),
                       output.with_suffix(output.suffix + '.patch.json')]
            inputs = {source.resolve(), morph.resolve(), Path(bpy.data.filepath).resolve()}
            if any(p.resolve() in inputs or p.exists() for p in outputs):
                raise ValueError('Choose a new output name; input and existing files are protected')
            report.update(source=str(source.resolve()), blend=bpy.data.filepath,
                          output=str(output.resolve()), collection=collection.name)
            with outputs[0].open('xb') as stream:
                stream.write(raw)
            with outputs[1].open('x') as stream:
                json.dump(edited, stream, separators=(',', ':'))
            with outputs[2].open('x') as stream:
                json.dump(report, stream, indent=2)
            self.report({'INFO'}, f'Validated GHG copy: {len(report["targets"])} edited part targets. Game test still required.')
            return {'FINISHED'}
        except (ValueError, KeyError, OSError, TypeError, OverflowError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class VIEW3D_PT_tt_native_face(bpy.types.Panel):
    bl_label = 'Native face targets (experimental)'
    bl_idname = 'VIEW3D_PT_tt_native_face'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Cutscene'

    @classmethod
    def poll(cls, context):
        return bool(context.scene.get('editing_collection'))

    def draw(self, context):
        self.layout.label(text=context.scene['editing_collection'])
        self.layout.label(text='Edit TT_Target keys; keep Basis unchanged.')
        self.layout.operator(EXPORT_SCENE_OT_tt_face_targets.bl_idname, icon='EXPORT')


CLASSES = (EXPORT_SCENE_OT_tt_face_targets, VIEW3D_PT_tt_native_face)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

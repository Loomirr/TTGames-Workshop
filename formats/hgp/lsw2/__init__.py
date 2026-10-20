"""LEGO Star Wars II (2006, PC) model import and export for Blender 4.2 and newer, with animations and
facial shapes.

File > Import / Export > LEGO Star Wars II Model (.hgp), or drag an .hgp into the 3D Viewport.
By Gibby. MIT licence.
"""
import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import exporter, hgp, importer

bl_info = {
    'name': 'LEGO Star Wars II Model (.hgp)',
    'author': 'Gibby',
    'version': (0, 2, 1),
    'blender': (4, 2, 0),
    'location': 'File > Import / Export > LEGO Star Wars II Model (.hgp)',
    'description': 'Experimental LEGO Star Wars II PC models: import and export a separate HGP copy',
    'category': 'Import-Export',
}


class LSW2_OT_import(bpy.types.Operator, ImportHelper):
    """Import a LEGO Star Wars II character or vehicle model (.hgp)"""
    bl_idname = 'import_scene.lsw2_hgp'
    bl_label = 'Import LEGO Star Wars II Model'
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = '.hgp'
    filter_glob: StringProperty(default='*.hgp', options={'HIDDEN'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    animations: BoolProperty(
        name='Import Animations', default=True,
        description='Make an action from every .an3 clip beside the model that is proven to belong to its '
                    'skeleton (frame 0 reproduces the bind pose)')
    animation_folder: StringProperty(
        name='Animation Folder', subtype='DIR_PATH',
        description='Take clips from this folder instead (they are still checked against the skeleton)')
    unproven_animations: BoolProperty(
        name='Also Unproven Clips', default=False,
        description='Also import clips with the same bone count that could not be proven to belong to this '
                    'skeleton, bound by bone order (may be wrong; such actions are marked lsw2_unproven)')
    show_all_layers: BoolProperty(
        name='Show All Detail Layers',
        description='Show every detail layer; otherwise only the default layer and the most detailed body')

    def execute(self, context):
        import os
        paths = [os.path.join(self.directory, f.name) for f in self.files if f.name] or [self.filepath]
        done = 0
        for path in paths:
            try:
                importer.import_hgp(context, path, self.show_all_layers, self.animations, self.animation_folder,
                                    report=lambda m: self.report({'INFO'}, m),
                                    unproven_animations=self.unproven_animations)
                done += 1
            except (hgp.HGPError, OSError) as e:
                self.report({'WARNING'}, f'{os.path.basename(path)}: {e}')
        if not done:
            return {'CANCELLED'}
        return {'FINISHED'}

    def invoke(self, context, event):
        if self.filepath:      # show import options for dropped files too
            return context.window_manager.invoke_props_dialog(self, width=500)
        return ImportHelper.invoke(self, context, event)


class LSW2_OT_export(bpy.types.Operator, ExportHelper):
    """Export the selected LEGO Star Wars II model to a separate source-format copy"""
    bl_idname = 'export_scene.lsw2_hgp'
    bl_label = 'Export LEGO Star Wars II Model'
    bl_options = {'REGISTER', 'PRESET'}

    filename_ext = '.hgp'
    filter_glob: StringProperty(default='*.hgp', options={'HIDDEN'})
    original: StringProperty(
        name='Original File', subtype='FILE_PATH',
        description='The .hgp this model was imported from (empty: the path stored at import)')

    def execute(self, context):
        arm = find_armature(context)
        if arm is None:
            self.report({'ERROR'}, 'Select an armature imported with this add-on (or one of its parts)')
            return {'CANCELLED'}
        try:
            _, notes = exporter.export_hgp(context, self.filepath, arm, self.original or None,
                                           report=lambda n: self.report({'INFO'}, n))
        except (exporter.ExportError, hgp.HGPError, OSError) as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Wrote {self.filepath}' + (f' ({len(notes)} note(s), see the Info log)' if notes else ''))
        return {'FINISHED'}


def find_armature(context):
    obj = context.active_object
    while obj is not None:
        if obj.type == 'ARMATURE' and 'lsw2_source' in obj:
            return obj
        obj = obj.parent
    found = [o for o in context.scene.objects if o.type == 'ARMATURE' and 'lsw2_source' in o]
    return found[0] if len(found) == 1 else None


class LSW2_FH_hgp(bpy.types.FileHandler):
    bl_idname = 'LSW2_FH_hgp'
    bl_label = 'LEGO Star Wars II Model'
    bl_import_operator = 'import_scene.lsw2_hgp'
    bl_file_extensions = '.hgp'

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'


def menu_import(self, context):
    self.layout.operator(LSW2_OT_import.bl_idname, text='LEGO Star Wars II Model (.hgp)')


def menu_export(self, context):
    self.layout.operator(LSW2_OT_export.bl_idname, text='LEGO Star Wars II Model (.hgp)')


classes = (LSW2_OT_import, LSW2_OT_export, LSW2_FH_hgp)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

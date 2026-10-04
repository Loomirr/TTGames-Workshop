"""Blender importer for characters from the original 2005 LSW1 PC release."""
import os
from pathlib import Path
import traceback

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .importer import import_character, remove_created_data, snapshot_data

bl_info = {
    'name': 'LEGO Star Wars 1 Character Importer',
    'author': 'LSW1 Importer Contributors',
    'version': (0, 1, 3),
    'blender': (4, 2, 0),
    'location': 'File > Import > LEGO Star Wars 1 Character (.hgp)',
    'description': 'Original 2005 LSW1 PC meshes, textures, native skeletons and weights',
    'category': 'Import-Export',
}


class IMPORT_SCENE_OT_lsw1_hgp(bpy.types.Operator, ImportHelper):
    bl_idname = 'import_scene.lsw1_hgp'
    bl_label = 'Import LEGO Star Wars 1 Character'
    bl_options = {'UNDO'}
    filename_ext = '.hgp'

    filter_glob: StringProperty(default='*.hgp', options={'HIDDEN'})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    import_armature: BoolProperty(name='Original Skeleton and Weights', default=True,
        description='Create a poseable armature with the original bones and vertex weights')
    import_textures: BoolProperty(name='Embedded Textures', default=True,
        description='Load embedded textures and pack them into the blend file automatically')
    custom_normals: BoolProperty(name='Original Normals', default=True,
        description='Preserve the source normals for smooth LEGO surfaces')
    detail: EnumProperty(name='Detail Layer', default='AUTO', items=[
        ('AUTO', 'Maximum Detail (Automatic)', 'Use the most detailed native layer, with shared heads and attachments'),
        ('0', 'Shared / Default Layer Only', 'Import the default layer; some characters keep their entire body here'),
        ('1', 'Layer 1', 'Shared layer plus native layer 1'),
        ('2', 'Layer 2', 'Shared layer plus native layer 2'),
        ('3', 'Layer 3', 'Shared layer plus native layer 3'),
        ('4', 'Layer 4', 'Shared layer plus native layer 4')])
    scale: FloatProperty(name='Scale', default=1.0, min=0.000001, soft_max=10,
        description='Uniform scale applied to the imported character root')
    placement: EnumProperty(name='Place At', default='CURSOR', items=[
        ('CURSOR', '3D Cursor', 'Place the first character at the 3D cursor'),
        ('ORIGIN', 'World Origin', 'Place the first character at the world origin')])
    spacing: FloatProperty(name='Multiple Character Spacing', default=0.6, min=0,
        description='Spacing along X when importing several selected files')
    correct_preview_pose: BoolProperty(name='Face Jango Helmet Forward', default=True,
        description='Correct the known Jango helmet facing with a pose rotation; preserve its native bind data')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        layout=self.layout
        layout.prop(self,'import_armature');layout.prop(self,'import_textures')
        layout.prop(self,'custom_normals');layout.prop(self,'detail')
        layout.prop(self,'scale');layout.prop(self,'placement');layout.prop(self,'spacing')
        layout.prop(self,'correct_preview_pose')
        layout.label(text='Original LSW1 PC character files only', icon='INFO')

    def execute(self, context):
        paths=[Path(self.directory or os.path.dirname(self.filepath))/entry.name for entry in self.files]
        if not paths:paths=[Path(self.filepath)]
        roots=[];failures=[]
        base=context.scene.cursor.location.copy() if self.placement=='CURSOR' else (0,0,0)
        for path in paths:
            before=snapshot_data()
            try:
                root=import_character(context,path,
                    location=(base[0]+len(roots)*self.spacing*self.scale,base[1],base[2]),
                    scale=self.scale,armature=self.import_armature,textures=self.import_textures,
                    custom_normals=self.custom_normals,detail=self.detail,
                    correct_preview_pose=self.correct_preview_pose)
                roots.append(root)
            except Exception as exc:
                traceback.print_exc()
                remove_created_data(context,before)
                failures.append(f'{path.name}: {str(exc) or type(exc).__name__}')
        if not roots:
            self.report({'WARNING'},'Import failed: '+('; '.join(failures))[:450])
            return {'CANCELLED'}
        bpy.ops.object.select_all(action='DESELECT')
        for root in roots:root.select_set(True)
        context.view_layer.objects.active=roots[0]
        if failures:self.report({'WARNING'},f'Imported {len(roots)} character(s); failed: '+('; '.join(failures))[:350])
        else:self.report({'INFO'},f'Imported {len(roots)} LSW1 character(s)')
        return {'FINISHED'}


def menu_import(self, context):
    self.layout.operator(IMPORT_SCENE_OT_lsw1_hgp.bl_idname,text='LEGO Star Wars 1 Character (.hgp)')


def register():
    bpy.utils.register_class(IMPORT_SCENE_OT_lsw1_hgp)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(IMPORT_SCENE_OT_lsw1_hgp)

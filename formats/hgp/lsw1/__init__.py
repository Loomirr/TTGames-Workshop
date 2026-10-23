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
    'version': (0, 1, 10),
    'blender': (4, 2, 0),
    'location': 'File > Import > LEGO Star Wars 1 Character (.hgp / .txt)',
    'description': 'Original 2005 LSW1 PC meshes, textures, native skeletons and weights',
    'category': 'Import-Export',
}


class IMPORT_SCENE_OT_lsw1_hgp(bpy.types.Operator, ImportHelper):
    bl_idname = 'import_scene.lsw1_hgp'
    bl_label = 'Import LEGO Star Wars 1 Character'
    bl_options = {'UNDO'}
    filename_ext = '.hgp'

    filter_glob: StringProperty(default='*.hgp;*.HGP;*.txt;*.TXT', options={'HIDDEN'})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    import_armature: BoolProperty(name='Original Skeleton and Weights', default=True,
        description='Create a poseable armature with the original bones and vertex weights')
    import_textures: BoolProperty(name='Embedded Textures', default=True,
        description='Load embedded textures and pack them into the blend file automatically')
    custom_normals: BoolProperty(name='Original Normals', default=True,
        description='Preserve the source normals for smooth LEGO surfaces')
    detail: EnumProperty(name='Detail Layer', default='AUTO', items=[
        ('AUTO', 'Maximum Detail (Automatic)', 'Choose nonempty body detail and observed complementary head, hair and vehicle layers; gameplay variants remain separate'),
        *[(f'GAME_{name.upper()}', f'Definition: {name.title()}',
           f'Use the exact layers_{name} list from the same-named character TXT; no extra layers are added')
          for name in ('special','high','medium','low','dead')],
        ('0', 'Shared / Default Layer Only', 'Import the default layer; some characters keep their entire body here'),
        ('1', 'Layer 1', 'Shared layer plus native layer 1'),
        ('2', 'Layer 2', 'Shared layer plus native layer 2'),
        ('3', 'Layer 3', 'Shared layer plus native layer 3'),
        ('4', 'Layer 4', 'Shared layer plus native layer 4'),
        *[(str(i), f'Layer {i}', f'Shared layer plus native layer {i}; consult the imported root layer names')
          for i in range(5, 32)]])
    scale: FloatProperty(name='Scale', default=1.0, min=0.000001, soft_max=10,
        description='Uniform scale applied to the imported character root')
    placement: EnumProperty(name='Place At', default='CURSOR', items=[
        ('CURSOR', '3D Cursor', 'Place the first character at the 3D cursor'),
        ('ORIGIN', 'World Origin', 'Place the first character at the world origin')])
    spacing: FloatProperty(name='Multiple Character Spacing', default=0.0, min=0,
        description='Spacing along X when importing several selected files')
    correct_preview_pose: BoolProperty(name='Correct Known Preview Poses', default=True,
        description='Apply reversible Jango helmet and known Clone hand display poses; disable for native bind inspection or animation')

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
        layout.label(text='TXT uses Definition: Special by default')

    def invoke(self, context, event):
        if self.filepath:
            return context.window_manager.invoke_props_dialog(self, width=500)
        return ImportHelper.invoke(self, context, event)

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


class LSW1_FH_hgp(bpy.types.FileHandler):
    bl_idname = 'LSW1_FH_hgp'
    bl_label = 'LEGO Star Wars 1 HGP'
    bl_import_operator = 'import_scene.lsw1_hgp'
    bl_file_extensions = '.hgp;.txt'

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'


def menu_import(self, context):
    self.layout.operator(IMPORT_SCENE_OT_lsw1_hgp.bl_idname,text='LEGO Star Wars 1 Character (.hgp / .txt)')


def register():
    bpy.utils.register_class(IMPORT_SCENE_OT_lsw1_hgp)
    bpy.utils.register_class(LSW1_FH_hgp)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(LSW1_FH_hgp)
    bpy.utils.unregister_class(IMPORT_SCENE_OT_lsw1_hgp)

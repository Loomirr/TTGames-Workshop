"""Direct native character and animation import, independent of the CU3 addon."""
bl_info = {'name': 'TT Character and Animation Importer', 'author': 'Loomirr and contributors',
           'version': (0, 1, 0), 'blender': (4, 4, 0), 'category': 'Import-Export',
           'location': 'File > Import; 3D View > Sidebar > TT Character',
           'description': 'Experimental LMSH1/LB3 CD/GHG/GSC models and observed AN4 skeletal animations'}

import json
from pathlib import Path
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty, FloatProperty, IntProperty, CollectionProperty, PointerProperty
from bpy_extras.io_utils import ImportHelper
from .importer import import_character, import_animations, find_rig
from ._core.cu3 import FormatError
from ._core.asset_index import open_assets

GAMES = [('LB3', 'LEGO Batman 3', 'Observed DX11 models'), ('LMSH1', 'LEGO Marvel Super Heroes', 'Observed NXG models')]
_catalog = []
_catalog_assets = None


class TTCHAR_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    lb3: StringProperty(name='LB3 game / extracted folder', subtype='DIR_PATH')
    lmsh1: StringProperty(name='LMSH1 game / extracted folder', subtype='DIR_PATH')
    cache: StringProperty(name='Optional asset cache', subtype='DIR_PATH')

    def draw(self, context):
        for prop in ('lb3', 'lmsh1', 'cache'):
            self.layout.prop(self, prop)


def preferences(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


class IMPORT_SCENE_OT_tt_game_character(bpy.types.Operator):
    bl_idname = 'import_scene.tt_game_character'
    bl_label = 'Browse game characters'
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = 'resource'
    resource: EnumProperty(name='Character', items=lambda self, context: _catalog)

    def invoke(self, context, event):
        global _catalog_assets, _catalog
        prefs = preferences(context)
        game = context.scene.tt_character_game
        root = getattr(prefs, game.lower()) if prefs else ''
        if not root:
            self.report({'ERROR'}, 'Set the game folder in addon preferences or the TT Character panel first')
            return {'CANCELLED'}
        try:
            _catalog_assets = open_assets(bpy.path.abspath(root), game,
                cache_root=bpy.path.abspath(prefs.cache) if prefs.cache else None)
            paths = set()
            for name, entries in _catalog_assets.files.items():
                if not name.endswith('.cd'):
                    continue
                for entry in entries:
                    path = entry[1]['path'] if isinstance(entry, tuple) else entry.relative_to(_catalog_assets.root).as_posix()
                    upper = path.upper()
                    if '/MINIFIG' in '/' + upper and '/SUPER_CHAR' not in upper:
                        paths.add(path)
            _catalog = [(p, Path(p).stem, p) for p in sorted(paths)]
            if not _catalog:
                raise FormatError('No minifig character definitions found in that folder')
        except (ValueError, OSError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if _catalog_assets is None:
            self.report({'ERROR'}, 'Open the character browser again')
            return {'CANCELLED'}
        try:
            path = _catalog_assets.find_exact(self.resource)
            prefs = preferences(context)
            game = context.scene.tt_character_game
            rig, report = import_character(context, path, Path(bpy.path.abspath(getattr(prefs, game.lower()))), game,
                cache=Path(bpy.path.abspath(prefs.cache)) if prefs.cache else None, assets=_catalog_assets)
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        count = len(report['issues']) + len(report['materials'])
        self.report({'WARNING'} if count else {'INFO'}, f'Imported {rig.name}; {count} notices in TT Character report')
        return {'FINISHED'}


class IMPORT_SCENE_OT_tt_character(bpy.types.Operator, ImportHelper):
    bl_idname = 'import_scene.tt_character'
    bl_label = 'LEGO Character / Model (.cd/.ghg/.gsc)'
    bl_options = {'REGISTER', 'UNDO'}
    filter_glob: StringProperty(default='*.cd;*.CD;*.ghg;*.GHG;*.gsc;*.GSC', options={'HIDDEN'})
    game: EnumProperty(name='Game', items=GAMES, default='LB3')
    assets: StringProperty(name='Game / extracted folder', subtype='DIR_PATH', description='Optional if saved in addon preferences; otherwise defaults to the input folder')
    definition: StringProperty(name='Optional matching CD', subtype='FILE_PATH', description='Use with a raw GHG to select its costume and native layers')
    attachments: BoolProperty(name='Import declared attachments', default=True)

    def execute(self, context):
        prefs = preferences(context)
        root = self.assets or (getattr(prefs, self.game.lower()) if prefs else '') or str(Path(self.filepath).parent)
        try:
            rig, report = import_character(context, Path(self.filepath), Path(bpy.path.abspath(root)), self.game,
                definition_path=Path(bpy.path.abspath(self.definition)) if self.definition else None,
                cache=Path(bpy.path.abspath(prefs.cache)) if prefs and prefs.cache else None,
                attachments=self.attachments)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        if prefs and self.assets:
            setattr(prefs, self.game.lower(), self.assets)
        issues = len(report['issues']) + len(report['materials'])
        self.report({'WARNING'} if issues else {'INFO'}, f'Imported {len(report["models"])} models; {issues} notices. See TT Character report in Text Editor.')
        return {'FINISHED'}


class IMPORT_ANIM_OT_tt_an4(bpy.types.Operator, ImportHelper):
    bl_idname = 'import_anim.tt_an4'
    bl_label = 'LEGO AN4 Animations (.an4)'
    bl_options = {'REGISTER', 'UNDO'}
    filter_glob: StringProperty(default='*.an4;*.AN4', options={'HIDDEN'})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')
    actor: StringProperty(name='Actor name (optional)', description='Blank selects one compatible root actor; ambiguous records require an exact name')
    fps: FloatProperty(name='Preview FPS', default=30, min=1, max=240, description='AN4 standalone preview timing assumption')

    @classmethod
    def poll(cls, context):
        return find_rig(context.object) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        rig = find_rig(context.object)
        paths = [Path(self.directory) / f.name for f in self.files] if self.files else [Path(self.filepath)]
        report = import_animations(context, rig, paths, self.actor, self.fps)
        imported = report['imported']
        self.report({'WARNING'} if report['issues'] else {'INFO'}, f'Imported {imported} actions; {len(report["issues"])} notices. See TT AN4 report.')
        return {'FINISHED'} if imported else {'CANCELLED'}


def set_clip(self, context):
    if not 0 <= self.tt_clip_index < len(self.tt_clips):
        return
    item = self.tt_clips[self.tt_clip_index]
    if item.action is None:
        return
    slot = next((slot for slot in item.action.slots if slot.identifier == item.slot), None)
    if slot is None:
        return
    self.animation_data_create()
    self.animation_data.action = item.action
    self.animation_data.action_slot = slot
    if context and context.scene:
        scene = context.scene
        scene.frame_start, scene.frame_end = 1, max(1, item.frames)
        scene.render.fps = round(item.fps)
        scene.render.fps_base = round(item.fps) / item.fps
        scene.frame_set(1)


class TTCHAR_Clip(bpy.types.PropertyGroup):
    action: PointerProperty(type=bpy.types.Action)
    slot: StringProperty()
    frames: IntProperty(default=1)
    fps: FloatProperty(default=30)


class TTCHAR_UL_clips(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon='ACTION')


class TTCHAR_PT_tools(bpy.types.Panel):
    bl_label = 'TT Character'
    bl_idname = 'TTCHAR_PT_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, 'tt_character_game', text='Game')
        prefs = preferences(context)
        if prefs:
            layout.prop(prefs, context.scene.tt_character_game.lower(), text='Game folder')
        layout.operator('import_scene.tt_game_character', text='Browse game characters', icon='VIEWZOOM')
        layout.operator('import_scene.tt_character', text='Import character / model')
        layout.operator('import_anim.tt_an4', text='Import AN4 animations')
        rig = find_rig(context.object)
        if rig:
            layout.label(text=rig.name, icon='ARMATURE_DATA')
            layout.template_list('TTCHAR_UL_clips', '', rig, 'tt_clips', rig, 'tt_clip_index', rows=5)
            layout.operator('screen.animation_play', text='Play / Pause', icon='PLAY')
            layout.label(text='Select a clip; Space plays the timeline.')
        else:
            layout.label(text='Select an imported character or its rig.')
        layout.label(text='Experimental materials and face preview.')


def menu_import(self, context):
    self.layout.operator(IMPORT_SCENE_OT_tt_character.bl_idname)
    self.layout.operator(IMPORT_ANIM_OT_tt_an4.bl_idname)


CLASSES = (TTCHAR_Preferences, TTCHAR_Clip, IMPORT_SCENE_OT_tt_character, IMPORT_SCENE_OT_tt_game_character, IMPORT_ANIM_OT_tt_an4, TTCHAR_UL_clips, TTCHAR_PT_tools)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.tt_clips = CollectionProperty(type=TTCHAR_Clip)
    bpy.types.Object.tt_clip_index = IntProperty(default=0, update=set_clip)
    bpy.types.Scene.tt_character_game = EnumProperty(name='Game', items=GAMES, default='LB3')
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    del bpy.types.Object.tt_clip_index
    del bpy.types.Object.tt_clips
    del bpy.types.Scene.tt_character_game
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

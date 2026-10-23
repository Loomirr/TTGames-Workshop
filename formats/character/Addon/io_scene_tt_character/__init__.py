"""Direct native character and animation import, independent of the CU3 addon."""
bl_info = {'name': 'TT Character and Animation Importer', 'author': 'Loomirr and contributors',
           'version': (0, 5, 31), 'blender': (4, 4, 0), 'category': 'Import-Export',
           'location': 'File > Import; 3D View > Sidebar > TT Character',
           'description': 'PC character and animation browsing, constrained native editing and experimental face preview'}

import json
from pathlib import Path
import bpy
from mathutils import Matrix
from bpy.props import StringProperty, EnumProperty, BoolProperty, FloatProperty, IntProperty, CollectionProperty, PointerProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from .importer import import_character, import_animations, find_rig, find_character, refresh_catalog, import_catalog_entry
from ._core.cu3 import FormatError
from ._core.asset_index import open_assets
from ._core.geometry_normals import normal_preservation_status
from .scene_settings import ensure_scene_settings, missing_scene_settings, unregister_scene_settings
from .preview_identity import linked_child
from .batch import TTCHAR_OT_batch_import
from .ui_guidance import game_guidance, note

GAMES = [('LB2', 'LEGO Batman 2', 'Observed PC NXG models (experimental)'), ('LB3', 'LEGO Batman 3', 'Observed DX11 models'), ('LMSH1', 'LEGO Marvel Super Heroes', 'Observed NXG models'),
         ('HOBBIT', 'LEGO The Hobbit', 'Observed PC NXG models'),
         ('AVENGERS', "LEGO Marvel's Avengers", 'Observed PC DX11 characters'),
         ('LB1', 'LEGO Batman 1 — models only', 'PC classic models and rigs; incomplete costume assembly; no animation playback or game export'),
         ('TCS', 'LEGO Star Wars: The Complete Saga — models only', 'PC classic models and rigs; incomplete costume assembly; no animation playback or game export'),
         ('FORTNITE', 'LEGO Fortnite — static models', 'Exported LEGO recipes/baked meshes; no animation or game export; reported import issue awaiting investigation')]
_catalog = []
_catalog_assets = None
_catalog_source = None


class TTCHAR_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    lb2: StringProperty(name='LB2 game / extracted folder', subtype='DIR_PATH')
    lb3: StringProperty(name='LB3 game / extracted folder', subtype='DIR_PATH')
    lmsh1: StringProperty(name='LMSH1 game / extracted folder', subtype='DIR_PATH')
    avengers: StringProperty(name='Avengers game / extracted folder', subtype='DIR_PATH')
    hobbit: StringProperty(name='The Hobbit game / extracted folder', subtype='DIR_PATH')
    lb1: StringProperty(name='Batman 1 game / extracted folder', subtype='DIR_PATH')
    tcs: StringProperty(name='TCS game / extracted folder', subtype='DIR_PATH')
    fortnite: StringProperty(name='LEGO Fortnite game / Paks / exported folder', subtype='DIR_PATH', description='Fortnite installation, Content/Paks folder, or an existing Exports/Models library; archive exports use a separate cache')
    fortnite_extractor: StringProperty(name='Optional LEGO Fortnite extractor', subtype='FILE_PATH', description='Separately built Workshop.Fortnite.Extractor executable; no external tools are bundled')
    fortnite_settings: StringProperty(name='Private Fortnite extractor settings', subtype='FILE_PATH', description='Private JSON with mappings, key-file and Oodle paths; Paks mode sets source and cache output automatically')
    cache: StringProperty(name='Optional asset cache', subtype='DIR_PATH')

    def draw(self, context):
        note(self.layout, context, 'Choose a game folder in the TT Character sidebar to get started. Saved folders are listed below.')
        for game, label, _ in GAMES:
            self.layout.prop(self, game.lower(), text=label.split(' — ')[0])
        box = self.layout.box()
        box.label(text='Optional Fortnite extraction setup')
        box.prop(self, 'fortnite_extractor')
        box.prop(self, 'fortnite_settings')
        self.layout.prop(self, 'cache')


def preferences(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def fortnite_source(prefs):
    from .fortnite_backend import resolve_source
    if not prefs or not prefs.fortnite:
        raise ValueError('Set the LEGO Fortnite game, Paks or exported-library folder first')
    return resolve_source(bpy.path.abspath(prefs.fortnite),
        bpy.path.abspath(prefs.cache) if prefs.cache else None,
        bpy.path.abspath(prefs.fortnite_settings) if prefs.fortnite_settings else None)


def character_catalog(assets):
    paths = set()
    for name, entries in assets.files.items():
        classic = getattr(assets, 'profile', None) in ('LB1', 'TCS')
        if not name.endswith('.ghg' if classic else '.cd'):
            continue
        for entry in entries:
            path = entry[1]['path'] if isinstance(entry, tuple) else entry.relative_to(assets.root).as_posix()
            upper = path.upper()
            if classic:
                if upper.startswith('CHARS/') and '_LR_PC.' not in upper:
                    paths.add(path)
                continue
            categories = ('/MINIFIG', '/SMALL/', '/BIGFIG', '/BIGGERFIG', '/CREATURE')
            if (any(c in '/' + upper for c in categories) and '/SUPER_CHAR' not in upper) or '/' not in path:
                paths.add(path)
    return [(p, Path(p).stem, p) for p in sorted(paths)]


def import_classic_model(context, path, game):
    from ._classic.blender_inspect import inspect_model
    from ._core.dds import read_dds
    from ._core.geometry_normals import apply_authored_normals
    return inspect_model(context, path, read_dds, apply_authored_normals, profile=game)


class IMPORT_SCENE_OT_tt_game_character(bpy.types.Operator):
    bl_idname = 'import_scene.tt_game_character'
    bl_label = 'Browse game characters'
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = 'resource'
    resource: EnumProperty(name='Character', items=lambda self, context: _catalog)

    def invoke(self, context, event):
        ensure_scene_settings()
        global _catalog_assets, _catalog, _catalog_source
        prefs = preferences(context)
        game = context.scene.tt_character_game
        root = getattr(prefs, game.lower()) if prefs else ''
        if not root:
            self.report({'ERROR'}, 'Set the game folder in addon preferences or the TT Character panel first')
            return {'CANCELLED'}
        try:
            if game == 'FORTNITE':
                from .fortnite_catalog import ExportLibrary
                selected = fortnite_source(prefs)
                if selected.paks and (not prefs.fortnite_extractor or not prefs.fortnite_settings):
                    raise ValueError('Paks browsing needs the optional Fortnite extractor and private settings in addon preferences')
                _catalog_source = selected
                if selected.paks and not (selected.root/'lego-fortnite-index.json').is_file():
                    bpy.ops.tt_character.fortnite_extract('INVOKE_DEFAULT', index_only=True)
                    return {'CANCELLED'}
                _catalog_assets = ExportLibrary(selected.root)
                _catalog = [(v['resource'], v['label'] + ' [' + v['code'] + '] (' + v['mode'] + ')', v['resource']) for v in _catalog_assets.catalog()]
                if not _catalog:
                    raise ValueError('No LEGO Fortnite dataless recipes or baked character exports found')
                context.window_manager.invoke_search_popup(self)
                return {'RUNNING_MODAL'}
            _catalog_assets = open_assets(bpy.path.abspath(root), game,
                cache_root=bpy.path.abspath(prefs.cache) if prefs.cache else None)
            _catalog = character_catalog(_catalog_assets)
            if not _catalog:
                if game in ('LB1', 'TCS'):
                    raise FormatError('No classic GHG files found under CHARS. Select the game/extracted root containing CHARS, or inspect a GHG/GSC directly.')
                raise FormatError('No character CD files found. Select a game folder or extracted folder containing character CDs; a model/texture-only folder is not enough. You can also import a CD directly.')
        except (ValueError, OSError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if _catalog_assets is None:
            self.report({'ERROR'}, 'Open the character browser again')
            return {'CANCELLED'}
        ensure_scene_settings()
        try:
            prefs = preferences(context)
            game = context.scene.tt_character_game
            if game == 'FORTNITE':
                from .fortnite_importer import import_fortnite
                from .fortnite_catalog import MissingExport
                if _catalog_source != fortnite_source(prefs):
                    raise ValueError('The Fortnite folder or archive build changed; open the character browser again')
                entry = next(v for v in _catalog_assets.catalog() if v['resource'] == self.resource)
                try:
                    _catalog_assets.plan(entry)
                except MissingExport:
                    if not entry.get('backend_resource') or not prefs.fortnite_extractor or not prefs.fortnite_settings:
                        raise
                    bpy.ops.tt_character.fortnite_extract('INVOKE_DEFAULT', resource=self.resource)
                    return {'FINISHED'}
                rig, report = import_fortnite(context, _catalog_assets.root, self.resource)
                self.report({'INFO'}, f'Imported {rig.name}; static source printing and normals. See TT LEGO Fortnite report for shader limits.')
                return {'FINISHED'}
            if getattr(_catalog_assets, 'profile', None) != game:
                raise ValueError('The game changed; open the character browser again')
            path = _catalog_assets.find_exact(self.resource)
            if game in ('LB1', 'TCS'):
                collection, report = import_classic_model(context, path, game)
                self.report({'WARNING'}, f'Classic inspection: {report["meshes"]} meshes, {report["rigid_bound_meshes"]} rigid pieces bound to joints, {report["unbound_rigid_meshes"]} unbound rigid pieces hidden. See Classic model report.')
                return {'FINISHED'}
            rig, report = import_character(context, path, Path(bpy.path.abspath(getattr(prefs, game.lower()))), game,
                cache=Path(bpy.path.abspath(prefs.cache)) if prefs.cache else None, assets=_catalog_assets,
                attachments=context.scene.tt_import_attachments, layer_mode=context.scene.tt_costume_layers,
                highest_detail=context.scene.tt_mesh_detail == 'HIGHEST',
                game_handedness=context.scene.tt_game_handedness)
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
    game_handedness: BoolProperty(name='Mirror to game handedness', default=False,
        description='Mirror the imported character object on X so left and right match the game; native and export data unchanged')
    mesh_detail: EnumProperty(name='Mesh detail', items=[('HIGHEST', 'Highest detail', 'Select the nearest verified native LOD'),
        ('AUTHORED', 'Authored binding', 'Inspect the original display binding without LOD override')], default='HIGHEST')
    layers: EnumProperty(name='Costume layers', items=[('default', 'Default costume', 'Use native default character layers'),
        ('cutscene', 'Cutscene costume', 'Use native cutscene layers'), ('authored', 'Authored selection flags', 'Original reader selection flags')], default='default')

    def draw(self, context):
        layout = self.layout
        layout.label(text='Character / Model import', icon='OUTLINER_OB_ARMATURE')
        layout.prop(self, 'game')
        game_guidance(layout, context, self.game)
        layout.prop(self, 'assets')
        if self.game in ('LB1', 'TCS'):
            note(layout, context, 'Choose a GHG or GSC model from this game.')
        elif self.game == 'FORTNITE':
            note(layout, context, 'Use Browse game characters in the TT Character sidebar for Fortnite exports.')
        else:
            layout.label(text='CD: assemble its declared character parts.')
            layout.label(text='GHG / GSC: open an individual model.')
            layout.prop(self, 'definition')
            layout.prop(self, 'attachments')
            layout.prop(self, 'mesh_detail')
            layout.prop(self, 'layers')
            layout.prop(self, 'game_handedness')
        layout.separator()
        note(layout, context, 'After import: press N in the 3D Viewport and open TT Character.')

    def invoke(self, context, event):
        ensure_scene_settings()
        # Blender remembers file-browser operator settings separately from the
        # sidebar. Always start this interactive import with the visible game.
        self.game = context.scene.tt_character_game
        self.mesh_detail = context.scene.tt_mesh_detail
        self.layers = context.scene.tt_costume_layers
        self.attachments = context.scene.tt_import_attachments
        self.game_handedness = context.scene.tt_game_handedness
        if self.filepath:
            return context.window_manager.invoke_props_dialog(self, width=500)
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        if not self.properties.is_property_set('game'):
            self.game = context.scene.tt_character_game
        prefs = preferences(context)
        if self.game == 'FORTNITE':
            self.report({'ERROR'}, 'Use Browse game characters for LEGO Fortnite exported recipes; CD/GHG/GSC import is for TT games')
            return {'CANCELLED'}
        root = self.assets or (getattr(prefs, self.game.lower()) if prefs else '') or str(Path(self.filepath).parent)
        try:
            if self.game in ('LB1', 'TCS'):
                if Path(self.filepath).suffix.lower() not in ('.ghg', '.gsc'):
                    raise ValueError('Classic inspection requires a PC GHG/GSC; modern CD definitions are not supported')
                collection, report = import_classic_model(context, Path(self.filepath), self.game)
                if prefs and self.assets:
                    setattr(prefs, self.game.lower(), self.assets)
                context.scene.tt_character_game = self.game
                self.report({'WARNING'}, f'Classic raw inspection: {report["meshes"]} meshes; see Classic model report for omitted parts and shader limits.')
                return {'FINISHED'}
            rig, report = import_character(context, Path(self.filepath), Path(bpy.path.abspath(root)), self.game,
                definition_path=Path(bpy.path.abspath(self.definition)) if self.definition else None,
                cache=Path(bpy.path.abspath(prefs.cache)) if prefs and prefs.cache else None,
                attachments=self.attachments, layer_mode=self.layers,
                highest_detail=self.mesh_detail == 'HIGHEST', game_handedness=self.game_handedness)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        if prefs and self.assets:
            setattr(prefs, self.game.lower(), self.assets)
        context.scene.tt_character_game = self.game
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

    def invoke(self, context, event):
        if self.filepath:
            return context.window_manager.invoke_props_dialog(self, width=500)
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        rig = find_rig(context.object)
        paths = [Path(self.directory or str(Path(self.filepath).parent)) / f.name for f in self.files] if self.files else [Path(self.filepath)]
        report = import_animations(context, rig, paths, self.actor, self.fps)
        imported = report['imported']
        if not imported and report['issues']:
            self.report({'WARNING'}, report['issues'][0])
        else:
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
    tracks = json.loads(item.action.get('tt_attachment_actions', '[]'))
    faces = json.loads(item.action.get('tt_facial_actions', '[]'))
    for child in self.children_recursive:
        if child.type == 'MESH' and child.data.shape_keys:
            keys = child.data.shape_keys
            if keys.animation_data:keys.animation_data.action = None
            for key in keys.key_blocks:
                if key.name.startswith('TT_Target_'):key.value = 0.0
        if child.type == 'ARMATURE' and child.get('tt_character_skeleton') and child.animation_data:
            child.animation_data.action = None
            for bone in child.pose.bones:
                bone.matrix_basis = Matrix.Identity(4)
    for track in tracks:
        child, action = linked_child(self, track['object']), bpy.data.actions.get(track['action'])
        if child is None or child not in self.children_recursive or action is None:
            continue
        child.animation_data_create()
        child.animation_data.action = action
        child.animation_data.action_slot = next((s for s in action.slots if s.identifier == track['slot']), None)
    for track in faces:
        child = linked_child(self, track['object'])
        action = bpy.data.actions.get(track['action'])
        if child is None or child.type!='MESH' or not child.data.shape_keys or action is None:continue
        keys = child.data.shape_keys
        keys.animation_data_create()
        keys.animation_data.action = action
        keys.animation_data.action_slot = next((s for s in action.slots if s.identifier==track['slot']), None)
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
    def filter_items(self, context, data, propname):
        query = data.tt_animation_search.casefold()
        return [self.bitflag_filter_item if query in item.name.casefold() else 0 for item in getattr(data, propname)], []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon='ACTION')


class TTCHAR_AnimationAsset(bpy.types.PropertyGroup):
    payload: StringProperty()
    label: StringProperty()
    available: BoolProperty()


class TTCHAR_UL_animation_assets(bpy.types.UIList):
    def filter_items(self, context, data, propname):
        query = data.tt_animation_search.casefold()
        return [self.bitflag_filter_item if query in item.label.casefold() else 0 for item in getattr(data, propname)], []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        entry = json.loads(item.payload)
        layout.label(text=item.label + (' [disabled]' if not entry['active'] else ''),
                     icon='ACTION' if item.available else 'ERROR')


class TTCHAR_OT_refresh_animations(bpy.types.Operator):
    bl_idname = 'tt_character.refresh_animations'
    bl_label = 'Find character animations'

    def execute(self, context):
        rig = find_rig(context.object)
        try:
            report = refresh_catalog(rig)
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{len(report["entries"])} declared actions; {len(report["issues"])} unresolved sets. See catalog report.')
        return {'FINISHED'}


class TTCHAR_OT_load_animation(bpy.types.Operator):
    bl_idname = 'tt_character.load_animation'
    bl_label = 'Load selected animation'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = find_rig(context.object)
        if rig is None or not 0 <= rig.tt_animation_asset_index < len(rig.tt_animation_assets):
            return {'CANCELLED'}
        try:
            entry = json.loads(rig.tt_animation_assets[rig.tt_animation_asset_index].payload)
            report = import_catalog_entry(context, rig, entry)
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'WARNING'} if report['issues'] else {'INFO'}, report['issues'][0] if report['issues'] else 'Animation ready; press Play / Pause')
        return {'FINISHED'} if report['imported'] else {'CANCELLED'}


class TTCHAR_OT_custom_clip(bpy.types.Operator):
    bl_idname = 'tt_character.custom_clip'
    bl_label = 'Create custom animation copy'
    bl_options = {'REGISTER', 'UNDO'}
    clip_name: StringProperty(name='Clip name', default='Custom animation')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from .custom_animation import create_custom_clip
        rig = find_rig(context.object)
        if rig is None:return {'CANCELLED'}
        try:create_custom_clip(rig,self.clip_name)
        except (ValueError, KeyError, RuntimeError) as error:
            self.report({'ERROR'},str(error));return {'CANCELLED'}
        self.report({'INFO'},'Custom copy ready. Keep the native rig and clip length; export replaces the template clip.')
        return {'FINISHED'}


class TTCHAR_OT_load_custom(bpy.types.Operator, ImportHelper):
    bl_idname = 'tt_character.load_custom'
    bl_label = 'Load custom AN4 / PAK for selected action'
    bl_options = {'REGISTER', 'UNDO'}
    filter_glob: StringProperty(default='*.AN4;*.an4;*.PAK;*.pak', options={'HIDDEN'})

    def execute(self, context):
        from .custom_animation import load_custom_clip
        rig = find_rig(context.object)
        if rig is None or not 0 <= rig.tt_animation_asset_index < len(rig.tt_animation_assets):
            self.report({'ERROR'},'Select a declared character action first');return {'CANCELLED'}
        try:
            entry=json.loads(rig.tt_animation_assets[rig.tt_animation_asset_index].payload)
            report=load_custom_clip(context,rig,self.filepath,entry)
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.report({'ERROR'},str(error));return {'CANCELLED'}
        self.report({'WARNING'} if report['issues'] else {'INFO'},
                    report['issues'][0] if report['issues'] else 'Custom animation loaded for preview')
        return {'FINISHED'} if report['imported'] else {'CANCELLED'}


class TTCHAR_OT_animation_details(bpy.types.Operator):
    """Explain which facial tracks loaded for the selected animation"""
    bl_idname = 'tt_character.animation_details'
    bl_label = 'Animation details'

    @classmethod
    def poll(cls, context):
        rig = find_rig(context.object)
        return bool(rig and rig.animation_data and rig.animation_data.action)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=640)

    def draw(self, context):
        import textwrap
        rig = find_rig(context.object)
        action = rig.animation_data.action
        layout = self.layout
        layout.label(text=action.name, icon='ACTION')
        data = json.loads(action.get('tt_facial_playback', '{}'))
        if not data:
            layout.label(text='Load this clip again to see its facial playback details.')
            return
        layout.label(text=f'Face tracks loaded: {data["mesh_tracks"]}; moving: {data["animated_mesh_tracks"]}')
        if data['status'] == 'static':
            layout.label(text='The loaded expression weights stay constant throughout this clip.')
        elif data['status'] == 'absent':
            layout.label(text='No facial tracks loaded. Check the character includes its face attachment.')
        for note in data.get('notices', []):
            box = layout.box()
            box.label(text=note.get('attachment', 'Face'), icon='INFO')
            for line in textwrap.wrap(note.get('reason', ''), width=82):
                box.label(text=line)
        layout.separator()
        layout.label(text='Edited facial tracks cannot currently be exported back to AN4.')
        if action.get('tt_animation_report'):
            layout.label(text='Full report in Blender Text Editor:')
            layout.label(text=action['tt_animation_report'])

    def execute(self, context):
        return {'FINISHED'}


class TTCHAR_OT_preview(bpy.types.Operator):
    bl_idname = 'tt_character.preview'
    bl_label = 'Create character preview scene'
    bl_options = {'REGISTER', 'UNDO'}
    composed_faces: BoolProperty(name='Composed face render', default=False,
        description='Create a separate Cycles/compositor scene for native facial masking; use F12')

    def execute(self, context):
        from .preview import create_preview
        rig = find_character(context.object)
        if context.scene.tt_character_game == 'FORTNITE':
            from .fortnite_importer import find_fortnite
            rig = find_fortnite(context.object)
            if self.composed_faces:
                self.report({'ERROR'}, 'LEGO Fortnite uses a different facial shader; the TT composed-mask helper does not apply')
                return {'CANCELLED'}
        if rig is None:
            return {'CANCELLED'}
        try:
            create_preview(context, rig, composed_faces=self.composed_faces)
        except (ValueError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'F12 renders composed facial masks' if self.composed_faces else
                    'Use camera view and Material Preview to inspect the static model' if rig.get('tt_fortnite_static') else
                    'Use camera view and Material Preview; Space plays animations')
        return {'FINISHED'}


class TTCHAR_OT_export_sources(bpy.types.Operator):
    bl_idname = 'tt_character.export_sources'
    bl_label = 'LEGO model edits (game files)'
    bl_description = 'Write supported edits to a new folder; keep the original meshes, bones and materials'
    directory: StringProperty(name='New export folder', subtype='DIR_PATH')
    face_edits: BoolProperty(name='Write supported existing face target edits', default=True,
        description='Write existing targets while preserving facial Basis and topology')
    mesh_edits: BoolProperty(name='Write supported vertex and skin edits', default=True,
        description='Positions, UVs, colors, normals and existing palette weights; preserve topology, bounds and skeleton')

    @classmethod
    def poll(cls, context):
        if find_character(context.object) is None:
            cls.poll_message_set('Select a character imported with source export support')
            return False
        return True

    def draw(self, context):
        note(self.layout, context, 'Write separate game files to a new folder. Existing mesh and face edits only; no new bones or parts.')
        self.layout.prop(self, 'mesh_edits', text='Include mesh edits')
        self.layout.prop(self, 'face_edits', text='Include face shape edits')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .exporter import export_sources
        rig = find_character(context.object)
        if rig is None or not self.directory:
            return {'CANCELLED'}
        try:
            report = export_sources(rig, bpy.path.abspath(self.directory), self.face_edits, self.mesh_edits)
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        notice = (' Older import: reimport to check missing meshes/attachments.'
                  if not report.get('assembly_inventory', {}).get('checked') else '')
        self.report({'WARNING'}, f'{len(report["files"])} loose files exported. Existing vertex/face edits only; see TT_Source_Export.json for limits.' + notice)
        return {'FINISHED'}


class TTCHAR_OT_export_action(bpy.types.Operator, ExportHelper):
    bl_idname = 'tt_character.export_action'
    bl_label = 'LEGO animation (.an4 / .pak)'
    bl_description = 'Export the selected character\'s active native clip; supported edits only'
    filename_ext = '.AN4'
    filter_glob: StringProperty(default='*.AN4', options={'HIDDEN'})
    rebuild_bank: BoolProperty(name='Rebuild source PAK bank', default=False,
        description='For clips imported from a bank: write a separate PAK, preserving the other clips and original order. Requires a fresh clip import')
    omit_auxiliary: BoolProperty(name='Omit unsupported events / auxiliary tables', default=False,
        description='Discard extra tables for a pose-only draft; leave off to preserve supported native detail tracks')

    @classmethod
    def poll(cls, context):
        rig = find_rig(context.object)
        action = rig.animation_data.action if rig and rig.animation_data else None
        if not action or not action.get('tt_native_pose_fingerprint'):
            cls.poll_message_set('Select an imported character and load a native animation first')
            return False
        return True

    def draw(self, context):
        note(self.layout, context, 'Export edits to an existing body animation. Keep its original bones and duration.')
        self.layout.prop(self, 'rebuild_bank', text='Write PAK with the other source clips')
        note(self.layout, context, 'On: write a separate PAK bank. Off: write this AN4 clip only.')
        box = self.layout.box()
        box.label(text='Advanced: pose-only draft')
        box.prop(self, 'omit_auxiliary', text='Discard unsupported extra tables')
        note(box, context, 'Leave this off to preserve supported game data. A draft may not play correctly in-game.')

    def check(self, context):
        self.filename_ext = '.PAK' if self.rebuild_bank else '.AN4'
        self.filter_glob = '*.PAK' if self.rebuild_bank else '*.AN4'
        previous = self.filepath
        if Path(self.filepath).suffix.lower() in ('.an4', '.pak'):
            self.filepath = str(Path(self.filepath).with_suffix(self.filename_ext))
        return ExportHelper.check(self, context) or self.filepath != previous

    def execute(self, context):
        from .animation_export import export_action
        rig = find_rig(context.object)
        if rig is None:return {'CANCELLED'}
        try:
            report = export_action(context, rig, self.filepath, omit_auxiliary=self.omit_auxiliary,
                                   rebuild_bank=self.rebuild_bank)
        except (ValueError, OSError, KeyError, RuntimeError, OverflowError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Separate PAK bank written; other clips preserved. See the export report.' if self.rebuild_bank
                    else 'Separate AN4 written and decoded. See the export report for limits.')
        return {'FINISHED'}


class TTCHAR_OT_apply_preview(bpy.types.Operator):
    bl_idname = 'tt_character.apply_preview_settings'
    bl_label = 'Apply preview settings'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):return bool(context.scene.get('tt_character_preview'))

    def execute(self, context):
        from .preview_settings import apply_settings
        try:apply_settings(context, context.scene)
        except (ValueError, RuntimeError, KeyError) as error:
            self.report({'ERROR'}, str(error));return {'CANCELLED'}
        self.report({'INFO'}, 'Updated the viewing scene; imported source materials are preserved')
        return {'FINISHED'}


class TTCHAR_OT_restore_settings(bpy.types.Operator):
    bl_idname = 'tt_character.restore_settings'
    bl_label = 'Restore missing settings'
    bl_description = 'Restore settings unavailable after an addon update; keep existing values'

    def execute(self, context):
        restored = ensure_scene_settings()
        self.report({'INFO'}, f'Restored {len(restored)} missing settings; existing settings are preserved')
        return {'FINISHED'}


class TTCHAR_PT_settings(bpy.types.Panel):
    bl_label = 'Preview quality (advanced)'
    bl_idname = 'TTCHAR_PT_settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, 'tt_show_advanced', False) and context.scene.tt_workflow == 'ANIMATE'

    def draw(self, context):
        layout = self.layout; scene = context.scene
        if missing_scene_settings():
            layout.label(text='Some settings are unavailable.', icon='ERROR')
            layout.operator('tt_character.restore_settings', icon='FILE_REFRESH')
            return
        box = layout.box(); box.label(text='Viewing scene')
        if scene.tt_character_game not in ('LB1', 'TCS', 'FORTNITE'):
            box.prop(scene, 'tt_face_detail')
            if not normal_preservation_status()['supported']:
                box.label(text='Facial preview normals are approximate.', icon='ERROR')
                box.label(text='This Blender lacks normal preservation.')
        box.prop(scene, 'tt_preview_normals')
        strength = box.row(); strength.enabled = scene.tt_preview_normals
        strength.prop(scene, 'tt_preview_normal_strength')
        box.prop(scene, 'tt_preview_shading')
        box.prop(scene, 'tt_preview_display'); box.prop(scene, 'tt_preview_exposure')
        box.prop(scene, 'tt_preview_samples')
        box.operator('tt_character.apply_preview_settings', icon='SHADING_RENDERED')
        box.label(text='Create a preview, then apply changes.')


class TTCHAR_PT_navigation(bpy.types.Panel):
    bl_label = 'Model tools'
    bl_idname = 'TTCHAR_PT_navigation'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        if missing_scene_settings():
            self.layout.operator('tt_character.restore_settings', icon='FILE_REFRESH')
            return
        self.layout.prop(context.scene, 'tt_workflow', expand=True)
        self.layout.prop(context.scene, 'tt_show_advanced')


class TTCHAR_PT_tools(bpy.types.Panel):
    bl_label = 'Import'
    bl_idname = 'TTCHAR_PT_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, 'tt_workflow', 'IMPORT') == 'IMPORT'

    def draw(self, context):
        layout = self.layout
        game = context.scene.tt_character_game
        layout.label(text='Game for the next import')
        layout.prop(context.scene, 'tt_character_game', text='')
        game_name = next(label.split(' — ')[0] for key, label, _ in GAMES if key == game)
        if len(game_name) > 28:
            note(layout, context, game_name)
        if context.scene.tt_show_advanced:
            game_guidance(layout, context, game)
        elif game in ('LB1', 'TCS', 'FORTNITE'):
            note(layout, context, 'Models only. No animation or game export.')
        prefs = preferences(context)
        if prefs:
            layout.label(text='Game / extracted folder')
            layout.prop(prefs, game.lower(), text='')
        else:
            note(layout, context, 'Enable the addon in Preferences to save game folders. You can still open an extracted file below.')
        browse = layout.column()
        browse.enabled = bool(prefs and getattr(prefs, game.lower(), ''))
        browse.operator('import_scene.tt_game_character', text='Browse characters...', icon='VIEWZOOM')
        if not browse.enabled:
            note(layout, context, 'Choose the game folder to browse its characters.')
        if game == 'FORTNITE':
            from .fortnite_importer import find_fortnite
            if find_fortnite(context.object):
                layout.operator('tt_character.preview', text='Create static viewing scene', icon='SCENE_DATA')
            if prefs and prefs.fortnite_extractor and prefs.fortnite_settings:
                layout.operator('tt_character.fortnite_extract', text='Refresh outfit list').index_only = True
            return
        layout.operator('import_scene.tt_character', text='Open model file...' if game in ('LB1', 'TCS') else 'Open character / model...', icon='FILE_FOLDER')
        if context.scene.tt_show_advanced:
            note(layout, context, 'GHG / GSC: individual model.' if game in ('LB1', 'TCS') else 'CD: character with its parts. GHG / GSC: individual model.')


class TTCHAR_PT_import_options(bpy.types.Panel):
    bl_label = 'Import options / batch import'
    bl_idname = 'TTCHAR_PT_import_options'
    bl_parent_id = 'TTCHAR_PT_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (context.scene.tt_character_game != 'FORTNITE' and
                context.scene.tt_workflow == 'IMPORT' and context.scene.tt_show_advanced)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if missing_scene_settings():
            layout.operator('tt_character.restore_settings', icon='FILE_REFRESH')
            return
        if scene.tt_character_game not in ('LB1', 'TCS'):
            layout.prop(scene, 'tt_mesh_detail')
            layout.prop(scene, 'tt_costume_layers')
            layout.prop(scene, 'tt_import_attachments')
            layout.prop(scene, 'tt_game_handedness')
            note(layout, context, 'These settings apply to the next import.')
        layout.operator('tt_character.batch_import', text='Import several models...', icon='OUTLINER_COLLECTION')


class TTCHAR_PT_animations(bpy.types.Panel):
    bl_label = 'Animate'
    bl_idname = 'TTCHAR_PT_animations'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, 'tt_workflow', 'IMPORT') == 'ANIMATE'

    def draw(self, context):
        layout = self.layout
        rig = find_rig(context.object)
        if rig:
            layout.label(text=rig.name, icon='ARMATURE_DATA')
            layout.operator('import_anim.tt_an4', text='Load a separate AN4 file')
            layout.label(text='Find an animation')
            layout.prop(rig, 'tt_animation_search', text='', icon='VIEWZOOM')
            layout.operator('tt_character.refresh_animations')
            if rig.tt_animation_assets:
                layout.label(text=f'{len(rig.tt_animation_assets)} declared actions')
                layout.template_list('TTCHAR_UL_animation_assets', '', rig, 'tt_animation_assets', rig, 'tt_animation_asset_index', rows=6)
                layout.operator('tt_character.load_animation', icon='IMPORT')
            if rig.tt_clips:
                layout.label(text='Loaded clips')
                layout.template_list('TTCHAR_UL_clips', '', rig, 'tt_clips', rig, 'tt_clip_index', rows=5)
            else:
                note(layout, context, 'No clips loaded. Find an animation above or open a separate AN4 file.')
            active = rig.animation_data.action if rig.animation_data else None
            if active and active.get('tt_facial_playback'):
                faces = json.loads(active['tt_facial_playback'])
                status = faces['status']
                label = {
                    'animated': f'Face: {faces["animated_mesh_tracks"]} moving parts',
                    'static': 'Face: this clip holds a fixed expression',
                    'absent': 'Face: no expression tracks loaded',
                    'unavailable': 'Face: could not load expression tracks',
                }.get(status, 'Face: see TT AN4 report')
                layout.label(text=label, icon='INFO' if status != 'unavailable' else 'ERROR')
                if any(note['status']=='unavailable' for note in faces.get('notices', [])):
                    layout.label(text='Missing face parts: see TT AN4 report.')
                layout.operator('tt_character.animation_details', icon='INFO')
            playback = layout.row()
            playback.enabled = active is not None
            playback.operator('screen.animation_play', text='Play / Pause', icon='PLAY')
        else:
            if find_character(context.object):
                layout.operator('tt_character.preview', text='Create viewing scene', icon='SCENE_DATA')
                layout.operator('tt_character.preview', text='Create face render preview', icon='RENDER_STILL').composed_faces = True
                note(layout, context, 'This model has no supported body animation rig.')
            elif context.scene.tt_character_game in ('LB1', 'TCS', 'FORTNITE'):
                note(layout, context, 'The selected game has model import only; animation playback is unavailable.')
            else:
                note(layout, context, 'Select an imported character or its rig to browse animations. Then load a clip and press Play.')


class TTCHAR_PT_animation_options(bpy.types.Panel):
    bl_label = 'Custom clips / viewing scenes'
    bl_idname = 'TTCHAR_PT_animation_options'
    bl_parent_id = 'TTCHAR_PT_animations'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (find_rig(context.object) is not None and context.scene.tt_workflow == 'ANIMATE'
                and context.scene.tt_show_advanced)

    def draw(self, context):
        layout = self.layout
        layout.operator('tt_character.custom_clip', text='Copy active clip for editing', icon='DUPLICATE')
        layout.operator('tt_character.load_custom', text='Load replacement AN4 / PAK...', icon='FILE_FOLDER')
        note(layout, context, 'Load a native clip before copying it. For a replacement file, select its action in the game animation list.')
        layout.separator()
        layout.operator('tt_character.preview', text='Create viewing scene', icon='SCENE_DATA')
        layout.operator('tt_character.preview', text='Create face render preview', icon='RENDER_STILL').composed_faces = True
        note(layout, context, 'For face masks, use camera view in the viewing scene.')


class TTCHAR_PT_export(bpy.types.Panel):
    bl_label = 'Export'
    bl_idname = 'TTCHAR_PT_export'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'
    @classmethod
    def poll(cls, context):
        return getattr(context.scene, 'tt_workflow', 'IMPORT') == 'EXPORT'

    def draw(self, context):
        layout = self.layout
        character = find_character(context.object)
        if character:
            note(layout, context, 'Export selected: ' + character.name)
        elif context.scene.tt_character_game in ('LB1', 'TCS', 'FORTNITE'):
            note(layout, context, 'Game export is unavailable for this game in this addon.')
        else:
            note(layout, context, 'Select an imported character first. For animation export, also load a native clip.')
        layout.operator('tt_character.export_sources', text='Export model edits...', icon='EXPORT')
        layout.operator('tt_character.export_action', text='Export animation (AN4 / PAK)...', icon='EXPORT')
        note(layout, context, 'Existing parts and clips only. Writes separate files.')
        if context.scene.tt_show_advanced:
            note(layout, context, 'New bones, parts and animation slots are not supported here. Installing exports in the game is a separate step.')



def menu_import(self, context):
    self.layout.operator(IMPORT_SCENE_OT_tt_character.bl_idname)
    self.layout.operator(IMPORT_ANIM_OT_tt_an4.bl_idname)


def menu_export(self, context):
    self.layout.operator(TTCHAR_OT_export_sources.bl_idname)
    self.layout.operator(TTCHAR_OT_export_action.bl_idname)


_fortnite_job = False


class TTCHAR_OT_fortnite_extract(bpy.types.Operator):
    bl_idname = 'tt_character.fortnite_extract'
    bl_label = 'Extract LEGO Fortnite character'
    bl_options = {'REGISTER', 'UNDO'}
    index_only: BoolProperty(default=False)
    resource: StringProperty()

    @classmethod
    def poll(cls, context):
        return not _fortnite_job and context.mode == 'OBJECT'

    def invoke(self, context, event):
        global _fortnite_job
        from concurrent.futures import ThreadPoolExecutor
        from .fortnite_backend import run_backend
        from .fortnite_catalog import ExportLibrary
        prefs = preferences(context)
        try:
            self._selected = fortnite_source(prefs)
            self._root = self._selected.root
            if not prefs.fortnite_extractor or not prefs.fortnite_settings:
                raise ValueError('Set the optional Fortnite extractor and private settings in addon preferences')
            source = None
            if not self.index_only:
                entry = next((v for v in ExportLibrary(self._root).catalog() if v['resource']==self.resource), None)
                if not entry or not entry.get('backend_resource'):
                    raise ValueError('Character has no installed-game inventory reference')
                source = entry['backend_resource']
        except (ValueError, OSError, KeyError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._future = self._executor.submit(run_backend, bpy.path.abspath(prefs.fortnite_extractor),
            bpy.path.abspath(prefs.fortnite_settings), self._root, 'index' if self.index_only else 'export', source,
            paks=self._selected.paks)
        self._scene = context.scene
        _fortnite_job = True
        self._timer = context.window_manager.event_timer_add(.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set('Indexing LEGO Fortnite outfits...' if self.index_only else 'Extracting LEGO Fortnite model and textures...')
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        global _fortnite_job
        if not self._future.done():
            return {'PASS_THROUGH'}
        context.window_manager.event_timer_remove(self._timer)
        self._executor.shutdown(wait=False)
        _fortnite_job = False
        context.workspace.status_text_set(None)
        try:
            self._future.result()
            if context.scene != self._scene or context.scene.tt_character_game != 'FORTNITE' or self._selected != fortnite_source(preferences(context)):
                self.report({'INFO'}, 'Extraction complete; return to the LEGO Fortnite browser to import')
            elif self.index_only:
                bpy.ops.import_scene.tt_game_character('INVOKE_DEFAULT')
            else:
                from .fortnite_importer import import_fortnite
                obj, report = import_fortnite(context, self._root, self.resource)
                self.report({'INFO'}, 'Imported ' + obj.name + '; see TT LEGO Fortnite report for shader limits')
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}


class TTCHAR_FH_model(bpy.types.FileHandler):
    bl_idname = 'TTCHAR_FH_model'
    bl_label = 'TT Character / Model'
    bl_import_operator = 'import_scene.tt_character'
    bl_file_extensions = '.cd;.ghg;.gsc'

    @classmethod
    def poll_drop(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'


class TTCHAR_FH_an4(bpy.types.FileHandler):
    bl_idname = 'TTCHAR_FH_an4'
    bl_label = 'TT Character Animation'
    bl_import_operator = 'import_anim.tt_an4'
    bl_file_extensions = '.an4'

    @classmethod
    def poll_drop(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and IMPORT_ANIM_OT_tt_an4.poll(context))


CLASSES = (TTCHAR_OT_batch_import, TTCHAR_Preferences, TTCHAR_Clip, TTCHAR_AnimationAsset, IMPORT_SCENE_OT_tt_character, IMPORT_SCENE_OT_tt_game_character, IMPORT_ANIM_OT_tt_an4, TTCHAR_UL_clips, TTCHAR_UL_animation_assets, TTCHAR_OT_refresh_animations, TTCHAR_OT_load_animation, TTCHAR_OT_custom_clip, TTCHAR_OT_load_custom, TTCHAR_OT_animation_details, TTCHAR_OT_preview, TTCHAR_OT_export_sources, TTCHAR_OT_export_action, TTCHAR_PT_navigation, TTCHAR_PT_tools, TTCHAR_PT_import_options, TTCHAR_PT_animations, TTCHAR_PT_animation_options, TTCHAR_PT_export, TTCHAR_PT_settings, TTCHAR_OT_apply_preview, TTCHAR_OT_restore_settings, TTCHAR_OT_fortnite_extract, TTCHAR_FH_model, TTCHAR_FH_an4)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.tt_clips = CollectionProperty(type=TTCHAR_Clip)
    bpy.types.Object.tt_clip_index = IntProperty(default=0, update=set_clip)
    bpy.types.Object.tt_animation_assets = CollectionProperty(type=TTCHAR_AnimationAsset)
    bpy.types.Object.tt_animation_asset_index = IntProperty(default=0)
    bpy.types.Object.tt_animation_search = StringProperty(name='Search animations')
    bpy.types.Scene.tt_character_game = EnumProperty(name='Game', items=GAMES, default='LB3')
    ensure_scene_settings()
    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    del bpy.types.Object.tt_clip_index
    del bpy.types.Object.tt_clips
    del bpy.types.Object.tt_animation_assets
    del bpy.types.Object.tt_animation_asset_index
    del bpy.types.Object.tt_animation_search
    del bpy.types.Scene.tt_character_game
    unregister_scene_settings()
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

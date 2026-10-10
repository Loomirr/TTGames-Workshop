"""Direct native character and animation import, independent of the CU3 addon."""
bl_info = {'name': 'TT Character and Animation Importer', 'author': 'Loomirr and contributors',
           'version': (0, 5, 15), 'blender': (4, 4, 0), 'category': 'Import-Export',
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

GAMES = [('LB3', 'LEGO Batman 3', 'Observed DX11 models'), ('LMSH1', 'LEGO Marvel Super Heroes', 'Observed NXG models'),
         ('HOBBIT', 'LEGO The Hobbit', 'Observed PC NXG models'),
         ('AVENGERS', "LEGO Marvel's Avengers", 'Observed PC DX11 characters'),
         ('FORTNITE', 'LEGO Fortnite', 'Static models from exported LEGO recipes/baked meshes; no animations')]
_catalog = []
_catalog_assets = None
_catalog_source = None


class TTCHAR_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    lb3: StringProperty(name='LB3 game / extracted folder', subtype='DIR_PATH')
    lmsh1: StringProperty(name='LMSH1 game / extracted folder', subtype='DIR_PATH')
    avengers: StringProperty(name='Avengers game / extracted folder', subtype='DIR_PATH')
    hobbit: StringProperty(name='The Hobbit game / extracted folder', subtype='DIR_PATH')
    fortnite: StringProperty(name='LEGO Fortnite game / Paks / exported folder', subtype='DIR_PATH', description='Fortnite installation, Content/Paks folder, or an existing Exports/Models library; archive exports use a separate cache')
    fortnite_extractor: StringProperty(name='Optional LEGO Fortnite extractor', subtype='FILE_PATH', description='Separately built Workshop.Fortnite.Extractor executable; no external tools are bundled')
    fortnite_settings: StringProperty(name='Private Fortnite extractor settings', subtype='FILE_PATH', description='Private JSON with mappings, key-file and Oodle paths; Paks mode sets source and cache output automatically')
    cache: StringProperty(name='Optional asset cache', subtype='DIR_PATH')

    def draw(self, context):
        for prop in ('lb3', 'lmsh1', 'hobbit', 'avengers', 'fortnite', 'fortnite_extractor', 'fortnite_settings', 'cache'):
            self.layout.prop(self, prop)


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
        if not name.endswith('.cd'):
            continue
        for entry in entries:
            path = entry[1]['path'] if isinstance(entry, tuple) else entry.relative_to(assets.root).as_posix()
            upper = path.upper()
            categories = ('/MINIFIG', '/SMALL/', '/BIGFIG', '/BIGGERFIG', '/CREATURE')
            if (any(c in '/' + upper for c in categories) and '/SUPER_CHAR' not in upper) or '/' not in path:
                paths.add(path)
    return [(p, Path(p).stem, p) for p in sorted(paths)]


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
            path = _catalog_assets.find_exact(self.resource)
            rig, report = import_character(context, path, Path(bpy.path.abspath(getattr(prefs, game.lower()))), game,
                cache=Path(bpy.path.abspath(prefs.cache)) if prefs.cache else None, assets=_catalog_assets,
                attachments=context.scene.tt_import_attachments, layer_mode=context.scene.tt_costume_layers,
                highest_detail=context.scene.tt_mesh_detail == 'HIGHEST')
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
    mesh_detail: EnumProperty(name='Mesh detail', items=[('HIGHEST', 'Highest detail', 'Select the nearest verified native LOD'),
        ('AUTHORED', 'Authored binding', 'Inspect the original display binding without LOD override')], default='HIGHEST')
    layers: EnumProperty(name='Costume layers', items=[('default', 'Default costume', 'Use native default character layers'),
        ('cutscene', 'Cutscene costume', 'Use native cutscene layers'), ('authored', 'Authored selection flags', 'Original reader selection flags')], default='default')

    def invoke(self, context, event):
        ensure_scene_settings()
        # Blender remembers file-browser operator settings separately from the
        # sidebar. Always start this interactive import with the visible game.
        self.game = context.scene.tt_character_game
        self.mesh_detail = context.scene.tt_mesh_detail
        self.layers = context.scene.tt_costume_layers
        self.attachments = context.scene.tt_import_attachments
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
            rig, report = import_character(context, Path(self.filepath), Path(bpy.path.abspath(root)), self.game,
                definition_path=Path(bpy.path.abspath(self.definition)) if self.definition else None,
                cache=Path(bpy.path.abspath(prefs.cache)) if prefs and prefs.cache else None,
                attachments=self.attachments, layer_mode=self.layers,
                highest_detail=self.mesh_detail == 'HIGHEST')
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

    def execute(self, context):
        rig = find_rig(context.object)
        paths = [Path(self.directory) / f.name for f in self.files] if self.files else [Path(self.filepath)]
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
    bl_label = 'Export loose native files / supported edits'
    directory: StringProperty(name='New export folder', subtype='DIR_PATH')
    face_edits: BoolProperty(name='Write supported existing face target edits', default=True,
        description='Write existing targets while preserving facial Basis and topology')
    mesh_edits: BoolProperty(name='Write supported vertex and skin edits', default=True,
        description='Positions, UVs, colors, normals and existing palette weights; preserve topology, bounds and skeleton')

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
        self.report({'WARNING'}, f'{len(report["files"])} loose files exported. Existing vertex/face edits only; see TT_Source_Export.json for limits.')
        return {'FINISHED'}


class TTCHAR_OT_export_action(bpy.types.Operator, ExportHelper):
    bl_idname = 'tt_character.export_action'
    bl_label = 'Export active AN4 clip (experimental)'
    filename_ext = '.AN4'
    filter_glob: StringProperty(default='*.AN4', options={'HIDDEN'})
    omit_auxiliary: BoolProperty(name='Omit unsupported events / auxiliary tables', default=False,
        description='Explicitly allow pose-only export when original ANI-D has auxiliary tables; gameplay cues will need separate setup')

    def execute(self, context):
        from .animation_export import export_action
        rig = find_rig(context.object)
        if rig is None:return {'CANCELLED'}
        try:
            report = export_action(context, rig, self.filepath, omit_auxiliary=self.omit_auxiliary)
        except (ValueError, OSError, KeyError, RuntimeError, OverflowError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        self.report({'WARNING'}, 'Separate AN4 written and decoded; experimental, no PAK/DAT writing or in-game validation')
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
    bl_label = 'Import and preview settings'
    bl_idname = 'TTCHAR_PT_settings'
    bl_parent_id = 'TTCHAR_PT_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TT Character'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout; scene = context.scene
        if missing_scene_settings():
            layout.label(text='Some settings are unavailable.', icon='ERROR')
            layout.operator('tt_character.restore_settings', icon='FILE_REFRESH')
            return
        if scene.tt_character_game != 'FORTNITE':
            box = layout.box(); box.label(text='Next character import')
            box.prop(scene, 'tt_mesh_detail'); box.prop(scene, 'tt_costume_layers')
            box.prop(scene, 'tt_import_attachments')
            box.label(text='Change detail/costume, then reimport.')
        box = layout.box(); box.label(text='Viewing scene')
        if scene.tt_character_game != 'FORTNITE':
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
        if context.scene.tt_character_game == 'FORTNITE':
            from .fortnite_importer import find_fortnite
            character = find_fortnite(context.object)
            if character:
                layout.label(text=character.name, icon='MESH_DATA')
                layout.operator('tt_character.preview', text='Create static character preview scene', icon='SCENE_DATA')
            layout.label(text='Static models, source colors, printing and normals.')
            layout.label(text='Game/Paks folder or existing export library.')
            layout.label(text='Facial atlas and special shaders remain approximate.')
            if prefs and prefs.fortnite_extractor and prefs.fortnite_settings:
                layout.operator('tt_character.fortnite_extract', text='Refresh installed LEGO outfit index').index_only=True
            return
        layout.operator('import_scene.tt_character', text='Import character / model')
        layout.operator('import_anim.tt_an4', text='Import AN4 animations')
        rig = find_rig(context.object)
        if rig:
            layout.label(text=rig.name, icon='ARMATURE_DATA')
            layout.operator('tt_character.preview', icon='SCENE_DATA')
            layout.label(text='Use camera view in the preview for facial masking.')
            layout.operator('tt_character.preview', text='Create composed face preview', icon='RENDER_STILL').composed_faces=True
            layout.prop(rig, 'tt_animation_search', text='', icon='VIEWZOOM')
            layout.operator('tt_character.refresh_animations')
            if rig.tt_animation_assets:
                layout.label(text=f'{len(rig.tt_animation_assets)} declared actions')
                layout.template_list('TTCHAR_UL_animation_assets', '', rig, 'tt_animation_assets', rig, 'tt_animation_asset_index', rows=6)
                layout.operator('tt_character.load_animation', icon='IMPORT')
            layout.label(text='Loaded clips')
            layout.template_list('TTCHAR_UL_clips', '', rig, 'tt_clips', rig, 'tt_clip_index', rows=5)
            layout.operator('screen.animation_play', text='Play / Pause', icon='PLAY')
            layout.operator('tt_character.export_sources', icon='EXPORT')
            if rig.animation_data and rig.animation_data.action:
                layout.operator('tt_character.export_action', icon='EXPORT')
            layout.label(text='Select a clip; Space plays the timeline.')
        else:
            if find_character(context.object):
                layout.operator('tt_character.preview', icon='SCENE_DATA')
                layout.operator('tt_character.preview', text='Create composed face preview', icon='RENDER_STILL').composed_faces=True
                layout.operator('tt_character.export_sources', icon='EXPORT')
            else:
                layout.label(text='Select an imported character or its rig.')
        layout.label(text='Experimental materials and face preview.')


def menu_import(self, context):
    self.layout.operator(IMPORT_SCENE_OT_tt_character.bl_idname)
    self.layout.operator(IMPORT_ANIM_OT_tt_an4.bl_idname)


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


CLASSES = (TTCHAR_Preferences, TTCHAR_Clip, TTCHAR_AnimationAsset, IMPORT_SCENE_OT_tt_character, IMPORT_SCENE_OT_tt_game_character, IMPORT_ANIM_OT_tt_an4, TTCHAR_UL_clips, TTCHAR_UL_animation_assets, TTCHAR_OT_refresh_animations, TTCHAR_OT_load_animation, TTCHAR_OT_preview, TTCHAR_OT_export_sources, TTCHAR_OT_export_action, TTCHAR_PT_tools, TTCHAR_PT_settings, TTCHAR_OT_apply_preview, TTCHAR_OT_restore_settings, TTCHAR_OT_fortnite_extract)


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


def unregister():
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

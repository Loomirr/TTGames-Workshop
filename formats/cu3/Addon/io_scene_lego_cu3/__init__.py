bl_info = {
    'name': 'LEGO CU3 Cutscene Importer (Experimental)',
    'author': 'Loomirr',
    'version': (0, 1, 16),
    'blender': (4, 4, 0),
    'location': 'File > Import > LEGO CU3 cutscene',
    'description': 'Assemble supported cutscene actors, attachments, materials and cameras from native companion assets',
    'category': 'Import-Export',
}

import bpy
from bpy.props import StringProperty, EnumProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from .cu3 import Cutscene, FormatError
from .skeleton import read_skeleton
from .cinematic import visibility
from .blender_import import inspect_scene, create_rig, duplicate_rig, check_rig, apply_pose, apply_actor_visibility, prepare_pose


class TT_CU3_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    lb3_asset_root: StringProperty(name='Batman 3 game or asset folder', subtype='DIR_PATH')
    lmsh1_asset_root: StringProperty(name='Marvel Super Heroes game or asset folder', subtype='DIR_PATH')
    cache_root: StringProperty(name='Extracted companion cache', subtype='DIR_PATH', description='Optional cache outside installed games; blank uses the local TTGamesWorkshop asset cache')

    def draw(self, context):
        self.layout.label(text='Saved companion folders for scene imports')
        self.layout.prop(self,'lb3_asset_root')
        self.layout.prop(self,'lmsh1_asset_root')
        self.layout.prop(self,'cache_root')
        self.layout.label(text='Installed game folders: extracts needed companions automatically.')
        self.layout.label(text='CU3 stores animation/references; models and textures are separate files.')


def assembly_profile(cut, requested):
    if requested != 'AUTO':return requested
    profile = {18:'LMSH1',19:'LB3'}.get(cut.version)
    if profile is None:
        raise FormatError(f'Full scene assembly is not implemented for CU3 version {cut.version}. Inspect scene references is available separately; it does not create meshes.')
    return profile


class IMPORT_SCENE_OT_lego_cu3(bpy.types.Operator, ImportHelper):
    bl_idname = 'import_scene.lego_cu3'
    bl_label = 'Import LEGO CU3 cutscene'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext = '.cu3'
    filter_glob: StringProperty(default='*.cu3;*.CU3', options={'HIDDEN'})
    mode: EnumProperty(name='Import mode', items=[
        ('ASSEMBLE', 'Assemble available scene assets', 'Import actors, costume materials and cameras from an installed game or extracted asset folder; report missing systems'),
        ('DEPENDENCIES', 'Check companion files', 'Report character definitions, models, active attachments and costume textures before building a scene'),
        ('INSPECT', 'Inspect scene references', 'Read actor names, timeline and source data report'),
        ('SKELETONS', 'Create source armatures', 'Create armatures for actors matching the supplied GHG/JSON source skeleton'),
        ('SELECTED', 'Animate selected source rig', 'Apply one actor track to a compatible source armature')], default='ASSEMBLE')
    skeleton_path: StringProperty(name='Source skeleton GHG / JSON', subtype='FILE_PATH', description='Uncompressed matching GHG or extracted source skeleton JSON')
    actor_filter: StringProperty(name='Actor name / filter', description='Exact actor name, or substring; required to identify one actor when animating a selected rig')
    record_index: IntProperty(name='Animation record', default=0, min=0)
    copy_rig: BoolProperty(name='Work on a copy', default=True)
    place_in_scene: BoolProperty(name='Use source scene movement', default=False, description='Apply static or animated actor placement separately from skeletal motion')
    source_visibility: BoolProperty(name='Use source visibility', default=True, description='Hide shot-specific character instances and their children according to source tracks')
    asset_root: StringProperty(name='Game or extracted asset folder', subtype='DIR_PATH')
    static_environment: BoolProperty(name='Recovered static environment (experimental)', default=True, description='Build bounded static stage draws from declared level resources; visibility, nested scenes and source lighting remain incomplete')
    game_profile: EnumProperty(name='Game / asset format', items=[('AUTO','Detect from CU3','Detect the verified LMSH1/LB3 versions; other games remain reference-only'),('LB3','LEGO Batman 3 PC DX11','Observed DX11 models'),('LMSH1','LEGO Marvel Super Heroes PC NXG','Observed NXG models')], default='AUTO')
    cameras: BoolProperty(name='Import source cameras', default=False, description='Import observed source camera tracks and shot markers into the current scene')

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'mode')
        if self.mode in ('ASSEMBLE','DEPENDENCIES'):
            layout.prop(self, 'game_profile')
            layout.prop(self, 'asset_root')
            if self.mode=='ASSEMBLE':layout.prop(self,'static_environment')
            layout.label(text='Blank uses the saved folder for the detected game.')
            layout.label(text='Checks declared character companion files.' if self.mode=='DEPENDENCIES' else 'Creates a new scene and a missing-assets report.', icon='INFO')
            layout.label(text='Stage visibility, props, lighting, audio and effects still need work.')
        elif self.mode != 'INSPECT':
            layout.prop(self, 'skeleton_path')
            layout.prop(self, 'actor_filter')
            layout.prop(self, 'record_index')
            layout.prop(self, 'place_in_scene')
            layout.prop(self, 'source_visibility')
            if self.mode == 'SELECTED':
                layout.prop(self, 'copy_rig')
        if self.mode not in ('ASSEMBLE','DEPENDENCIES'):layout.prop(self, 'cameras')

    def execute(self, context):
        try:
            cut = Cutscene(self.filepath)
            source = context.view_layer.objects.active
            if self.mode in ('ASSEMBLE','DEPENDENCIES'):
                profile = assembly_profile(cut,self.game_profile)
                addon = context.preferences.addons.get(__package__)
                preferences = addon.preferences if addon else None
                preference_field = 'lb3_asset_root' if profile=='LB3' else 'lmsh1_asset_root'
                asset_root = self.asset_root.strip() or (getattr(preferences,preference_field,'') if preferences else '')
                if not asset_root:
                    raise FormatError('Choose the installed game or extracted asset folder once; it is remembered for this game. CU3 alone does not contain the companion meshes and textures.')
                asset_root = bpy.path.abspath(asset_root)
                from .asset_index import open_assets
                cache_root = getattr(preferences,'cache_root','') if preferences else ''
                assets = open_assets(asset_root, profile, bpy.path.abspath(cache_root) if cache_root else None)
                if preferences and self.asset_root.strip():
                    setattr(preferences,preference_field,asset_root)
            if self.mode == 'DEPENDENCIES':
                import json
                from .dependencies import dependency_report
                from .scene_inputs import prepare_resources
                resolver, configuration = prepare_resources(cut, assets, profile)
                report = dependency_report(cut, resolver)
                report['configuration'] = configuration
                if hasattr(assets,'get_info'):report['asset_source'] = assets.get_info()
                text = bpy.data.texts.new(cut.name+' / companion files')
                text.write(json.dumps(report,indent=2))
                self.report({'INFO'}, f'{report["resolved_resources"]} resources found; {report["missing_resources"]} missing, {report["unresolved_resources"]} unresolved. See "{text.name}" in Text Editor.')
                return {'FINISHED'}
            if self.mode == 'ASSEMBLE':
                from .scene_assembly import assemble
                from .playback_ui import show_scene, prepare_saved_preview
                scene, report = assemble(cut, asset_root, profile, context, assets=assets, static_environment=self.static_environment)
                prepare_saved_preview(context,scene)
                if context.area and context.area.type=='VIEW_3D':show_scene(context, scene)
                self.report({'WARNING'}, f'Imported {len(report["actors"])} model instances; see "{scene["tt_import_report"]}" for missing assets and systems')
                return {'FINISHED'}
            if self.cameras:
                from .cinematic_blender import import_cameras
                import_cameras(cut, context.scene)
            if self.mode == 'INSPECT':
                inspect_scene(cut, context.scene)
                if not cut.actors:
                    self.report({'WARNING'}, 'No actors in this CU3. It may be a control/audio-only file; choose an animated A/B/C segment if present.')
                else:self.report({'INFO'}, f'{cut.name}: {len(cut.actors)} actor nodes, {cut.frames} frames at {cut.fps:g} FPS')
                return {'FINISHED'}
            if not self.skeleton_path:
                raise FormatError('Choose the matching source skeleton GHG or JSON')
            rigdata = read_skeleton(bpy.path.abspath(self.skeleton_path))
            actors = [a for a in cut.actors if len(a['records']) > self.record_index and
                      a['records'][self.record_index]['animation'].nodes == len(rigdata['joints'])]
            exact = [a for a in actors if a['name'].lower() == self.actor_filter.lower()]
            actors = exact or [a for a in actors if self.actor_filter.lower() in a['name'].lower()]
            if not actors:
                counts=sorted({a['records'][self.record_index]['animation'].nodes for a in cut.actors if len(a['records'])>self.record_index})
                if not counts:
                    raise FormatError('No animated actor record in this CU3. Choose an animated segment (often A/B/C) or another record index.')
                raise FormatError(f'No matching actor/skeleton/record: source rig has {len(rigdata["joints"])} joints; this record has joint counts {counts}. Inspect actor names and use a matching source GHG.')
            if self.mode == 'SELECTED':
                if len(actors) != 1:
                    raise FormatError('Use an exact actor name: this filter matches multiple actors')
                if source is None:
                    raise FormatError('Select the matching source armature before importing')
                check_rig(source, rigdata)
            # Validate supported records before changing scene data.
            for a in actors:
                prepare_pose(a['records'][self.record_index]['animation'])
                if self.source_visibility or self.place_in_scene:
                    outer = a.get('visibility_animation')
                    if outer:
                        outer.prepare(scene_channels=True)
                if self.source_visibility:
                    visibility(cut, a)
            collection = inspect_scene(cut, context.scene)
            for a in actors:
                if self.mode == 'SELECTED':
                    rig = duplicate_rig(source, 'CU3 / ' + a['name'], collection) if self.copy_rig else source
                else:
                    rig = create_rig(rigdata, 'CU3 / ' + a['name'], collection)
                apply_pose(cut, a, self.record_index, rig, rigdata, self.place_in_scene, scene_channels=True)
                if self.source_visibility:
                    apply_actor_visibility(cut, a, [rig] + list(rig.children_recursive))
            context.scene.frame_set(1)
            self.report({'INFO'}, f'Imported {len(actors)} source skeletal track(s); scene systems remain experimental')
            return {'FINISHED'}
        except (ValueError, OSError, UnicodeError, KeyError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


def menu_import(self, context):
    self.layout.operator(IMPORT_SCENE_OT_lego_cu3.bl_idname, text='LEGO CU3 cutscene (.cu3) [experimental]')


def register():
    from . import face_edit_ui, face_preview_ui, playback_ui
    bpy.utils.register_class(TT_CU3_Preferences)
    bpy.utils.register_class(IMPORT_SCENE_OT_lego_cu3)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    face_edit_ui.register()
    face_preview_ui.register()
    playback_ui.register()


def unregister():
    from . import face_edit_ui, face_preview_ui, playback_ui
    playback_ui.unregister()
    face_preview_ui.unregister()
    face_edit_ui.unregister()
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(IMPORT_SCENE_OT_lego_cu3)
    bpy.utils.unregister_class(TT_CU3_Preferences)

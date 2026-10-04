"""Assemble supported source actors and cameras from an extracted asset root.

Every omitted resource/system is recorded in a Blender text report. This is
an incremental importer, not a claim of complete engine reconstruction.
"""
import json
import re
from pathlib import Path
import bpy
from mathutils import Matrix
from .cu3 import FormatError
from .asset_index import AssetIndex
from .definitions import character_definition
from .native_model_blender import load_model, create_model
from .costume_materials import CostumeMaterials
from .cinematic_blender import import_cameras
from .blender_import import C, CI, row_matrix, apply_pose, apply_actor_visibility, prepare_pose
from .cinematic import visibility
from .morph import actor_morph_animation, animate_shape_keys
from .face_live import prepare_live


STORES = ('scenes','objects','collections','meshes','armatures','cameras','lights',
          'materials','images','actions','shape_keys','node_groups','texts','worlds')


def snapshot():
    return {name:set(getattr(bpy.data,name)) for name in STORES}


def rollback(before):
    bpy.data.batch_remove(ids={item for name in STORES for item in getattr(bpy.data,name) if item not in before[name]})


def assemble(cut, asset_root, profile, context):
    if cut.version == 30:
        raise FormatError('DCSV ANI-E and cinematic assembly remain unverified; use reference inspection')
    if cut.version != {'LB3':19, 'LMSH1':18}[profile]:
        raise FormatError('Cutscene version does not match the selected game profile')
    suffix = {'LB3':'_DX11', 'LMSH1':'_NXG'}[profile]
    assets = AssetIndex(asset_root)
    initial, original = snapshot(), context.scene
    report = {'source':str(cut.path), 'profile':profile, 'actors':[], 'materials':[], 'issues':[],
              'limitations':['Environment, rigid props, audio, source lighting, events and VFX are not yet automatically assembled.',
                             'Shared texture slots, layered materials and some native layouts remain unresolved.',
                             'Camera framing and native shaders still need comparison against game playback.']}
    models, definitions = {}, {}
    materials = CostumeMaterials(assets, suffix, report['materials'])
    def resource(reference):
        definition_path = assets.find(reference, extension='.CD', required=False)
        definition = None
        if definition_path:
            if definition_path not in definitions:
                definitions[definition_path] = character_definition(definition_path)
            definition = definitions[definition_path]
            fields = definition['character']
            reference = fields.get('Override Model File') or fields['Skeleton Name']
        path = assets.find(reference, suffix, '.GHG', required=False) or assets.find(reference, suffix, '.GSC')
        if path not in models:
            models[path] = load_model(path)
        return models[path], definition
    imported = set()
    def build(actor, model, definition, name, parent=None, depth=0):
        if depth > 8:
            raise FormatError('Attachment nesting exceeds the verified limit')
        skeleton = model['skeleton']
        record = None
        if actor:
            if skeleton is None:
                raise FormatError('Actor pose requires a native skeleton')
            matches = [i for i,r in enumerate(actor['records']) if r['animation'].nodes==len(skeleton['joints'])]
            if len(matches) != 1:
                raise FormatError('Source model does not identify one compatible actor pose record')
            record = matches[0]
            prepare_pose(actor['records'][record]['animation'])
            visibility(cut, actor)
        rig, parts = create_model(model, name, collection, definition, materials)
        if parent:
            parent_rig, parent_skeleton, attachment = parent
            logical = attachment['Locator']
            remap = parent_skeleton['post_poi_bytes']
            if not 0 <= logical < len(remap) or remap[logical] >= len(parent_skeleton['points_of_interest']):
                raise FormatError('Attachment locator is outside native skeleton table')
            point = parent_skeleton['points_of_interest'][remap[logical]]
            anchor = bpy.data.objects.new(name+' / native attachment', None)
            collection.objects.link(anchor)
            constraint = anchor.constraints.new('COPY_TRANSFORMS')
            constraint.target = parent_rig
            constraint.subtarget = parent_skeleton['joints'][point['joint']]['name']
            rig.parent = anchor
            rig.matrix_parent_inverse = Matrix.Identity(4)
            rig.matrix_basis = C @ row_matrix(point['matrix']) @ row_matrix(list(attachment['Object Offset'])) @ CI
        if actor:
            apply_pose(cut, actor, record, rig, skeleton, place_in_scene=parent is None)
            apply_actor_visibility(cut, actor, [rig]+[p for p in parts if p.get('tt_colour_write_mask')!=0])
            morph = actor_morph_animation(cut, actor)
            if morph:
                for obj in parts:
                    if obj.data.shape_keys:
                        animate_shape_keys(obj, morph, cut.frames)
            imported.add(actor['index'])
        row = {'name':name, 'model':str(model['source']), 'meshes':len(parts), 'animated':actor is not None}
        report['actors'].append(row)
        if definition and skeleton:
            character = definition['character']
            mask = character.get('Default Layers',0) if character.get('Use Default Layers',-1)&2 else character.get('Cutscene Layers',0)
            for item in definition['objects']:
                if item['class']!='Character Attachment':
                    continue
                attachment = item['fields']
                if 'Resource File' not in attachment:
                    report['issues'].append({'actor':name, 'issue':'Attachment resource fields are not decoded'})
                    continue
                if not mask & (1 << attachment['Layer']):
                    continue
                before = snapshot()
                child_rows = len(report['actors'])
                child_imported = imported.copy()
                try:
                    child_model, child_definition = resource(attachment['Resource File'])
                    child_skeleton = child_model['skeleton']
                    matches = []
                    if actor and child_skeleton:
                        declared = {child_skeleton['joints'][0]['name'].casefold()}
                        if child_definition:
                            declared.add(child_definition['character']['Skeleton Name'].casefold())
                        matches = [a for a in cut.actors if a['parent']==actor['index'] and a['name'].casefold() in declared]
                    if len(matches)>1:
                        raise FormatError('Attachment matches multiple source animation nodes')
                    child_actor = matches[0] if matches else None
                    child_rig, child_parts = build(child_actor, child_model, child_definition,
                                                   name+' / '+attachment['Resource File'],
                                                   (rig,skeleton,attachment), depth+1)
                    if actor and not child_actor:
                        apply_actor_visibility(cut, actor, [child_rig]+[p for p in child_parts if p.get('tt_colour_write_mask')!=0])
                except (ValueError, OSError, KeyError, RuntimeError) as error:
                    rollback(before)
                    materials.images.clear()
                    del report['actors'][child_rows:]
                    imported.intersection_update(child_imported)
                    report['issues'].append({'actor':name, 'resource':attachment['Resource File'], 'issue':str(error)})
        return rig, parts
    try:
        scene = bpy.data.scenes.new(cut.name+' / imported scene')
        context.window.scene = scene
        scene.render.fps = max(1,round(cut.fps))
        scene.render.fps_base = scene.render.fps/cut.fps
        scene.frame_start, scene.frame_end = 1, cut.frames
        scene.render.engine = 'BLENDER_EEVEE'
        scene.view_settings.view_transform = 'Standard'
        scene.sync_mode = 'FRAME_DROP'
        scene.world = bpy.data.worlds.new('Inspection lighting — source lighting unresolved')
        scene.world.use_nodes = True
        scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8
        light_data = bpy.data.lights.new('Inspection sun — source lighting unresolved', 'SUN')
        light_data.energy = 2
        light = bpy.data.objects.new(light_data.name, light_data)
        scene.collection.objects.link(light)
        light.rotation_euler = (.4, -.5, -.5)
        collection = bpy.data.collections.new('Native source actors')
        scene.collection.children.link(collection)
        camera_before = snapshot()
        try:
            report['camera'] = import_cameras(cut, scene)
        except (ValueError, KeyError) as error:
            rollback(camera_before)
            report['issues'].append({'system':'cameras','issue':str(error)})
        for index, actor in enumerate(cut.actors):
            actor['index'] = index
        for actor in cut.actors:
            if actor['parent'] is not None or not actor['records']:
                continue
            before = snapshot()
            rows_before = len(report['actors'])
            imported_before = imported.copy()
            try:
                reference = re.sub(r'^instance[^_]*_', '', actor['name'], flags=re.I)
                model, definition = resource(reference)
                build(actor, model, definition, actor['name'])
            except (ValueError, OSError, KeyError, RuntimeError) as error:
                rollback(before)
                report['actors'] = report['actors'][:rows_before]
                imported = imported_before
                materials.images.clear()
                report['issues'].append({'actor':actor['name'],'issue':str(error)})
        report['unassembled_actor_nodes'] = [a['name'] for a in cut.actors if a['index'] not in imported]
        if scene.camera:
            report['live_preview'] = prepare_live(scene, detail_level=3)
        scene.frame_set(1)
        scene['cu3_source'] = str(cut.path)
        scene['tt_import_complete'] = False
        report['complete'] = False
        text = bpy.data.texts.new(cut.name+' / import report')
        text.write(json.dumps(report,indent=2))
        scene['tt_import_report'] = text.name
        return scene, report
    except Exception:
        context.window.scene = original
        rollback(initial)
        raise

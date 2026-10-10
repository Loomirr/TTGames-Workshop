"""Assemble supported source actors and cameras from an extracted asset root.

Every omitted resource/system is recorded in a Blender text report. This is
an incremental importer, not a claim of complete engine reconstruction.
"""
import json
from pathlib import Path
import bpy
from mathutils import Matrix
from .cu3 import FormatError
from .asset_index import open_assets
from .dependencies import ResourceResolver, dependency_report, actor_resource, active_attachments
from .native_model_blender import load_model, create_model
from .costume_materials import CostumeMaterials
from .cinematic_blender import import_cameras
from .blender_import import C, CI, row_matrix, apply_pose, apply_actor_visibility, prepare_pose
from .cinematic import visibility
from .morph import actor_morph_animation, animate_shape_keys
from .face_live import prepare_live
from .scene_inputs import prepare_resources
from .profiles import profile_identity, validate_profile_model
from .resource_identity import model_resource_identity
from .animation_ownership import attachment_tracks
from .skeleton import attachment_locator


STORES = ('scenes','objects','collections','meshes','armatures','cameras','lights',
          'materials','images','actions','shape_keys','node_groups','texts','worlds')


def snapshot():
    return {name:set(getattr(bpy.data,name)) for name in STORES}


def rollback(before):
    bpy.data.batch_remove(ids={item for name in STORES for item in getattr(bpy.data,name) if item not in before[name]})


def assemble(cut, asset_root, profile, context, *, assets=None, static_environment=True):
    if cut.version == 30:
        raise FormatError('DCSV ANI-E and cinematic assembly remain unverified; use reference inspection')
    if assets is None:assets = open_assets(asset_root, profile)
    resolver, configuration = prepare_resources(cut, assets, profile)
    dependencies = dependency_report(cut, resolver)
    suffix = resolver.suffix
    initial, original = snapshot(), context.scene
    report = {'source':str(cut.path), 'profile':profile, 'actors':[], 'materials':[], 'issues':[],
              'profile_identity':profile_identity(profile,structure_versions={'CU3':cut.version,'embedded_AN4':getattr(cut,'tree_version',None)}),
              'dependencies':dependencies,
              'configuration':configuration,
              'limitations':['Recovered static stage draws approximate environment visibility; nested scenes, rigid props, audio, source lighting, events and VFX are not yet automatically assembled.',
                             'Shared texture slots, layered materials and some native layouts remain unresolved.',
                             'Camera framing and native shaders still need comparison against game playback.']}
    models = {}
    materials = CostumeMaterials(assets, suffix, report['materials'])
    def resource(reference):
        resolved = resolver.resolve(reference)
        path, definition = resolved['model'], resolved['definition']
        if path not in models:
            models[path] = load_model(path)
        validate_profile_model(profile,path,models[path]['mesh_version'])
        return models[path], definition
    imported = set()
    def build(actor, model, definition, name, parent=None, depth=0):
        if depth > 8:
            raise FormatError('Attachment nesting exceeds the verified limit')
        skeleton = model['skeleton']
        identity = model_resource_identity(model['source'],skeleton,assets=assets,definition=definition,game=profile,
                                            reference=parent[2]['Resource File'] if parent else resolver.actor_reference(actor['name']) if actor else '')
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
        attachment_tint = parent[2].get('Tint Colour') if parent else None
        def model_material(model, entry, definition):
            return materials(model, entry, definition, attachment_tint=attachment_tint)
        rig, parts = create_model(model, name, collection, definition, model_material)
        rig['tt_native_resource_identity'] = json.dumps(identity)
        if parent:
            parent_rig, parent_skeleton, attachment = parent
            point = attachment_locator(parent_skeleton,attachment['Locator'])
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
        row = {'name':name, 'model':str(model['source']), 'meshes':len(parts), 'animated':actor is not None,
               'resource_identity':identity}
        report['actors'].append(row)
        if definition and skeleton:
            children, ownership_inputs = [], []
            for index, attachment in enumerate(active_attachments(definition,renderer_suffix=suffix)):
                try:
                    child_model, child_definition = resource(attachment['Resource File'])
                    children.append((index,attachment,child_model,child_definition))
                    if child_model['skeleton']:
                        child_identity = model_resource_identity(child_model['source'],child_model['skeleton'],assets=assets,
                            definition=child_definition,reference=attachment['Resource File'],game=profile)
                        ownership_inputs.append({'id':index,'parent_id':None,'skeleton':child_model['skeleton'],'identity':child_identity})
                except (ValueError,OSError,KeyError,RuntimeError) as error:
                    report['issues'].append({'actor':name,'resource':attachment['Resource File'],'issue':str(error)})
            matches, ownership_issues = attachment_tracks(cut.actors,actor,ownership_inputs,None) if actor else ({},[])
            report['issues'].extend(dict(issue,actor=name) for issue in ownership_issues)
            for index, attachment, child_model, child_definition in children:
                before = snapshot()
                child_rows = len(report['actors'])
                child_imported = imported.copy()
                material_rows = len(report['materials'])
                saved_images,saved_stores = dict(materials.images),dict(materials.stores)
                try:
                    match = matches.get(index)
                    child_actor = match['actor'] if match else None
                    child_rig, child_parts = build(child_actor, child_model, child_definition,
                                                   name+' / '+attachment['Resource File'],
                                                   (rig,skeleton,attachment), depth+1)
                    if match:child_rig['tt_animation_ownership'] = json.dumps(match['evidence'])
                    if actor and not child_actor:
                        apply_actor_visibility(cut, actor, [child_rig]+[p for p in child_parts if p.get('tt_colour_write_mask')!=0])
                except (ValueError, OSError, KeyError, RuntimeError) as error:
                    rollback(before)
                    materials.images.clear();materials.images.update(saved_images)
                    materials.stores.clear();materials.stores.update(saved_stores)
                    del report['materials'][material_rows:]
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
                reference = resolver.actor_reference(actor['name'])
                model, definition = resource(reference)
                build(actor, model, definition, actor['name'])
                if reference != actor_resource(actor['name']):
                    report.setdefault('applied_character_replacements',[]).append({'actor':actor['name'], 'original':actor_resource(actor['name']), 'resource':reference})
            except (ValueError, OSError, KeyError, RuntimeError) as error:
                rollback(before)
                report['actors'] = report['actors'][:rows_before]
                imported = imported_before
                materials.images.clear()
                report['issues'].append({'actor':actor['name'],'issue':str(error)})
        report['unassembled_actor_nodes'] = [a['name'] for a in cut.actors if a['index'] not in imported]
        report['stages'] = []
        if static_environment:
            from .stage_geometry import read_stage_geometry
            from .stage_blender import build_static_stage
            seen = set()
            for declaration in configuration.get('stages',[]):
                reference = declaration['resource_prefix']+suffix+'.GSC'
                if reference.casefold() in seen:continue
                seen.add(reference.casefold())
                stage_report = dict(declaration, reference=reference, status='unresolved')
                before = snapshot()
                try:
                    path = assets.find_exact(reference)
                    model = load_model(path)
                    stage_report['model_validation'] = model['validation']
                    inventory = read_stage_geometry(path, len(model['parts']), len(model['materials']))
                    stage_collection = bpy.data.collections.new('Recovered static stage / '+path.stem)
                    scene.collection.children.link(stage_collection)
                    _, stage_parts, detail = build_static_stage(model, inventory, stage_collection, materials)
                    stage_report.update(detail)
                    stage_report['status'] = 'imported_static_candidates'
                    if stage_parts:
                        # Inspection lighting must reach interior geometry. This
                        # is deliberately labeled separately from native lights.
                        light_data.use_shadow = False
                        stage_report['inspection_lighting'] = 'Unshadowed inspection sun; native lights are not reconstructed.'
                except (ValueError, OSError, KeyError, RuntimeError) as error:
                    rollback(before)
                    materials.images.clear()
                    stage_report['issue'] = str(error)
                report['stages'].append(stage_report)
            if not report['stages']:
                report['stages'].append({'status':'unresolved','issue':'No selected stage declaration was recovered; see configuration report.'})
        else:
            report['stages'].append({'status':'disabled','issue':'Static environment loading was disabled for this import.'})
        if scene.camera:
            report['live_preview'] = prepare_live(scene, detail_level=4)
        scene.frame_set(1)
        scene['cu3_source'] = str(cut.path)
        scene['tt_import_complete'] = False
        report['complete'] = False
        report['model_validation'] = [dict(source=str(path), **model['validation']) for path, model in models.items()]
        report['asset_source'] = assets.get_info() if hasattr(assets,'get_info') else {'kind':'extracted-assets','root':str(assets.root)}
        text = bpy.data.texts.new(cut.name+' / import report')
        text.write(json.dumps(report,indent=2))
        scene['tt_import_report'] = text.name
        return scene, report
    except Exception:
        context.window.scene = original
        rollback(initial)
        raise

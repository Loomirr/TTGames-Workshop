"""Render an original HGP with the importer and the ordinary shader experiment.

Run in a fresh background Blender process. Writes two PNGs, two standalone
scenes and a scope report to a new directory. Optional explicit ANI bindings
produce a playback scene plus a frozen shader pose. This is not a new default
importer material or a game-frame fidelity comparison.
"""
import argparse
import importlib.util
import json
import hashlib
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shader_reference import check_material, check_legacy_plastic, check_specular_material, check_bump_material, specular_uv, reflection_parameters, reflection_vertex, unit_vector, vector
from shader_nodes import material, NORMAL_ATTRIBUTE, SPECULAR_UV_ATTRIBUTE, BUMP_LIGHT_ATTRIBUTES, REFLECTION_PROBE_ATTRIBUTE, REFLECTION_CAMERA_ATTRIBUTE
from shader_pose import posed_normals, bump_corner_lights
from shader_reference import native_lighting


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--detail', default='AUTO', help='AUTO, a layer number, or GAME_HIGH/GAME_SPECIAL etc.')
    parser.add_argument('--color-space', choices=('linear', 'display'), required=True,
                        help='Explicit test hypothesis: shader values are linear, or display RGB')
    parser.add_argument('--preview-pose', action='store_true', help='Apply known reversible importer preview poses; translation-only supported by this lab')
    parser.add_argument('--specular-matrix', type=Path, help='Explicit JSON four-row matrix hypothesis; enables effect-129 lookup test')
    parser.add_argument('--animation', type=Path, help='ANI for an explicitly bound research playback example')
    parser.add_argument('--binding', type=Path, help='Reviewed source hashes, bone mapping and preview rate JSON')
    parser.add_argument('--face-animation', type=Path, help='Original BSA with an explicit reviewed facial binding')
    parser.add_argument('--face-binding', type=Path, help='BSA/HGP source hashes, native layers, preview rate and evidence JSON')
    parser.add_argument('--frame', type=int, default=1, help='Integer native sample shown in the render')
    parser.add_argument('--legacy-plastic', action='store_true', help='Enable observed effect-145 ordinary fallback, with advanced lighting disabled')
    parser.add_argument('--bump', action='store_true', help='Enable effect-135 bump comparison; combines reflections when a reflection profile is supplied')
    parser.add_argument('--native-culling', action='store_true', help='Apply the observed material face-culling field; native depth ordering remains separate')
    parser.add_argument('--native-tangents',action='store_true',help='Use reviewed last-triangle tangent assignment for single-primitive strips')
    parser.add_argument('--face-target',type=int,help='Explicit native morph ID for a frozen research pose; not a decoded game clip')
    parser.add_argument('--face-weight',type=float,default=1.,help='Manual target weight from zero to one')
    parser.add_argument('--face-preview-animation',action='store_true',help='Key the selected target 0 -> 1 -> 0 over 17 frames; fixed body pose, not a decoded game clip')
    parser.add_argument('--reflection-profile',type=Path,help='Explicit JSON environment/minimum_scale/maximum_scale/player_native; effect-145 reflection experiment')
    parser.add_argument('--lighting-profile',type=Path,help='Explicit native ambient_rgba, directions and colors_rgba JSON; no automatic level selection')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if not bpy.app.background:
        raise ValueError('Run this experiment in background Blender to preserve open projects')
    if not 0<=args.face_weight<=1 or args.face_target is not None and args.face_target<0:
        raise ValueError('Face pose needs a nonnegative target ID and finite weight from zero to one')
    if args.face_preview_animation and (args.face_target is None or args.animation):
        raise ValueError('Live face preview needs a target and a fixed body; do not combine with a body ANI')
    if bool(args.animation) != bool(args.binding) or (args.animation and args.preview_pose):
        raise ValueError('Animation needs a binding and must not be combined with preview-pose corrections')
    if bool(args.face_animation) != bool(args.face_binding):
        raise ValueError('Decoded facial playback needs both --face-animation and --face-binding')
    if args.face_animation and (args.animation or args.preview_pose or args.face_target is not None or args.face_preview_animation):
        raise ValueError('Decoded facial shader preview needs a fixed body and no manual face pose')
    reflection_profile = None
    reflection_environment = None
    lighting_profile = None
    if args.lighting_profile:
        with args.lighting_profile.open('rb') as stream:
            raw_lighting = stream.read(16385)
        if len(raw_lighting)>16384:
            raise ValueError('Lighting profile exceeds 16 KiB')
        lighting_profile=json.loads(raw_lighting)
        if not isinstance(lighting_profile,dict) or set(lighting_profile)!={'ambient_rgba','directions','colors_rgba'}:
            raise ValueError('Lighting profile needs ambient_rgba, directions and colors_rgba')
        native_lighting(**lighting_profile)
    if args.reflection_profile:
        reflection_profile=json.loads(args.reflection_profile.read_text(encoding='utf-8'))
        if set(reflection_profile) != {'environment','minimum_scale','maximum_scale','player_native'}:
            raise ValueError('Reflection profile needs environment, minimum_scale, maximum_scale and player_native')
        vector(reflection_profile['player_native'],3,'Explicit player position')
        reflection_parameters(1.,reflection_profile['minimum_scale'],reflection_profile['maximum_scale'])
        environment_path=(args.reflection_profile.parent/reflection_profile['environment']).resolve()
        if not environment_path.is_file():raise ValueError('Reflection environment image is missing')
    specular_rows = json.loads(args.specular_matrix.read_text(encoding='utf-8')) if args.specular_matrix else None
    if specular_rows is not None:
        specular_uv((0, 0, 1), specular_rows)  # Validate the requested matrix before importing.
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    component = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('lsw1_shader_lab', component / '__init__.py',
                                                submodule_search_locations=[str(component)])
    addon = importlib.util.module_from_spec(spec); sys.modules[spec.name] = addon; spec.loader.exec_module(addon)
    from lsw1_shader_lab.importer import import_character, matrix, C
    from lsw1_shader_lab.hgp import HGP

    bpy.ops.wm.read_factory_settings(use_empty=True)
    if reflection_profile:
        if environment_path.suffix.lower()=='.dds':
            from shader_cubemap import load_faces
            reflection_environment=load_faces(environment_path,output/'reflection-cube')
        else:
            reflection_environment=bpy.data.images.load(str(environment_path),check_existing=False)
            reflection_environment.pack()
    rig = import_character(bpy.context, args.model, detail=args.detail, correct_preview_pose=args.preview_pose)
    if any(abs(b.matrix_basis.to_quaternion().angle)>1e-6 for b in rig.pose.bones):
        raise ValueError('Shader lab supports translation-only preview poses')
    source = HGP(Path(rig['lsw1_source_file']))
    facial_playback = None
    if args.face_animation:
        from bake_face_preview import load_binding as load_face_binding, bake as bake_face
        face_clip, face_binding = load_face_binding(source, args.face_animation, args.face_binding)
        # Static authored normals are verified for ordinary facial materials.
        # Bump/reflection paths need per-frame vertex inputs and remain refused.
        if any(source.materials()[p['material']]['effect'] != 0
               for layer in face_binding['layers'] for p in source.layer_meshes(layer) if p.get('morph')):
            raise ValueError('Decoded facial shader playback currently requires ordinary face materials')
        facial_playback = bake_face(list(rig.children), source, face_clip, face_binding, bpy.context.scene)
        if not 1 <= args.frame <= facial_playback['frames']:
            raise ValueError('Requested frame is outside decoded facial playback')
        bpy.context.scene.frame_set(args.frame)
    if args.face_target is not None:
        matches=0
        for obj in rig.children:
            if obj.type=='MESH' and obj.data.shape_keys:
                key=obj.data.shape_keys.key_blocks.get(f'morph {args.face_target}')
                if key is not None:
                    matches+=1
                    if args.face_preview_animation:
                        for frame,weight in ((1,0.),(9,1.),(17,0.)):
                            key.value=weight;key.keyframe_insert('value',frame=frame)
                    else:key.value=args.face_weight
        if not matches:raise ValueError('Selected meshes have no requested face target')
        if args.face_preview_animation:
            bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=17
            bpy.context.scene.frame_set(1)
    playback = None
    if args.animation:
        from bake_animation_preview import load_binding, bake
        clip, binding = load_binding(source, args.animation, args.binding)
        playback = bake(rig, source, clip, binding, bpy.context.scene)
        if not 1 <= args.frame <= playback['frames']:
            raise ValueError('Requested frame is outside the baked preview')
        bpy.context.scene.frame_set(args.frame)
    sources = source.materials()
    native = {(part['geometry'], part['primitive'], part['rigid_bone']): part
              for layer in range(source.layer_count) for part in source.layer_meshes(layer)}
    worlds = []
    for bone in source.bones:
        local = matrix(bone['local'])
        worlds.append(worlds[bone['parent']] @ local if bone['parent'] >= 0 else local)
    worlds = [C @ world @ C for world in worlds]
    bpy.context.view_layer.update()
    objects = [obj for obj in rig.children if obj.type == 'MESH']
    # Frame the evaluated pose, not the source bind vertices. For playback,
    # include every baked frame so a standing or jumping pose stays on screen.
    points = []
    scene = bpy.context.scene
    preview_frame = scene.frame_current
    bounds_frames = range(1, playback['frames']+1) if playback else range(1, facial_playback['frames']+1) if facial_playback else range(1,18) if args.face_preview_animation else (preview_frame,)
    for frame in bounds_frames:
        scene.frame_set(frame)
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in objects:
            evaluated = obj.evaluated_get(graph)
            points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
    scene.frame_set(args.frame if playback else preview_frame)
    if not points:
        raise ValueError('No geometry to compare')
    low = Vector([min(v[i] for v in points) for i in range(3)])
    high = Vector([max(v[i] for v in points) for i in range(3)])
    center = (low + high) / 2; extent = max(high - low) * 1.35
    camera_direction = (.7, -2, .9) if high.z - low.z < max(high.x - low.x, high.y - low.y) * .5 else (.35, -2, .4)
    bpy.ops.object.camera_add(location=center + Vector(camera_direction) * extent)
    scene = bpy.context.scene; scene.camera = bpy.context.object
    scene.camera.rotation_euler = (center - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera.data.type = 'ORTHO'; scene.camera.data.ortho_scale = extent
    ambient = (.24, .24, .24)
    lights = [(tuple(Vector(direction).normalized()), color) for direction, color in
              [((.7, -1, 1), (.6, .58, .55)), ((-1, -.5, .25), (.22, .25, .32)), ((0, 1, .6), (.2, .22, .2))]]
    if lighting_profile is not None:
        ambient, native_lights = native_lighting(**lighting_profile)
        lights = [((direction[0],direction[2],direction[1]),color) for direction,color in native_lights]
    for direction, color in lights:
        # A SUN normalizes its orientation. Compensate its energy only in the
        # importer baseline; shader materials keep the original vector intact.
        direction_length=Vector(direction).length
        if direction_length<1e-12:
            continue
        bpy.ops.object.light_add(type='SUN')
        light = bpy.context.object
        light.rotation_euler = (-Vector(direction)).to_track_quat('-Z', 'Y').to_euler()
        light.data.energy = direction_length; light.data.color = color; light.data.angle = .05
    scene.world = bpy.data.worlds.new('Controlled shader experiment'); scene.world.use_nodes = True
    nodes = scene.world.node_tree.nodes; links = scene.world.node_tree.links
    nodes['Background'].inputs[0].default_value = (*ambient, 1)
    # Keep a neutral camera background while preserving the baseline's chosen
    # ambient world illumination. Lab materials use their explicit ambient term.
    camera_bg = nodes.new('ShaderNodeBackground'); camera_bg.inputs[0].default_value = (.035, .035, .035, 1)
    ray = nodes.new('ShaderNodeLightPath'); mix = nodes.new('ShaderNodeMixShader')
    links.new(ray.outputs['Is Camera Ray'], mix.inputs[0])
    links.new(nodes['Background'].outputs[0], mix.inputs[1]); links.new(camera_bg.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], nodes['World Output'].inputs['Surface'])
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 32; scene.cycles.use_denoising = True
    scene.render.resolution_x = 900; scene.render.resolution_y = 800; scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'

    def save(label):
        scene.render.filepath = str(output / f'{label}.png')
        bpy.ops.render.render(write_still=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output / f'{label}.blend'))

    save('importer-preview')
    # The importer scene keeps its complete action for playback. Shader normal
    # and lookup attributes below are sampled at this frame, so the shader scene
    # deliberately freezes the pose rather than saving misleading moving shading.
    if playback:
        rig.animation_data_clear()
    changed, retained, cache = [], [], {}
    for obj in objects:
        bone = int(obj['lsw1_attachment_bone'])
        part = native[(int(obj['lsw1_geometry_offset'], 16), int(obj['lsw1_primitive_offset'], 16), None if bone == -1 else bone)]
        index = part['material']; info = sources[index]
        auxiliary = None
        bump = info['effect'] == 135 and args.bump
        corner_lights = None
        scalar=None
        if reflection_profile and info['effect'] in (135,145):
            pointer=source.u32(source.header[3]+4+4*index)
            scalar=source.floats(pointer+0x60,1)[0]
        reflection = reflection_profile is not None and (info['effect']==145 or (bump and scalar!=0))
        legacy_plastic = info['effect'] == 145 and args.legacy_plastic and not reflection
        parameters = None
        view_vectors = None
        try:
            face_active=bool(obj.data.shape_keys and (any(key.value!=0 for key in obj.data.shape_keys.key_blocks[1:]) or
                args.face_preview_animation and obj.data.shape_keys.key_blocks.get(f'morph {args.face_target}') is not None))
            if face_active and info['effect']!=0:
                raise ValueError('Manual face preview currently validates ordinary morph materials only')
            if bump:
                auxiliary = sources[info['linked_material']-1] if info['linked_material'] else None
                if auxiliary is None:
                    raise ValueError('Missing bump auxiliary material')
                check_bump_material(info, auxiliary)
                if obj.data.shape_keys and any(key.value != 0 for key in obj.data.shape_keys.key_blocks[1:]):
                    raise ValueError('Active face targets need separately evaluated bump basis inputs')
                posed = [rig.pose.bones[b['name']].matrix.copy() for b in source.bones]
                tangents=None
                if args.native_tangents:
                    import struct
                    from shader_tangents import strip_tangents
                    primitive=part['primitive']
                    if source.u32(primitive+4)!=6 or source.u32(primitive) or source.u32(part['geometry']+48)!=primitive:
                        raise ValueError('Native tangent experiment requires one triangle strip per geometry')
                    count=source.u16(primitive+8);at=source.u32(primitive+12)
                    remap={old:new for new,old in enumerate(part['source_vertex_indices'])}
                    indices=[remap[i] for i in struct.unpack_from(f'<{count}H',source.body,at)]
                    tangents=strip_tangents(part['vertices'],part['uvs'],indices)
                corner_lights = bump_corner_lights(part, posed, worlds, lights, normalize_reflection_normal=reflection,native_tangents=tangents)
                if len(corner_lights) != len(obj.data.loops):
                    raise ValueError('Bump tangent corners differ from imported topology')
            elif info['effect'] == 129 and specular_rows is not None:
                auxiliary = sources[info['linked_material'] - 1] if info['linked_material'] else None
                if auxiliary is None:
                    raise ValueError('Missing linked texture-specular material')
                check_specular_material(info, auxiliary)
                if part.get('morph') and any(key.value != 0 for key in obj.data.shape_keys.key_blocks[1:]):
                    raise ValueError('Active morphs are outside the observed effect-129 path')
            elif reflection:
                check_legacy_plastic(info)
            elif legacy_plastic:
                check_legacy_plastic(info)
            else:
                check_material(info)
            if reflection:
                if obj.data.shape_keys and any(key.value != 0 for key in obj.data.shape_keys.key_blocks[1:]):
                    raise ValueError('Active facial targets need verified reflection vertex inputs')
                parameters=reflection_parameters(scalar,reflection_profile['minimum_scale'],reflection_profile['maximum_scale'])
                evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                if len(evaluated.data.vertices)!=len(obj.data.vertices):
                    raise ValueError('Reflection input topology differs from source')
                positions=[evaluated.matrix_world@v.co for v in evaluated.data.vertices]
                cam=scene.camera.location
                view_vectors=[reflection_vertex((p.x,p.z,p.y),(cam.x,cam.z,cam.y),reflection_profile['player_native']) for p in positions]
        except ValueError as error:
            retained.append(dict(object=obj.name, material=index, reason=str(error)))
            continue
        cache_key=(index,reflection and bone<0)
        if cache_key not in cache:
            # The importer names embedded images by their original texture ID;
            # node order cannot distinguish diffuse and bump images.
            diffuse_image = bpy.data.images.get(f"{source.path.stem} texture {info['texture']:02d}") if info['texture'] is not None else None
            auxiliary_image = bpy.data.images.get(f"{source.path.stem} texture {auxiliary['texture']:02d}") if auxiliary else None
            cache[cache_key] = material(info, diffuse_image, ambient, lights,
                                    color_space=args.color_space, name=f'LSW1 lab material {index}',
                                    legacy_plastic=legacy_plastic,
                                    auxiliary=auxiliary, specular_image=auxiliary_image if auxiliary and not bump else None,
                                    bump_image=auxiliary_image if bump else None, native_culling=args.native_culling,
                                    reflection_parameters=parameters,reflection_environment=reflection_environment if reflection else None,
                                    reflection_skinned=bone<0)
        obj.data.materials[0] = cache[cache_key]
        attribute = obj.data.attributes.new(NORMAL_ATTRIBUTE, 'FLOAT_VECTOR', 'POINT')
        posed = [rig.pose.bones[b['name']].matrix.copy() for b in source.bones]
        normals = posed_normals(part['normals'], None if bone < 0 else bone, part['weights'], posed, worlds)
        if reflection:
            normals=[Vector(unit_vector(n,'Reflection vertex normal')) for n in normals]
            for i,name in enumerate((REFLECTION_PROBE_ATTRIBUTE,REFLECTION_CAMERA_ATTRIBUTE)):
                view_attribute=obj.data.attributes.new(name,'FLOAT_VECTOR','POINT')
                for point,views in zip(view_attribute.data,view_vectors):
                    v=views[i];point.vector=(v[0],v[2],v[1])
        lookup = obj.data.attributes.new(SPECULAR_UV_ATTRIBUTE, 'FLOAT_VECTOR', 'POINT') if auxiliary and not bump else None
        if bump:
            for light_index,name in enumerate(BUMP_LIGHT_ATTRIBUTES):
                attribute_light = obj.data.attributes.new(name, 'FLOAT_VECTOR', 'CORNER')
                for point,values in zip(attribute_light.data,corner_lights):
                    point.vector = values[light_index]
        for vertex_index, (point, normal) in enumerate(zip(attribute.data, normals)):
            # Deliberately retain the authored vector length and let raster
            # interpolation happen without the normal shader's renormalization.
            point.vector = normal
            if lookup:
                u, v = specular_uv(point.vector, specular_rows)
                lookup.data[vertex_index].vector = (u, 1 - v, 0)
        obj['lsw1_shader_lab_static_normals'] = True
        changed.append(dict(object=obj.name, material=index,
                            reflection_parameters=parameters,
                            path='bump-reflection' if bump and reflection else 'reflection' if reflection else 'bump' if bump else 'legacy-plastic' if legacy_plastic else 'texture-specular' if auxiliary else 'ordinary'))
    if not changed:
        raise ValueError('No selected parts use the supported ordinary shader path')
    if args.face_preview_animation and retained:
        raise ValueError(f'Live face example has unsupported materials: {retained}')
    save('shader-experiment')
    if args.face_preview_animation:
        for frame in (1,5,9,13,17):
            scene.frame_set(frame);scene.render.filepath=str(output/f'face-frame-{frame:03d}.png')
            bpy.ops.render.render(write_still=True)
        scene.frame_set(1)
    if facial_playback:
        for frame in sorted({1, facial_playback['frames']//2 + 1, facial_playback['frames']}):
            scene.frame_set(frame); scene.render.filepath = str(output / f'decoded-face-{frame:03d}.png')
            bpy.ops.render.render(write_still=True)
        scene.frame_set(args.frame)
    report = dict(model=args.model.name, detail=args.detail, preview_pose=args.preview_pose, playback=playback, facial_playback=facial_playback,
                  sampled_frame=args.frame, legacy_plastic=args.legacy_plastic, bump=args.bump, color_space=args.color_space,
                  native_culling=args.native_culling,
                  native_tangents=args.native_tangents,
                  face_target=args.face_target,face_weight=args.face_weight if args.face_target is not None and not args.face_preview_animation else None,
                  face_preview_keys=[[1,0.],[9,1.],[17,0.]] if args.face_preview_animation else None,
                  face_preview_animation=args.face_preview_animation,
                  lighting_profile=lighting_profile,
                  lighting_profile_sha256=hashlib.sha256(raw_lighting).hexdigest() if lighting_profile is not None else None,
                  reflection_profile=reflection_profile,
                  reflection_environment_sha256=hashlib.sha256(environment_path.read_bytes()).hexdigest() if reflection_profile else None,
                  bump_basis=('Native single-strip last-triangle assignment; external normalization contract' if args.native_tangents else 'MikkTSpace in source coordinates/UVs; native tangent generation unverified') if args.bump else None,
                  ambient=ambient, lights=lights, camera_direction=camera_direction, specular_matrix_hypothesis=specular_rows,
                  changed=changed, retained=retained,
                  scope='Fixed body-pose shader arithmetic experiment; ordinary face targets can animate with authored normals retained, with optional explicitly bound decoded BSA playback; importer-preview retains any baked research action. Weighted normal transforms and generated tangents are shader-input hypotheses. Effect 129 uses the older texture-specular candidate; effect 145 uses its ordinary fallback; effect 135 optionally uses the bump-only candidate. Effects 145 and nonzero-strength 135 optionally use verified reflection arithmetic with an explicit DDS cube or equirectangular environment and player-position hypothesis; native cube filtering and runtime inputs remain unverified. Chosen lights; raw DDS samples; declared display hypothesis. No proof of runtime selection, vertex preparation, texture filtering, color-space state, native blending space, shadows or reflection fidelity. Unsupported materials retain the importer preview.')
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('SHADER_COMPARISON', len(changed), 'parts changed;', len(retained), 'retained', flush=True)


if __name__ == '__main__':
    main()

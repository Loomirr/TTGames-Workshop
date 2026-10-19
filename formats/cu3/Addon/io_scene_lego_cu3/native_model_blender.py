"""Build native source geometry with preserved vertex order and display bindings."""
import math
import hashlib
from pathlib import Path
import bpy
from mathutils import Vector
from .cu3 import FormatError
from .native_model import load_model as decode_model, selected_draws
from .morph import add_shape_keys
from .blender_import import C, row_matrix, create_rig
from .material_preview import attach_vertex_albedo, attach_vertex_opacity
from .face_edit_blender import bind_source
from .mesh_edit_blender import bind_vertices
from .material_edit_guard import bind_materials
from .model_validation import validate_draw, matrix
from .geometry_normals import normal_preservation_status, apply_authored_normals


def load_model(path, *, skeleton_identity=None):
    model = decode_model(path, skeleton_identity=skeleton_identity)
    model['validation']['blender_capabilities'] = dict(normal_preservation=normal_preservation_status())
    return model


def add_vertex_frames(obj, frames, transform):
    """LEGO Batman 2 MESH 48 vertex animation: one shape key per source frame
    (TT_Frame_000...), keyed so scene frame k+1 shows source frame k. The mesh's
    own positions are left as decoded."""
    keys = obj.shape_key_add(name='Basis', from_mix=False).id_data
    blocks = []
    for k, frame in enumerate(frames):
        block = obj.shape_key_add(name=f'TT_Frame_{k:03d}', from_mix=False)
        block.data.foreach_set('co', [c for p in frame for c in (transform @ Vector(p))])
        blocks.append(block)
    keys.animation_data_create()
    action = bpy.data.actions.new(obj.name + ' / source vertex frames')
    slot = action.slots.new('KEY', keys.name)
    bag = action.layers.new('Source vertex frames').strips.new(type='KEYFRAME').channelbag(slot, ensure=True)
    for k, block in enumerate(blocks):
        curve = bag.fcurves.new(data_path=block.path_from_id('value'))
        # Constant interpolation needs only the boundaries of this frame.
        # Avoid a quadratic number of keys for long native frame sequences.
        points = [(1, 0.0)] if k else []
        points.append((k + 1, 1.0))
        if k + 1 < len(frames):
            points.append((k + 2, 0.0))
        curve.keyframe_points.add(len(points))
        curve.keyframe_points.foreach_set('co', [c for point in points for c in point])
        for point in curve.keyframe_points:
            point.interpolation = 'CONSTANT'
    keys.animation_data.action, keys.animation_data.action_slot = action, slot
    obj['tt_vertex_frames'] = len(frames)


def create_model(model, name, collection, definition=None, material_factory=None, *, layer_mode='authored', highest_detail=True):
    skeleton = model['skeleton']
    draws = selected_draws(model, definition, layer_mode=layer_mode, highest_detail=highest_detail)
    prepared = []
    for special, binding, metadata in draws:
        joint = metadata['joint'] if metadata and not metadata['kind'] else None
        validate_draw(model, binding, joint)
        part = model['parts'][binding['part']]
        transform = C @ row_matrix(skeleton['joints'][joint]['inverse_world_bind_row_major']).inverted() if joint is not None else C
        if skeleton is None:
            matrix(special['matrix'], 'coordinate conversion', f'special {special["index"]}')
            transform = C @ row_matrix(special['matrix'])
        prepared.append((special, binding, part, joint, transform))
    rig = create_rig(skeleton, name, collection) if skeleton else bpy.data.objects.new(name, None)
    if skeleton is None:
        collection.objects.link(rig)
    objects = []
    materials = {}
    companion = dict(schema='tt.relative-position-targets.v1', mesh_version=model['mesh_version'],
        sha256=hashlib.sha256(Path(model['source']).read_bytes()).hexdigest(),
        parts={str(p['index']):p['morphs'] for p in model['parts'] if p['morphs']})
    for draw_order, (special, binding, part, joint, transform) in enumerate(prepared):
        vertices = part['vertices']
        mesh = bpy.data.meshes.new(f'{name} / {special["name"]} / {part["index"]}')
        mesh.from_pydata([transform @ Vector(v['position'][:3]) for v in vertices], [], part['triangles'])
        mesh.update()
        obj = bpy.data.objects.new(mesh.name, mesh)
        collection.objects.link(obj)
        obj.parent = rig
        obj['source_model'] = str(model['source']).replace('\\','/').rsplit('/',1)[-1].rsplit('.',1)[0]
        obj['source_part'] = part['index']
        obj['source_special'] = special['index']
        bind_vertices(obj, transform)
        obj['tt_native_rigid_joint'] = joint if joint is not None else -1
        for field in ('uv', 'uv2', 'uv3'):
            if not vertices or field not in vertices[0]:
                continue
            for component in range(len(vertices[0][field])//2):
                uv = mesh.uv_layers.new(name=f'Source {field} {component}')
                for loop in mesh.loops:
                    value = vertices[loop.vertex_index][field]
                    uv.data[loop.index].uv = (value[component*2], 1-value[component*2+1])
        if vertices and 'color' in vertices[0]:
            color = mesh.color_attributes.new(name='SourceColor', type='BYTE_COLOR', domain='POINT')
            for value, vertex in zip(color.data, vertices):
                value.color_srgb = tuple(v/255 for v in vertex['color'])
        # Custom normal encoding depends on the smooth-face fan topology.
        # Set smooth flags first; changing them afterwards reinterprets the
        # encoded normals and can visibly distort shading on an intact mesh.
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        if vertices and all('normal' in v for v in vertices):
            packed = part['attribute_types']['normal'] == 8
            normals = [Vector(tuple(x/127.5-1 if packed else x for x in v['normal'][:3])) for v in vertices]
            if any(n.length>.1 for n in normals):
                rotation = transform.to_3x3().inverted().transposed()
                # Blender's zero-vector sentinel keeps the automatic normal
                # for that vertex. A missing direction (even on an unused
                # vertex) must not discard valid authored normals elsewhere.
                apply_authored_normals(obj, [
                    (rotation@n).normalized() if n.length>.1 else (0,0,0) for n in normals])
        if vertices and 'normal' in vertices[0]:
            baseline=mesh.attributes.new(name='TT_NativeNormalBaseline',type='FLOAT_VECTOR',domain='CORNER')
            baseline.data.foreach_set('vector',[x for normal in mesh.corner_normals for x in normal.vector])
        index = binding['material']
        entry = model['materials'][index]
        uv_names = tuple(mesh.uv_layers.keys())
        material_key = (index, uv_names)
        if material_key not in materials:
            if material_factory:
                material = material_factory(model, entry, definition)
            else:
                material = bpy.data.materials.new(f'{name} / {entry["name"]}')
                material.use_nodes = True
                if vertices and 'color' in vertices[0]:
                    node = material.node_tree.nodes.new('ShaderNodeVertexColor')
                    node.layer_name = 'SourceColor'
                    material.node_tree.links.new(node.outputs['Color'], material.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
                material['tt_material_status'] = 'Vertex-color inspection; texture/lighting reconstruction incomplete'
            # Packed UV pairs can occupy more than one source attribute.
            # Keep export-layer names but resolve the shader's ordinal UV
            # selector against all recovered pairs, including a third pair.
            for node in material.node_tree.nodes if material.node_tree else ():
                if node.type not in {'UVMAP', 'NORMAL_MAP'} or not node.uv_map.startswith('Source uv '):continue
                number = int(node.uv_map.rsplit(' ',1)[1])
                if number < len(uv_names):node.uv_map = uv_names[number]
                elif uv_names:
                    raise FormatError(f'Material UV selector {number} exceeds native mesh channels')
            materials[material_key] = material
        mesh.materials.append(materials[material_key])
        obj['tt_native_cast_shadows'] = bool(entry['render_flags']['castShadows'])
        obj['tt_native_draw_order'] = draw_order
        obj['tt_native_alpha_test'] = entry['fields'].get('alphaTest', -1)
        if 175 <= entry['table_version'] <= 202:
            obj['tt_native_z_bias'] = entry['fields']['zBias']
        if hasattr(obj, 'visible_shadow'):
            obj.visible_shadow = bool(entry['render_flags']['castShadows'])
        bind_materials(obj)
        if entry['render_flags']['colourWriteMask']==0:
            obj['tt_colour_write_mask'] = 0
            obj.hide_render = True
            obj.hide_set(True)
        else:
            obj['tt_colour_write_mask'] = entry['render_flags']['colourWriteMask']
        if skeleton:
            groups = {}
            for i, vertex in enumerate(vertices):
                for j, weight in ([(joint, 1)] if joint is not None else vertex['weights']):
                    if j not in groups:
                        groups[j] = obj.vertex_groups.new(name=skeleton['joints'][j]['name'])
                    groups[j].add([i], weight, 'REPLACE')
            obj.modifiers.new('Native source skin', 'ARMATURE').object = rig
        if part['morphs']:
            add_shape_keys(obj, part['morphs'], transform)
            bind_source(obj, companion, part['index'], transform)
        elif part.get('frame_positions'):
            add_vertex_frames(obj, part['frame_positions'], transform)
        objects.append(obj)
    return rig, objects

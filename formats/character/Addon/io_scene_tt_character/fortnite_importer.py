"""Static LEGO Fortnite assembly from exported native meshes and recipes."""
import json
import struct
import bpy
import bmesh
from .fortnite_catalog import ExportLibrary
from .importer import snapshot, rollback, write_report


class Materials:
    def __init__(self, library):
        self.library = library
        self.images = {}
        self.lut = None

    def image(self, ref, data=False):
        path = self.library.file(ref, '.png')
        metadata = self.library.object(ref)
        with path.open('rb') as stream:
            header = stream.read(24)
        if header[:8] != b'\x89PNG\r\n\x1a\n' or len(header) != 24:
            raise ValueError('Invalid exported PNG: ' + path.name)
        dimensions = struct.unpack_from('>II', header, 16)
        expected = (metadata.get('SizeX'), metadata.get('SizeY'))
        if all(isinstance(v, int) and v > 0 for v in expected) and dimensions != expected:
            raise ValueError('Exported texture is a reduced mip: ' + path.name + '; extract its full streamed payload')
        key = (path, data)
        if key not in self.images:
            image = bpy.data.images.load(str(path), check_existing=False)
            image.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
            image.alpha_mode = 'STRAIGHT'
            self.images[key] = image
        return self.images[key]

    def color(self, value):
        if self.lut is None:
            self.lut = self.image('T_LUT_Default', data=True)
        code = int(value)
        if code != value or not 0 <= code < self.lut.size[0]:
            raise ValueError('Invalid native plastic color ID: ' + str(value))
        values = self.lut.pixels[code*4:code*4+3]
        return tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values) + (1,)

    def build(self, name, *, base=(.18,.18,.18,1), color_texture=None, layers=(), normal=None, vertex_colors=False):
        material = bpy.data.materials.new(name)
        material.use_nodes = True
        material.diffuse_color = base
        nodes, links = material.node_tree.nodes, material.node_tree.links
        nodes.clear()
        output = nodes.new('ShaderNodeOutputMaterial')
        shader = nodes.new('ShaderNodeBsdfPrincipled')
        shader.inputs['Base Color'].default_value = base
        shader.inputs['Roughness'].default_value = .32
        links.new(shader.outputs['BSDF'], output.inputs['Surface'])
        color = None
        if vertex_colors:
            attr = nodes.new('ShaderNodeVertexColor')
            attr.layer_name = 'Fortnite recipe plastic'
            color = attr.outputs['Color']

        def texture(ref, uv, data=False):
            node = nodes.new('ShaderNodeTexImage')
            node.image = self.image(ref, data)
            node.extension = 'EXTEND'
            coord = nodes.new('ShaderNodeUVMap')
            coord.uv_map = uv
            links.new(coord.outputs['UV'], node.inputs['Vector'])
            return node

        if color_texture:
            color = texture(color_texture, 'UVMap').outputs['Color']
        for ref, uv in layers:
            if not ref:
                continue
            decal = texture(ref, uv)
            mix = nodes.new('ShaderNodeMixRGB')
            mix.inputs[1].default_value = base
            links.new(decal.outputs['Alpha'], mix.inputs[0])
            links.new(decal.outputs['Color'], mix.inputs[2])
            if color:
                links.new(color, mix.inputs[1])
            color = mix.outputs[0]
        if color:
            links.new(color, shader.inputs['Base Color'])
        if normal:
            source = texture(normal, 'UVMap', True)
            split = nodes.new('ShaderNodeSeparateColor')
            merge = nodes.new('ShaderNodeCombineColor')
            invert = nodes.new('ShaderNodeMath')
            invert.operation = 'SUBTRACT'
            invert.inputs[0].default_value = 1
            links.new(source.outputs['Color'], split.inputs[0])
            links.new(split.outputs[0], merge.inputs[0])
            links.new(split.outputs[1], invert.inputs[1])
            links.new(invert.outputs[0], merge.inputs[1])
            links.new(split.outputs[2], merge.inputs[2])
            normal_map = nodes.new('ShaderNodeNormalMap')
            normal_map.uv_map = 'UVMap'
            links.new(merge.outputs[0], normal_map.inputs['Color'])
            links.new(normal_map.outputs[0], shader.inputs['Normal'])
        material['tt_fortnite_shader'] = 'Static plastic, source alpha decals and DirectX normal conversion; Unreal shader approximation'
        return material


def plastic_colors(obj, floats, materials, role):
    if len(obj.data.uv_layers) < 2:
        raise ValueError('Recipe mesh needs native base and decoration UV channels')
    attr = obj.data.color_attributes.new(name='Fortnite recipe plastic', type='FLOAT_COLOR', domain='CORNER')
    names = {group.index: group.name for group in obj.vertex_groups}
    for loop in obj.data.loops:
        vertex = obj.data.vertices[loop.vertex_index]
        if role == 'body':
            if not vertex.groups:
                raise ValueError('Shared preview body has an unbound vertex')
            bone = names[max(vertex.groups, key=lambda g: g.weight).group]
            if bone.startswith('leg_') and bone[-1] in 'lr':
                half = 'u' if obj.data.uv_layers[0].data[loop.index].uv.x > .625 else 'l'
                key = 'leg_' + bone[-1] + half + ' Color'
            elif bone in ('pelvis', 'hip_pegs', 'hip_accessory'):
                key = 'hips Color'
            elif bone.startswith('arm_') and bone[-1] in 'lr':
                key = 'arm_' + bone[-1] + 'u Color'
            elif ('hand' in bone or 'wrist' in bone) and bone[-1] in 'lr':
                key = 'hand_' + bone[-1] + ' Color'
            elif bone in ('torso', 'root'):
                key = 'torso Color'
            else:
                raise ValueError('Unverified preview-body color binding: ' + bone)
        else:
            uv = obj.data.uv_layers[1].data[loop.index].uv
            quadrant = ('L' if uv.x < .5 else 'R') + ('U' if uv.y >= .5 else 'L')
            key = quadrant + ' Color ' + role.removesuffix(' SKM')
        if key not in floats:
            raise ValueError('Missing native color parameter: ' + key)
        attr.data[loop.index].color = materials.color(floats[key])


def import_fortnite(context, root, resource):
    if context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before importing')
    library = ExportLibrary(root)
    entry = next((v for v in library.catalog() if v['resource'] == resource), None)
    if entry is None:
        raise ValueError('Refresh the LEGO Fortnite character browser')
    plan = library.plan(entry)
    original_active, selected = context.view_layer.objects.active, list(context.selected_objects)
    before = snapshot()
    try:
        for obj in selected:
            obj.select_set(False)
        collection = bpy.data.collections.new(entry['label'] + ' / LEGO Fortnite')
        context.scene.collection.children.link(collection)
        root_obj = bpy.data.objects.new(entry['label'], None)
        collection.objects.link(root_obj)
        root_obj['tt_fortnite_library'] = str(library.root)
        root_obj['tt_fortnite_resource'] = resource
        root_obj['tt_fortnite_static'] = True
        materials = Materials(library)
        meshes = []
        for spec in plan['meshes']:
            old = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=str(spec['path']), import_shading='NORMALS', bone_heuristic='BLENDER')
            imported = set(bpy.data.objects) - old
            bodies = [obj for obj in imported if obj.type == 'MESH' and obj.data.uv_layers and obj.data.materials]
            if len(bodies) != 1:
                raise ValueError('Expected one mesh in the exported skeletal part; unknown GLB assembly')
            obj = bodies[0]
            # CUE4Parse glTF may include small debug bounds meshes. Preserve
            # them hidden for inspection rather than deleting native geometry.
            for part in imported:
                for owner in list(part.users_collection):
                    owner.objects.unlink(part)
                collection.objects.link(part)
                if part.parent not in imported:
                    world = part.matrix_world.copy()
                    part.parent = root_obj
                    part.matrix_world = world
                if part.type == 'MESH' and part is not obj:
                    part.hide_render = True
                    part.hide_set(True)
                if part.type == 'ARMATURE':
                    part.hide_set(True)
                    # Animation UI/export remain unavailable for this backend.
                    if part.animation_data:
                        part.animation_data_clear()
            if plan['mode'] == 'recipe':
                role = spec['role']
                if role == 'body':
                    slots = [m.name.split('.')[0] for m in obj.data.materials]
                    if slots != ['MI_Figure_DecoratedPlastic', 'MI_Figure_RigDrivenFace_rc1']:
                        raise ValueError('Unverified shared body preview material layout: ' + str(slots))
                    # Preview head is a placeholder for the recipe's Head SKM.
                    native_normals = {}
                    for loop, normal in zip(obj.data.loops, obj.data.corner_normals):
                        native_normals[loop.vertex_index] = tuple(normal.vector)
                    bm = bmesh.new()
                    try:
                        bm.from_mesh(obj.data)
                        source_ids = bm.verts.layers.int.new('tt_fortnite_source_vertex')
                        for vertex in bm.verts:
                            vertex[source_ids] = vertex.index
                        bmesh.ops.delete(bm, geom=[face for face in bm.faces if face.material_index == 1], context='FACES')
                        bm.to_mesh(obj.data)
                    finally:
                        bm.free()
                    ids = obj.data.attributes['tt_fortnite_source_vertex']
                    obj.data.normals_split_custom_set_from_vertices([native_normals[v.value] for v in ids.data])
                    obj.data.attributes.remove(ids)
                    plastic_colors(obj, plan['floats'], materials, role)
                    material = materials.build(entry['label'] + ' / Body', vertex_colors=True,
                        layers=[(plan['textures']['Body Deco D'], 'UVMap.001')], normal=plan['textures'].get('Body Normal'))
                elif role == 'Head SKM':
                    props = plan['head_material']
                    material = materials.build(entry['label'] + ' / Face', base=materials.color(plan['head_color']),
                        layers=[(props.get(k), 'UVMap.001') for k in ('Tex Background-D', 'Tex Foreground-D')], normal=props.get('Tex Normal'))
                else:
                    plastic_colors(obj, plan['floats'], materials, role)
                    prefix = role.removesuffix(' SKM')
                    material = materials.build(entry['label'] + ' / ' + prefix, vertex_colors=True,
                        layers=[(plan['textures'].get(prefix+' Deco D'), 'UVMap.001')], normal=plan['textures'].get(prefix+' Normal'))
                obj.data.materials.clear()
                obj.data.materials.append(material)
                for polygon in obj.data.polygons:
                    polygon.material_index = 0
            else:
                props_list = spec['materials']
                if len(obj.data.materials) != len(props_list):
                    raise ValueError('Baked material slots differ from metadata')
                for i, props in enumerate(props_list):
                    if props.get('Tex Color D'):
                        material = materials.build(entry['label'] + ' / Baked plastic', color_texture=props['Tex Color D'],
                            layers=[(props.get('Tex Deco D'), 'UVMap.001')], normal=props.get('Tex Normal'))
                    elif 'Color Head ID' in props:
                        material = materials.build(entry['label'] + ' / Baked face', base=materials.color(props['Color Head ID']),
                            layers=[(props.get(k), 'UVMap.001') for k in ('Tex Background-D', 'Tex Foreground-D')])
                    else:
                        raise ValueError('Unverified baked material shader parameters')
                    obj.data.materials[i] = material
            obj.name = entry['label'] + ' / ' + obj.name
            obj['tt_fortnite_source'] = str(spec['path'])
            meshes.append(dict(object=obj.name, vertices=len(obj.data.vertices), polygons=len(obj.data.polygons), uv_layers=len(obj.data.uv_layers)))
        # Keep every exported map referenced by the chosen recipe's material
        # chain available in the blend, including shader channels not decoded.
        retained = set()
        material_values = [plan.get('textures', {}), plan.get('head_material', {})] + [p for spec in plan['meshes'] for p in spec.get('materials', [])]
        for values in material_values:
            for value in values.values():
                if isinstance(value, dict) and value.get('ObjectName', '').startswith('Texture'):
                    path = library.file(value, '.png', required=False)
                    if path:
                        retained.add(str(path))
                        retained_image = materials.image(value, data=True)
                        retained_image.use_fake_user = True
        for image in materials.images.values():
            image.pack()
        report = dict(game='FORTNITE', character=entry, meshes=meshes, retained_texture_paths=sorted(retained),
                      issues=[], animations=False, limitations=['Static reconstruction of source plastic colors, alpha printing and normals.',
                      'Runtime eye/brow/mouth atlas expressions, shader masks, metallic/glitter/emissive effects are not fully reconstructed.',
                      'No cooked Unreal asset writing or Fortnite animation import.'])
        root_obj['tt_fortnite_report'] = write_report('TT LEGO Fortnite report', report)
        for obj in context.selected_objects:
            obj.select_set(False)
        root_obj.select_set(True)
        for child in root_obj.children_recursive:
            if child.type == 'MESH' and not child.hide_render:
                child.select_set(True)
        context.view_layer.objects.active = root_obj
        return root_obj, report
    except Exception:
        rollback(before)
        for obj in selected:
            obj.select_set(True)
        context.view_layer.objects.active = original_active
        raise


def find_fortnite(obj):
    while obj:
        if obj.get('tt_fortnite_library'):
            return obj
        obj = obj.parent
    return None

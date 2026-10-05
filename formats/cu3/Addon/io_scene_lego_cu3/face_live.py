"""Camera-dependent preview clipping; source meshes and targets stay intact.

Zero-colour masks remain evaluated as raycast targets. Subdivided facial
details behind them are removed after skinning, allowing the head to show
through in a single viewport pass. This is an approximation, not a TT shader.
"""
import bpy


def copy_layer_flags(source, destination):
    """FULL_COPY can reset per-layer exclusions; retain native/user selection."""
    if len(source.children) != len(destination.children):
        raise ValueError('Copied collection hierarchy differs from the source')
    for prop in ('exclude', 'holdout', 'indirect_only', 'hide_viewport'):
        setattr(destination, prop, getattr(source, prop))
    for old, new in zip(source.children, destination.children):copy_layer_flags(old, new)


def cameras(scene):
    cuts = sorted(((m.frame, m.camera) for m in scene.timeline_markers if m.camera), key=lambda item: item[0])
    if not cuts:
        cuts = [(scene.frame_start, scene.camera)]
    if any(camera is None or camera.data.type not in {'PERSP', 'ORTHO'} for _, camera in cuts):
        raise ValueError('Live facial clipping needs a perspective or orthographic source camera')
    if len({frame for frame, _ in cuts}) != len(cuts):
        raise ValueError('Multiple camera cuts occupy the same frame')
    return cuts


def clip_details(obj, masks, scene, level=3):
    """Append a reversible modifier after existing morph/skin/depth evaluation."""
    if obj.type != 'MESH' or not masks or not 0 <= level <= 4:
        raise ValueError('Expected a detail mesh, verified masks and level 0–4')
    if obj.modifiers.get('TT live facial clipping'):
        raise ValueError('Live facial clipping is already installed')
    cuts = cameras(scene)
    tree = bpy.data.node_groups.new(obj.name + ' / live facial clipping', 'GeometryNodeTree')
    tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes, links = tree.nodes, tree.links
    src = nodes.new('NodeGroupInput'); out = nodes.new('NodeGroupOutput')
    join = nodes.new('GeometryNodeJoinGeometry')
    for mask in masks:
        info = nodes.new('GeometryNodeObjectInfo'); info.transform_space = 'RELATIVE'
        info.inputs['Object'].default_value = mask
        links.new(info.outputs['Geometry'], join.inputs['Geometry'])
    vertex = nodes.new('GeometryNodeInputPosition')
    camera_position = None
    for frame, camera in cuts:
        info = nodes.new('GeometryNodeObjectInfo'); info.transform_space = 'RELATIVE'
        info.inputs['Object'].default_value = camera
        position = info.outputs['Location']
        if camera.data.type == 'ORTHO':
            rotate = nodes.new('ShaderNodeVectorRotate'); rotate.rotation_type = 'EULER_XYZ'
            rotate.inputs['Vector'].default_value = (0, 0, -1)
            links.new(info.outputs['Rotation'], rotate.inputs['Rotation'])
            difference = nodes.new('ShaderNodeVectorMath'); difference.operation = 'SUBTRACT'
            links.new(vertex.outputs[0], difference.inputs[0]); links.new(info.outputs['Location'], difference.inputs[1])
            distance = nodes.new('ShaderNodeVectorMath'); distance.operation = 'DOT_PRODUCT'
            links.new(difference.outputs[0], distance.inputs[0]); links.new(rotate.outputs[0], distance.inputs[1])
            scale = nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
            links.new(rotate.outputs[0], scale.inputs[0]); links.new(distance.outputs['Value'], scale.inputs['Scale'])
            start = nodes.new('ShaderNodeVectorMath'); start.operation = 'SUBTRACT'
            links.new(vertex.outputs[0], start.inputs[0]); links.new(scale.outputs[0], start.inputs[1])
            position = start.outputs[0]
        if camera_position is not None:
            switch = nodes.new('GeometryNodeSwitch'); switch.input_type = 'VECTOR'
            links.new(camera_position, switch.inputs['False'])
            links.new(position, switch.inputs['True'])
            driver = switch.inputs['Switch'].driver_add('default_value').driver
            variable = driver.variables.new(); variable.name = 'frame'; variable.type = 'SINGLE_PROP'
            variable.targets[0].id_type = 'SCENE'; variable.targets[0].id = scene
            variable.targets[0].data_path = 'frame_current'
            driver.expression = f'frame >= {frame}'
            position = switch.outputs['Output']
        camera_position = position
    subdivide = nodes.new('GeometryNodeSubdivideMesh'); subdivide.inputs['Level'].default_value = level
    links.new(src.outputs['Geometry'], subdivide.inputs['Mesh'])
    direction = nodes.new('ShaderNodeVectorMath'); direction.operation = 'SUBTRACT'
    links.new(vertex.outputs[0], direction.inputs[0]); links.new(camera_position, direction.inputs[1])
    length = nodes.new('ShaderNodeVectorMath'); length.operation = 'LENGTH'
    links.new(direction.outputs[0], length.inputs[0])
    shorten = nodes.new('ShaderNodeMath'); shorten.operation = 'SUBTRACT'
    shorten.inputs[1].default_value = 0.0000001
    links.new(length.outputs['Value'], shorten.inputs[0])
    ray = nodes.new('GeometryNodeRaycast')
    links.new(join.outputs[0], ray.inputs['Target Geometry'])
    links.new(camera_position, ray.inputs['Source Position'])
    links.new(direction.outputs[0], ray.inputs['Ray Direction'])
    links.new(shorten.outputs[0], ray.inputs['Ray Length'])
    delete = nodes.new('GeometryNodeDeleteGeometry'); delete.domain = 'FACE'
    links.new(subdivide.outputs['Mesh'], delete.inputs['Geometry'])
    links.new(ray.outputs['Is Hit'], delete.inputs['Selection'])
    links.new(delete.outputs['Geometry'], out.inputs['Geometry'])
    modifier = obj.modifiers.new('TT live facial clipping', 'NODES'); modifier.node_group = tree
    obj['tt_live_face_preview'] = 'Camera-dependent subdivided mask clipping; original mesh and keys unchanged'
    return modifier


def prepare_live(scene, detail_level=3):
    """Configure a scene-local copy. Masks keep their source animation data."""
    cameras(scene)  # Validate before changing scene state.
    meshes = [o for o in scene.objects if o.type == 'MESH']
    if any(any(o.name in other.objects for other in bpy.data.scenes if other != scene) for o in meshes):
        raise ValueError('Make a full scene copy before configuring live preview')
    if scene.get('tt_live_preview'):
        raise ValueError('This scene already has a live preview setup')
    groups = {}
    for obj in meshes:
        if obj.get('source_model', '').startswith('FACE_'):
            groups.setdefault((obj.parent, obj['source_model']), []).append(obj)
    planned = []
    for objects in groups.values():
        masks = [o for o in objects if o.get('tt_colour_write_mask') == 0]
        if masks:
            planned.extend((obj, masks) for obj in objects if obj not in masks)
    # Native masks and facial detail can be coplanar. The composed preview
    # already offsets these depth-only surfaces after skinning; omitting that
    # step here creates alternating teeth/skin stripes in raycast clipping.
    # Keep the same explicit preview approximation, without editing Basis,
    # topology, source animation, or the visible facial detail meshes.
    from .face_preview import depth_bias_modifier
    biased_masks = {mask for _, masks in planned for mask in masks}
    for mask in biased_masks:
        depth_bias_modifier(mask, .001)
    # Preserve the source compositor, but don't execute it in this viewing copy.
    scene.render.use_compositing = False; scene.render.use_sequencer = False
    scene.render.engine = 'BLENDER_EEVEE'; scene.render.film_transparent = False
    for layer in list(scene.view_layers)[1:]:scene.view_layers.remove(layer)
    layer = scene.view_layers[0]; layer.name = 'TT live viewport'
    facial = {o for o in meshes if o.get('source_model', '').startswith('FACE_') or o.get('source_model') == 'SpiderFace'}
    def unmask(collection):
        # Only undo the facial pass's exclusion; preserve unrelated user/LOD
        # exclusions rather than bringing hidden variants back into view.
        if any(o in facial for o in collection.collection.all_objects):
            # Assigning exclude=False to an already included parent can reset
            # child exclusions in Blender. Touch only the excluded facial path.
            for prop in ('exclude', 'holdout', 'indirect_only'):
                if getattr(collection, prop):setattr(collection, prop, False)
        for child in collection.children:unmask(child)
    unmask(layer.layer_collection)
    for obj, masks in planned:clip_details(obj, masks, scene, detail_level)
    hidden = bpy.data.collections.new(scene.name + ' / depth-only dependencies')
    scene.collection.children.link(hidden); hidden.hide_render = True
    masks = [o for o in meshes if o.get('tt_colour_write_mask') == 0]
    for obj in masks:
        for collection in list(obj.users_collection):collection.objects.unlink(obj)
        hidden.objects.link(obj)
        obj.hide_set(True, view_layer=layer)
    if scene.get('editing_collection'):
        bound = [o for o in meshes if o.get('tt_face_source_sha256')]
        if not bound or len({o['tt_face_source_sha256'] for o in bound}) != 1:
            raise ValueError('Live face editor requires one verified native export binding')
        # FULL_COPY remaps IDs but not string-valued collection names. Include
        # depth-only parts too: removing them from export loses edited masks.
        export = bpy.data.collections.new(scene.name + ' / native export bindings')
        scene.collection.children.link(export); export.hide_render = True
        for obj in bound:export.objects.link(obj)
        layer.layer_collection.children[export.name].exclude = True
        scene['editing_collection'] = export.name
        controller = next((o.parent for o in bound if o.parent and o.parent.get('tt_manual_face_controller')), None)
        if controller:layer.objects.active = controller
    scene.sync_mode = 'FRAME_DROP'
    scene['tt_live_preview'] = 'Source camera mask approximation. Orbiting is for mesh inspection; use camera view for facial clipping.'
    scene['tt_preview_kind'] = 'LIVE'
    return {'detail_parts': len(planned), 'hidden_depth_parts': len(masks), 'subdivision_level': detail_level,
            'biased_depth_masks': len(biased_masks), 'depth_bias_distance': .001,
            'depth_bias_note':'Post-skin offset on depth-only raycast targets; preview approximation, not native shader equivalence.'}

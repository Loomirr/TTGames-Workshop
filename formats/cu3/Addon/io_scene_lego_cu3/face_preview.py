"""Render native zero-colour facial depth masks over a separate solid pass.

This is a Blender approximation of colourWriteMask=0, not a translation of
the complete TT shader. Original target coordinates remain unmodified.
"""
import bpy
from .geometry_normals import capture_normals, restore_normals

def face_objects(scene):
    # Asset lookup is case-insensitive, but imported provenance retains the
    # actual filename spelling. Lowercase extraction/cache names need the
    # same helper as their uppercase equivalents; preserve the stored value.
    result = []
    for obj in scene.objects:
        source = obj.get('source_model')
        if obj.type != 'MESH' or not isinstance(source, str):continue
        source = source.casefold()
        if source.startswith('face_') or source == 'spiderface':result.append(obj)
    return result


def masked_detail(obj):
    """Keep cutout printing and unbiased legacy surfaces in the solid pass.

    Missing provenance retains the historical inspection behavior. This is
    a preview classification, not a complete native draw-stage implementation.
    """
    return obj.get('tt_colour_write_mask') == 0 or not (
        obj.get('tt_native_alpha_test') == 5 or obj.get('tt_native_z_bias') == 0)


def prepare_depth(objects):
    """Resolve coplanar preview surfaces in native draw order, after skinning."""
    for obj in objects:
        mask = obj.get('tt_colour_write_mask') == 0
        if 'tt_native_draw_order' not in obj:
            if mask:depth_bias_modifier(obj)
            continue
        if masked_detail(obj):
            distance = .0003 * (obj['tt_native_draw_order'] + 1)
        elif obj.get('tt_native_cast_shadows') and obj.get('tt_native_alpha_test') != 5:
            continue  # Authored solid hair/beard geometry, not a flat decal.
        else:
            distance = .001
        depth_bias_modifier(obj, distance, camera_only=mask)
        obj['tt_face_preview_pass'] = 'masked detail' if masked_detail(obj) else 'solid printing'


def prepare_render(scene):
    """Set up scene-local source surfaces, including initially hidden masks."""
    objects=face_objects(scene)
    masks=[obj for obj in objects if obj.get('tt_colour_write_mask')==0]
    if not masks:
        raise ValueError('No verified native colourWriteMask=0 facial surfaces')
    if getattr(scene,'compositing_node_group',None) or getattr(scene,'node_tree',None):
        raise ValueError('Use a scene copy with an empty compositor')
    if any(any(obj.name in other.objects for other in bpy.data.scenes if other!=scene) for obj in objects):
        raise ValueError('Make a full scene copy before preparing facial render layers')
    collection=bpy.data.collections.new('TT native facial surfaces')
    scene.collection.children.link(collection)
    prepare_depth(objects)
    for obj in objects:
        if not masked_detail(obj):continue
        for owner in list(obj.users_collection):owner.objects.unlink(obj)
        collection.objects.link(obj)
        if obj in masks:
            obj.data=obj.data.copy()
            obj.data.materials.clear();obj.data.materials.append(depth_mask_material())
            for polygon in obj.data.polygons:polygon.material_index=0
            # Model import deliberately hides depth-only surfaces. They must
            # participate in the facial pass for holdout masking to work.
            obj.hide_render=False
            obj.hide_set(False,view_layer=scene.view_layers[0])
    # Character preview copies can have meshes linked directly to the scene.
    # They must be depth occluders in the facial pass, just like meshes inside
    # collections; otherwise the two passes shade the head differently.
    direct=[obj for obj in scene.collection.objects if obj.type=='MESH']
    if direct:
        solid=bpy.data.collections.new('TT solid source surfaces')
        scene.collection.children.link(solid)
        for obj in direct:
            scene.collection.objects.unlink(obj);solid.objects.link(obj)
    scene.view_layers[0].update()
    setup_layers(scene,collection)
    scene.render.engine='CYCLES'
    return {'detail_parts':len(objects)-len(masks),'depth_parts':len(masks),
            'validation':'Composed depth-mask approximation; native shaders and facial timing are separate'}


def depth_mask_material():
    name='TT / native colourWriteMask 0'
    material=bpy.data.materials.get(name)
    if material:return material
    material=bpy.data.materials.new(name);material.use_nodes=True
    tree=material.node_tree;tree.nodes.clear()
    out=tree.nodes.new('ShaderNodeOutputMaterial');mask=tree.nodes.new('ShaderNodeHoldout')
    tree.links.new(mask.outputs[0],out.inputs['Surface'])
    material['tt_colour_write_mask']=0
    return material

def depth_bias_modifier(obj, distance=.001, *, camera_only=True):
    """A rendering offset after skin/morph evaluation; never edits Basis."""
    modifier=obj.modifiers.get('TT facial depth bias')
    if modifier:return modifier
    tree=bpy.data.node_groups.new(obj.name+' / depth bias','GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    n=tree.nodes;links=tree.links;src=n.new('NodeGroupInput');out=n.new('NodeGroupOutput')
    position=n.new('GeometryNodeSetPosition');normal=n.new('GeometryNodeInputNormal')
    scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=distance
    geometry, shading_normal = capture_normals(n, links, src.outputs['Geometry'])
    links.new(geometry,position.inputs['Geometry']);links.new(normal.outputs[0],scale.inputs[0])
    links.new(scale.outputs[0],position.inputs['Offset'])
    links.new(restore_normals(n, links, position.outputs[0], shading_normal),out.inputs[0])
    modifier=obj.modifiers.new('TT facial depth bias','NODES');modifier.node_group=tree
    obj['tt_preview_depth_bias']=distance
    obj['tt_depth_normals_preserved'] = shading_normal is not None
    # Source masks have castShadow=0; holdout must only affect the camera ray.
    if camera_only:
        for prop in ('visible_shadow','visible_diffuse','visible_glossy','visible_transmission','visible_volume_scatter'):
            if hasattr(obj,prop):setattr(obj,prop,False)
    return modifier

def setup_layers(scene, face_collection):
    """Preserve body/environment depth in both passes, then alpha composite."""
    base=scene.view_layers[0];base.name='TT solid surfaces'
    base.layer_collection.children[face_collection.name].exclude=True
    face=scene.view_layers.get('TT facial surfaces') or scene.view_layers.new('TT facial surfaces')
    face.layer_collection.children[face_collection.name].exclude=False
    for child in face.layer_collection.children:
        if child.name!=face_collection.name:child.holdout=True
    scene.render.film_transparent=True
    scene.render.use_compositing=True
    if hasattr(scene,'compositing_node_group'):
        tree=bpy.data.node_groups.new(scene.name+' / TT facial layers','CompositorNodeTree')
        scene.compositing_node_group=tree
        tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
        out=tree.nodes.new('NodeGroupOutput')
    else:
        scene.use_nodes=True;tree=scene.node_tree;tree.nodes.clear();out=tree.nodes.new('CompositorNodeComposite')
    a=tree.nodes.new('CompositorNodeRLayers');a.scene=scene;a.layer=base.name
    b=tree.nodes.new('CompositorNodeRLayers');b.scene=scene;b.layer=face.name
    over=tree.nodes.new('CompositorNodeAlphaOver')
    background=over.inputs.get('Background') or over.inputs[1]
    foreground=over.inputs.get('Foreground') or over.inputs[2]
    tree.links.new(a.outputs['Image'],background);tree.links.new(b.outputs['Image'],foreground)
    tree.links.new(over.outputs[0],out.inputs[0])
    scene['tt_face_preview']='Native vertex albedo and zero-colour depth masks; approximate polygon bias. Rendered preview required.'
    return base,face

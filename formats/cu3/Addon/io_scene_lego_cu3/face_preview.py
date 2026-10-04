"""Render native zero-colour facial depth masks over a separate solid pass.

This is a Blender approximation of colourWriteMask=0, not a translation of
the complete TT shader. Original target coordinates remain unmodified.
"""
import bpy

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

def depth_bias_modifier(obj, distance=.001):
    """A rendering offset after skin/morph evaluation; never edits Basis."""
    modifier=obj.modifiers.get('TT facial depth bias')
    if modifier:return modifier
    tree=bpy.data.node_groups.new(obj.name+' / depth bias','GeometryNodeTree')
    tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    n=tree.nodes;links=tree.links;src=n.new('NodeGroupInput');out=n.new('NodeGroupOutput')
    position=n.new('GeometryNodeSetPosition');normal=n.new('GeometryNodeInputNormal')
    scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=distance
    links.new(src.outputs['Geometry'],position.inputs['Geometry']);links.new(normal.outputs[0],scale.inputs[0])
    links.new(scale.outputs[0],position.inputs['Offset']);links.new(position.outputs[0],out.inputs[0])
    modifier=obj.modifiers.new('TT facial depth bias','NODES');modifier.node_group=tree
    obj['tt_preview_depth_bias']=distance
    # Source masks have castShadow=0; holdout must only affect the camera ray.
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

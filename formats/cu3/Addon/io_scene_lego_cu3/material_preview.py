"""Observed normal texture reconstruction for locally extracted TT assets."""

def attach_vertex_albedo(material, *, native_vert_albedo, layer='SourceColor'):
    """Multiply recovered albedo only when its decoded shader flag is enabled.

    The caller supplies verified color attributes and isolates shared materials
    before changing them. Already connected vertex-color graphs are preserved.
    """
    if native_vert_albedo is not True:return False
    tree=material.node_tree
    if not tree or material.get('tt_vertex_albedo_layer'):return False
    principled=next((n for n in tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not principled:return False
    base=principled.inputs['Base Color']
    def vertex_input(node,seen):
        if node in seen:return False
        seen.add(node)
        if node.type in {'VERTEX_COLOR','ATTRIBUTE'}:return True
        return any(vertex_input(link.from_node,seen) for socket in node.inputs for link in socket.links)
    if any(vertex_input(link.from_node,set()) for link in base.links):return False
    source=base.links[0].from_socket if base.is_linked else None
    color=tree.nodes.new('ShaderNodeVertexColor');color.layer_name=layer
    multiply=tree.nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
    if source:tree.links.new(source,multiply.inputs[1])
    else:multiply.inputs[1].default_value=base.default_value
    tree.links.new(color.outputs['Color'],multiply.inputs[2]);tree.links.new(multiply.outputs[0],base)
    material['tt_vertex_albedo_layer']=layer
    return True


def attach_vertex_opacity(material, *, native_ignore_vertex_opacity, native_can_alpha_blend, layer='SourceColor'):
    """Retain texture alpha and multiply native vertex opacity for blend surfaces."""
    if native_ignore_vertex_opacity is not False or native_can_alpha_blend is not True:return False
    tree=material.node_tree
    if not tree or material.get('tt_vertex_opacity_layer'):return False
    principled=next((n for n in tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not principled:return False
    alpha=principled.inputs['Alpha'];source=alpha.links[0].from_socket if alpha.is_linked else None
    color=tree.nodes.new('ShaderNodeVertexColor');color.layer_name=layer
    multiply=tree.nodes.new('ShaderNodeMath');multiply.operation='MULTIPLY'
    if source:tree.links.new(source,multiply.inputs[0])
    else:multiply.inputs[0].default_value=alpha.default_value
    tree.links.new(color.outputs['Alpha'],multiply.inputs[1]);tree.links.new(multiply.outputs[0],alpha)
    if hasattr(material,'surface_render_method'):material.surface_render_method='DITHERED'
    material['tt_vertex_opacity_layer']=layer
    return True

def attach_albedo_glow(material):
    """Unit-intensity viewing approximation for a verified additive albedo layer."""
    tree=material.node_tree
    if not tree:return False
    p=next((node for node in tree.nodes if node.type=='BSDF_PRINCIPLED'),None)
    if not p or p.inputs['Emission Color'].is_linked:return False
    base=p.inputs['Base Color']
    if base.is_linked:tree.links.new(base.links[0].from_socket,p.inputs['Emission Color'])
    else:p.inputs['Emission Color'].default_value=base.default_value
    p.inputs['Emission Strength'].default_value=1
    material['tt_native_albedo_glow']='Declared additive vertex color; unit preview intensity, native intensity unverified'
    return True


def attach_normal_map(material, image, packed_x_alpha=False, flip_green=True, uv_map=None):
    tree=material.node_tree;nodes=tree.nodes;links=tree.links
    principled=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not principled or principled.inputs['Normal'].is_linked:return False
    image.colorspace_settings.name='Non-Color'
    if packed_x_alpha:image.alpha_mode='CHANNEL_PACKED'
    texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.label='Native tangent-space normal'
    split=nodes.new('ShaderNodeSeparateColor');links.new(texture.outputs['Color'],split.inputs[0])
    combine=nodes.new('ShaderNodeCombineColor')
    links.new(texture.outputs['Alpha'] if packed_x_alpha else split.outputs['Red'],combine.inputs['Red'])
    if flip_green:
        invert=nodes.new('ShaderNodeMath');invert.operation='SUBTRACT';invert.inputs[0].default_value=1
        links.new(split.outputs['Green'],invert.inputs[1]);links.new(invert.outputs[0],combine.inputs['Green'])
    else:links.new(split.outputs['Green'],combine.inputs['Green'])
    links.new(split.outputs['Blue'],combine.inputs['Blue'])
    normal=nodes.new('ShaderNodeNormalMap');links.new(combine.outputs[0],normal.inputs['Color']);links.new(normal.outputs[0],principled.inputs['Normal'])
    if uv_map is not None:
        uv=nodes.new('ShaderNodeUVMap');uv.uv_map=uv_map
        links.new(uv.outputs['UV'],texture.inputs['Vector'])
        normal.uv_map=uv_map
    material['tt_normal_encoding']='X=alpha, Y=green, Z=blue' if packed_x_alpha else 'RGB normal'
    material['tt_normal_green_flipped']=flip_green
    return True

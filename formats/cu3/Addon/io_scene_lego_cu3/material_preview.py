"""Observed normal texture reconstruction for locally extracted TT assets."""
def attach_normal_map(material, image, packed_x_alpha=False, flip_green=True):
    tree=material.node_tree;nodes=tree.nodes;links=tree.links
    principled=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
    if not principled or principled.inputs['Normal'].is_linked:return False
    image.colorspace_settings.name='Non-Color'
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
    material['tt_normal_encoding']='X=alpha, Y=green, Z=blue' if packed_x_alpha else 'RGB normal'
    material['tt_normal_green_flipped']=flip_green
    return True

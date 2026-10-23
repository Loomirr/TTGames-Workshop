"""Blender laboratory material for the verified ordinary ps_2_0 equations.

Explicitly selected by research scripts, never by the normal importer. Supply
post-transform, interpolated normals through a vector attribute. All lighting
values are caller-chosen. Texture sampling and final display conversion remain
declared experiment settings, not recovered game state.
"""
import bpy

from shader_reference import check_material, check_legacy_plastic, check_specular_material, check_bump_material, lighting_inputs, vector, reflection_terms

NORMAL_ATTRIBUTE = 'LSW1 shader test normal'
OPACITY_ATTRIBUTE = 'LSW1 vertex opacity'
SPECULAR_UV_ATTRIBUTE = 'LSW1 shader test specular UV'
REFLECTION_PROBE_ATTRIBUTE = 'LSW1 shader vector to probe'
REFLECTION_CAMERA_ATTRIBUTE = 'LSW1 shader vector from camera'
BUMP_LIGHT_ATTRIBUTES = tuple(f'LSW1 shader tangent light {i}' for i in range(3))


def material(source, image, ambient, lights, *, color_space, name='LSW1 shader experiment',
             specular_image=None, auxiliary=None, legacy_plastic=False, bump_image=None,
             native_culling=False, reflection_parameters=None, reflection_environment=None,
             reflection_sample=None, reflection_skinned=False):
    """Create a new material; leave source materials and images untouched.

    color_space='linear' measures raw shader arithmetic in Blender EXR output.
    'display' treats texture/material RGB as display values and applies the sRGB
    transfer function after lighting, as an explicit hypothesis for comparison.
    """
    bump = bump_image is not None
    reflection = reflection_parameters is not None
    if reflection:
        if (auxiliary is not None and not bump) or specular_image is not None or legacy_plastic:
            raise ValueError('Reflection experiment needs a dedicated plastic or bump path')
        if not bump:check_legacy_plastic(source)
        reflection_terms((0,0,1),(0,0,1),(0,0,1),reflection_parameters)
        if (reflection_environment is None) == (reflection_sample is None):
            raise ValueError('Supply one explicit reflection environment or constant test sample')
        if reflection_sample is not None:
            reflection_sample = vector(reflection_sample,4,'Reflection sample')
    elif reflection_environment is not None or reflection_sample is not None:
        raise ValueError('Reflection sampling requires explicit parameters')
    specular = auxiliary is not None and not bump
    if bump:
        if auxiliary is None or specular_image is not None or legacy_plastic:
            raise ValueError('Bump experiment needs a dedicated checked auxiliary')
        check_bump_material(source, auxiliary)
    if legacy_plastic and specular:
        raise ValueError('Legacy plastic fallback cannot use a texture-specular auxiliary')
    if specular:
        strength = check_specular_material(source, auxiliary)
        if specular_image is None:
            raise ValueError('Texture-specular experiment requires the original lookup image')
    elif not bump and not reflection:
        (check_legacy_plastic if legacy_plastic else check_material)(source)
        if specular_image is not None:
            raise ValueError('A specular image requires a checked auxiliary material')
    ambient, lights = lighting_inputs(ambient, lights)
    diffuse = vector(source['diffuse'], 3, 'Material color')
    if color_space not in ('linear', 'display'):
        raise ValueError('Choose linear or display shader color space explicitly')
    textured = source.get('texture') is not None
    if textured != (image is not None):
        raise ValueError('The selected textured shader requires its diffuse image')
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    nodes = result.node_tree.nodes; nodes.clear()
    links = result.node_tree.links

    def input_value(socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            links.new(value, socket)
        else:
            socket.default_value = value

    def math(operation, a, b=0., clamp=False):
        node = nodes.new('ShaderNodeMath'); node.operation = operation; node.use_clamp = clamp
        input_value(node.inputs[0], a); input_value(node.inputs[1], b)
        return node.outputs[0]

    def vec(operation, a, b):
        node = nodes.new('ShaderNodeVectorMath'); node.operation = operation
        input_value(node.inputs[0], a)
        input_value(node.inputs[3 if operation == 'SCALE' else 1], b)
        return node.outputs['Value' if operation == 'DOT_PRODUCT' else 'Vector']

    def rgb_transform(value, function):
        split = nodes.new('ShaderNodeSeparateXYZ'); input_value(split.inputs[0], value)
        combine = nodes.new('ShaderNodeCombineXYZ')
        for index in range(3):
            input_value(combine.inputs[index], function(split.outputs[index]))
        return combine.outputs[0]

    normal = nodes.new('ShaderNodeAttribute'); normal.attribute_name = NORMAL_ATTRIBUTE
    normal.label = 'Interpolated input normal; do not normalize'
    normal_value = normal.outputs['Vector']
    if bump:
        bump_node = nodes.new('ShaderNodeTexImage')
        bump_node.image = bump_image.copy(); bump_node.image.name = name + ' raw bump sample'
        bump_node.image.colorspace_settings.name = 'Non-Color'
        bump_node.interpolation = 'Linear'
        normal_value = vec('SUBTRACT', vec('SCALE', bump_node.outputs['Color'], 2.), (1.,1.,1.))
    total = ambient
    for index, (direction, color) in enumerate(lights):
        if bump:
            projected = nodes.new('ShaderNodeAttribute'); projected.attribute_name = BUMP_LIGHT_ATTRIBUTES[index]
            direction = projected.outputs['Vector']
        amount = math('MAXIMUM', vec('DOT_PRODUCT', normal_value, direction), 0.)
        total = vec('ADD', total, vec('SCALE', color, amount))
    reflected_color = None
    if reflection:
        n = vec('NORMALIZE',normal.outputs['Vector'],(0,0,0))
        probe = nodes.new('ShaderNodeAttribute'); probe.attribute_name = REFLECTION_PROBE_ATTRIBUTE
        camera_vector = nodes.new('ShaderNodeAttribute'); camera_vector.attribute_name = REFLECTION_CAMERA_ATTRIBUTE
        p = vec('NORMALIZE',probe.outputs['Vector'],(0,0,0))
        v = vec('NORMALIZE',camera_vector.outputs['Vector'],(0,0,0))
        reflected = vec('SUBTRACT',vec('SCALE',n,math('MULTIPLY',2.,vec('DOT_PRODUCT',n,p))),p)
        if bump and reflection_skinned:
            reflected=vec('SCALE',reflected,-1.)  # Original effect 45 uses the opposite cube direction.
        low,high,start,end = reflection_parameters
        edge = math('SUBTRACT',1.,math('ABSOLUTE',vec('DOT_PRODUCT',v,n)))
        x = math('DIVIDE',math('SUBTRACT',edge,start),end-start,clamp=True)
        smooth = math('MULTIPLY',math('MULTIPLY',x,x),math('SUBTRACT',3.,math('MULTIPLY',2.,x)))
        amount = math('ADD',low,math('MULTIPLY',high-low,smooth))
        sample = reflection_sample[:3] if reflection_sample is not None else None
        if isinstance(reflection_environment,(list,tuple)):
            from shader_cubemap import sample_nodes
            sample=sample_nodes(nodes,links,math,vec,reflected,reflection_environment)
        elif reflection_environment is not None:
            environment = nodes.new('ShaderNodeTexEnvironment')
            environment.image = reflection_environment.copy()
            environment.image.name = name+' explicit reflection environment'
            environment.image.colorspace_settings.name = 'Non-Color'
            environment.projection = 'EQUIRECTANGULAR'
            environment.interpolation = 'Linear'
            links.new(reflected,environment.inputs['Vector'])
            sample = environment.outputs['Color']
        reflected_color = vec('SCALE',sample,amount)
    vertex = nodes.new('ShaderNodeAttribute'); vertex.attribute_name = OPACITY_ATTRIBUTE
    alpha = vertex.outputs['Fac']
    if textured:
        texture = nodes.new('ShaderNodeTexImage')
        # Original render materials often share images, including normal maps.
        # Copy before assigning the experiment's raw shader-number role.
        texture.image = image.copy(); texture.image.name = name + ' raw diffuse sample'
        texture.image.colorspace_settings.name = 'Non-Color'
        texture.interpolation = 'Linear'
        color = vec('MULTIPLY', texture.outputs['Color'], tuple(v * .5 for v in diffuse))
        if reflection and not bump:
            color = vec('ADD',color,reflected_color)
        if bump and not reflection:
            color = rgb_transform(color, lambda value: math('MULTIPLY', value, 1., clamp=True))
        color = vec('MULTIPLY',color,total)
        if bump and reflection:color=vec('ADD',color,reflected_color)
        color = vec('SCALE',color,2.)
        if not bump and not (reflection and reflection_skinned):
            color = rgb_transform(color, lambda value: math('MULTIPLY', value, 1., clamp=True))
        alpha = math('MULTIPLY', alpha, texture.outputs['Alpha'])
    else:
        color = vec('MULTIPLY',vec('ADD',diffuse,reflected_color) if reflection and not bump else diffuse,total)
        if bump and reflection:color=vec('ADD',color,reflected_color)
    alpha = math('MULTIPLY', alpha, 2., clamp=True)
    if specular:
        lookup = nodes.new('ShaderNodeTexImage')
        lookup.image = specular_image.copy(); lookup.image.name = name + ' raw specular lookup'
        lookup.image.colorspace_settings.name = 'Non-Color'
        lookup.interpolation = 'Linear'
        # Coordinate/filter conventions remain explicit lab settings. DDS uses
        # top-down texture coordinates; Blender's image coordinates are bottom-up.
        uv = nodes.new('ShaderNodeAttribute'); uv.attribute_name = SPECULAR_UV_ATTRIBUTE
        links.new(uv.outputs['Vector'], lookup.inputs['Vector'])
        highlight = vec('SCALE', lookup.outputs['Color'], 2 * strength)
        highlight = rgb_transform(highlight, lambda value: math('MULTIPLY', value, 1., clamp=True))
        color = vec('ADD', color, highlight)  # Native sum is deliberately NOT saturated.
    if color_space == 'display':
        def to_linear(channel):
            channel = math('MAXIMUM', channel, 0.)
            low = math('DIVIDE', channel, 12.92)
            high = math('POWER', math('DIVIDE', math('ADD', channel, .055), 1.055), 2.4)
            choose_low = math('LESS_THAN', channel, .04045)
            return math('ADD', math('MULTIPLY', low, choose_low),
                        math('MULTIPLY', high, math('SUBTRACT', 1., choose_low)))
        color = rgb_transform(color, to_linear)
    emission = nodes.new('ShaderNodeEmission'); input_value(emission.inputs['Color'], color)
    camera = nodes.new('ShaderNodeLightPath')
    blend = source['attributes'] & 15
    input_value(emission.inputs['Strength'], math('MULTIPLY', alpha, camera.outputs['Is Camera Ray'])
                if blend == 2 else camera.outputs['Is Camera Ray'])
    surface = emission.outputs[0]
    if blend in (1, 2):
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader' if blend == 1 else 'ShaderNodeAddShader')
        if blend == 1:
            input_value(mix.inputs[0], alpha)
        links.new(transparent.outputs[0], mix.inputs[1 if blend == 1 else 0])
        links.new(emission.outputs[0], mix.inputs[2 if blend == 1 else 1])
        surface = mix.outputs[0]
        result.surface_render_method = 'BLENDED'
    if native_culling:
        cull = (source['attributes'] >> 12) & 3
        if cull in (0,1):
            geometry = nodes.new('ShaderNodeNewGeometry')
            transparent = nodes.new('ShaderNodeBsdfTransparent')
            mix = nodes.new('ShaderNodeMixShader')
            # The importer reverses triangles with its Y/Z coordinate swap.
            # Native CCW culling becomes Blender back-face rejection.
            discard = geometry.outputs['Backfacing']
            if cull == 1:
                discard = math('SUBTRACT',1.,discard)
            input_value(mix.inputs[0],discard)
            links.new(surface,mix.inputs[1]);links.new(transparent.outputs[0],mix.inputs[2])
            surface = mix.outputs[0]
            result.surface_render_method = 'BLENDED'
    output = nodes.new('ShaderNodeOutputMaterial'); links.new(surface, output.inputs['Surface'])
    result['lsw1_shader_lab'] = ('Texture-specular' if specular else 'Ordinary') + ' ps_2_0 arithmetic; explicit test inputs; not a captured game pass'
    if legacy_plastic:
        result['lsw1_shader_lab'] = 'Effect 145 ordinary fallback; advanced lighting disabled; not full reflection reconstruction'
    if bump:
        result['lsw1_shader_lab'] = 'Effects 27/43/47 bump arithmetic; interpolated vertex light vectors; advanced reflections disabled; tangent generation is a hypothesis'
    if reflection:
        result['lsw1_shader_lab'] = ('Effects 31/45 bump plus reflection' if bump else 'Effects 35/44/48 reflection')+' arithmetic; explicit environment and parameters; not captured game lighting'
        result['lsw1_shader_reflection_parameters'] = list(reflection_parameters)
        result['lsw1_shader_reflection_skinned'] = reflection_skinned
    if specular:
        result['lsw1_shader_specular_strength'] = strength
    result['lsw1_shader_color_space'] = color_space
    result['lsw1_shader_native_culling'] = native_culling
    result['lsw1_shader_ambient'] = list(ambient)
    for index, (direction, color) in enumerate(lights):
        result[f'lsw1_shader_light_{index}_direction'] = list(direction)
        result[f'lsw1_shader_light_{index}_color'] = list(color)
    return result

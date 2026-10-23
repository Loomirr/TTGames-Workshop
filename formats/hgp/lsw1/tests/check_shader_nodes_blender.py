"""Render shader-lab cases and compare raw pixels with independent CPU arithmetic."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools'))
from shader_reference import ordinary_pixel, specular_pixel, bump_pixel, reflection_pixel, bump_reflection_pixel
from shader_nodes import material, NORMAL_ATTRIBUTE, OPACITY_ATTRIBUTE, SPECULAR_UV_ATTRIBUTE, BUMP_LIGHT_ATTRIBUTES, REFLECTION_PROBE_ATTRIBUTE, REFLECTION_CAMERA_ATTRIBUTE
from shader_pose import posed_normals, bump_corner_lights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_plane_add(size=2)
    plane = bpy.context.object
    plane.data.attributes.new(NORMAL_ATTRIBUTE, 'FLOAT_VECTOR', 'POINT')
    plane.data.attributes.new(OPACITY_ATTRIBUTE, 'FLOAT', 'POINT')
    plane.data.attributes.new(SPECULAR_UV_ATTRIBUTE, 'FLOAT_VECTOR', 'POINT')
    for name in (*BUMP_LIGHT_ATTRIBUTES,REFLECTION_PROBE_ATTRIBUTE,REFLECTION_CAMERA_ATTRIBUTE):
        plane.data.attributes.new(name, 'FLOAT_VECTOR', 'POINT')
    for point in plane.data.attributes[SPECULAR_UV_ATTRIBUTE].data:
        point.vector = (.5, .5, 0)
    bpy.ops.object.camera_add(location=(0, 0, 3))
    scene = bpy.context.scene; scene.camera = bpy.context.object
    scene.camera.data.type = 'ORTHO'; scene.camera.data.ortho_scale = 3
    scene.world = bpy.data.worlds.new('Shader test background'); scene.world.use_nodes = True
    background = (.1, .2, .3)
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (*background, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 1
    scene.render.resolution_x = 32; scene.render.resolution_y = 32
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'OPEN_EXR'; scene.render.image_settings.color_depth = '32'
    scene.cycles.samples = 8; scene.cycles.use_denoising = False
    ambient = (.12, .2, .08)
    lights = (((0, 0, 2), (.8, .25, .5)), ((1, 0, 0), (.2, .8, .4)), ((0, 0, -1), (4, 4, 4)))
    # Third light must contribute nothing for these front-facing input normals.
    cases = [
        ('opaque', 0, (0, 0, 1), .1, None, 'linear'),
        ('short-normal', 0, (0, 0, .25), 1, None, 'linear'),
        ('three-lights', 0, (.5, 0, -.25), 1, None, 'linear'),
        ('source-alpha', 1, (0, 0, 1), .2, None, 'linear'),
        ('textured-clamp', 0, (0, 0, 2), 1, (.8, .4, .2, 1), 'linear'),
        ('alpha-order', 1, (0, 0, 1), .8, (.8, .4, .2, .5), 'linear'),
        ('additive', 2, (0, 0, 1), .2, (.8, .4, .2, .5), 'linear'),
        ('black-additive', 2, (0, 0, 1), 1, (0, 0, 0, 1), 'linear'),
        ('invisible', 1, (0, 0, 1), 0, None, 'linear'),
        ('display-hypothesis', 0, (0, 0, .25), 1, None, 'display'),
    ]
    cases.extend([
        ('opaque-10-zero-alpha',10,(0,0,1),0,None,'linear'),
        ('opaque-10-transparent-texture',10,(0,0,1),0,(.8,.4,.2,0),'linear'),
    ])
    for cull in range(4):
        for back in (False,True):
            cases.append((f'cull-{cull}-'+('back' if back else 'front'),
                          10 | cull<<12,(0,0,1),0,None,'linear'))
    cases = [(*case, None) for case in cases] + [
        ('specular-only', 0, (0, 0, 1), .2, None, 'linear', (.6, .25, .9, 0)),
        ('specular-textured', 0, (0, 0, 1), 1, (.8, .4, .2, 1), 'linear', (.6, .25, .9, 0)),
        ('specular-alpha', 1, (0, 0, 1), .2, (.8, .4, .2, .5), 'linear', (.6, .25, .9, 1)),
        ('specular-clamp', 0, (0, 0, 2), 1, (1, 1, 1, 1), 'linear', (10, 20, 30, 1)),
        ('specular-display', 0, (0, 0, .25), 1, None, 'display', (.6, .25, .9, 0)),
        ('legacy-plastic-untextured', 0, (0,0,1), 1, None, 'linear', None),
        ('legacy-plastic-textured', 0, (0,0,1), 1, (.8,.4,.2,1), 'linear', None),
        ('bump-untextured', 0, (0,0,1), .2, None, 'linear', None),
        ('bump-bright-texture', 0, (0,0,1), 1, (1,1,1,1), 'linear', None),
        ('bump-neutral', 0, (0,0,1), 1, (.8,.4,.2,1), 'linear', None),
        ('bump-alpha', 1, (0,0,1), .2, (.8,.4,.2,.5), 'linear', None),
        ('bump-additive', 2, (0,0,1), .2, (.8,.4,.2,.5), 'linear', None),
        ('bump-display', 0, (0,0,1), 1, (.8,.4,.2,1), 'display', None),
    ]
    for skin in (False,True):
        kind = 'skin' if skin else 'rigid'
        for variation,normal,texel,mode in (
                ('front',(0,0,1),None,0),('edge',(0,0,1),None,0),
                ('short-normal',(0,0,.25),None,0),('bright',(0,0,1),(1,1,1,1),0),
                ('alpha',(0,0,1),(.8,.4,.2,.5),1),('environment',(0,0,1),None,0)):
            cases.append((f'reflection-{kind}-{variation}',mode,normal,.2,texel,'linear',None))
    cases.extend([(label.replace('reflection-','reflection-bump-'),*rest) for label,*rest in list(cases) if label.startswith('reflection-')])
    identity = Matrix.Identity(4)
    # Source-coordinate tangent hypothesis: T=X, T cross N=-Y, N=Z.
    # The importer's Y/Z swap transforms these to X, -Z, Y respectively.
    part = dict(vertices=[(0,0,0),(1,0,0),(0,1,0)], faces=[(0,1,2)],
                normals=[(0,0,1)]*3, uvs=[(0,0),(1,0),(0,1)],
                weights=[{0:1.}]*3, rigid_bone=0)
    basis_lights = (((1,0,0),(1,1,1)),((0,0,-1),(1,1,1)),((0,1,0),(1,1,1)))
    mesh_count = len(bpy.data.meshes)
    corners = bump_corner_lights(part,[identity],[identity],basis_lights)
    for corner in corners:
        for actual,wanted in zip(corner,((1,0,0),(0,1,0),(0,0,1))):
            assert max(abs(a-b) for a,b in zip(actual,wanted)) < 1e-6
    scaled=dict(part,normals=[(0,0,3)]*3)
    diagonal=(((1,1,0),(1,1,1)),)*3
    reflected=bump_corner_lights(scaled,[identity],[identity],diagonal,normalize_reflection_normal=True)
    for corner in reflected:
        for value in corner:
            assert max(abs(a-b) for a,b in zip(value,(2**-.5,0,2**-.5)))<1e-6
    # The same basis after a rigid pose and a one-bone skin pose must agree.
    turn = Matrix.Rotation(.7,4,'Y')
    rigid = bump_corner_lights(part,[turn],[identity],basis_lights)
    skin = bump_corner_lights(dict(part,rigid_bone=None),[turn],[identity],basis_lights)
    assert rigid == skin
    try:
        bump_corner_lights(dict(part,normals=[(0,0,0)]*3),[identity],[identity],basis_lights)
    except ValueError:
        pass
    else:
        raise AssertionError('Zero authored bump basis accepted')
    assert len(bpy.data.meshes) == mesh_count, 'Temporary tangent mesh leaked'
    rotated = Matrix(((0,0,1,0),(0,1,0,0),(-1,0,0,0),(0,0,0,1)))
    # Native Y maps to Blender Z. One rotated bone maps it to X; a 25/75
    # two-bone blend must retain (.25,0,.75), not renormalize its length.
    for label, rigid, weights, expected_normal in (
            ('posed-rigid', 0, {0:1.}, (1.,0.,0.)),
            ('posed-skin', None, {0:.25,1:.75}, (.25,0.,.75))):
        sampled = posed_normals([(0,1,0)], rigid, [weights], [rotated,identity], [identity,identity])[0]
        assert max(abs(a-b) for a,b in zip(sampled,expected_normal)) < 1e-7
        cases.append((label,0,tuple(sampled),1,None,'linear',None))
    for weights in ({}, {5:1.}, {0:float('nan')}, {0:.5}, {0:-1.,1:2.}):
        try:
            posed_normals([(0,1,0)],None,[weights],[rotated,identity],[identity,identity])
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid shader weights accepted')
    reports = []
    eevee = 'BLENDER_EEVEE' if bpy.app.version >= (5, 0, 0) else 'BLENDER_EEVEE_NEXT'
    for engine in ('CYCLES', eevee):
        scene.render.engine = engine
        for label, blend, normal, opacity, texel, space, specular_texel in cases:
            source = dict(effect=0, attributes=blend, linked_material=0, normal_texture=None,
                          diffuse=(.5, .25, 1), texture=0 if texel is not None else None)
            legacy_plastic = label.startswith('legacy-plastic-')
            if legacy_plastic:
                source['effect'] = 145
            image = None
            if texel is not None:
                image = bpy.data.images.new(label, 2, 2, alpha=True, float_buffer=True)
                image.colorspace_settings.name = 'Non-Color'
                image.pixels[:] = list(texel) * 4; image.pack()
            auxiliary, lookup, bump_image = None, None, None
            bump_texel = (.5,.5,.5,1.) if label == 'bump-neutral' else (.8,.6,1.,.25)
            if label.startswith(('bump-','reflection-bump-')):
                source.update(effect=135,linked_material=2,normal_texture=1)
                auxiliary = dict(effect=135,attributes=0x3f520002,texture_aux=0x7fef,texture=1,linked_material=0)
                bump_image = bpy.data.images.new(label+' bump',2,2,alpha=True,float_buffer=True)
                bump_image.colorspace_settings.name = 'Non-Color'
                bump_image.pixels[:] = list(bump_texel)*4; bump_image.pack()
                for name,(direction,_) in zip(BUMP_LIGHT_ATTRIBUTES,lights):
                    for point in plane.data.attributes[name].data:
                        point.vector = direction
            if specular_texel is not None:
                source.update(effect=129, linked_material=2)
                auxiliary = dict(effect=129, attributes=0x3f514512, texture=0, linked_material=0, diffuse=(1, 1, 1))
                lookup = bpy.data.images.new(label + ' lookup', 2, 2, alpha=True, float_buffer=True)
                lookup.colorspace_settings.name = 'Non-Color'; lookup.pixels[:] = list(specular_texel) * 4; lookup.pack()
            reflection = label.startswith('reflection-')
            parameters,environment,reflection_sample = None,None,None
            if reflection:
                if bump_image is None:source['effect']=145
                parameters=(.05,.7,.2,.8)
                reflection_sample=(10.,5.,2.,0.) if label.endswith('-bright') else (.8,.4,.25,0.)
                camera_vector=(1,0,0) if label.endswith('-edge') else (.3,0,1)
                for name,value in ((REFLECTION_PROBE_ATTRIBUTE,(.6,.2,1)),(REFLECTION_CAMERA_ATTRIBUTE,camera_vector)):
                    for point in plane.data.attributes[name].data: point.vector=value
                if label.endswith('-environment'):
                    environment=bpy.data.images.new(label+' environment',4,2,alpha=True,float_buffer=True)
                    environment.colorspace_settings.name='Non-Color'
                    environment.pixels[:]=list(reflection_sample)*8; environment.pack()
            plane.rotation_euler.x = math.pi if label.startswith('cull-') and label.endswith('-back') else 0.
            candidate = material(source, image, ambient, lights, color_space=space, name=label,
                                 specular_image=lookup, auxiliary=auxiliary, legacy_plastic=legacy_plastic,
                                 bump_image=bump_image, native_culling=label.startswith('cull-'),
                                 reflection_parameters=parameters,reflection_environment=environment,
                                 reflection_sample=reflection_sample if environment is None else None,
                                 reflection_skinned='-skin-' in label)
            plane.data.materials.clear(); plane.data.materials.append(candidate)
            for point in plane.data.attributes[NORMAL_ATTRIBUTE].data:
                point.vector = normal
            for point in plane.data.attributes[OPACITY_ATTRIBUTE].data:
                point.value = opacity
            plane.data.update()
            scene.render.filepath = str(output / f'{engine}-{label}.exr')
            bpy.ops.render.render(write_still=True)
            rendered = bpy.data.images.load(scene.render.filepath, check_existing=False)
            offset = (16 * 32 + 16) * 4
            actual = tuple(rendered.pixels[offset:offset + 3])
            rgba = ordinary_pixel(source['diffuse'], opacity, normal, ambient, lights, texel)
            if specular_texel is not None:
                rgba = specular_pixel(source['diffuse'], opacity, normal, ambient, lights, specular_texel, .1, texel)
            if bump_image is not None:
                rgba = bump_pixel(source['diffuse'],opacity,bump_texel,ambient,lights,texel)
                rgba = (*rgba[:3],min(1.,max(0.,rgba[3])))  # surface coverage clamps output alpha
            if reflection:
                rgba=reflection_pixel(source['diffuse'],opacity,normal,ambient,lights,(.6,.2,1),camera_vector,
                                      parameters,reflection_sample,texel,skinned='-skin-' in label)
                if bump_image is not None:
                    rgba=bump_reflection_pixel(source['diffuse'],opacity,normal,ambient,lights,(.6,.2,1),camera_vector,
                                               parameters,reflection_sample,bump_texel,texel)
                rgba=(*rgba[:3],min(1.,max(0.,rgba[3])))
            color = rgba[:3]
            if space == 'display':
                color = tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in color)
            mode = blend & 15
            expected = color if mode in (0,10) else tuple(
                value * rgba[3] + bg * (1 - rgba[3] if mode == 1 else 1)
                for value, bg in zip(color, background))
            if label.startswith('cull-'):
                cull = (blend >> 12) & 3
                back = label.endswith('-back')
                if (cull == 0 and back) or (cull == 1 and not back):
                    expected = background
            error = max(abs(a - b) for a, b in zip(actual, expected))
            if error > .003:
                raise AssertionError((engine, label, actual, expected, error))
            reports.append(dict(engine=engine, case=label, actual=actual, expected=expected, error=error))
            bpy.data.images.remove(rendered)
    (output / 'report.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print('SHADER_NODE_RENDER_PASS', len(reports), 'cases', flush=True)


if __name__ == '__main__':
    main()

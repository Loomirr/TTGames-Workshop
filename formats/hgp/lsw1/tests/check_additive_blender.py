"""Render a mode-2 surface over a known background and check its contribution.

blender -b --factory-startup --python-exit-code 1 --python this.py -- new-output
Checks Cycles and Eevee, including zero alpha and black additive texels.
"""
import importlib.util
import argparse
import json
from pathlib import Path
import struct
import sys

import bpy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--addon',type=Path,help='Extracted extension ZIP to verify instead of source')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    component=args.addon.resolve() if args.addon else Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('lsw1_additive_test',component/'__init__.py',
                                              submodule_search_locations=[str(component)])
    addon=importlib.util.module_from_spec(spec);sys.modules[spec.name]=addon;spec.loader.exec_module(addon)
    from lsw1_additive_test.importer import make_materials, OPACITY_ATTRIBUTE
    from lsw1_additive_test.colour import diffuse_to_linear

    class Source:
        path=Path('synthetic.hgp')
        def __init__(self,color,effect=0,linked=0,texture_alpha=None):
            self.texture_alpha=texture_alpha
            self.source=dict(diffuse=color,attributes=0x3ed00a12,effect=effect,
                             linked_material=linked,texture=0 if texture_alpha is not None else None,normal_texture=None)
        def materials(self):return [self.source]
        def textures(self):
            # Uncompressed BGRA DDS, uniform RGB with a separately chosen alpha.
            header=struct.pack('<31I',124,0x100f,2,2,8,0,0,*([0]*11),32,0x41,0,32,
                               0xff0000,0xff00,0xff,0xff000000,0x1000,0,0,0,0)
            return [b'DDS '+header+bytes((32,64,128,self.texture_alpha))*4]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    # The same blend nibble is also used by auxiliary shader passes. Do not
    # replace those with a simple additive emitter.
    for effect,linked in ((129,0),(0,1)):
        material=make_materials(Source((1,1,1),effect,linked),'auxiliary',False)[0]
        assert 'lsw1_additive_preview' not in material
        assert material.node_tree.nodes.get('Principled BSDF')
    bpy.ops.mesh.primitive_plane_add(size=2)
    plane=bpy.context.object
    opacity=plane.data.attributes.new(OPACITY_ATTRIBUTE,'FLOAT','POINT')
    bpy.ops.object.camera_add(location=(0,0,3))
    scene=bpy.context.scene;scene.camera=bpy.context.object
    scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=3
    scene.world=bpy.data.worlds.new('Known background');scene.world.use_nodes=True
    background=(.1,.2,.3)
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(*background,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=1
    scene.render.resolution_x=48;scene.render.resolution_y=48;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32'
    scene.render.film_transparent=False
    scene.cycles.samples=8;scene.cycles.use_denoising=False
    reports=[]
    eevee='BLENDER_EEVEE' if bpy.app.version>=(5,0,0) else 'BLENDER_EEVEE_NEXT'
    for engine in ('CYCLES',eevee):
        scene.render.engine=engine
        for case,color,alpha,texture_alpha in [('black',(0,0,0),1,None),('invisible',(.5,.25,.125),0,None),
                ('partial',(.5,.25,.125),.25,None),('full',(.5,.25,.125),1,None),
                ('texture-alpha',(128/255,64/255,32/255),.25,128),
                ('transparent-texture',(128/255,64/255,32/255),1,0)]:
            material=make_materials(Source(color,texture_alpha=texture_alpha),case,texture_alpha is not None)[0]
            plane.data.materials.clear();plane.data.materials.append(material)
            for point in opacity.data:point.value=alpha
            assert 'lsw1_additive_preview' in material
            path=output/(engine+'-'+case+'.exr');scene.render.filepath=str(path)
            bpy.ops.render.render(write_still=True)
            rendered=bpy.data.images.load(str(path),check_existing=False)
            index=(24*48+24)*4
            actual=tuple(rendered.pixels[index:index+3])
            coverage=alpha*(texture_alpha/255 if texture_alpha is not None else 1)
            expected=tuple(b+c*coverage for b,c in zip(background,diffuse_to_linear(color)))
            error=max(abs(a-b) for a,b in zip(actual,expected))
            assert error<.003,(engine,case,actual,expected,error)
            reports.append(dict(engine=engine,case=case,actual=actual,expected=expected,error=error))
            bpy.data.images.remove(rendered)
    (output/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print('ADDITIVE_RENDER_PASS',len(reports),'cases',flush=True)


if __name__=='__main__':main()

"""Check actual imported color/material roles against user-supplied LSW1 HGPs.

blender -b --factory-startup --python tests/check_colours_blender.py -- source_dir report.json
Game files and reports are not included in the extension package.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Color

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lsw1_colour_check',root/'__init__.py',submodule_search_locations=[str(root)])
addon=importlib.util.module_from_spec(spec);sys.modules[spec.name]=addon;spec.loader.exec_module(addon)
from lsw1_colour_check.hgp import HGP
from lsw1_colour_check.importer import make_materials


def main():
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    if len(args)!=2:raise SystemExit('Supply a directory of original HGPs and a new JSON report path')
    source,output=map(Path,args)
    if output.exists():raise ValueError('Report already exists; use a fresh output path')
    paths=sorted(p for p in source.iterdir() if p.suffix.lower()=='.hgp')
    if not paths:raise ValueError('No HGP inputs')
    results=[];unsupported=[]
    for path in paths:
        try:h=HGP(path);sources=h.materials();h.meshes()
        except (ValueError,AssertionError,IndexError) as error:
            unsupported.append(dict(file=path.name,error=str(error)));continue
        mats=make_materials(h,path.stem,True)
        colored=normal=alpha=textured=0
        for source,mat in zip(sources,mats):
            expected=Color(source['diffuse']).from_srgb_to_scene_linear()
            assert max(abs(mat.diffuse_color[i]-expected[i]) for i in range(3))<2e-6,(path.name,mat.name)
            bsdf=mat.node_tree.nodes.get('Principled BSDF')
            if source['texture'] is None:
                assert not bsdf.inputs['Base Color'].is_linked
                assert max(abs(bsdf.inputs['Base Color'].default_value[i]-expected[i]) for i in range(3))<2e-6
                colored+=any(abs(v-1)>1e-6 for v in source['diffuse'])
            else:
                tex=bsdf.inputs['Base Color'].links[0].from_node
                assert tex.type=='TEX_IMAGE' and tex.image.colorspace_settings.name=='sRGB' and tex.image.packed_file
                textured+=1
                if source['attributes']&15 in (1,10):
                    assert bsdf.inputs['Alpha'].links[0].from_node==tex
                    assert bsdf.inputs['Alpha'].links[0].from_socket.name=='Alpha';alpha+=1
            if source['normal_texture'] is not None:
                node=bsdf.inputs['Normal'].links[0].from_node
                assert node.type=='NORMAL_MAP'
                image=node.inputs['Color'].links[0].from_node.image
                assert image.colorspace_settings.name=='Non-Color' and image.packed_file;normal+=1
        results.append(dict(file=path.name,materials=len(mats),colored_constants=colored,
                            textured=textured,alpha=alpha,normals=normal))
        for mat in mats:bpy.data.materials.remove(mat,do_unlink=True)
        for image in list(bpy.data.images):
            if image.users==0:bpy.data.images.remove(image)
        print('COLOR_CHECK',path.name,len(mats),flush=True)
    assert results,'No readable inputs checked'
    output.parent.mkdir(parents=True,exist_ok=True)
    report=dict(blender=bpy.app.version_string,checked=results,unsupported=unsupported,
                method='Blender native sRGB conversion, actual material nodes, packed images, alpha and normal roles')
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('LSW1_COLOUR_REGRESSION_PASSED',len(results),'files',len(unsupported),'unsupported',flush=True)

if __name__=='__main__':main()

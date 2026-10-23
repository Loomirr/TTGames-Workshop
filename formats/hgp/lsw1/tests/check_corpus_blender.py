"""Import a user-owned original PC corpus and check preserved source data.

blender -b --factory-startup --python-exit-code 1 --python this.py -- input-root new-output
Use an isolated profile. Reports contain input paths and belong under local/.
This checks structure/material links; it does not certify game rendering.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback

import bpy
from mathutils import Matrix,Vector


def main():
    source,output=[Path(p).resolve() for p in sys.argv[sys.argv.index('--')+1:]]
    output.mkdir(parents=True,exist_ok=False)
    component=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('lsw1_corpus',component/'__init__.py',submodule_search_locations=[str(component)])
    addon=importlib.util.module_from_spec(spec);sys.modules[spec.name]=addon;spec.loader.exec_module(addon)
    from lsw1_corpus.hgp import HGP
    from lsw1_corpus.importer import import_character,C,matrix,OPACITY_ATTRIBUTE,PACKED_COLOR_ATTRIBUTE
    paths=sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower()=='.hgp')
    assert paths,'No original HGP files found'
    reports=[]
    for path in paths:
        row=dict(file=str(path.relative_to(source)))
        try:
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            bpy.ops.wm.read_factory_settings(use_empty=True)
            h=HGP(path);parts=h.meshes();rig=import_character(bpy.context,path,correct_preview_pose=False)
            assert len(rig.data.bones)==h.count
            assert list(rig['lsw1_selected_layers'])==sorted({p['layer'] for p in parts})
            meshes=sorted(rig.children,key=lambda o:int(o.name.rsplit(' ',1)[1]))
            assert len(meshes)==len(parts)
            bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
            max_uv_error=0.;deform_error=0.;nonopaque=0;normal_anomalies=0;degenerate=0;worlds=[]
            for bone in h.bones:
                local=matrix(bone['local']);world=worlds[bone['parent']]@local if bone['parent']>=0 else local;worlds.append(world)
            for obj,part in zip(meshes,parts):
                mesh=obj.data
                assert len(mesh.vertices)==len(part['vertices'])
                assert [tuple(p.vertices) for p in mesh.polygons]==part['faces']
                assert obj['lsw1_layer_index']==part['layer']
                assert obj['lsw1_layer_name']==h.layers[part['layer']]
                opacity=mesh.attributes[OPACITY_ATTRIBUTE];packed=mesh.attributes[PACKED_COLOR_ATTRIBUTE]
                assert opacity.domain==packed.domain=='POINT'
                for i,color in enumerate(part['colors']):
                    assert abs(opacity.data[i].value-color[3]/255.)<1e-7
                    assert packed.data[i].value&0xffffffff==int.from_bytes(bytes(color),'little')
                    nonopaque+=color[3]!=255
                for vertex,expected in zip(mesh.vertices,part['weights']):
                    actual={rig.data.bones[obj.vertex_groups[g.group].name]['lsw1_joint_index']:g.weight for g in vertex.groups}
                    assert actual.keys()==expected.keys()
                    assert all(math.isfinite(w) and w>0 for w in actual.values())
                    assert abs(sum(actual.values())-1)<1e-5
                    assert all(abs(actual[i]-w)<1e-6 for i,w in expected.items())
                bind=C@worlds[part['rigid_bone']]@C if part['rigid_bone'] is not None else Matrix.Identity(4)
                normal_matrix=bind.to_3x3().inverted().transposed()
                normals=[n.vector.copy() for n in mesh.corner_normals]
                uv=mesh.uv_layers['Original LSW1 UV']
                for polygon in mesh.polygons:
                    if polygon.area==0:
                        degenerate+=1;assert not polygon.use_smooth
                    for li in polygon.loop_indices:
                        vi=mesh.loops[li].vertex_index;u,v=part['uvs'][vi]
                        max_uv_error=max(max_uv_error,abs(uv.data[li].uv.x-u),abs(uv.data[li].uv.y-(1-v)))
                        assert all(math.isfinite(x) for x in normals[li])
                        n=part['normals'][vi]
                        if polygon.area>0 and math.hypot(*n)>0:
                            expected=(normal_matrix@Vector((n[0],n[2],n[1]))).normalized()
                            if (normals[li]-expected).length>.005:normal_anomalies+=1
                ev=obj.evaluated_get(deps);evaluated=ev.to_mesh()
                for a,b in zip(mesh.vertices,evaluated.vertices):
                    assert all(math.isfinite(x) for x in b.co)
                    deform_error=max(deform_error,(a.co-b.co).length)
                ev.to_mesh_clear()
            assert max_uv_error<1e-6 and deform_error<2e-5
            records=h.materials()
            for obj,part in zip(meshes,parts):
                mat=obj.data.materials[0];record=records[part['material']];bsdf=mat.node_tree.nodes.get('Principled BSDF')
                if bsdf:
                    color=bsdf.inputs['Base Color']
                    product=bsdf.inputs['Alpha'].links[0].from_node if bsdf.inputs['Alpha'].is_linked else None
                else:
                    assert record['attributes']&15==2 and record['effect']==0
                    assert not record['linked_material'] and record['normal_texture'] is None
                    assert mat.surface_render_method=='BLENDED'
                    surface=mat.node_tree.nodes['Material Output'].inputs['Surface'].links[0].from_node
                    assert surface.type=='ADD_SHADER' and surface.inputs[0].links[0].from_node.type=='BSDF_TRANSPARENT'
                    emission=surface.inputs[1].links[0].from_node
                    assert emission.type=='EMISSION'
                    color=emission.inputs['Color']
                    product=emission.inputs['Strength'].links[0].from_node.inputs[0].links[0].from_node
                if record['attributes']&15 in (1,10) or bsdf is None:
                    assert product.type=='MATH' and product.operation=='MULTIPLY'
                    assert product.inputs[0].links[0].from_node.attribute_name==OPACITY_ATTRIBUTE
                    if record['texture'] is not None:
                        assert product.inputs[1].links[0].from_socket.name=='Alpha'
                    else:assert not product.inputs[1].is_linked and product.inputs[1].default_value==1.
                if record['texture'] is not None:
                    image=color.links[0].from_node.image
                    assert image.packed_file and image.colorspace_settings.name=='sRGB'
                if record['normal_texture'] is not None:
                    image=bsdf.inputs['Normal'].links[0].from_node.inputs['Color'].links[0].from_node.image
                    assert image.packed_file and image.colorspace_settings.name=='Non-Color'
            assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            row.update(imported=True,bones=h.count,parts=len(parts),faces=sum(len(p['faces']) for p in parts),
                selected_layers=h.selected_layers(),max_uv_error=max_uv_error,neutral_deform_error=deform_error,
                nonopaque_vertices=nonopaque,preserved_degenerate_faces=degenerate,remaining_normal_corners=normal_anomalies)
        except Exception:row['error']=traceback.format_exc()
        reports.append(row)
        print('HGP_CORPUS',len(reports),len(paths),row['file'],row.get('error','OK'),flush=True)
        (output/'validation.json').write_text(json.dumps(dict(blender=bpy.app.version_string,results=reports),indent=2),encoding='utf-8')
    assert all(r.get('imported') for r in reports),[r for r in reports if not r.get('imported')]
    print('LSW1_CORPUS_CHECK_PASSED',len(reports),'files; remaining normal corners',sum(r['remaining_normal_corners'] for r in reports))

if __name__=='__main__':main()

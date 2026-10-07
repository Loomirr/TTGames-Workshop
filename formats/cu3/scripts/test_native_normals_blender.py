"""Asset-free import-normal regression on adjacent non-coplanar triangles.

blender --background --factory-startup --python-exit-code 1 --python this.py -- output
"""
import copy,hashlib,struct,sys,tempfile,types
from pathlib import Path
import bpy
from mathutils import Matrix,Vector

root=Path(__file__).resolve().parents[1]
package=types.ModuleType('io_scene_lego_cu3');package.__path__=[str(root/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from io_scene_lego_cu3.native_model_blender import create_model
from io_scene_lego_cu3.blender_import import C
from io_scene_lego_cu3.material_edit_guard import check_materials
from io_scene_lego_cu3.cu3 import FormatError
from io_scene_lego_cu3.native_mesh import read_mesh_bytes
from io_scene_lego_cu3.mesh_edit_blender import vertex_edits
from io_scene_lego_cu3.mesh_edit import patch_vertices
output=Path(sys.argv[sys.argv.index('--')+1]).resolve();output.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
source=output/'synthetic-source.txt';source.write_text('Asset-free geometry fixture')
positions=[(0,0,0),(0,1,0),(0,0,1),(1,0,0)]
normal=[255,128,128,255]
part=dict(index=0,vertices=[dict(position=list(p),normal=normal) for p in positions],
          triangles=[[0,1,2],[0,3,1]],morphs=None,attribute_types={'normal':8})
identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
model=dict(source=str(source),mesh_version=175,skeleton=None,parts=[part],
           display={'specials':[dict(index=0,name='Fixture',matrix=identity,parts=[{'part':0,'material':0}])]},
           materials=[dict(name='Vertex inspection',table_version=175,
                           fields={'alphaTest':False,'zBias':0},
                           render_flags={'colourWriteMask':15,'castShadows':True})])
rig,objects=create_model(model,'Normal regression',bpy.context.scene.collection)
obj=objects[0];expected=(C.to_3x3()@Vector([v/127.5-1 for v in normal[:3]])).normalized()
errors=[(n.vector-expected).length for n in obj.data.corner_normals]
assert max(errors)<.005,errors  # Below one packed-normal byte step (1/127.5).
assert [tuple(v.co) for v in obj.data.vertices]==[tuple(C@Vector(p)) for p in positions]
assert obj.data.attributes.get('TT_NativeNormalBaseline')
assert all((n.vector-base.vector).length<1e-7 for n,base in zip(obj.data.corner_normals,obj.data.attributes['TT_NativeNormalBaseline'].data))
check_materials(obj)
material=obj.data.materials[0];roughness=material.node_tree.nodes['Principled BSDF'].inputs['Roughness']
old=roughness.default_value;roughness.default_value=.123
try:check_materials(obj)
except FormatError:pass
else:raise AssertionError('Native export must reject unsupported material node edits')
roughness.default_value=old;check_materials(obj)

# Original LB3 helmet parts contain repeated-index faces. The legacy Blender
# normal encoder can crash on those fans; the evaluated helper must preserve
# both the native topology and authored directions instead of deleting faces.
degenerate=copy.deepcopy(model)
degenerate['parts'][0]['triangles'].append([0,1,1])
_,safe_objects=create_model(degenerate,'Repeated-index normal regression',bpy.context.scene.collection)
safe=safe_objects[0]
assert safe.get('tt_native_normal_workaround')
assert [list(p.vertices) for p in safe.data.polygons]==degenerate['parts'][0]['triangles']
bpy.context.view_layer.update()
evaluated=safe.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
assert all((normal.vector-expected).length<.005 for normal in evaluated.corner_normals)
assert [tuple(v.co) for v in safe.data.vertices]==[tuple(C@Vector(p)) for p in positions]


def mixed_normal_bytes(version, packed, fallback):
    """Independent bounded vertex/index payload; fallback can be a loose vertex."""
    dx=version==175;endian='<' if dx else '>'
    points=positions+([(2,2,2)] if fallback=='loose' else [])
    valid=[255,128,128,255] if packed else [1.,.2,.1]
    missing=[128,128,128,255] if packed else [0.,0.,0.]
    values=[missing if fallback=='all' or fallback=='used' and i==1 or fallback=='loose' and i==4
            else valid for i in range(len(points))]
    raw=b'HSEM'+struct.pack('>I',version)+(b'' if dx else b'ROTV')+struct.pack('>I',1)
    if dx:raw+=struct.pack('>I',1)
    raw+=struct.pack('>I',1)+struct.pack('>3I',1,0,len(points))+b'DXTV'+struct.pack('>2I',169,2)
    raw+=bytes((0,3,0,1,8 if packed else 3,12))+bytes(6)
    for position,direction in zip(points,values):
        raw+=struct.pack(endian+'3f',*position)
        raw+=bytes(direction) if packed else struct.pack(endian+'3f',*direction)
    raw+=struct.pack('>2I',0,0)
    raw+=struct.pack('>4I',1,0,6,2)+struct.pack(endian+'6H',0,1,2,0,3,1)
    raw+=struct.pack('>3IH3I',0,6,0,0,len(points),0,0)+bytes(44)
    return raw+(b'' if dx else bytes(32))


case_errors=[]
with tempfile.TemporaryDirectory(prefix='tt-mixed-normal-check-',dir=output) as temporary:
    for version in (169,170,175):
        for packed in (False,True):
            for fallback in ('used','loose','all'):
                label=f'{version}-{"packed" if packed else "float"}-{fallback}'
                raw=mixed_normal_bytes(version,packed,fallback)
                file=Path(temporary)/(label+'.ghg');file.write_bytes(raw)
                decoded=read_mesh_bytes(raw)
                # Nonuniform static scaling exercises the existing inverse-
                # transpose conversion while normals remain source directions.
                transform_values=[2,0,0,0,0,3,0,0,0,0,.5,0,0,0,0,1]
                decoded.update(source=str(file),skeleton=None,
                    display={'specials':[dict(index=0,name='Mixed normal fixture',matrix=transform_values,
                                             parts=[{'part':0,'material':0}])]},materials=model['materials'])
                source_parts=copy.deepcopy(decoded['parts'])
                fixture_rig,parts=create_model(decoded,label,bpy.context.scene.collection)
                imported=parts[0];mesh=imported.data
                transform=C@Matrix.Diagonal((2,3,.5,1))
                normal_transform=transform.to_3x3().inverted().transposed()
                original=decoded['parts'][0]['vertices']
                assert [tuple(v.co) for v in mesh.vertices]==[tuple(transform@Vector(v['position'])) for v in original],label
                assert [list(p.vertices) for p in mesh.polygons]==decoded['parts'][0]['triangles'],label
                automatic=bpy.data.meshes.new(label+' / automatic reference')
                automatic.from_pydata([tuple(v.co) for v in mesh.vertices],[],[tuple(p.vertices) for p in mesh.polygons])
                for polygon in automatic.polygons:polygon.use_smooth=True
                automatic.update()
                for loop in mesh.loops:
                    stored=original[loop.vertex_index]['normal'][:3]
                    direction=Vector([x/127.5-1 for x in stored] if packed else stored)
                    expected=((normal_transform@direction).normalized() if direction.length>.1
                              else automatic.corner_normals[loop.index].vector)
                    error=(mesh.corner_normals[loop.index].vector-expected).length
                    assert error<.005,(label,loop.index,error)
                    case_errors.append(error)
                # The importer must never repair the original vertex payload.
                assert decoded['parts']==source_parts,label
                assert file.read_bytes()==raw,label
                manifest=vertex_edits(parts,decoded,hashlib.sha256(raw).hexdigest())
                assert manifest['parts']=={'0':{}},(label,manifest)
                output_bytes,report=patch_vertices(raw,manifest)
                assert output_bytes==raw and report['changed_bytes']==0,(label,report)
                check_materials(imported)
                bpy.data.meshes.remove(automatic)
print('NATIVE_NORMALS_CHECK_PASSED',max(errors+case_errors),
      '18 NXG/DX11 mixed/loose/all-fallback normal fixtures; packed/float directions, transforms, topology and byte-identical no-op export')

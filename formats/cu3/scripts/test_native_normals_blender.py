"""Asset-free import-normal regression on adjacent non-coplanar triangles.

blender --background --factory-startup --python-exit-code 1 --python this.py -- output
"""
import sys,types
from pathlib import Path
import bpy
from mathutils import Vector

root=Path(__file__).resolve().parents[1]
package=types.ModuleType('io_scene_lego_cu3');package.__path__=[str(root/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from io_scene_lego_cu3.native_model_blender import create_model
from io_scene_lego_cu3.blender_import import C
from io_scene_lego_cu3.material_edit_guard import check_materials
from io_scene_lego_cu3.cu3 import FormatError
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
print('NATIVE_NORMALS_CHECK_PASSED',max(errors))

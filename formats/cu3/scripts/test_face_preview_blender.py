"""Manual asset-free check of facial holdout compositing and hidden-mask setup.

blender --background --factory-startup --python-exit-code 1 --python this.py -- output
"""
import sys,types
from pathlib import Path
import bpy

root=Path(__file__).resolve().parents[1]
package=types.ModuleType('io_scene_lego_cu3')
package.__path__=[str(root/'Addon/io_scene_lego_cu3')]
sys.modules[package.__name__]=package
from io_scene_lego_cu3.face_preview import prepare_render

output=Path(sys.argv[sys.argv.index('--')+1]).resolve()
output.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
body=bpy.data.collections.new('Body');scene.collection.children.link(body)
details=bpy.data.collections.new('Source facial geometry');scene.collection.children.link(details)

def plane(name,size,z,color,collection,mask=None):
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata([(-size,-size,z),(size,-size,z),(size,size,z),(-size,size,z)],[],[(0,1,2,3)])
    obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj)
    material=bpy.data.materials.new(name);material.use_nodes=True
    tree=material.node_tree;tree.nodes.clear()
    emission=tree.nodes.new('ShaderNodeEmission');emission.inputs['Color'].default_value=(*color,1)
    target=tree.nodes.new('ShaderNodeOutputMaterial');tree.links.new(emission.outputs[0],target.inputs['Surface'])
    mesh.materials.append(material)
    if mask is not None:
        obj['source_model']='FACE_SYNTHETIC';obj['tt_colour_write_mask']=mask
    return obj

plane('Blue body',1,0,(0,0,1),body)
detail=plane('Red facial detail',.8,.1,(1,0,0),details,15)
mask=plane('Initially hidden depth mask',.3,.1,(0,1,0),details,0)
mask.hide_render=True;mask.hide_set(True)
mask.shape_key_add(name='Basis');mask.shape_key_add(name='TT_Target_000').value=0
original_vertices=[tuple(v.co) for v in mask.data.vertices]
camera_data=bpy.data.cameras.new('Camera');camera=bpy.data.objects.new('Camera',camera_data)
scene.collection.objects.link(camera);camera.location=(0,0,3)
camera_data.type='ORTHO';camera_data.ortho_scale=2.4;scene.camera=camera
scene.view_settings.view_transform='Standard'
report=prepare_render(scene)
assert report['depth_parts']==1 and not mask.hide_render and not mask.hide_get()
assert original_vertices==[tuple(v.co) for v in mask.data.vertices]
assert mask.data.shape_keys.key_blocks['TT_Target_000'].value==0
assert len(scene.view_layers)==2 and scene.render.use_compositing
scene.cycles.device='CPU';scene.cycles.samples=4
scene.render.resolution_x=scene.render.resolution_y=128;scene.render.resolution_percentage=100
scene.render.filepath=str(output/'mask-composite.png')
bpy.ops.render.render(write_still=True)
image=bpy.data.images.load(scene.render.filepath,check_existing=False)
pixels=list(image.pixels)
def pixel(x,y):return pixels[(y*128+x)*4:(y*128+x)*4+4]
center,edge=pixel(64,64),pixel(96,64)
assert center[2]>.9 and center[0]<.05,center
assert edge[0]>.9 and edge[2]<.05,edge
assert original_vertices==[tuple(v.co) for v in mask.data.vertices]
print('FACE_COMPOSITOR_CHECK_PASSED',report,center,edge)

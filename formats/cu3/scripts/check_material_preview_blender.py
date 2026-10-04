"""Check recovered vertex albedo through a bake and opacity through EEVEE."""
import bpy,sys,tempfile,argparse,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'Addon'))
from io_scene_lego_cu3.material_preview import attach_vertex_albedo,attach_vertex_opacity
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',type=Path,help='Writable folder for temporary rendered fixtures')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.output_dir:args.output_dir.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object
color=plane.data.color_attributes.new(name='SourceColor',type='FLOAT_COLOR',domain='POINT')
for c in color.data:c.color=(.5,.25,.75,0)
mat=bpy.data.materials.new('Verified albedo fixture');mat.use_nodes=True;plane.data.materials.append(mat)
principled=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
principled.inputs['Base Color'].default_value=(.8,.6,.4,1)
principled.inputs['Specular IOR Level'].default_value=0
assert not attach_vertex_albedo(mat,native_vert_albedo=False)
assert attach_vertex_albedo(mat,native_vert_albedo=True)
assert not attach_vertex_albedo(mat,native_vert_albedo=True)
image=bpy.data.images.new('Bake fixture',16,16,float_buffer=True)
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;mat.node_tree.nodes.active=node
bpy.context.scene.render.engine='CYCLES';bpy.context.scene.cycles.samples=1
bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'})
pixel=list(image.pixels)[(8*16+8)*4:][:3]
assert max(abs(x-y) for x,y in zip(pixel,(.4,.15,.3)))<.005,pixel
assert not attach_vertex_opacity(mat,native_ignore_vertex_opacity=True,native_can_alpha_blend=True)
alpha_image=bpy.data.images.new('Source alpha fixture',1,1,float_buffer=True)
alpha_image.pixels[:]=(1,1,1,.5)
alpha_texture=mat.node_tree.nodes.new('ShaderNodeTexImage');alpha_texture.image=alpha_image
mat.node_tree.links.new(alpha_texture.outputs['Alpha'],principled.inputs['Alpha'])
assert attach_vertex_opacity(mat,native_ignore_vertex_opacity=False,native_can_alpha_blend=True)
assert not attach_vertex_opacity(mat,native_ignore_vertex_opacity=False,native_can_alpha_blend=True)
principled.inputs['Emission Color'].default_value=(1,0,0,1);principled.inputs['Emission Strength'].default_value=1
bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,-.1));back=bpy.context.object
blue=bpy.data.materials.new('Blue background');blue.use_nodes=True;back.data.materials.append(blue)
p=next(n for n in blue.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
p.inputs['Emission Color'].default_value=(0,0,1,1);p.inputs['Emission Strength'].default_value=1
bpy.ops.object.camera_add(location=(0,0,3));camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=2
scene=bpy.context.scene;scene.camera=camera;scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=16;scene.render.resolution_y=16;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='OPEN_EXR'
temporary=(args.output_dir or Path(tempfile.gettempdir())).resolve()
prefix='tt-material-check-'+uuid.uuid4().hex
files=[]
try:
    results=[]
    for alpha in (0,1):
        for c in color.data:c.color=(.5,.25,.75,alpha)
        plane.data.update();bpy.context.view_layer.update()
        path=temporary/f'{prefix}-{alpha}.exr';assert not path.exists();files.append(path)
        scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        result=bpy.data.images.load(scene.render.filepath)
        results.append(list(result.pixels)[(8*16+8)*4:][:3]);bpy.data.images.remove(result)
    assert results[0][0]<.01 and results[0][2]>.99,results
    assert .35<results[1][0]<.65 and .35<results[1][2]<.65,results
finally:
    for path in files:path.unlink(missing_ok=True)
print('MATERIAL_PREVIEW_CHECK_PASSED: linear albedo bake, preserved texture alpha, native vertex fade, idempotence and disabled flags',pixel,results)

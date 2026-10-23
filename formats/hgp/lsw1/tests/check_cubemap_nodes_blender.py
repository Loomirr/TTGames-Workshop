"""Render asymmetric cube faces to check axis selection and image orientation."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from shader_cubemap import sample_nodes


def main(output):
    output.mkdir(parents=True,exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object
    bpy.ops.object.camera_add(location=(0,0,3))
    scene=bpy.context.scene;scene.camera=bpy.context.object
    scene.camera.data.type='ORTHO';scene.camera.data.ortho_scale=3
    scene.render.resolution_x=32;scene.render.resolution_y=32;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32'
    scene.cycles.samples=4;scene.cycles.use_denoising=False
    images=[]
    for face in range(6):
        image=bpy.data.images.new(f'Cube face {face}',4,4,alpha=True,float_buffer=True)
        image.colorspace_settings.name='Non-Color'
        image.pixels[:]=[v for y in range(4) for x in range(4) for v in ((x+.5)/4,(y+.5)/4,(face+1)/8,1.)]
        image.pack();images.append(image)
    mat=bpy.data.materials.new('Cube orientation');mat.use_nodes=True
    nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
    def set_input(socket,value):
        if isinstance(value,bpy.types.NodeSocket):links.new(value,socket)
        else:socket.default_value=value
    def math(operation,a,b=0.,clamp=False):
        n=nodes.new('ShaderNodeMath');n.operation=operation;n.use_clamp=clamp
        set_input(n.inputs[0],a);set_input(n.inputs[1],b);return n.outputs[0]
    def vec(operation,a,b):
        n=nodes.new('ShaderNodeVectorMath');n.operation=operation
        set_input(n.inputs[0],a);set_input(n.inputs[3 if operation=='SCALE' else 1],b)
        return n.outputs['Vector']
    direction=nodes.new('ShaderNodeCombineXYZ')
    sample=sample_nodes(nodes,links,math,vec,direction.outputs[0],images)
    emission=nodes.new('ShaderNodeEmission');links.new(sample,emission.inputs[0])
    out=nodes.new('ShaderNodeOutputMaterial');links.new(emission.outputs[0],out.inputs[0])
    plane.data.materials.append(mat)
    # Independent face-camera definitions from Direct3D's look-at example.
    frames=(((1,0,0),(0,1,0)),((-1,0,0),(0,1,0)),
            ((0,1,0),(0,0,-1)),((0,-1,0),(0,0,1)),
            ((0,0,1),(0,1,0)),((0,0,-1),(0,1,0)))
    reports=[]
    eevee='BLENDER_EEVEE' if bpy.app.version>=(5,0,0) else 'BLENDER_EEVEE_NEXT'
    for engine in ('CYCLES',eevee):
        scene.render.engine=engine
        for face,(forward,up) in enumerate(frames):
            forward,up=Vector(forward),Vector(up);right=up.cross(forward)
            for u,v in ((.375,.625),(.625,.375),(.5,.5)):
                native=forward+right*(2*u-1)+up*(2*v-1)
                for socket,value in zip(direction.inputs,(native.x,native.z,native.y)):
                    socket.default_value=value
                scene.render.filepath=str(output/f'{engine}-{face}-{u}.exr')
                bpy.ops.render.render(write_still=True)
                image=bpy.data.images.load(scene.render.filepath,check_existing=False)
                actual=tuple(image.pixels[(16*32+16)*4:(16*32+16)*4+3])
                wanted=(u,v,(face+1)/8)
                error=max(abs(a-b) for a,b in zip(actual,wanted))
                if error>.003:raise AssertionError((engine,face,u,v,actual,wanted))
                reports.append(dict(engine=engine,face=face,uv=(u,v),actual=actual,error=error))
                bpy.data.images.remove(image)
    (output/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print('CUBE_ORIENTATION_PASS',len(reports),flush=True)


if __name__=='__main__':main(Path(sys.argv[sys.argv.index('--')+1]).resolve())

"""Viewing-only classic geometry and CU2 references. No native export bindings.

Coordinates convert source left-handed Y-up into Blender Z-up with (x,z,y).
Skinned geometry keeps its source bind positions; unresolved rigid pieces are
isolated and hidden until their native attachment ownership is decoded.
"""
import json
import math
import struct
import tempfile
from pathlib import Path
import bpy
from mathutils import Matrix, Vector
from .nu20 import NU20
from .cu2 import Cutscene

C = Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
STORES = ('objects','collections','meshes','armatures','materials','images','texts','cameras','scenes')


def row_matrix(values):
    if len(values) != 16 or not all(math.isfinite(v) for v in values):
        raise ValueError('Invalid classic source matrix')
    return Matrix([values[i:i+4] for i in range(0,16,4)]).transposed()


def transaction(operation):
    if bpy.context.mode != 'OBJECT':
        raise ValueError('Switch to Object Mode before importing')
    before={kind:set(getattr(bpy.data,kind)) for kind in STORES}
    scene=bpy.context.window.scene if bpy.context.window else None
    try:
        return operation()
    except Exception:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if scene and bpy.context.window:bpy.context.window.scene=scene
        bpy.data.batch_remove(ids={v for kind in STORES for v in getattr(bpy.data,kind) if v not in before[kind]})
        raise


def skeleton(nu, collection):
    if not nu.bones:return None
    worlds=[]
    for b in nu.bones:
        local=row_matrix(b['bind_local'])
        world=local if b['parent']<0 else worlds[b['parent']] @ local
        # Blender edit-bone matrices cannot retain arbitrary rest scale/shear.
        # Refuse these rigs rather than silently stripping native transforms.
        basis=world.to_3x3();metric=basis.transposed() @ basis
        if basis.determinant() <= 0 or max(abs(metric[i][j]-(i==j)) for i in range(3) for j in range(3)) > 0.002:
            raise ValueError('Classic rig has unsupported rest scale/shear/reflection: '+b['name'])
        residual=world @ row_matrix(b['inverse_bind'])
        if max(abs(residual[i][j] - (i==j)) for i in range(4) for j in range(4))>0.002:
            raise ValueError('Classic bind and inverse-bind matrices disagree: '+b['name'])
        worlds.append(world)
    arm=bpy.data.armatures.new(Path(nu.path).stem+' / native rig')
    rig=bpy.data.objects.new(arm.name,arm);collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for b,world in zip(nu.bones,worlds):
        bone=arm.edit_bones.new(b['name']);bone.matrix=C @ world @ C
        bone.length=0.015
        if b['parent']>=0:bone.parent=arm.edit_bones[nu.bones[b['parent']]['name']]
    bpy.ops.object.mode_set(mode='OBJECT')
    for b in nu.bones:
        bone=arm.bones[b['name']]
        bone['native_index']=b['index'];bone['native_bind_local']=b['bind_local']
        bone['native_inverse_bind']=b['inverse_bind'];bone['native_record_matrix']=b['record_matrix']
    rig['tt_classic_inspection']=True
    rig['tt_classic_source']=str(nu.path)
    rig['tt_classic_limitations']='Static source rig inspection. AN3 binding and native export are not enabled.'
    return rig


def weights(nu, mesh):
    fmt,note=nu.mesh_layout(mesh)
    if note:raise ValueError(note)
    w=fmt.get('blend_weights');j=fmt.get('blend_indices')
    if not w and not j:return None
    if not w or not j or w[0]!='byte4' or j[0]!='byte4':
        raise ValueError('Unsupported classic skin weight/index encoding')
    vb=nu.vertex_buffers[mesh['vertex_buffer']][0]
    rows=[]
    for v in range(mesh['vertex_count']):
        at=vb+(mesh['vertex_offset']+v)*mesh['stride']
        values=nu.d[at+w[1]:at+w[1]+3];indices=nu.d[at+j[1]:at+j[1]+3]
        if sum(values) not in (254,255,256):
            raise ValueError('Classic skin weights do not sum to one')
        row=[]
        for value,index in zip(values,indices):
            if not value:continue
            if index>=len(mesh['bones']) or not 0<=mesh['bones'][index]<len(nu.bones):
                raise ValueError('Classic skin palette references an invalid native bone')
            row.append((mesh['bones'][index],value/255.0))
        rows.append(row)
    return rows


def inspect_model(context, path, read_dds, apply_normals):
    nu=NU20(path)
    report=dict(source=str(path),version=nu.version,mode='classic_raw_inspection',issues=[],meshes=0,
                limitations=['Raw source draws include costume/visibility alternatives; this is not a configured character.',
                             'Unbound rigid GHG pieces are hidden in a separate collection. Native attachment ownership is not inferred by index.',
                             'Diffuse RGB and vertex-color approximation only. Material tint/render states, alpha, layered shaders, expressions and AN3 playback remain incomplete.'])
    planned=[]
    planned_vertices=0
    # Keep each declared model-material pairing; do not borrow another draw's material.
    special_models={s['model'] for s in nu.special_objects if s['model']>=0}
    draws=[(s['name'],nu.models[s['model']],row_matrix(s['matrix'])) for s in nu.special_objects if 0<=s['model']<len(nu.models)]
    draws += [('Static',model,Matrix.Identity(4)) for model in nu.models if model['index'] not in special_models]
    for name,model,transform in draws:
        for mi,material in zip(model['meshes'],model['materials']):
            if mi<0:
                report['issues'].append('Unsupported display command in model '+str(model['index']));continue
            mesh=dict(nu.meshes[mi],material=material)
            if planned_vertices + mesh['vertex_count'] > 4000000:
                raise ValueError('Classic scene exceeds four million imported vertices; inspect smaller source files')
            try:
                geo=nu.mesh_geometry(mesh)
                if not geo:raise ValueError(mesh['geometry_note'])
                if not geo[4]:continue
                skin=weights(nu,mesh) if nu.bones else None
                planned.append((name,model['index'],mesh,geo,skin,transform))
                planned_vertices+=len(geo[0])
            except ValueError as error:
                report['issues'].append(f'Mesh {mi}: {error}')
    if not planned:raise ValueError('No supported classic geometry: '+'; '.join(report['issues'][:3]))

    def build():
        collection=bpy.data.collections.new(Path(path).stem+' / Classic inspection')
        context.scene.collection.children.link(collection)
        unbound=bpy.data.collections.new('Unbound rigid pieces / inspect separately')
        collection.children.link(unbound);unbound.hide_render=True;unbound.hide_viewport=True
        rig=skeleton(nu,collection)
        materials={};images={}
        def material(index):
            if index in materials:return materials[index]
            if not 0<=index<len(nu.materials):raise ValueError('Invalid classic material index')
            source=nu.materials[index];mat=bpy.data.materials.new(f'Classic / {index}')
            mat.use_nodes=True;mat['tt_native_material']=json.dumps(source)
            bsdf=mat.node_tree.nodes.get('Principled BSDF')
            bsdf.inputs['Base Color'].default_value=source['colour']
            bsdf.inputs['Roughness'].default_value=0.5
            color=mat.node_tree.nodes.new('ShaderNodeVertexColor');color.layer_name='NativeColor'
            mat.node_tree.links.new(color.outputs['Color'],bsdf.inputs['Base Color'])
            tex=source['texture']
            if 0<=tex<len(nu.textures):
                try:
                    if tex not in images:
                        t=nu.textures[tex]
                        if not t['size'] or t.get('cubemap'):raise ValueError('Not a 2D diffuse texture')
                        raw=nu.d[t['data_offset']:t['data_offset']+t['size']]
                        read_dds(raw,legacy_d3d9=True)
                        with tempfile.TemporaryDirectory(prefix='tt-classic-') as folder:
                            file=Path(folder)/'image.dds';file.write_bytes(raw)
                            im=bpy.data.images.load(str(file),check_existing=False)
                            im.pack()
                            if not len(im.pixels):raise ValueError('Blender did not decode this DDS format')
                            im.name=Path(path).stem+f' / DDS {tex}';images[tex]=im
                    node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=images[tex]
                    multiply=mat.node_tree.nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY';multiply.inputs[0].default_value=1
                    mat.node_tree.links.new(node.outputs['Color'],multiply.inputs[1])
                    mat.node_tree.links.new(color.outputs['Color'],multiply.inputs[2])
                    mat.node_tree.links.new(multiply.outputs[0],bsdf.inputs['Base Color'])
                    # Native alpha render-state interpretation is not yet verified.
                    # Keep the original alpha in the image/node for inspection,
                    # without treating every texture alpha as surface opacity.
                except (ValueError,RuntimeError,OSError) as error:
                    report['issues'].append(f'Texture {tex}: {error}')
            materials[index]=mat;return mat
        for name,model_id,source,(pos,normals,uv,col,tris),skin,transform in planned:
            mesh=bpy.data.meshes.new(f'{name} / model {model_id} / mesh {source["index"]}')
            matrix=C @ transform
            mesh.from_pydata([matrix @ Vector(v) for v in pos],[],[(a,c,b) for a,b,c in tris]);mesh.update()
            obj=bpy.data.objects.new(mesh.name,mesh)
            unresolved=bool(nu.bones and skin is None)
            (unbound if unresolved else collection).objects.link(obj)
            obj['tt_classic_mesh_index']=source['index'];obj['tt_classic_model_index']=model_id
            if uv:
                layer=mesh.uv_layers.new(name='Native UV')
                for loop in mesh.loops:
                    u,v=uv[loop.vertex_index];layer.data[loop.index].uv=(u,1-v)
            attr=mesh.color_attributes.new(name='NativeColor',type='BYTE_COLOR',domain='POINT')
            for target,value in zip(attr.data,col or [(1,1,1,1)]*len(pos)):target.color_srgb=value
            for poly in mesh.polygons:poly.use_smooth=True
            if normals:
                nmat=matrix.to_3x3().inverted().transposed()
                apply_normals(obj,[nmat @ Vector(n) for n in normals])
            mesh.materials.append(material(source['material']))
            if rig:
                obj.parent=rig
                if skin:
                    groups=[obj.vertex_groups.new(name=b['name']) for b in nu.bones]
                    for vi,row in enumerate(skin):
                        for bi,value in row:groups[bi].add([vi],value,'ADD')
                    mod=obj.modifiers.new('Native skin','ARMATURE');mod.object=rig
            report['meshes']+=1
        report['bones']=len(nu.bones)
        report['unbound_rigid_meshes']=len(unbound.objects)
        text=bpy.data.texts.new(Path(path).stem+' / Classic model report');text.write(json.dumps(report,indent=2))
        collection['tt_import_report']=text.name
        return collection,report
    return transaction(build)


def inspect_cutscene(context,path):
    cut=Cutscene(path)
    report=dict(source=str(path),version=cut.version,frames=cut.frames,fps=cut.fps,fps_source=cut.fps_source,
                cameras=cut.cameras,shots=cut.shots,characters=cut.characters,objects=cut.objects,notes=cut.notes,
                limitations=['Static source placements and shot timing only. Camera movement/lens, actor rigs, animation, environments and effects are not assembled.'])
    # Validate all matrices before making scene changes. Lens units remain unverified.
    for row in cut.cameras+cut.characters+cut.objects:row_matrix(row['matrix'])
    def build():
        scene=bpy.data.scenes.new(Path(path).stem+' / CU2 references')
        scene.frame_start=1;scene.frame_end=max(1,cut.frames)
        scene.render.fps=round(cut.fps);scene.render.fps_base=round(cut.fps)/cut.fps
        cameras=[]
        for i,row in enumerate(cut.cameras):
            # An empty shows the native placement without pretending the lens
            # or camera-axis convention has been verified for playback.
            obj=bpy.data.objects.new(f'Camera reference {i}',None);scene.collection.objects.link(obj)
            obj.empty_display_type='ARROWS';obj.empty_display_size=0.15
            obj.matrix_world=C @ row_matrix(row['matrix']) @ C
            obj['source_camera_record']=json.dumps(row);cameras.append(obj)
        for kind,rows in [('Actor',cut.characters),('Object',cut.objects)]:
            for i,row in enumerate(rows):
                obj=bpy.data.objects.new(f'{kind} {i} / {row["name"]}',None);scene.collection.objects.link(obj)
                obj.empty_display_type='PLAIN_AXES';obj.empty_display_size=0.1
                obj.matrix_world=C @ row_matrix(row['matrix']) @ C
                obj['source_record']=json.dumps(row)
        for first,last,camera in cut.shots:
            scene.timeline_markers.new('No source camera' if camera is None else f'Source camera {camera}',frame=first+1)
        text=bpy.data.texts.new(Path(path).stem+' / CU2 report');text.write(json.dumps(report,indent=2))
        scene['tt_import_report']=text.name;scene['tt_classic_inspection']=True
        if context.window:context.window.scene=scene
        return scene,report
    return transaction(build)

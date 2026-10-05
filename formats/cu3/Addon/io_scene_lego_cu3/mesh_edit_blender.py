"""Collect native-space edits from original, unevaluated Blender mesh data."""
import json
from mathutils import Matrix, Vector
from .cu3 import FormatError
from .face_edit_blender import topology_hash
from .mesh_edit import SCHEMA


def bind_vertices(obj, transform):
    obj['tt_vertex_topology_sha256'] = topology_hash(obj.data)
    obj['tt_vertex_transform'] = json.dumps([list(row) for row in transform])


def vertex_edits(objects, model, source_hash):
    result = dict(schema=SCHEMA,sha256=source_hash,mesh_version=model['mesh_version'],parts={})
    parts = {p['index']:p for p in model['parts']}
    for obj in objects:
        if obj.type!='MESH' or not obj.get('tt_vertex_transform'):continue
        if topology_hash(obj.data)!=obj['tt_vertex_topology_sha256']:
            raise FormatError('Native mesh topology or vertex order changed')
        part = parts[obj['source_part']]
        transform = Matrix(json.loads(obj['tt_vertex_transform']))
        inverse = transform.inverted()
        mesh, vertices, changes = obj.data, part['vertices'], {}
        if vertices and 'normal' in vertices[0]:
            typ=part['attribute_types']['normal']
            if typ not in (3,4,6,8):raise FormatError('Unverified native normal encoding')
            normal_transform=transform.to_3x3().inverted().transposed()
            normal_inverse=normal_transform.inverted()
            baseline=mesh.attributes.get('TT_NativeNormalBaseline')
            if baseline is None or baseline.domain!='CORNER' or baseline.data_type!='FLOAT_VECTOR':
                raise FormatError('Preserve the imported native normal baseline attribute')
            rows=[v['normal'][:] for v in vertices];changed=False;normal_loops={}
            for loop in mesh.loops:
                index=loop.vertex_index;normal=mesh.corner_normals[loop.index].vector.copy()
                normal_loops.setdefault(index,[]).append((normal,baseline.data[loop.index].vector.copy()))
            for index,loops in normal_loops.items():
                if all((normal-base).length<=2e-5 for normal,base in loops):continue
                normal=loops[0][0]
                if any((normal-other).length>.002 for other,base in loops):
                    raise FormatError('Split normals require native vertex splits')
                old=vertices[index]['normal']
                native=Vector([x/127.5-1 for x in old[:3]] if typ==8 else old[:3])
                if native.length<.1:raise FormatError('Native normal is not a verified unit direction')
                native=(normal_inverse@normal).normalized()
                rows[index]=([max(0,min(255,round((x+1)*127.5))) for x in native] if typ==8 else list(native))+old[3:]
                changed=True
            if changed:changes['normal']=rows
        skeleton=model.get('skeleton')
        if skeleton:
            if 'tt_native_rigid_joint' not in obj:
                raise FormatError('Reimport this model with the current addon before editing native skin weights')
            joints={j['name']:j['index'] for j in skeleton['joints']}
            rows=[];changed=False;rigid=obj['tt_native_rigid_joint']
            for point,original in zip(mesh.vertices,vertices):
                actual={}
                for group in point.groups:
                    if group.weight==0:continue
                    name=obj.vertex_groups[group.group].name
                    if name not in joints:raise FormatError('Non-native weighted vertex group: '+name)
                    actual[joints[name]]=actual.get(joints[name],0)+group.weight
                baseline={rigid:1} if rigid>=0 else {}
                if rigid<0:
                    for j,w in original.get('weights',[]):baseline[j]=baseline.get(j,0)+w
                different=actual.keys()!=baseline.keys() or any(abs(actual[j]-baseline[j])>1e-6 for j in actual)
                if different and rigid>=0:raise FormatError('Rigid joint reassignment requires native display editing')
                rows.append([[j,w] for j,w in sorted(actual.items())]);changed|=different
            if changed:changes['weights']=rows
        rows, changed = [], False
        for point,original in zip(mesh.vertices,vertices):
            expected = transform @ Vector(original['position'][:3])
            if tuple(point.co)==tuple(expected):rows.append(original['position']);continue
            changed = True
            rows.append(list(inverse @ point.co)+original['position'][3:])
        if changed:changes['position']=rows
        for field in ('uv','uv2','uv3'):
            if not vertices or field not in vertices[0]:continue
            rows = [v[field][:] for v in vertices];changed=False
            for component in range(len(rows[0])//2):
                layer = mesh.uv_layers.get(f'Source {field} {component}')
                if layer is None:raise FormatError('Original native UV layer was removed')
                seen = {}
                for loop in mesh.loops:
                    index=loop.vertex_index;uv=layer.data[loop.index].uv
                    pair=tuple(uv)
                    if index in seen and seen[index]!=pair:
                        raise FormatError('UV seams require native vertex splits; preserve one UV per vertex')
                    seen[index]=pair
                    old=vertices[index][field][component*2:component*2+2]
                    # Match float32 Blender rounding, so no-op half/float UVs stay byte-identical.
                    from mathutils import Vector as V
                    if pair!=tuple(V((old[0],1-old[1]))):
                        rows[index][component*2:component*2+2]=[uv[0],1-uv[1]];changed=True
            if changed:changes[field]=rows
        if vertices and 'color' in vertices[0]:
            color=mesh.color_attributes.get('SourceColor')
            if color is None or color.domain!='POINT' or color.data_type!='BYTE_COLOR':
                raise FormatError('Preserve original SourceColor point byte attribute')
            rows=[[round(x*255) for x in c.color_srgb] for c in color.data]
            if rows!=[v['color'] for v in vertices]:changes['color']=rows
        key=str(part['index'])
        previous=result['parts'].get(key)
        if previous is not None and previous!=changes:
            raise FormatError('Different display copies have conflicting edits to native part '+key)
        result['parts'][key]=changes
    return result

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

"""Layout-preserving native vertex edits, with no topology or skeleton encoder.

Only verified attributes are patched. All other bytes, buffers, references,
draw bindings and bounds stay intact. Face Basis positions remain immutable.
"""
import hashlib
import math
import struct
from .cu3 import FormatError
from .native_mesh import read_mesh_bytes


SCHEMA = 'tt.native-vertex-edits.v1'


def patch_vertices(data, edits):
    if edits.get('schema') != SCHEMA or edits.get('sha256') != hashlib.sha256(data).hexdigest():
        raise FormatError('Native vertex source hash/schema mismatch')
    model = read_mesh_bytes(data)
    if edits.get('mesh_version') != model['mesh_version']:
        raise FormatError('Native vertex layout version mismatch')
    parts = {str(p['index']):p for p in model['parts']}
    patch, writes = {}, []
    requested = edits.get('parts')
    if not isinstance(requested, dict):
        raise FormatError('Vertex edits require a part table')
    for key, changes in requested.items():
        if key not in parts or not isinstance(changes, dict):
            raise FormatError('Vertex edits reference an absent native part')
        part = parts[key]
        for field, rows in changes.items():
            if field not in ('position','uv','uv2','uv3','color') or field not in part['attribute_layout']:
                raise FormatError('Unsupported edited native attribute: '+field)
            layout = part['attribute_layout'][field]
            typ, endian = layout['type'], layout['endian']
            if field=='color':
                if typ not in (8,9):raise FormatError('Unverified native color encoding')
                fmt, width = '4B', 4
            else:
                if typ not in (2,3,4,5,6):raise FormatError('Unverified native float encoding')
                fmt = f'{typ}f' if typ in (2,3,4) else '2e' if typ==5 else '4e'
                width = typ if typ in (2,3,4) else 2 if typ==5 else 4
            if not isinstance(rows,list) or len(rows)!=part['vertex_count']:
                raise FormatError('Native vertex count/order must be preserved')
            native = [v[field] for v in part['vertices']]
            bounds = [(min(v[i] for v in native),max(v[i] for v in native)) for i in range(3)] if field=='position' and native else []
            for index,(row,old) in enumerate(zip(rows,native)):
                if not isinstance(row,(tuple,list)) or len(row)!=width or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in row):
                    raise FormatError('Invalid native vertex attribute values')
                if field=='color' and any(type(x)!=int or not 0<=x<=255 for x in row):
                    raise FormatError('Native colors require four integer bytes')
                stored = list(row)
                if field=='color' and model['mesh_version']==175 and typ==9:
                    stored = [row[2],row[1],row[0],row[3]]
                try:
                    payload = struct.pack(endian+fmt,*stored)
                except (OverflowError,struct.error) as error:
                    raise FormatError('Edited value exceeds native attribute precision') from error
                at = layout['offset']+index*layout['stride']
                if payload == data[at:at+len(payload)]:continue
                if field=='position':
                    if part['morphs']:
                        raise FormatError('Face Basis position edits are not supported')
                    decoded = struct.unpack(endian+fmt,payload)
                    if len(row)>3 and row[3:] != old[3:]:
                        raise FormatError('Preserve native position padding/homogeneous coordinate')
                    if any(x<low or x>high for x,(low,high) in zip(decoded[:3],bounds)):
                        raise FormatError('Position edit exceeds original part bounds; bounds rebuilding is not supported')
                for off,value in enumerate(payload,at):
                    if off in patch and patch[off]!=value:
                        raise FormatError('Conflicting edits to a shared native vertex buffer')
                    patch[off]=value
                writes.append(dict(part=key,attribute=field,vertex=index,offset=at,bytes=len(payload)))
    output = bytearray(data)
    for at,value in patch.items():output[at]=value
    output = bytes(output)
    decoded = read_mesh_bytes(output)
    if len(decoded['parts'])!=len(model['parts']):raise FormatError('Patched native part count changed')
    aliases = []
    for old,new in zip(model['parts'],decoded['parts']):
        if old['triangles']!=new['triangles'] or old['palette']!=new['palette'] or old['morphs']!=new['morphs']:
            raise FormatError('Vertex patch changed native topology, skinning or shape targets')
        for field in old['attribute_layout']:
            for index,(a,b) in enumerate(zip(old['vertices'],new['vertices'])):
                if a[field] != b[field]:
                    if field=='position':
                        if old['morphs']:raise FormatError('Shared buffer edit would change a facial Basis')
                        bounds=[(min(v[field][i] for v in old['vertices']),max(v[field][i] for v in old['vertices'])) for i in range(3)]
                        if any(x<lo or x>hi for x,(lo,hi) in zip(b[field][:3],bounds)):
                            raise FormatError('Shared buffer edit exceeds another native part bounds')
                    if field not in ('position','uv','uv2','uv3','color'):
                        raise FormatError('Vertex patch changed an unedited native attribute')
                    if str(old['index']) not in requested or field not in requested[str(old['index'])]:
                        aliases.append(dict(part=old['index'],attribute=field,vertex=index))
    return output, dict(schema=SCHEMA,mesh_version=model['mesh_version'],source_sha256=edits['sha256'],
        output_sha256=hashlib.sha256(output).hexdigest(),changed_bytes=sum(a!=b for a,b in zip(data,output)),
        writes=writes,shared_buffer_changes=aliases,validation='Decoded patched native mesh; preserved topology, palettes and targets')

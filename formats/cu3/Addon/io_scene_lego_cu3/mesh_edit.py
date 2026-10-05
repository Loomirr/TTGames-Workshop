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


def skin_rows(part, rows):
    """Quantize four existing palette influences; preserve unchanged bytes."""
    if not all(part['attribute_layout'].get(f,{}).get('type')==t for f,t in (('indices',7),('packed_weights',8))):
        raise FormatError('Unverified native skin attribute layout')
    if not isinstance(rows,list) or len(rows)!=part['vertex_count']:
        raise FormatError('Native skin vertex count/order must be preserved')
    indices,weights=[],[]
    for row,old in zip(rows,part['vertices']):
        if not isinstance(row,list):raise FormatError('Invalid native influence table')
        values={}
        for pair in row:
            if not isinstance(pair,(tuple,list)) or len(pair)!=2 or type(pair[0])!=int or not isinstance(pair[1],(int,float)) or not math.isfinite(pair[1]) or pair[1]<0:
                raise FormatError('Invalid native skin influence')
            if pair[1]:values[pair[0]]=values.get(pair[0],0)+pair[1]
        original={}
        for joint,weight in old.get('weights',[]):original[joint]=original.get(joint,0)+weight
        if values.keys()==original.keys() and all(abs(values[j]-original[j])<1e-6 for j in values):
            indices.append(old['indices']);weights.append(old['packed_weights']);continue
        if not 1<=len(values)<=4 or abs(sum(values.values())-1)>1e-5:
            raise FormatError('Normalize one to four native skin influences per vertex')
        if any(j not in part['palette'] for j in values):
            raise FormatError('Skin edit requires a new native palette bone; palette rebuilding is unsupported')
        if sum(w for ix,w in zip(old['indices'],old['packed_weights']) if ix!=255)!=255:
            raise FormatError('Native skin writer requires the verified 255-byte weight total')
        ordered=sorted(values,key=lambda j:(-values[j],j))
        scaled=[values[j]/sum(values.values())*255 for j in ordered]
        quantized=[math.floor(v) for v in scaled]
        remainder=255-sum(quantized)
        for i in sorted(range(len(ordered)),key=lambda i:(-(scaled[i]-quantized[i]),i))[:remainder]:quantized[i]+=1
        kept=[(j,w) for j,w in zip(ordered,quantized) if w]
        indices.append([part['palette'].index(j) for j,w in kept]+[255]*(4-len(kept)))
        weights.append([w for j,w in kept]+[0]*(4-len(kept)))
    return {'indices':indices,'packed_weights':weights}


def patch_vertices(data, edits):
    if edits.get('schema') != SCHEMA or edits.get('sha256') != hashlib.sha256(data).hexdigest():
        raise FormatError('Native vertex source hash/schema mismatch')
    model = read_mesh_bytes(data)
    if edits.get('mesh_version') != model['mesh_version']:
        raise FormatError('Native vertex layout version mismatch')
    parts = {str(p['index']):p for p in model['parts']}
    patch, writes, skin_origins = {}, [], {}
    requested = edits.get('parts')
    if not isinstance(requested, dict):
        raise FormatError('Vertex edits require a part table')
    for key, changes in requested.items():
        if key not in parts or not isinstance(changes, dict):
            raise FormatError('Vertex edits reference an absent native part')
        part = parts[key]
        changes=dict(changes)
        if any(field in changes for field in ('indices','packed_weights')):
            raise FormatError('Use paired native weights, not raw palette/weight byte edits')
        if 'weights' in changes:
            changes.update(skin_rows(part,changes.pop('weights')))
        for field, rows in changes.items():
            if field not in ('position','uv','uv2','uv3','color','normal','indices','packed_weights') or field not in part['attribute_layout']:
                raise FormatError('Unsupported edited native attribute: '+field)
            if field in ('indices','packed_weights') and 'weights' not in requested[key]:
                raise FormatError('Use paired native weights, not raw palette/weight byte edits')
            layout = part['attribute_layout'][field]
            typ, endian = layout['type'], layout['endian']
            if field in ('indices','packed_weights') or field=='normal' and typ==8:
                fmt,width='4B',4
            elif field=='color':
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
                if fmt=='4B' and any(type(x)!=int or not 0<=x<=255 for x in row):
                    raise FormatError('Native packed attributes require four integer bytes')
                stored = list(row)
                if field=='color' and model['mesh_version']==175 and typ==9:
                    stored = [row[2],row[1],row[0],row[3]]
                try:
                    payload = struct.pack(endian+fmt,*stored)
                except (OverflowError,struct.error) as error:
                    raise FormatError('Edited value exceeds native attribute precision') from error
                at = layout['offset']+index*layout['stride']
                if payload == data[at:at+len(payload)]:continue
                if field=='normal':
                    xyz=[v/127.5-1 for v in row[:3]] if typ==8 else row[:3]
                    if abs(math.sqrt(sum(v*v for v in xyz))-1)>.02:
                        raise FormatError('Edited native normals must be unit directions')
                    if len(row)>3 and row[3:]!=old[3:]:raise FormatError('Preserve native normal padding')
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
                    if field in ('indices','packed_weights'):skin_origins[off]=tuple(part['palette'])
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
                    if field not in ('position','uv','uv2','uv3','color','normal','indices','packed_weights'):
                        raise FormatError('Vertex patch changed an unedited native attribute')
                    request_field='weights' if field in ('indices','packed_weights') else field
                    if str(old['index']) not in requested or request_field not in requested[str(old['index'])]:
                        if request_field=='weights':
                            layout=old['attribute_layout'][field];at=layout['offset']+index*layout['stride']
                            if any(skin_origins.get(off,tuple(old['palette']))!=tuple(old['palette']) for off in range(at,at+4)):
                                raise FormatError('Shared skin buffer uses a different native palette; edit each alias explicitly')
                        aliases.append(dict(part=old['index'],attribute=field,vertex=index))
    return output, dict(schema=SCHEMA,mesh_version=model['mesh_version'],source_sha256=edits['sha256'],
        output_sha256=hashlib.sha256(output).hexdigest(),changed_bytes=sum(a!=b for a,b in zip(data,output)),
        writes=writes,shared_buffer_changes=aliases,validation='Decoded patched native mesh; preserved topology, palettes and targets')

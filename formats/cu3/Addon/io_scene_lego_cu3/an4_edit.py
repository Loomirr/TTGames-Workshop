"""Experimental standalone ANI-D sample writer; existing trees stay intact.

Append one rebuilt six/nine-channel block, redirect its record and decode it again.
Frame count, native node order, actor names and all other records are retained.
This does not rebuild PAK banks or encode ANI-E, events, scales or face controls.
"""
import hashlib
import math
import struct
from .cu3 import FormatError,Reader,Animation
from .an4 import AnimationFile


def encode_samples(samples,node_flags,curves=6):
    frames=len(samples);nodes=len(node_flags)
    keys=4*(frames-1)+1
    if not 0<frames<=16384 or not 0<nodes<=2048 or keys>65535:
        raise FormatError('Baked ANI-D counts exceed verified writer limits')
    if curves not in (6,9) or any(flag & ~(0x7b if curves==9 else 0x73) for flag in node_flags):
        raise FormatError('ANI-D writer requires six/nine-channel skeletal nodes')
    for frame in samples:
        if len(frame)!=nodes or any(len(row)!=curves or not all(math.isfinite(v) for v in row) for row in frame):
            raise FormatError('ANI-D samples require finite channels for each native node')
        if any(abs(v)>3.4e38 for row in frame for v in row):
            raise FormatError('ANI-D sample exceeds float32 precision')
        if curves==9 and any(v<=1e-8 for row in frame for v in row[6:]):
            raise FormatError('ANI-D writer requires positive nonzero scale')
    constants,scales,types,animated,tolerances=[],[],[],[],[]
    for node in range(nodes):
        for channel in range(curves):
            values=[frame[node][channel] for frame in samples]
            tolerances.append((max(values)-min(values))/65535)
            if min(values)==max(values):
                value=values[0]
                if value in (0,1):types.append(14 if value==0 else 15)
                else:
                    types.append(16+len(constants));constants.append(value)
            else:
                low,high=min(values),max(values)
                scale=(high-low)/65535
                low=struct.unpack('>f',struct.pack('>f',low))[0]
                scale=struct.unpack('>f',struct.pack('>f',scale))[0]
                if not math.isfinite(scale) or scale<=0:raise FormatError('ANI-D range exceeds float32 precision')
                types.append(7);scales.extend((scale,low));animated.append((values,scale,low))
    if len(constants)+16>=0x8000:raise FormatError('ANI-D constant pool exceeds curve-type range')
    stride=8*len(animated)
    if stride>65535:raise FormatError('ANI-D baked key stride exceeds uint16')
    def aligned(value):return (value+3)&~3
    scale_at=80;constant_at=scale_at+4*len(scales);type_at=constant_at+4*len(constants)
    key_at=aligned(type_at+2*len(types));flags_at=key_at+(frames+1)*stride
    if flags_at+nodes>256*1024*1024:raise FormatError('Baked ANI-D output exceeds 256 MiB')
    raw=bytearray(flags_at+nodes);raw[:4]=b'ANID'
    struct.pack_into('>6H',raw,4,nodes,keys,stride,frames,curves,0)
    raw[19]=0xc0;struct.pack_into('>H',raw,22,frames)
    struct.pack_into('>2f',raw,28,0,1)
    struct.pack_into('>9I',raw,36,scale_at,constant_at,type_at,key_at,flags_at,0,0,0,0)
    struct.pack_into('>2f',raw,72,4,0)
    if scales:struct.pack_into('>'+str(len(scales))+'f',raw,scale_at,*scales)
    if constants:struct.pack_into('>'+str(len(constants))+'f',raw,constant_at,*constants)
    struct.pack_into('>'+str(len(types))+'H',raw,type_at,*types)
    # With ratio four, each integer source frame lands on a group base.
    # Intermediate tangents interpolate toward the following frame.
    tangents=[round(t*4095) for t in (0,.25,.5,.75)]
    # First word contains t0; subsequent low words contain t1/t2. t3 spans highs.
    words=[tangents[i] | (((tangents[3]>>(4*i))&15)<<12) for i in range(3)]
    for group in range(frames+1):
        for index,(values,scale,low) in enumerate(animated):
            value=values[min(group,frames-1)];packed=max(0,min(65535,round((value-low)/scale)))
            struct.pack_into('>4H',raw,key_at+group*stride+index*8,packed,*words)
    raw[flags_at:]=bytes(flag|3|(8 if curves==9 else 0) for flag in node_flags)
    anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
    maximum=0.
    for frame,expected in enumerate(samples):
        actual=anim.sample(frame)
        for node in range(nodes):
            for channel in range(curves):
                error=abs(actual[node][channel]-expected[node][channel]);maximum=max(maximum,error)
                tolerance=tolerances[node*curves+channel]+max(1.,abs(expected[node][channel]))*2e-6
                if error>tolerance:raise FormatError('Baked ANI-D decoded sample failed precision validation')
    return bytes(raw),maximum


def patch_record(data,actor_name,record_index,samples,source_hash,*,omit_auxiliary=False):
    if hashlib.sha256(data).hexdigest()!=source_hash:raise FormatError('AN4 source changed since import')
    source=AnimationFile('source.AN4',data=data)
    actors=[a for a in source.actors if a['name']==actor_name]
    if len(actors)!=1 or not 0<=record_index<len(actors[0]['records']):raise FormatError('AN4 writer requires one exact native actor/record')
    record=actors[0]['records'][record_index];anim=record['animation']
    anim.prepare(scene_channels=True)
    if anim.magic!=b'DINA' or anim.curves not in (6,9) or anim.frames!=len(samples):
        raise FormatError('AN4 writer supports existing six/nine-channel ANI-D records with unchanged frame counts only')
    if any(anim.offsets[5:]) and not omit_auxiliary:
        raise FormatError('Source has unsupported animation auxiliaries. Enable explicit omission for a pose-only experimental export; their writer is not verified')
    block,error=encode_samples(samples,anim.node_flags,anim.curves)
    output=bytearray(source.data);output.extend(bytes((-len(output))%4));at=len(output);output.extend(block)
    struct.pack_into('>I',output,record['offset']+68,at);struct.pack_into('>I',output,4,len(output))
    decoded=AnimationFile('edited.AN4',data=output)
    for actor,new_actor in zip(source.actors,decoded.actors):
        if actor['name']!=new_actor['name'] or len(actor['records'])!=len(new_actor['records']):raise FormatError('AN4 tree changed during patch')
        for old,new in zip(actor['records'],new_actor['records']):
            if actor['name']==actor_name and old['index']==record_index:
                new['animation'].prepare(scene_channels=True)
                if new['animation'].frames!=len(samples):raise FormatError('Edited AN4 timing changed')
            elif old['animation'].header()!=new['animation'].header():raise FormatError('Unselected AN4 record changed')
    return bytes(output),dict(schema='tt.ani-d-sample-edit.v1',actor=actor_name,record=record_index,frames=len(samples),
        source_sha256=source_hash,output_sha256=hashlib.sha256(output).hexdigest(),maximum_sample_error=error,
        omitted_auxiliary_offsets=list(anim.offsets[5:]) if any(anim.offsets[5:]) else [],
        validation='Decoded native AN4 tree and every baked sample; no in-game validation',
        limitations=['Standalone uncompressed AN4 output; no PAK or DAT writing.',
                    'Same frame count; six channels with unit scale, or nine channels with positive nonzero scale. Attachments are separate.',
                    'Unsupported event/auxiliary tables are not linked into the replaced animation block; original unused payload remains in the file.'])

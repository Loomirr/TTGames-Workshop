"""Experimental standalone ANI-B/D sample writer; existing trees stay intact.

Append rebuilt six/nine-channel streams while retaining original block addresses.
Frame count, native node order, actor names and all other records are retained.
Known detail tables remain linked; unknown auxiliaries require explicit omission.
"""
import hashlib
import math
import struct
from .cu3 import FormatError,Reader,Animation
from .an4 import AnimationFile
from .tt_deflate import compress
from .animation_details import detail_tracks


def effective_samples(animation, frame):
    """Expose identity scale for absent channels without activating them."""
    rows = animation.sample(frame)
    if animation.curves == 9:
        for index, flags in enumerate(animation.node_flags):
            if not flags & 8:rows[index][6:9] = [1.0, 1.0, 1.0]
    return rows


def encode_samples(samples,node_flags,curves=6,*,endian='>',variant='ANID'):
    if endian not in ('>','<') or variant not in ('ANIB','ANID'):
        raise FormatError('Unsupported skeletal animation encoding profile')
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
        for index, row in enumerate(frame):
            for channel, value in enumerate(row):
                bit = 2 if channel < 3 else 1 if channel < 6 else 8
                neutral = 0 if channel < 6 else 1
                if not node_flags[index] & bit and abs(value-neutral) > 1e-5:
                    raise FormatError('Edit requires activating an absent native channel group; '
                                      f'bone {index}, channel {channel}. Keep the source channel flags')
    constants,scales,types,animated,tolerances=[],[],[],[],[]
    for node in range(nodes):
        for channel in range(curves):
            values=[frame[node][channel] for frame in samples]
            tolerances.append((max(values)-min(values))/65535)
            bit = 2 if channel < 3 else 1 if channel < 6 else 8
            if not node_flags[node] & bit:
                types.append(14)
                continue
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
    constant_at=80;type_at=constant_at+4*len(constants)
    # With 0x20 clear, the engine reads one step-control byte per channel
    # immediately after the type words, even for constant/inactive channels.
    # Native loading sizes constants from type_at-constant_at and swaps scale
    # pairs across [scale_at,key_at). Interleaving other tables in that span
    # corrupts them even though a pointer-based offline decoder can read them.
    scale_at=aligned(type_at+3*len(types))
    key_at=scale_at+4*len(scales);flags_at=key_at+(frames+1)*stride
    if flags_at+nodes>256*1024*1024:raise FormatError('Baked ANI-D output exceeds 256 MiB')
    raw=bytearray(flags_at+nodes);magic=variant.encode('ascii');raw[:4]=magic if endian=='>' else magic[::-1]
    struct.pack_into(endian+'6H',raw,4,nodes,keys,stride,frames,curves,0)
    raw[19]=0xd0;struct.pack_into(endian+'H',raw,22,frames)
    struct.pack_into(endian+'2f',raw,28,0,1)
    struct.pack_into(endian+'9I',raw,36,scale_at,constant_at,type_at,key_at,flags_at,0,0,0,0)
    struct.pack_into(endian+'2f',raw,72,4,0)
    if scales:struct.pack_into(endian+str(len(scales))+'f',raw,scale_at,*scales)
    if constants:struct.pack_into(endian+str(len(constants))+'f',raw,constant_at,*constants)
    struct.pack_into(endian+str(len(types))+'H',raw,type_at,*types)
    # With ratio four, each integer source frame lands on a group base.
    # Intermediate tangents interpolate toward the following frame.
    tangents=[round(t*4095) for t in (0,.25,.5,.75)]
    # First word contains t0; subsequent low words contain t1/t2. t3 spans highs.
    words=[tangents[i] | (((tangents[3]>>(4*i))&15)<<12) for i in range(3)]
    for group in range(frames+1):
        for index,(values,scale,low) in enumerate(animated):
            value=values[min(group,frames-1)];packed=max(0,min(65535,round((value-low)/scale)))
            struct.pack_into(endian+'4H',raw,key_at+group*stride+index*8,packed,*words)
    # Inactive root channels can retain game-owned placement/scale. Explicit
    # identity channels are not an equivalent replacement for that contract.
    raw[flags_at:]=bytes(node_flags)
    anim=Animation(Reader(raw),0,len(raw));anim.prepare(scene_channels=True)
    maximum=0.
    for frame,expected in enumerate(samples):
        actual=effective_samples(anim,frame)
        for node in range(nodes):
            for channel in range(curves):
                error=abs(actual[node][channel]-expected[node][channel]);maximum=max(maximum,error)
                tolerance=tolerances[node*curves+channel]+max(1.,abs(expected[node][channel]))*2e-6
                bit = 2 if channel < 3 else 1 if channel < 6 else 8
                if not node_flags[node] & bit:tolerance=max(tolerance,1e-5)
                if error>tolerance:raise FormatError('Baked ANI-D decoded sample failed precision validation')
    return bytes(raw),maximum


def patch_record(data,actor_name,record_index,samples,source_hash,*,omit_auxiliary=False,detail_samples=None):
    if hashlib.sha256(data).hexdigest()!=source_hash:raise FormatError('AN4 source changed since import')
    source=AnimationFile('source.AN4',data=data)
    actors=[a for a in source.actors if a['name']==actor_name]
    if len(actors)!=1 or not 0<=record_index<len(actors[0]['records']):raise FormatError('AN4 writer requires one exact native actor/record')
    record=actors[0]['records'][record_index];anim=record['animation']
    modern = source.endian == '>' and source.version in (8,11,13,14,15,16,17,18,19,20) and anim.variant == 'ANID'
    older = ((source.endian == '>' and source.version in (2,4,5,6,7)) or
             (source.endian == '<' and source.version in (1,2))) and anim.variant in ('ANIB','ANID')
    if not (modern or older) or anim.endian != source.endian:
        raise FormatError('This animation tree/block combination can be inspected but not rewritten')
    anim.prepare(scene_channels=True)
    if anim.magic!=b'DINA' or anim.curves not in (6,9) or anim.frames!=len(samples):
        raise FormatError('AN4 writer supports existing six/nine-channel ANI-B/D records with unchanged frame counts only')
    if any(anim.offsets[i] for i in (5,7,8)) and not omit_auxiliary:
        raise FormatError('Source has unsupported animation auxiliaries; only the verified detail table can be preserved')
    tracks = [anim] if omit_auxiliary else detail_tracks(anim)
    requested = detail_samples or {}
    required = {index for index,track in enumerate(tracks) if track.at != anim.at}
    if set(requested) != required:
        raise FormatError('Animation detail tracks require samples from their verified native skeletons')
    jobs = {anim.at: (anim,samples)}
    for index in required:
        track = tracks[index]
        if len(requested[index]) != anim.frames:
            raise FormatError('Animation detail frame count changed')
        if track.at in jobs and jobs[track.at][1] != requested[index]:
            raise FormatError('Aliased animation detail slots propose different edits')
        jobs[track.at] = (track,requested[index])
    for actor in source.actors:
        for other in actor['records']:
            if other is not record and other['animation'].at in jobs:
                raise FormatError('Animation block is shared by another record; separate edits are unsupported')
    output=bytearray(source.data);error=0.
    for at,(track,rows) in jobs.items():
        if track.reader.get('B',at+18) & 1:
            raise FormatError('Already-relocated ANI-D cannot be exported')
        block,maximum=encode_samples(rows,track.node_flags,track.curves,endian=track.endian,variant=track.variant)
        error=max(error,maximum)
        if len(output)+len(block)+3>256*1024*1024:
            raise FormatError('Rebuilt AN4 exceeds 256 MiB')
        output.extend(bytes((-len(output))%4));streams=len(output);output.extend(block[80:])
        # Keep unknown metadata and every auxiliary pointer at their original
        # address. Only replace fields belonging to the newly encoded streams.
        output[at+6:at+10]=block[6:10]  # Key count/stride; keep legacy timing words.
        output[at+17]=0  # No indexed integer constants in baked body curves.
        output[at+19]=(track.flags & ~0x20) | 0x10  # Indexed float pool + separate step bytes.
        output[at+72:at+80]=block[72:80]
        pointers=struct.unpack_from(track.endian+'5I',block,36)
        struct.pack_into(track.endian+'5I',output,at+36,*(streams+p-80-at for p in pointers))
        if omit_auxiliary:struct.pack_into(track.endian+'4I',output,at+56,0,0,0,0)
    struct.pack_into(source.endian+'I',output,4,len(output))
    decoded=AnimationFile('edited.AN4',data=output)
    for actor,new_actor in zip(source.actors,decoded.actors):
        if actor['name']!=new_actor['name'] or len(actor['records'])!=len(new_actor['records']):raise FormatError('AN4 tree changed during patch')
        for old,new in zip(actor['records'],new_actor['records']):
            if actor['name']==actor_name and old['index']==record_index:
                new['animation'].prepare(scene_channels=True)
                if new['animation'].frames!=len(samples):raise FormatError('Edited AN4 timing changed')
            elif old['animation'].header()!=new['animation'].header():raise FormatError('Unselected AN4 record changed')
    for at,(old,rows) in jobs.items():
        rebuilt=Animation(Reader(output),at,len(output));rebuilt.prepare(scene_channels=True)
        for frame,expected in enumerate(rows):
            actual=effective_samples(rebuilt,frame)
            if any(abs(a-b)>error+max(1.,abs(b))*3e-6
                   for got,want in zip(actual,expected) for a,b in zip(got,want)):
                raise FormatError('Delivered ANI-D streams failed sample verification')
        if not omit_auxiliary and rebuilt.offsets[5:]!=old.offsets[5:]:
            raise FormatError('Original animation auxiliary pointers changed')
        if rebuilt.node_flags!=old.node_flags:
            raise FormatError('Original native bone channel flags changed')
    if not omit_auxiliary:
        actual_tracks=detail_tracks(decoded.actors[actors[0]['index']]['records'][record_index]['animation'])
        if [track.at for track in actual_tracks]!=[track.at for track in tracks]:
            raise FormatError('Native animation detail ownership changed')
    decoded_bytes=len(output)
    wrapped=data.startswith(b'Deflate_v1.0')
    output=compress(bytes(output)) if wrapped else bytes(output)
    # Validate the actual bytes delivered to the caller, including their wrapper.
    delivered=AnimationFile('edited.AN4',data=output)
    if delivered.data != decoded.data:
        raise FormatError('AN4 compression changed the rebuilt animation data')
    return bytes(output),dict(schema='tt.ani-d-sample-edit.v2',actor=actor_name,record=record_index,frames=len(samples),
        tree_version=source.version,byte_order=source.endian,animation_variant=anim.variant,
        source_sha256=source_hash,output_sha256=hashlib.sha256(output).hexdigest(),maximum_sample_error=error,
        storage=dict(source='Deflate_v1.0' if wrapped else 'raw',output='Deflate_v1.0' if wrapped else 'raw',
                     decoded_bytes=decoded_bytes,stored_bytes=len(output)),
        omitted_auxiliary_offsets=list(anim.offsets[5:]) if omit_auxiliary and any(anim.offsets[5:]) else [],
        preserved_detail_slots=len(tracks) if anim.offsets[6] and not omit_auxiliary else 0,
        rebuilt_animation_blocks=len(jobs),
        validation='Decoded native AN4 tree and every baked sample; no in-game validation',
        limitations=['AN4 payload preserves raw/Deflate_v1.0 storage; container publication is handled separately.',
                    'Original bone channel flags are preserved; activating absent channel groups is unsupported.',
                    'Edited tracks are baked at integer frames; interpolation between frames can differ from the source.',
                    'Same frame count; six channels with unit scale, or nine channels with positive nonzero scale. Attachments are separate.',
                    'Unknown auxiliaries require explicit omission; known detail tables and unedited face/attachment records are retained.'])

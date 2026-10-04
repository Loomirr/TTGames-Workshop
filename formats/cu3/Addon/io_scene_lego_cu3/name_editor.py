"""Copy-on-write name growth for the observed serialized PC CU3 layouts.

Relocate the complete embedded AN4 tree instead of shifting opaque ANI blocks.
Old blob bytes remain intact; only explicit tree references are repointed.
This has structural validation, not an in-game compatibility certification.
"""
import hashlib
import struct
import re
from .cu3 import Cutscene, FormatError
from .cinematic import read_cameras, read_rigids


def inventory(cut):
    actors = [dict(index=a['index'], name=a['name'], parent=a['parent'],
                   character=character_key(a['name'])[1] if a['parent'] is None else None,
                   resource_reference=a.get('metadata',{}).get('actor_id'),
                   records=[dict(index=r['index'], name=r['name'],nodes=r['animation'].nodes,curves=r['animation'].curves) for r in a['records']]) for a in cut.actors]
    rigid_error = None
    try:
        rigid = [dict(index=r['index'], name=r['name']) for r in read_rigids(cut, read_cameras(cut))]
    except FormatError as exc:
        rigid, rigid_error = [], str(exc)
    return dict(source=str(cut.path), version=cut.version, frames=cut.frames, fps=cut.fps,
                actors=actors, objects=rigid, object_layout_error=rigid_error)


def character_key(name):
    """Split an authored instance prefix; do not infer character identity from record labels."""
    match=re.match(r'^(instance\d+_)(.+)$',name,re.I)
    return (match.group(1),match.group(2)) if match else ('',name)


def plan_character_replacement(cut, source_character, replacement_character, scope='character'):
    _name(replacement_character)
    if character_key(replacement_character)[0]:
        raise FormatError('Enter a character name without an Instance prefix')
    roots=[a for a in cut.actors if a['parent'] is None]
    matches=[a for a in roots if character_key(a['name'])[1].casefold()==source_character.casefold()]
    if not matches:raise FormatError('No root instances for character '+source_character)
    if scope not in ('character','shared-reference'):raise FormatError('Unknown replacement scope')
    references={a.get('metadata',{}).get('actor_id') for a in matches}-{None,0}
    if scope=='shared-reference':
        matches=[a for a in roots if a in matches or a.get('metadata',{}).get('actor_id') in references]
    reserved={a['name'].casefold() for a in roots if a not in matches};names={};changes=[]
    for actor in matches:
        prefix,_=character_key(actor['name']);new=(prefix or 'Instance1_')+replacement_character
        number=1
        while new.casefold() in reserved:
            new=f'Instance{number}_{replacement_character}';number+=1
        reserved.add(new.casefold());names[actor['index']]=new
        changes.append(dict(index=actor['index'],old=actor['name'],new=new,resource_reference=actor.get('metadata',{}).get('actor_id'),record_labels=[r['name'] for r in actor['records']]))
    return names,dict(source_character=source_character,replacement_character=replacement_character,scope=scope,changes=changes,
        record_policy='Preserved: shared animation-record labels are not reliable model identifiers.',
        limitations=['Character assets and script replacement rules may affect game loading.','Shared numeric reference runtime semantics remain unverified.','Skeletal compatibility and attachments must be checked separately.'])


def _name(value):
    if not isinstance(value,str) or not value or any(not 32<=ord(c)<=126 for c in value):
        raise FormatError('Names must be nonempty printable ASCII without NUL characters')
    try:
        encoded=value.encode('ascii')
    except UnicodeEncodeError as exc:
        raise FormatError('This PC name editor accepts ASCII names only') from exc
    if len(encoded)>255:
        raise FormatError('Research editor limits names to 255 bytes; runtime maximum is unverified')
    return encoded+b'\0'


def rewrite_names(cut, actor_names=None, object_names=None, record_names=None):
    """Return validated bytes and manifest. Maps use zero-based inventory indices.

    record_names keys are (actor_index, record_index). Actor/object maps patch
    selected references, not every equal string. Shared names stay independent.
    """
    actor_names=dict(actor_names or {});object_names=dict(object_names or {});record_names=dict(record_names or {})
    original=cut.reader.data
    if not (actor_names or object_names or record_names):
        return original,dict(changes=[],byte_identical=True,sha256=cut.sha256)
    for value in [*actor_names.values(),*object_names.values(),*record_names.values()]:_name(value)
    for index in actor_names:
        if not isinstance(index,int) or not 0<=index<len(cut.actors):raise FormatError('Actor index outside inventory')
    for ai,ri in record_names:
        if not 0<=ai<len(cut.actors) or not any(r['index']==ri for r in cut.actors[ai]['records']):raise FormatError('Animation-record index outside inventory')
    prefix=bytearray(original[:cut.blob_start]);blob=bytearray(original[cut.blob_start:cut.blob_end]);changes=[]
    if actor_names or record_names:
        size=cut.reader.get('I',cut.root+4,'<');old_end=cut.root+size
        if old_end>cut.blob_end:raise FormatError('Embedded tree extends outside blob')
        tree=bytearray(original[cut.root:old_end]);strings=cut.reader.get('I',cut.root+16,'<')
        if not 0<strings<size:raise FormatError('Unknown AN4 string layout')
        additions={}
        def append_name(value):
            if value not in additions:
                additions[value]=len(tree)-strings+1
                tree.extend(_name(value))
            return additions[value]
        for ai,value in actor_names.items():
            actor=cut.actors[ai]
            struct.pack_into('<I',tree,actor['offset']-cut.root+28,append_name(value))
            changes.append(dict(kind='actor',index=ai,old=actor['name'],new=value))
        for (ai,ri),value in record_names.items():
            record=next(r for r in cut.actors[ai]['records'] if r['index']==ri)
            struct.pack_into('<I',tree,record['offset']-cut.root+64,append_name(value))
            changes.append(dict(kind='record',actor_index=ai,index=ri,old=record['name'],new=value))
        while len(tree)%8:tree.append(0)
        struct.pack_into('<I',tree,4,len(tree))
        while len(blob)%8:blob.append(0)
        new_root=len(blob);old_root=cut.root-cut.blob_start;shift=new_root-old_root
        blob.extend(tree)
        struct.pack_into('>I',prefix,24+cut.header_shift,new_root)
        for meta in cut.actor_metadata:
            struct.pack_into('>I',prefix,meta['table_offset']+6,meta['tree_ref']+shift)
    struct.pack_into('>I',prefix,cut.blob_start-4,len(blob))
    outer_strings=bytearray(original[cut.strings_start:cut.strings_end])
    suffix=bytearray(original[cut.strings_end:]);objects=[]
    if object_names:
        objects=read_rigids(cut,read_cameras(cut));by_index={r['index']:r for r in objects}
        for index,value in object_names.items():
            if index not in by_index:raise FormatError('Object index outside typed rigid inventory')
            record=by_index[index];offset=len(outer_strings);outer_strings.extend(_name(value))
            struct.pack_into('>I',suffix,record['record_offset']-cut.strings_end,offset)
            changes.append(dict(kind='object',index=index,old=record['name'],new=value))
    output=bytes(prefix+blob+struct.pack('>I',len(outer_strings))+outer_strings+suffix)
    declared=cut.reader.get('I',0)
    if declared!=0xffffffff:
        output=bytearray(output)
        struct.pack_into('>I',output,0,len(output)-(len(original)-declared))
        output=bytes(output)
    edited=Cutscene(cut.path,data=output)
    if edited.reader.data[edited.blob_start:edited.blob_start+cut.blob_end-cut.blob_start] != original[cut.blob_start:cut.blob_end]:
        raise FormatError('Original animation blob changed unexpectedly')
    if (edited.frames,edited.fps,edited.version,edited.tree_version)!=(cut.frames,cut.fps,cut.version,cut.tree_version):
        raise FormatError('Timeline or format changed unexpectedly')
    if edited.matrices!=cut.matrices or len(edited.actors)!=len(cut.actors):raise FormatError('Scene structure changed unexpectedly')
    for a,b in zip(cut.actors,edited.actors):
        if b['name']!=actor_names.get(a['index'],a['name']) or a['parent']!=b['parent']:raise FormatError('Actor rename / hierarchy failed')
        for old,new in zip(a['records'],b['records']):
            if new['name']!=record_names.get((a['index'],old['index']),old['name']):raise FormatError('Record rename failed')
            # Compare the entire numerical block through its node-flag table.
            x,y=old['animation'],new['animation'];length=x.offsets[4]+x.nodes
            if original[x.at:x.at+length]!=output[y.at:y.at+length]:raise FormatError('Skeletal animation bytes changed')
    if object_names:
        new_objects=read_rigids(edited,read_cameras(edited))
        if any(b['name']!=object_names.get(a['index'],a['name']) for a,b in zip(objects,new_objects)):raise FormatError('Rigid rename failed')
    return output,dict(changes=changes,source_sha256=cut.sha256,output_sha256=hashlib.sha256(output).hexdigest(),
                       source_bytes=len(original),output_bytes=len(output),growth_bytes=len(output)-len(original),
                       preserved_original_animation_blob=True,validation='Reparsed; hierarchy, matrices and numerical animation bytes preserved',
                       game_validation='Not yet tested in the installed games',
                       strategy='Relocated copy of embedded AN4 tree; appended scene strings; original animation blob retained')

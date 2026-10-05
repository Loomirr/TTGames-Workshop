"""Read-only .CC40TAD v2/-12 index reader, checked on local DCSV archives."""
from pathlib import Path
import struct,json

def index(path):
    path=Path(path)
    if path.suffix.lower()=='.hdr':data=path.read_bytes()
    else:
        with path.open('rb') as stream:
            offset,size=struct.unpack('<II',stream.read(8))
            if offset&0x80000000:offset=((offset^0xffffffff)<<8)+0x100
            stream.seek(offset);data=stream.read(size)
    size,magic,kind,version,files,names,string_size=struct.unpack_from('>I8si4I',data)
    if magic!=b'.CC40TAD' or kind!=-12 or version!=2:raise ValueError('Unverified CC4 index version')
    if not 0<files<=1000000 or not 0<names<=1000000:raise ValueError('Implausible CC4 counts')
    at=32+string_size+4;folders={};paths=[]
    for i in range(names):
        name_offset,parent,unused,sibling,file_id=struct.unpack_from('>IHHhH',data,at);at+=12
        if name_offset==0xffffffff:continue
        address=32+name_offset
        if not 32<=address<32+string_size:raise ValueError('CC4 name outside table')
        name=data[address:data.index(0,address,32+string_size)].decode('ascii')
        full=folders.get(parent,'')+'\\'+name
        # The final name's file marker is omitted in this serialized layout;
        # require its computed hash to match a real file table entry below.
        if i==names-1:file_id=1
        if file_id:paths.append(full.lstrip('\\').upper())
        else:folders[i]=full
    table_kind,count=struct.unpack_from('>iI',data,at);at+=8
    if table_kind!=-12 or count!=files:raise ValueError('CC4 file table differs')
    entries=[]
    for i in range(files):
        offset,packed_size,raw=struct.unpack_from('>QII',data,at);at+=16
        entries.append(dict(offset=offset,packed_size=packed_size,size=raw&0x7fffffff,flags=2 if raw&0x80000000 else 0))
    if at+files*8>len(data):raise ValueError('Missing 64-bit CC4 path hashes')
    hashes={struct.unpack_from('>Q',data,at+i*8)[0]:i for i in range(files)}
    mapped={}
    for path_name in paths:
        h=0xcbf29ce484222325
        for b in path_name.encode('ascii'):h=((h^b)*1099511628211)&0xffffffffffffffff
        if h not in hashes:raise ValueError('CC4 path hash not found: '+path_name)
        i=hashes[h];mapped[i]=dict(path=path_name.replace('\\','/'),**entries[i])
    if len(mapped)!=files:raise ValueError(f'CC4 mapped {len(mapped)} of {files} files')
    return [mapped[i] for i in range(files)]

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('output',type=Path,help='New index JSON filename')
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new output filename')
    rows=index(args.archive)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(rows,stream,indent=2)
    print('CC4_INDEX',len(rows),'CU3',sum(r['path'].endswith('.CU3') for r in rows))

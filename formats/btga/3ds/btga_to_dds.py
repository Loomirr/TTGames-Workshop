"""Decode observed Universe in Peril BTGA mip chains to PNG and RGBA8 DDS."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
from PIL import Image
from pica_texture import decode

BITS={0:32,1:24,2:16,3:16,4:16,5:16,6:16,7:8,8:8,9:8,10:4,11:4,12:4,13:8}

def levels_from_btga(raw):
    if len(raw)<56 or raw[:12]!=bytes.fromhex('0004000010000000f2ffffff'):
        raise ValueError('Unsupported BTGA header')
    payload,w,h,size,fmt,count=struct.unpack_from('<IHHIII',raw,20)
    if payload!=size or len(raw)!=size+56 or fmt not in BITS:
        raise ValueError('BTGA payload size or format mismatch')
    if not 8<=w<=8192 or not 8<=h<=8192 or not 1<=count<=14:
        raise ValueError('Unsupported dimensions or mip count')
    at=56;levels=[]
    for level in range(count):
        mw,mh=w>>level,h>>level
        if min(mw,mh)<8 or mw%8 or mh%8:
            raise ValueError('Unsupported sub-tile or non-tiled mip')
        length=mw*mh*BITS[fmt]//8
        if at+length>len(raw):raise ValueError('Truncated mip chain')
        levels.append(decode(raw[at:at+length],mw,mh,fmt,flip_y=True))
        at+=length
    if at!=len(raw):raise ValueError('Unexpected trailing bytes')
    return levels,fmt

def dds(levels):
    w,h=levels[0].size;n=len(levels)
    flags=0x100f|(0x20000 if n>1 else 0)
    caps=0x1000|(0x400008 if n>1 else 0)
    fields=[124,flags,h,w,w*4,0,n]+[0]*11
    fields+=[32,0x41,0,32,0xff,0xff00,0xff0000,0xff000000,caps,0,0,0,0]
    return b'DDS '+struct.pack('<31I',*fields)+b''.join(im.tobytes() for im in levels)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path,help='New output directory')
    args=parser.parse_args()
    raw=args.source.read_bytes();levels,fmt=levels_from_btga(raw);encoded=dds(levels)
    check=Image.open(io.BytesIO(encoded)).convert('RGBA')
    if check.size!=levels[0].size or check.tobytes()!=levels[0].tobytes():
        raise ValueError('DDS round trip failed')
    # Decode and validate before creating output. Never replace an existing folder.
    args.output.mkdir(parents=True,exist_ok=False)
    name=args.source.stem
    (args.output/(name+'.dds')).write_bytes(encoded)
    levels[0].save(args.output/(name+'.png'))
    for i,level in enumerate(levels):level.save(args.output/f'{name}_mip{i}.png')
    (args.output/'Manifest.json').write_text(json.dumps(dict(
        source=args.source.name,sha256=hashlib.sha256(raw).hexdigest(),
        format=fmt,mips=[list(im.size) for im in levels],
        output='RGBA8; all stored mips; original pixels; vertical flip',
        ddsRoundtripPassed=True),indent=2),encoding='utf-8')
    print(f'Exported {name}: {len(levels)} stored mips')

if __name__=='__main__':main()

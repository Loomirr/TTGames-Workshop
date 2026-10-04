from pathlib import Path
import struct,json,sys
from PIL import Image
# Independent Python reference. Xbox address equations: Xenia, BSD-3-Clause;
# see THIRD_PARTY_NOTICES.txt. This development check is not used by the EXE.
if len(sys.argv)!=2:
 raise SystemExit('Usage: python Research/probe.py <folder containing the original samples>')
R=Path(__file__).resolve().parents[1];O=R/'SampleOutput';O.mkdir(parents=True,exist_ok=True)
def addr(x,y,pitch,log):
 outer=((y>>5)*(pitch>>5)+(x>>5))<<6;inner=(((y>>1)&7)<<3)|(x&7);a=(outer|inner)<<log;bank=(y>>4)&1;pipe=((x>>3)&3)^(((y>>3)&1)<<1)
 return ((y&1)<<4)|(pipe<<6)|(bank<<11)|(a&15)|(((a>>4)&1)<<5)|(((a>>5)&7)<<8)|((a>>8)<<12)
def untile(raw,w,h,bpp,pitch,x0=0,y0=0):
 out=bytearray(w*h*bpp)
 for y in range(h):
  for x in range(w):
   at=addr(x+x0,y+y0,pitch,bpp.bit_length()-1);assert at+bpp<=len(raw)
   block=raw[at:at+bpp];block=bytes(v for i in range(0,bpp,2) for v in (block[i+1],block[i]));i=(y*w+x)*bpp;out[i:i+bpp]=block
 return out
def header(w,h,fmt,mips):
 return b'DDS '+struct.pack('<31I',124,0xa1007 if mips>1 else 0x81007,h,w,(w//4)*(h//4)*(8 if fmt=='DXT1' else 16),0,mips,*([0]*11),32,4,int.from_bytes(fmt.encode(),'little'),0,0,0,0,0,0x401008 if mips>1 else 0x1000,0,0,0,0)
results=[]
for p in Path(sys.argv[1]).glob('*360.G*'):
 d=p.read_bytes();start=d.index(b'0TST')+8;a=start;index=0
 while struct.unpack_from('>I',d,a)[0]:
  w,h=struct.unpack_from('>2I',d,a);f,rel,n,size=struct.unpack_from('>IiII',d,a+56);data=a+60+rel;raw=d[data:data+size];fmt={1:'DXT1',6:'DXT5'}[f];bpp=8 if f==1 else 16;tail=max(0,min(w.bit_length()-1,h.bit_length()-1)-4);level_start=0;allbytes=[];mipstats=[]
  for lev in range(n):
   mw,mh=max(1,w>>lev),max(1,h>>lev);bw,bh=max(1,(mw+3)//4),max(1,(mh+3)//4);pitch=max(32,((bw+31)//32)*32);x0=y0=0
   if lev>=tail:
    pitch=max(32,(((w>>tail)+3)//4+31)//32*32);packed=lev-tail
    if packed<3:
     if w>h:y0=(16>>packed)//4
     else:x0=(16>>packed)//4
    else:
     off=(max(w,h)>>tail)>>(packed-2)
     if w>h:x0=off//4
     else:y0=off//4
   linear=untile(raw[level_start:],bw,bh,bpp,pitch,x0,y0);allbytes.append(linear)
   check=header(mw,mh,fmt,1)+linear;im=Image.open(__import__('io').BytesIO(check));im.load();im.save(O/f'{p.stem}_{index:02d}_mip{lev:02d}.png')
   mipstats.append(dict(level=lev,size=[mw,mh],storage_offset=level_start,tail_xy=[x0,y0],linear_bytes=len(linear)))
   if lev<tail:level_start+=pitch*max(32,((bh+31)//32)*32)*bpp
  dest=O/f'{p.stem}_{index:02d}_{w}x{h}_{fmt}.dds';dest.write_bytes(header(w,h,fmt,n)+b''.join(allbytes));print(dest.name,'mips',n,'tail offset',hex(level_start),'allocation',hex(size));results.append(dict(source=p.name,index=index,dimensions=[w,h],format=fmt,mips=mipstats));index+=1;a+=180
(O/'Probe.json').write_text(json.dumps(results,indent=2))

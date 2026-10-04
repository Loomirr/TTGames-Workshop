"""Decode PICA200 tiled textures to RGBA. No synthesis or resampling.

Layout references: Azahar texture_decode.cpp and Ohana3DS-Rebirth TextureCodec.cs.
ETC1 uses 8-byte little endian blocks; alpha nibbles precede ETC1A4 color.
"""
import struct
from PIL import Image

MOD=((2,8,-2,-8),(5,17,-5,-17),(9,29,-9,-29),(13,42,-13,-42),
     (18,60,-18,-60),(24,80,-24,-80),(33,106,-33,-106),(47,183,-47,-183))

def etc_block(word, alpha=(1<<64)-1):
    diff=bool(word&(1<<33));flip=bool(word&(1<<32))
    colors=[]
    if diff:
        a=[word>>s&31 for s in (59,51,43)]
        delta=[word>>s&7 for s in (56,48,40)]
        b=[v+(d if d<4 else d-8) for v,d in zip(a,delta)]
        if any(v<0 or v>31 for v in b):raise ValueError('Invalid ETC1 differential color')
        colors=[[(v<<3)|(v>>2) for v in c] for c in (a,b)]
    else:
        colors=[[17*(word>>s&15) for s in shifts] for shifts in ((60,52,44),(56,48,40))]
    tables=(word>>37&7,word>>34&7)
    out=[]
    for y in range(4):
        for x in range(4):
            i=x*4+y;sub=int(y>=2 if flip else x>=2)
            ix=((word>>i)&1)+2*((word>>(i+16))&1)
            m=MOD[tables[sub]][ix]
            out.append(tuple(max(0,min(255,c+m)) for c in colors[sub])+(17*(alpha>>(4*i)&15),))
    return out

def decode(data,width,height,fmt,flip_y=False):
    if width%8 or height%8 or min(width,height)<8:raise ValueError('Unsupported tile dimensions')
    out=Image.new('RGBA',(width,height));pixels=out.load();at=0
    if fmt in (12,13):
        for ty in range(0,height,8):
            for tx in range(0,width,8):
                for bx,by in ((0,0),(4,0),(0,4),(4,4)):
                    alpha=(1<<64)-1
                    if fmt==13:alpha,=struct.unpack_from('<Q',data,at);at+=8
                    word,=struct.unpack_from('<Q',data,at);at+=8
                    block=etc_block(word,alpha)
                    for y in range(4):
                        for x in range(4):pixels[tx+bx+x,ty+by+y]=block[y*4+x]
    else:
        bits={0:32,1:24,2:16,3:16,4:16,5:16,6:16,7:8,8:8,9:8,10:4,11:4}
        if fmt not in bits:raise ValueError(f'Unsupported format {fmt}')
        for ty in range(0,height,8):
            for tx in range(0,width,8):
                for i in range(64):
                    x=(i&1)|((i>>1)&2)|((i>>2)&4);y=((i>>1)&1)|((i>>2)&2)|((i>>3)&4)
                    nbits=bits[fmt];byteat=at//8
                    v=int.from_bytes(data[byteat:byteat+(nbits+7)//8],'little')
                    if nbits==4:v=v>>(at%8)&15
                    if fmt==0:rgba=(v>>24&255,v>>16&255,v>>8&255,v&255)
                    elif fmt==1:rgba=(v>>16&255,v>>8&255,v&255,255)
                    elif fmt==2:rgba=tuple(((v>>s&31)*255+15)//31 for s in (11,6,1))+(255*(v&1),)
                    elif fmt==3:rgba=((v>>11&31)*255//31,(v>>5&63)*255//63,(v&31)*255//31,255)
                    elif fmt==4:rgba=tuple(17*(v>>s&15) for s in (12,8,4,0))
                    elif fmt==5:rgba=(v>>8&255,)*3+(v&255,)
                    elif fmt==6:rgba=(v>>8&255,v&255,0,255)
                    elif fmt==7:rgba=(v,)*3+(255,)
                    elif fmt==8:rgba=(0,0,0,v)
                    elif fmt==9:rgba=(17*(v>>4),)*3+(17*(v&15),)
                    elif fmt==10:rgba=(17*v,)*3+(255,)
                    elif fmt==11:rgba=(0,0,0,17*v)
                    pixels[tx+x,ty+y]=rgba;at+=nbits
    return out.transpose(Image.Transpose.FLIP_TOP_BOTTOM) if flip_y else out

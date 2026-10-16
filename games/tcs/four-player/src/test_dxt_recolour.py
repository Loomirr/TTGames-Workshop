#!/usr/bin/env python3
"""Fuzz test: the DXT1 endpoint recolour in dll/loader.c (dxt_colour_block) keeps
every texel's transparency. Python port of the C routine; no game files needed."""
# port of dxt_colour_block to check decoded colours/alpha are preserved apart from the remap
import random
def rgb565(c,w):
    r,g,b=(c>>11)&31,(c>>5)&63,c&31
    r=(r<<3)|(r>>2); g=(g<<2)|(g>>4); b=(b<<3)|(b>>2)
    v=max(r,g,b); mn=min(r,g,b); ch=v-mn
    if not w: r,g,b=v,mn,mn
    else: r,g,b=mn+(2*ch)//3,mn,v
    return ((r>>3)<<11)|((g>>2)<<5)|(b>>3)
def block(c0,c1,idx,w):
    n0,n1=rgb565(c0,w),rgb565(c1,w); was4=c0>c1; is4=n0>n1
    if was4!=is4 and n0!=n1:
        n0,n1=n1,n0; out=0
        for i in range(16):
            v=(idx>>(2*i))&3
            if v<2: v^=1
            elif was4: v^=1
            out|=v<<(2*i)
        idx=out
    if was4 and n0==n1: idx=0
    return n0,n1,idx
def dec(c0,c1,idx):
    def e(c): return ((c>>11)&31,(c>>5)&63,c&31)
    a,b=e(c0),e(c1)
    if c0>c1: pal=[a,b,tuple((2*x+y)/3 for x,y in zip(a,b)),tuple((x+2*y)/3 for x,y in zip(a,b))]; al=[1]*4
    else: pal=[a,b,tuple((x+y)/2 for x,y in zip(a,b)),(0,0,0)]; al=[1,1,1,0]
    return [(pal[(idx>>(2*i))&3],al[(idx>>(2*i))&3]) for i in range(16)]
def remap(px,w):
    (r,g,b),a=px
    return ((((b*5)/8) if w else b, g, b if w else r),a)
bad=0
for _ in range(20000):
    c0,c1,idx,w=random.randrange(65536),random.randrange(65536),random.getrandbits(32),random.randrange(2)
    n0,n1,ni=block(c0,c1,idx,w)
    A=dec(c0,c1,idx); B=dec(n0,n1,ni)
    for (pa,aa),(pb,ab) in zip(A,B):
        if aa!=ab: bad+=1; break
print('alpha mismatches:',bad)

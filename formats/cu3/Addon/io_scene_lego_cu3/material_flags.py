"""Read bounded material footers using the local NuMtl serialization layout."""
import json, struct
from pathlib import Path


def footer(data,end,version):
    if not 174 <= version <= 202:raise ValueError("Material footer version outside the observed family")
    flags='old_alpha old_atst afail aref cull zmode stencilMode noprepass filter utc vtc colour fill only2d stencil_shadows castShadows old_autoStencil colourWriteMask alwaysUpdateRefraction sortLast'.split()
    if version>=190: flags.append('externalFixupTarget')
    flags.append('alphaTestMode')
    tail='isCreaseMeshMaterial hasVariants wasSerialized legoStudMaterial maskShadows sortAfterDeferred sortAfterRefraction skipValidation specialDepthSorting forceAlphaLightingSupport noAutoScreenDoor compileLiveCubemapGenShader compileToonShader shadowImpostor shadowsFromFrontFaces doUntexturedTPage forceTPageRemap'.split()
    if version>=164:tail.remove('sortAfterDeferred')
    if version>=187: tail.append('forceTPageSurfType')
    if version>=191: tail.append('forceTPageAlphaFade')
    size=len(flags)+20+4+(2 if version<199 else 0)+2+16+8+len(tail)+8
    at=end-size; start=at; out={}
    if start<0 or end>len(data):raise ValueError('Material footer outside the input buffer')
    def get(name,fmt):
        nonlocal at
        out[name]=struct.unpack_from('>'+fmt,data,at)[0];at+=struct.calcsize('>'+fmt)
    for f in flags:get(f,'B')
    for f in ('fx1','fx2','fx3','fx4','localTID'):get(f,'I')
    get('fxid','B');get('special_id','B');get('shortPri16bit','H')
    if version<199:get('shineSortID','H')
    get('uanmode','B');get('vanmode','B')
    for f in ('du','dv','su','sv'):get(f,'f')
    get('firstVariantIdx','I');get('nextVariantIdx','I')
    for f in tail:get(f,'B')
    get('name_ix','I');get('defaultRenderStage','I')
    assert at==end
    return start,out

def read_render_flags(data, entries, version):
    """Use extraction metadata to bound every record; reject invalid layouts."""
    rows=[]
    if not entries:raise ValueError('Material extraction metadata is empty')
    offsets=[e['offset'] for e in entries]
    if any(not isinstance(x,int) or not 0<=x<len(data) for x in offsets) or offsets!=sorted(set(offsets)):
        raise ValueError('Material record offsets must be unique, ordered and inside the file')
    for i,entry in enumerate(entries):
        if i+1<len(entries):end=entries[i+1]['offset']
        else:
            limit=data.find(b'TDML',entry['offset']);end=limit-21
            if limit<0 or data[end:end+8]!=b'ROTV\0\0\0\0':
                raise ValueError('Unrecognized final UMTL boundary')
        start,flags=footer(data,end,version)
        if start<=entry['offset'] or flags['cull']>7 or flags['colourWriteMask']>15:
            raise ValueError('Invalid native material footer')
        for key in ('firstVariantIdx','nextVariantIdx'):
            if flags[key]!=0xffffffff and not 0<=flags[key]<len(entries):
                raise ValueError('Material variant pointer outside the table')
        rows.append(dict(index=i,name=entry['name'],offset=start,flags=flags))
    return rows

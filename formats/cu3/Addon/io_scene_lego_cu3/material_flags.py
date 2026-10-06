"""Read bounded material footers using the local NuMtl serialization layout."""
import json, struct
from pathlib import Path


def footer(data,end,version):
    if not 174 <= version <= 202 and version not in (163,229,232,234,235):raise ValueError("Material footer version outside the observed family")
    flags='old_alpha old_atst afail aref cull zmode stencilMode noprepass filter utc vtc colour fill only2d stencil_shadows castShadows old_autoStencil colourWriteMask alwaysUpdateRefraction sortLast'.split()
    if version>=190: flags.append('externalFixupTarget')
    flags.append('alphaTestMode')
    tail='isCreaseMeshMaterial hasVariants wasSerialized legoStudMaterial maskShadows sortAfterDeferred sortAfterRefraction skipValidation specialDepthSorting forceAlphaLightingSupport noAutoScreenDoor compileLiveCubemapGenShader compileToonShader shadowImpostor shadowsFromFrontFaces doUntexturedTPage forceTPageRemap'.split()
    if version>=163:tail.remove('sortAfterDeferred')
    if version>=187: tail.append('forceTPageSurfType')
    if version>=191: tail.append('forceTPageAlphaFade')
    modern = version in (229,232,234,235)
    if modern:
        flags.remove('only2d');flags.remove('stencil_shadows')
    size=(76 if modern else len(flags)+20+4+(2 if version<199 else 0)+2+16+8+len(tail)+8)
    at=end-size; start=at; out={}
    if start<0 or end>len(data):raise ValueError('Material footer outside the input buffer')
    def get(name,fmt):
        nonlocal at
        out[name]=struct.unpack_from('>'+fmt,data,at)[0];at+=struct.calcsize('>'+fmt)
    for f in flags:get(f,'I' if modern and f=='alphaTestMode' else 'B')
    for f in ('fx1','fx2','fx3','fx4','localTID'):get(f,'I')
    get('fxid','B');get('special_id','B')
    get('shortPri16bit','H')
    if version<199:get('shineSortID','H')
    if not modern:
        get('uanmode','B');get('vanmode','B')
    if not modern:
        for f in ('du','dv','su','sv'):get(f,'f')
    get('firstVariantIdx','I');get('nextVariantIdx','I')
    if modern:
        out['opaqueModernTail'] = list(data[at:at+17]);at+=17
    else:
        for f in tail:get(f,'B')
    if not modern:get('name_ix','I')
    get('defaultRenderStage','I')
    assert at==end
    return start,out

def read_render_flags(data, entries, version, *, table_end=None):
    """Use extraction metadata to bound every record; reject invalid layouts."""
    rows=[]
    if not entries:raise ValueError('Material extraction metadata is empty')
    offsets=[e['offset'] for e in entries]
    if any(not isinstance(x,int) or not 0<=x<len(data) for x in offsets) or offsets!=sorted(set(offsets)):
        raise ValueError('Material record offsets must be unique, ordered and inside the file')
    for i,entry in enumerate(entries):
        if i+1<len(entries):end=entries[i+1]['offset']
        else:
            limit=data.find(b'TDML',entry['offset']) if table_end is None else table_end
            end=limit-21
            if limit<0 or data[limit:limit+4]!=b'TDML' or data[end:end+8]!=b'ROTV\0\0\0\0':
                raise ValueError('Unrecognized final UMTL boundary')
        start,flags=footer(data,end,version)
        if start<=entry['offset'] or flags['cull']>7 or flags['colourWriteMask']>15:
            raise ValueError('Invalid native material footer')
        if any(entry.get(field,entry['offset']) > start for field in ('prefix_end','texture_end','name_end')):
            raise ValueError('Native material prefix, texture or name overlaps its footer')
        for key in ('firstVariantIdx','nextVariantIdx'):
            if flags[key]!=0xffffffff and not 0<=flags[key]<len(entries):
                raise ValueError('Material variant pointer outside the table')
        rows.append(dict(index=i,name=entry['name'],offset=start,end=end,flags=flags))
    return rows

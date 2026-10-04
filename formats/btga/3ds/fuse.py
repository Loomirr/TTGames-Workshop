"""Observed FUSE payload commands; caller supplies a verified archive index."""
import struct

def decompress(data,expected):
    if not 0<=expected<=128*1024*1024:raise ValueError('Invalid decoded size')
    out=bytearray();at=0
    def get(count):
        nonlocal at
        if at+count>len(data):raise ValueError('Truncated FUSE command')
        result=data[at:at+count];at+=count;return result
    while at<len(data):
        c=get(1)[0]
        if c<128:
            d=get(1)[0];n=(c>>2)&3;m=(c>>4)+3;off=((c&3)<<8)+d+1
        elif c<192:
            d,e=get(2);n=d>>6;m=(c&63)+4;off=((d&63)<<8)+e+1
        elif c<224:
            d,e,z=get(3);n=(c>>3)&3;m=((c&7)<<7)+z+5;off=(d<<8)+e+1
        elif c<252:n=((c&31)+1)*4;m=0;off=0
        else:n=c&3;m=0;off=0
        if len(out)+n+m>expected:raise ValueError('FUSE decoded-size overflow')
        out.extend(get(n))
        if m:
            if off>len(out):raise ValueError('Invalid history distance')
            pattern=out[len(out)-off:len(out)-off+min(m,off)]
            out.extend(pattern*(m//off)+pattern[:m%off] if m>=off else pattern)
    if len(out)!=expected:raise ValueError('FUSE decoded-size mismatch')
    return bytes(out)

def read_entry(stream,row,archive_base,archive_size):
    size=row['packed']>>5;flags=row['packed']&31;offset=row['offset']
    if archive_base<0 or archive_size<0 or offset<0:
        raise ValueError('Invalid archive bounds')
    if flags not in (0,12,13) or size>128*1024*1024:
        raise ValueError('Unsupported FUSE record')
    if not size:return b''
    stream.seek(archive_base+offset)
    if flags&1:
        if offset+4>archive_size:raise ValueError('Record outside archive')
        header=stream.read(4)
        if len(header)!=4:raise ValueError('Truncated record header')
        stored,=struct.unpack('<I',header)
        if offset+4+stored>archive_size:raise ValueError('Payload outside archive')
        raw=stream.read(stored)
        if len(raw)!=stored:raise ValueError('Truncated stored payload')
        return decompress(raw,size)
    if offset+size>archive_size:raise ValueError('Payload outside archive')
    raw=stream.read(size)
    if len(raw)!=size:raise ValueError('Truncated raw payload')
    return raw

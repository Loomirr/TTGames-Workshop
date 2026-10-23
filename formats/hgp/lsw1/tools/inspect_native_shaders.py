"""Inventory embedded LSW1 PC shaders using Windows' shader disassembler.

Requires pefile and Windows D3DCompiler_47.dll. This reads a supplied executable;
it never launches or patches the game. Reports/disassembly belong in a private
research directory, outside published tool builds.
"""
import argparse
from collections import Counter
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct

from check_native_curves import EXE_SHA256
from native_effects import registrations


PROFILES={0xffff0101,0xffff0102,0xffff0103,0xffff0104,0xffff0200,0xffff0300,
          0xfffe0101,0xfffe0200,0xfffe0300}


def shader_end(data, offset, limit=65536):
    """Bound SM2/3 instructions by token lengths, skipping complete comments.

    END-looking words inside CTAB/preshader metadata or instruction operands
    are data. Legacy SM1 retains the inventory's bounded scan/disassembler gate.
    Returns an exclusive end offset, or None for a truncated/invalid stream.
    """
    if offset < 0 or offset + 4 > len(data) or limit < 8:
        return None
    version = struct.unpack_from('<I', data, offset)[0]
    if version not in PROFILES:
        return None
    bound = min(len(data), offset + limit)
    if (version >> 8) & 255 < 2:
        return next((at + 4 for at in range(offset + 4, bound - 3, 4)
                     if data[at:at + 4] == b'\xff\xff\x00\x00'), None)
    at = offset + 4
    while at + 4 <= bound:
        token = struct.unpack_from('<I', data, at)[0]
        if token == 0x0000ffff:
            return at + 4
        if token & 0xffff == 0xfffe:
            words = (token >> 16) & 0x7fff
        else:
            if token & 0x80000000:
                return None  # Parameter token where an instruction is required.
            words = (token >> 24) & 15
        at += (words + 1) * 4
    return None


def inspect(executable, output, include_assembly=False):
    if os.name!='nt':
        raise ValueError('This research tool requires the Windows shader disassembler')
    import pefile
    with executable.open('rb') as stream:
        raw=stream.read(128*1024*1024+1)
    if hashlib.sha256(raw).hexdigest()!=EXE_SHA256:
        raise ValueError('Unsupported executable hash for this shader inventory')
    dll=Path(os.environ['SystemRoot'])/'System32/d3dcompiler_47.dll'
    library=ctypes.WinDLL(str(dll))
    disassemble=library.D3DDisassemble
    disassemble.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,
                         ctypes.c_char_p,ctypes.POINTER(ctypes.c_void_p)]
    disassemble.restype=ctypes.c_long
    pe=pefile.PE(data=raw)
    output.mkdir(parents=True,exist_ok=False)
    records=[]
    for section in pe.sections:
        data=section.get_data()
        # A real initial CTAB comment distinguishes shader starts from profile
        # words repeated inside constant-table metadata. Comment-free shaders
        # are deliberately outside this inventory's scope.
        for match in re.finditer(b'CTAB',data):
            offset=match.start()-8
            if offset<0 or (section.VirtualAddress+offset)%4:
                continue
            version=struct.unpack_from('<I',data,offset)[0]
            if version not in PROFILES or data[offset+4:offset+6]!=b'\xfe\xff':
                continue
            end=shader_end(data,offset)
            if end is None:
                continue
            code=data[offset:end]
            buffer=ctypes.create_string_buffer(code);blob=ctypes.c_void_p()
            status=disassemble(buffer,len(code),0,None,ctypes.byref(blob))
            if status<0 or not blob.value:
                continue
            table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            try:
                pointer=ctypes.WINFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p)(table[3])(blob)
                size=ctypes.WINFUNCTYPE(ctypes.c_size_t,ctypes.c_void_p)(table[4])(blob)
                assembly=ctypes.string_at(pointer,size).decode('utf-8').rstrip('\0')
            finally:
                ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(blob)
            if '???' in assembly:
                continue
            profile=re.search(r'^\s*((?:ps|vs)_\d_\d)\s*$',assembly,re.M)
            if not profile:
                continue
            address=pe.OPTIONAL_HEADER.ImageBase+section.VirtualAddress+offset
            record=dict(address=hex(address),bytes=len(code),sha256=hashlib.sha256(code).hexdigest(),
                        profile=profile.group(1),
                        parameters=re.findall(r'^//   ((?:float|sampler|matrix)[^;]+);',assembly,re.M))
            records.append(record)
            if include_assembly:
                (output/f'{address:08x}.txt').write_text(assembly,encoding='utf-8')
    # These are registrations in alternative initialization branches, not one
    # table to collapse by ID. Each blob can contain several techniques/passes.
    effects=registrations(pe.get_memory_mapped_image(),pe.OPTIONAL_HEADER.ImageBase,
                          0x12e300,0x12f230,records)
    report=dict(executable_sha256=EXE_SHA256,programs=len(records),
                distinct_bytecode=len({r['sha256'] for r in records}),
                profiles=dict(Counter(r['profile'] for r in records)),shaders=records,
                effect_registrations=effects,
                distinct_effect_ids=len({e['effect_id'] for e in effects}),
                effect_blob_locations=len({e['blob_address'] for e in effects}),
                distinct_effect_blobs=len({e['sha256'] for e in effects}),
                scope='Embedded CTAB shaders and candidate effect registrations; active initialization branch, technique/pass selection and runtime constants not verified')
    (output/'inventory.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--disassembly',action='store_true',help='Also save original shader assembly in the private output directory')
    args=parser.parse_args()
    report=inspect(args.executable,args.output,args.disassembly)
    print(json.dumps({key:value for key,value in report.items() if key not in ('shaders','effect_registrations')}))
    if not report['programs']:raise SystemExit(1)


if __name__=='__main__':main()

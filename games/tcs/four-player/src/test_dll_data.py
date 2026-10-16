#!/usr/bin/env python3
"""Check the DLL patch data against the executable build.

Usage: python test_dll_data.py <unpacked LEGOStarWarsSaga.exe>

Simulates the loader (loader.c) at several load addresses and compares the
patched code and mod area with build.py's output for the same address.
Needs the same binutils as build.py; LLVM is not needed.
"""
import os, sys, struct, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, build_dll  # noqa: E402
if len(sys.argv) < 2:
    sys.exit(__doc__)
EXE = sys.argv[1]
for research in (False,):  # the research build (icon dump) no longer fits the code area
    hdr, m = build_dll.generate(EXE, research)
    d0 = bytearray(open(EXE,'rb').read())
    _,_,_,secs,fo = build.check_input(d0)
    for base in [0x2a8e000, 0x10000, 0x7ffe0000, 0x05f30000] + [random.randrange(1,0x7fff)<<16 for _ in range(6)]:
        # simulate loader.c
        mem = bytearray(d0)
        for va, off, n, fx, nfx in m['table']:
            assert mem[fo(va):fo(va)+n] == m['orig'][off:off+n]
            seg = bytearray(m['new'][off:off+n])
            for p in m['fix'][fx:fx+nfx]:
                struct.pack_into('<I', seg, p, (struct.unpack_from('<I',seg,p)[0]+base)&0xffffffff)
            mem[fo(va):fo(va)+n] = seg
        blob = bytearray(build.M_SIZE); blob[:m['init_len']] = m['blob0'][:m['init_len']]
        for o,k in m['bf'].items():
            v = struct.unpack_from('<I',blob,o)[0]
            struct.pack_into('<I',blob,o,(v+base if k=='abs' else v-base)&0xffffffff)
        # reference: exe patcher at the same base
        code, sym = build.assemble(research, base)
        ref = bytearray(d0); build.patch_code(ref, fo, base, sym)
        assert mem == ref, hex(base)
        assert blob == build.mod_section(code), hex(base)
    print('research' if research else 'public', 'OK: records', len(m['table']), 'blob abs/rel', sum(k=='abs' for k in m['bf'].values()), sum(k=='rel' for k in m['bf'].values()))

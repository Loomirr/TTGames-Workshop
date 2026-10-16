#!/usr/bin/env python3
"""Build the TCS PC four-player patch.

Usage:
    python build.py <unpacked LEGOStarWarsSaga.exe> <output.exe> [--research]

Most users want the DLL build instead (build_dll.py), which leaves the game
executable unchanged. This script produces a standalone patched executable and
is mainly kept for research.

Input must be an *unpacked* copy of the Steam PC executable (SteamStub removed,
for example with Steamless). The packed executable is rejected. The original is
never modified. Every patched location is compared with the expected original
bytes first; any mismatch aborts without writing output.

Requires GNU binutils for i386 (as, ld, objcopy, nm) on PATH. On Windows use
WSL or MSYS2 (mingw-w64-i686-binutils); the i686 tools may be named
i686-w64-mingw32-as etc. - set the BINUTILS_PREFIX environment variable.
"""
import os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = 0x400000
M_SIZE = 0x8000             # new section .mod, appended after the last section
CODE2 = 0x3000              # second hook code area (section .text2), after the state areas
CODE_END = 0x4000           # end of the hook code (.text2)
# layout inside .mod: +0x000 port table, +0x040 gamepads, +0x100 hook code,
# +0x1F00.. mod state; +0x2600.. Free Play select state, camera lists, debug buffer;
# +0x3000.. more hook code (.text2)

# 41 references to the 3-entry port->device table 0x297E040..0x297E063,
# relocated to a 4-entry table at M_BASE. Format: <instruction operand VA> <old value>.
RELOCS = """
494f56 297e048 4f0bfd 297e044 4f42dc 297e044 4f431f 297e048 4f432d 297e048
4f47aa 297e044 4f47c9 297e044 4f480e 297e044 4f4830 297e048 4f4865 297e044
4f488b 297e048 4f48b1 297e044 4f48cd 297e048 4f48ed 297e048 4f48f6 297e044
4f495c 297e040 4f4962 297e044 4f4968 297e04c 4f496e 297e050 4f4974 297e058
4f497a 297e05c 4f4982 297e048 4f4988 297e054 4f498e 297e060 4f49bc 297e044
4f4bf1 297e044 4f4c26 297e044 4f4c2c 297e050 4fb21c 297e044 4fb261 297e044
4fb2b8 297e044 4fb2d9 297e048 4fb2e6 297e044 4fb320 297e048 4fb33e 297e044
4fb347 297e048 4fb34d 297e054 4fb37d 297e048 4fb398 297e044 4fb3cf 297e048
4fb419 297e044
"""


def tool(name):
    return os.environ.get("BINUTILS_PREFIX", "") + name


def assemble(research, m_base):
    tmp = tempfile.mkdtemp()
    obj, elf, binf = (os.path.join(tmp, n) for n in ("h.o", "h.elf", "h.bin"))
    args = [tool("as"), "--32", "--defsym", "M_BASE=0x%x" % m_base,
            "-o", obj, os.path.join(HERE, "hooks.s")]
    if research:
        args[1:1] = ["--defsym", "RESEARCH=1"]
    subprocess.check_call(args)
    subprocess.check_call([tool("ld"), "-m", "elf_i386", "-Ttext=0x%x" % (m_base + 0x100),
                           "--section-start=.text2=0x%x" % (m_base + CODE2),
                           "-e", "_start", "-o", elf, obj])
    subprocess.check_call([tool("objcopy"), "-O", "binary", "-j", ".text", "-j", ".text2", elf, binf])
    sym = {}
    for line in subprocess.check_output([tool("nm"), elf], text=True).splitlines():
        a, _t, n = line.split()
        sym[n] = int(a, 16)
    return open(binf, "rb").read(), sym


def read_sections(d):
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, pe + 6)[0]
    opt = pe + 0x18
    sect = opt + struct.unpack_from("<H", d, pe + 0x14)[0]
    secs = []
    for i in range(nsec):
        h = sect + i * 40
        vs, va, rs, ro = struct.unpack_from("<4I", d, h + 8)
        secs.append((d[h:h + 8].rstrip(b"\0"), va, max(vs, rs), rs, ro))
    return pe, opt, sect, secs


def check_input(d):
    """Validate an unpacked image; return (pe, opt, sect, secs, fo)."""
    pe, opt, sect, secs = read_sections(d)
    names = [x[0] for x in secs]
    if b".mod" in names:
        sys.exit("input already contains a .mod section (already patched?)")
    if names[:5] != [b".text", b".rdata", b".data", b".rsrc", b".extra"]:
        sys.exit("unexpected section layout %r - not the analysed Steam build" % names)

    def fo(va):
        rva = va - IMG
        for _n, sva, vsz, rsz, roff in secs:
            if sva <= rva < sva + min(vsz, rsz):
                return rva - sva + roff
        raise SystemExit("0x%X is not backed by file data" % va)
    # an unpacked image starts at the original entry point inside .text
    ep = struct.unpack_from("<I", d, opt + 16)[0] + IMG
    if ep != 0x6E74A2:
        sys.exit("entry point 0x%X: executable is still packed or a different build" % ep)
    return pe, opt, sect, secs, fo


def mod_section(code):
    """Initial contents of the 0x2000-byte mod area (port table defaults + code)."""
    # code is .text from +0x100 and .text2 from CODE2; the state areas between stay zero
    if any(code[0x1F00 - 0x100:CODE2 - 0x100]):
        sys.exit("hook code too large (.text runs into the state area)")
    if 0x100 + len(code) > CODE_END:
        sys.exit("hook code too large (.text2)")
    sec = bytearray(M_SIZE)
    for i in range(4):
        struct.pack_into("<iiI", sec, i * 12, -1, -1, 0)
    sec[0x100:0x100 + len(code)] = code
    return sec


def patch_code(d, fo, m_base, sym):
    """Apply the port-table relocation and all hooks to the game code in d."""
    m_pads = m_base + 0x40

    def expect(va, hexbytes):
        b = bytes.fromhex(hexbytes)
        if d[fo(va):fo(va) + len(b)] != b:
            sys.exit("unexpected bytes at 0x%X: %s" % (va, d[fo(va):fo(va) + len(b)].hex()))

    def call(va, target):
        d[fo(va):fo(va) + 5] = b"\xe8" + struct.pack("<i", target - (va + 5))

    def jmp(va, target, total):
        d[fo(va):fo(va) + total] = b"\xe9" + struct.pack("<i", target - (va + 5)) + b"\x90" * (total - 5)

    # relocate the port table
    vals = RELOCS.split()
    for i in range(0, len(vals), 2):
        va, old = int(vals[i], 16), int(vals[i + 1], 16)
        expect(va, struct.pack("<I", old).hex())
        struct.pack_into("<I", d, fo(va), old - 0x297E040 + m_base)

    # hooks (see ../PATCHES.md)
    expect(0x4F4992, "891d30ef9100"); jmp(0x4F4992, sym["h1_porttable_init"], 6)
    expect(0x4F4C2A, "890d"); jmp(0x4F4C2A, sym["h2_port_reset"], 6)
    expect(0x54B0E4, "55896c2414"); jmp(0x54B0E4, sym["h5_frame_update"], 5)
    expect(0x4285C8, "83fb02"); d[fo(0x4285CA)] = 4
    expect(0x42807D, "51e85dc80c00"); jmp(0x42807D, sym["h7_dropin_mask"], 5)
    expect(0x6DC392, "8b74247885f6740e")
    d[fo(0x6DC392):fo(0x6DC392) + 8] = b"\xbe" + struct.pack("<I", m_pads + 8) + b"\x90" * 3
    expect(0x6DC3A8, "8bb4248000000085f6740e")
    d[fo(0x6DC3A8):fo(0x6DC3A8) + 11] = b"\xbe" + struct.pack("<I", m_pads + 12) + b"\x90" * 6
    expect(0x4B9266, "8b34adf0d79300"); jmp(0x4B9266, sym["hud_getchar"], 7)
    expect(0x4B9C62, "83fd020f8cf5f5ffff"); jmp(0x4B9C62, sym["hud_loopend"], 9)
    expect(0x4B92C1, "f686fc01000080"); jmp(0x4B92C1, sym["hud_ring"], 7)
    expect(0x4B9479, "e8b2230a00"); jmp(0x4B9479, sym["hud_portrait"], 5)
    # HUD per-player state 4 wide (moved into the mod area; hud_swap feeds P3/P4's to the
    # P3/P4 pass): counter pulse 0x879358 (2 floats) and multiplier icon timer 0x879360
    # (2 words, written by 0x46ac0d for any player index)
    hpulse, hicon = m_base + 0x1F60, m_base + 0x1F80
    for va, old_b, off, base in ((0x4B7139, "d9048558938700", 3, hpulse), (0x4B791F, "d98658938700", 2, hpulse),
                                 (0x4B792D, "d99e58938700", 2, hpulse), (0x46AC0D, "6689 2c45 60938700", 4, hicon),
                                 (0x4B784B, "0fb715 60938700", 3, hicon), (0x4B785E, "0fb70d 62938700", 3, hicon + 2),
                                 (0x4B788E, "66a3 60938700", 2, hicon), (0x4B973E, "0fb7146d 60938700", 4, hicon),
                                 (0x4B97B2, "0fb7146d 60938700", 4, hicon)):
        expect(va, old_b.replace(" ", ""))
        struct.pack_into("<I", d, fo(va) + off, base)
    # P3/P4 corner portraits with P2's in every menu that draws the corner portraits
    for va in (0x496729, 0x496880, 0x47B34D, 0x47B62B, 0x49745F):
        expect(va, (b"\xe8" + struct.pack("<i", 0x55B830 - (va + 5))).hex()); call(va, sym["menu_corner"])
    for va in (0x47C2D1, 0x47C34F):
        expect(va, (b"\xe8" + struct.pack("<i", 0x594C30 - (va + 5))).hex()); call(va, sym["grid_list"])
    expect(0x47719B, "0fb72c55c4b68700"); jmp(0x47719B, sym["skip_other1"], 8)
    expect(0x4771E0, "0fb7144dc4b68700"); jmp(0x4771E0, sym["skip_other2"], 8)
    expect(0x477244, "0fb7144dc4b68700"); jmp(0x477244, sym["skip_other3"], 8)
    expect(0x476EE8, "bab0539200"); jmp(0x476EE8, sym["p2_feed"], 5)
    expect(0x4BC08B, "0381c02a000089442460"); jmp(0x4BC08B, sym["part_spawn1"], 10)
    expect(0x4BC284, "0390c02a000089542440"); jmp(0x4BC284, sym["part_spawn2"], 10)
    for va in (0x56174C, 0x561840):
        expect(va, (b"\xe8" + struct.pack("<i", 0x552C10 - (va + 5))).hex()); call(va, sym["part_draw"])
    expect(0x47C593, "66890d849b8700bd02000000"); jmp(0x47C593, sym["rv_list"], 12)
    expect(0x47C7F1, "83fb01754d"); jmp(0x47C7F1, sym["rv_idx1"], 5)
    expect(0x47C978, "33c083fb010f95c08d8400a50000008bf0"); jmp(0x47C978, sym["rv_ring2"], 17)
    expect(0x47BEF9, (b"\xe8" + struct.pack("<i", 0x55B830 - (0x47BEF9 + 5))).hex()); call(0x47BEF9, sym["sel_corner"])
    expect(0x4B7939, "83fe08"); d[fo(0x4B793B)] = 0x10           # pulse loop: party slots 0..3
    # "Techno" state timer 0x880584: 2 floats indexed by the character's player number
    # (0x4ccc60 runs for every human character, so P4 wrote into the state record at
    # 0x880590). 8 floats in the mod area; the reset at 0x4cdcda covers players 0..3.
    techno = m_base + 0x1FB0
    for va, old_b in ((0x4CCDAE, "d9048584058800"), (0x4CCDC7, "d91c8d84058800"),
                      (0x4CCDD5, "d9049584058800"), (0x4CDCE9, "d91c8d84058800")):
        expect(va, old_b); struct.pack_into("<I", d, fo(va) + 3, techno)
    expect(0x4CDCDE, "3c017524"); d[fo(0x4CDCDF)] = 3; d[fo(0x4CDCE0)] = 0x77   # cmp al,3 ; ja
    expect(0x4B78C1, "668915629387 00".replace(" ", "")); jmp(0x4B78C1, sym["hud_icon_timers"], 7)
    expect(0x55B8FC, "e80f73ffff"); call(0x55B8FC, sym["ring_draw"])
    expect(0x46B209, "0fbe9f80020000"); jmp(0x46B209, sym["stud_pickup"], 7)
    expect(0x46B391, "83fb01d905e0c27f00"); jmp(0x46B391, sym["stud_fly"], 9)
    expect(0x46AF80, "0fbe8efd000000"); jmp(0x46AF80, sym["stud_owner2"], 7)
    # stud arrival: accept owners 0..3 (test al,al; je; cmp al,1; jne 46b184 -> cmp al,3; ja 46b184)
    expect(0x46B07D, "84c074083c010f85fb000000")
    d[fo(0x46B07D):fo(0x46B07D) + 12] = bytes.fromhex("3c030f87ff000000") + b"\x90" * 4
    expect(0x41FE40, "a1f4d79300"); jmp(0x41FE40, sym["purse_init"], 5)
    expect(0x41FBAC, "8b1584378000"); jmp(0x41FBAC, sym["party_restore"], 6)
    expect(0x4B7606, "8b0df4d79300"); jmp(0x4B7606, sym["tj_sum"], 6)
    expect(0x483D94, "803ddca6870002"); jmp(0x483D94, sym["stud_bank"], 7)
    # HUD stud counter row y offset: fld [0x7fc2e4] -> fld [M_CTRY]
    for va in (0x4B9A7B, 0x4B9B60):
        expect(va, "d905e4c27f00")
        d[fo(va):fo(va) + 6] = b"\xd9\x05" + struct.pack("<I", m_base + 0x1F20)
    expect(0x40B6FE, "8b3495f0d79300"); jmp(0x40B6FE, sym["cam_pick"], 7)
    expect(0x40B8B7, "8b148df0d79300"); jmp(0x40B8B7, sym["cam_pick2"], 7)
    # Free Play character select: P3/P4 cursors and picks
    expect(0x4773DA, "81fa705492008944241489542440894c24440f8c1efbffff")
    jmp(0x4773DA, sym["fs_loopend"], 24)
    expect(0x476E76, "891d64958700"); jmp(0x476E76, sym["fs_init"], 6)
    expect(0x47BB5C, "891dfc9a8700"); jmp(0x47BB5C, sym["fs_clear"], 6)
    expect(0x4772C3, "e898d61100"); call(0x4772C3, sym["fs_unlocked"])
    for va, old in ((0x47C2E5, "e846b3ffff"), (0x47C362, "e8c9b2ffff"), (0x47C55E, "e8cdb0ffff")):
        expect(va, old); call(va, sym["fs_grid"])
    for va, old in ((0x477843, "e8e83f0e00"), (0x47789E, "e88d3f0e00")):
        expect(va, old); call(va, sym["fs_portrait"])
    expect(0x489278, "833dc8a9870000"); jmp(0x489278, sym["fp_roster"], 7)
    expect(0x414E71, "c7057c5f850000000000"); jmp(0x414E71, sym["fp_party"], 10)
    for va, old, name in ((0x47BFE2, "d90558937f00", "sel_size"), (0x47C112, "d90554937f00", "sel_ctry"),
                          (0x47C1C8, "d9055c937f00", "sel_namey"), (0x47C19A, "d905c4327500", "sel_namesc")):
        expect(va, old)
        d[fo(va) + 2:fo(va) + 6] = struct.pack("<I", sym[name])
    expect(0x489327, "a1c4b28700"); jmp(0x489327, sym["fp_roster2"], 5)
    expect(0x476A48, "5f5e5d5b59"); jmp(0x476A48, sym["fs_extras"], 5)
    # party lists (Free Play picks, Cantina P3/P4) and Cantina load list
    expect(0x41FA84, "33c066837d00ff"); jmp(0x41FA84, sym["fp_plist"], 7)
    expect(0x47AABC, "66c70594d59300ffff"); jmp(0x47AABC, sym["hub_list"], 9)
    for va in (0x48AF5F, 0x48AFAE):
        expect(va + 2, "20958700")
        struct.pack_into("<I", d, fo(va) + 2, sym["hub_listbuf"])
    # select: P3/P4 Exit/Select prompts; reveal lineup rings and fly-in
    expect(0x4B7A80, "55e85ace030050e864ed210055e8aee82100"); jmp(0x4B7A80, sym["pr_dev"], 18)
    expect(0x4B7A92, "d905b4327500")
    d[fo(0x4B7A92) + 2:fo(0x4B7A92) + 6] = struct.pack("<I", sym["pr_y"])
    expect(0x4B7B0A, "dc0560167500")
    d[fo(0x4B7B0A) + 2:fo(0x4B7B0A) + 6] = struct.pack("<I", sym["pr_yd"])
    expect(0x47C477, "83c4385f5e"); jmp(0x47C477, sym["pr_again"], 5)
    expect(0x47C8B5, "bea7000000"); jmp(0x47C8B5, sym["rv_start"], 5)
    expect(0x47CA0E, "e81dee0d00"); call(0x47CA0E, sym["rv_portrait"])
    # door / chapter menus: P3/P4 corner portraits and prompts
    for va, old in ((0x47B426, "e875c50300"), (0x47B9EC, "e8afbf0300"), (0x4968C0, "e8db100200"),
                    (0x4C780E, "e88d01ffff")):
        expect(va, old); call(va, sym["door_prompts"])
    # pause / drop-out: drop-out offered with any two human players
    for va in (0x495929, 0x495B55):       # pause menu only; 0x55f1a0 has other callers
        expect(va, (b"\xe8" + struct.pack("<i", 0x55F1A0 - (va + 5))).hex()); call(va, sym["two_humans"])
    # drop-in: P3/P4 keep their own slots
    expect(0x428419, "bdf8d79300"); jmp(0x428419, sym["dropin_cands"], 5)
    expect(0x428401, "837c2414007411e921ffffff"); jmp(0x428401, sym["dropin_offscreen"], 12)
    # Cantina loading screen: P3/P4 portraits, 2x2
    expect(0x48BEF2, "03f783fe020f8c63feffff"); jmp(0x48BEF2, sym["ld_loopend"], 11)
    expect(0x48BED6, "e855f90c00"); call(0x48BED6, sym["ld_portrait"])
    for va, old, name in ((0x48BE7B, "d9051ca27500", "ld_y0"), (0x48BEC4, "d90518a27500", "ld_y1")):
        expect(va, old)
        d[fo(va) + 2:fo(va) + 6] = struct.pack("<I", sym[name])
    # Control Configuration (pause menu): 4 players, P3/P4 on a second page
    expect(0x493CB6, "6a02"); d[fo(0x493CB7)] = 4
    expect(0x4234A5, "e986f2ffff"); jmp(0x4234A5, sym["kc_draw"], 5)
    expect(0x4218AE, "8b7c8c1c85ff"); jmp(0x4218AE, sym["kc_pad"], 6)
    m_kcin = m_base + 0x2980
    for va, old in ((0x4218B4, 0x856868), (0x421907, 0x856860), (0x42191A, 0x856858),
                    (0x42192F, 0x856858), (0x42193F, 0x856858), (0x421946, 0x856868),
                    (0x42194F, 0x856858), (0x42195A, 0x856860), (0x421961, 0x856858),
                    (0x421968, 0x856868), (0x4219CC, 0x856868)):
        expect(va + 3, struct.pack("<I", old).hex())
        struct.pack_into("<I", d, fo(va) + 3, (old - 0x856858) * 2 + m_kcin)   # 4 wide
    for va in (0x421A53, 0x421B46):
        expect(va, (b"\xe8" + struct.pack("<i", 0x6D9510 - (va + 5))).hex()); call(va, sym["kc_devmap"])
    for va in (0x421AA9, 0x421FE7, 0x422048):
        expect(va, (b"\xe8" + struct.pack("<i", 0x6D95B0 - (va + 5))).hex()); call(va, sym["kc_preset"])
    expect(0x422065, "8b7e3833ed"); jmp(0x422065, sym["kc_reset"], 5)
    for va in (0x422EFB, 0x422FF1):
        expect(va, (b"\xe8" + struct.pack("<i", 0x6D9670 - (va + 5))).hex()); call(va, sym["kc_bindname"])
    for va in (0x422E93, 0x422EB8):
        expect(va, (b"\xe8" + struct.pack("<i", 0x6D68E0 - (va + 5))).hex()); call(va, sym["kc_bound"])
    # Cantina shop: opened and controlled by P3/P4 too; no toggling onto P3/P4 there
    expect(0x47CFAA, "8b0df0d79300"); jmp(0x47CFAA, sym["shop_open"], 6)
    expect(0x4C1196, "81fd785492000f8c0effffff"); jmp(0x4C1196, sym["shop_input"], 12)
    expect(0x487CAA, "85ed5657742b"); jmp(0x487CAA, sym["tg_target"], 6)
    expect(0x487CDB, "b9f0d79300"); jmp(0x487CDB, sym["tg_scan"], 5)
    # cheat codes ALLCHR / STUD1M
    expect(0x4C4714, "83c40433f6"); jmp(0x4C4714, sym["cheat_code"], 5)
    expect(0x5949C4, "8b0d6c139500"); jmp(0x5949C4, sym["story_owned"], 6)
    # select: big portraits and names for P3/P4
    expect(0x47C1F8, "83c60183fe020f8c27fdffff"); jmp(0x47C1F8, sym["fs_bigloop"], 12)
    expect(0x47BFCC, "80bbc8b6870000"); jmp(0x47BFCC, sym["fs_bigother"], 7)
    expect(0x47C144, "e8e7f60d00"); call(0x47C144, sym["fs_bigportrait"])
    for va, old, name in ((0x47BF9E, "d90574517500", "sel_cx0"), (0x47BFB7, "d905b8327500", "sel_cx1"),
                          (0x47C004, "d90510c37f00", "sel_cy")):
        expect(va, old)
        d[fo(va) + 2:fo(va) + 6] = struct.pack("<I", sym[name])


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    research = "--research" in sys.argv[3:]
    d = bytearray(open(src, "rb").read())
    pe, opt, sect, secs, fo = check_input(d)
    nsec = len(secs)

    salign = struct.unpack_from("<I", d, opt + 32)[0]
    falign = struct.unpack_from("<I", d, opt + 36)[0]
    last_end = max(x[1] + x[2] for x in secs)
    m_rva = (last_end + salign - 1) // salign * salign
    m_base = IMG + m_rva
    code, sym = assemble(research, m_base)
    sec = mod_section(code)

    # add .mod section (RWX)
    hdr_off = sect + nsec * 40
    if d[hdr_off:hdr_off + 40] != b"\0" * 40:
        sys.exit("no room for an extra section header")
    raw = (len(d) + falign - 1) // falign * falign
    d += b"\0" * (raw - len(d))
    hdr = bytearray(40)
    hdr[:8] = b".mod\0\0\0\0"
    struct.pack_into("<4I", hdr, 8, M_SIZE, m_rva, M_SIZE, raw)
    struct.pack_into("<I", hdr, 36, 0xE0000060)
    d[hdr_off:hdr_off + 40] = hdr
    struct.pack_into("<H", d, pe + 6, nsec + 1)
    struct.pack_into("<I", d, opt + 56, m_rva + M_SIZE)
    d += sec

    patch_code(d, fo, m_base, sym)
    open(out, "wb").write(d)
    print("wrote", out)


if __name__ == "__main__":
    main()

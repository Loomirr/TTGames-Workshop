/* LEGO Star Wars: The Complete Saga (PC) - four-player patch, hook code.
   Original work for TTGames Workshop. Assembled with GNU as (Intel syntax) at
   0x02A8E100 inside the added .mod section; see ../README.md and build.py.
   Addresses are virtual addresses of the unpacked Steam PC image (base 0x400000).
   Assemble with --defsym RESEARCH=1 to include the icon-memory dump used to
   locate ring materials (writes 4p_icons*.bin next to the game). */
.intel_syntax noprefix
.code32

.ifdef RESEARCH
.set DEBUG_TOOLS, 1      /* the icon dump uses the logger's file helpers */
.endif
.ifndef M_BASE
.set M_BASE,   0x2a8e000      /* build.py passes the real section address */
.endif
.set M_PT,     M_BASE+0x000      /* relocated port table: 4 x {x, device, active} (12 bytes) */
.set M_PADS,   M_BASE+0x040      /* gamepad pointers for ports 0..3 (we fill [2],[3]) */
.set M_DUMMY,  M_BASE+0x080      /* dummy control entry (0x60 bytes) */
.set M_PURSE,  M_BASE+0x1f00     /* stud purses for P3/P4, 2 x 16 bytes like 0x855f38 */

.set PARTY,    0x93d7f0
.set GETPORTDEV, 0x4f48e0
.set CTRL_UPDATE, 0x54ae40
.set CTRL_POOL, 0x9253b0
.set PAD_CREATE, 0x4f41f0
.set CHAR_COUNT, 0x93d500
.set CHAR_BASE, 0x93d504

.globl _start
_start:

/* ---- H1: port table init (4f4992) - also init entry 3 ---- */
h1_porttable_init:
    mov dword ptr [M_PT+0x24], 0xffffffff
    mov dword ptr [M_PT+0x28], 0xffffffff
    mov dword ptr [M_PT+0x2c], 0
    mov dword ptr [0x91ef30], ebx
    jmp 0x4f4998

/* ---- H2: port device reset (4f4c2a) - reset devices of ports 1..3 ---- */
h2_port_reset:
    mov dword ptr [M_PT+0x10], ecx
    mov dword ptr [M_PT+0x1c], ecx
    mov dword ptr [M_PT+0x28], ecx
    jmp 0x4f4c30

/* ---- fix_owner(k): make human party slot k (2/3) own control entry k with gamepad k ----
   The game identifies players by (char.ca4 - 0x9253b0)/0x60 and movement reads the
   gamepad through entry->pad (field 0), exactly like P1/P2 with entries 0/1.
   returns eax=1 if slot k is human-controlled */
fix_owner:
    push ebx
    push esi
    push edi
    push ebp
    mov ebx, dword ptr [esp+0x14]
    xor eax, eax
    mov esi, dword ptr [ebx*4+PARTY]
    test esi, esi
    jz fo_done
    test byte ptr [esi+0x1fc], 0x80
    jz fo_done
    push ebx                               /* human but no device on port k: P1/P2 switched */
    call GETPORTDEV                        /* onto this character (character toggle), not */
    add esp, 4                             /* P3/P4 - leave its control alone */
    test eax, eax
    mov eax, 0
    js fo_done
    lea edi, [ebx+ebx*2]
    shl edi, 5
    add edi, CTRL_POOL
    mov eax, dword ptr [ebx*4+M_PADS]
    test eax, eax
    jnz fo_havepad
    push 0
    push ebx
    call PAD_CREATE
    add esp, 8
    mov dword ptr [ebx*4+M_PADS], eax
fo_havepad:
    mov dword ptr [edi], eax
    test eax, eax
    jz fo_owner
    mov byte ptr [eax+0x88], 0x2a
    mov byte ptr [eax+0x89], 0x60
    mov byte ptr [eax+0x8a], 0x38
fo_owner:
    mov ebp, dword ptr [esi+0xca4]
    cmp ebp, edi
    je fo_human
    mov ecx, dword ptr [CHAR_COUNT]
    mov edx, dword ptr [CHAR_BASE]
    test edx, edx
    jz fo_noowner
    test ecx, ecx
    jle fo_noowner
fo_scan:
    cmp dword ptr [edx+0xca4], edi
    jne fo_next
    cmp edx, esi
    je fo_next
    mov dword ptr [edx+0xca4], ebp
    jmp fo_swapped
fo_next:
    add edx, 0x10d8
    dec ecx
    jnz fo_scan
fo_noowner:
    or word ptr [edi+0x5a], 1
    test ebp, ebp
    jz fo_swapped
    and word ptr [ebp+0x5a], 0xfffe
fo_swapped:
    mov dword ptr [esi+0xca4], edi
fo_human:
    lea eax, [ebx*8-16]                    /* own stud purse: M_PURSE + (k-2)*16 */
    lea eax, [eax*2+M_PURSE]
    mov dword ptr [esi+0x7fc], eax
    cmp word ptr [eax+8], 0                /* stud icon type, as 0x41fdda sets for P1/P2 */
    jne 1f
    mov cx, word ptr [0x803bac]
    mov word ptr [eax+8], cx
1:  mov eax, 1
fo_done:
    pop ebp
    pop edi
    pop esi
    pop ebx
    ret

/* ---- H5: per-frame controller update (54b0e4) - also slots 2,3 when human ---- */
h5_frame_update:
    cmp dword ptr [M_DBGFN], 0             /* loader: log party/port changes */
    je 1f
    call dword ptr [M_DBGFN]
1:  call level_frames
    call skip_check
    push 2
    call hub_guard
    push 3
    call hub_guard
    add esp, 8
.ifdef RESEARCH
    call icon_dump
.endif
    push 2
    call fix_owner
    add esp, 4
    test eax, eax
    jz 1f
    push 2
    call CTRL_UPDATE
    add esp, 4
    push 2
    call p34_pause
    add esp, 4
    jmp h5_s3
1:  push 2
    call idle_update
    add esp, 4
h5_s3:
    push 3
    call fix_owner
    add esp, 4
    test eax, eax
    jz 1f
    push 3
    call CTRL_UPDATE
    add esp, 4
    push 3
    call p34_pause
    add esp, 4
    jmp h5_done
1:  push 3
    call idle_update
    add esp, 4
h5_done:
    push ebp
    mov dword ptr [esp+0x14], ebp
    jmp 0x54b0e9

/* ---- idle_update(k): P3/P4 computer-controlled (never joined, or dropped out). The game
   updates control entries 0/1 every frame whether the player is human or not
   (0x54b0d0); without the same for 2/3 a dropped-out P3's entry and pad kept the last
   frame's buttons (In-game v0.26: the dropped character kept jumping, and the frozen
   pad rejoined by itself). Runs only on an entry fix_owner gave our pad. ---- */
idle_update:
    mov eax, dword ptr [esp+4]
    lea ecx, [eax+eax*2]
    shl ecx, 5
    mov ecx, dword ptr [ecx+CTRL_POOL]
    test ecx, ecx
    jz 1f
    cmp ecx, dword ptr [eax*4+M_PADS]
    jne 1f
    push eax
    call CTRL_UPDATE
    add esp, 4
1:  ret

/* ---- party setup, carry-over between level parts (replaces mov edx,[0x803784] @41fbac):
   the human flag of each slot was just restored from the saved slot state
   (0x93d516 + slot*0x10). P3/P4 stay human only if their port still has a device;
   otherwise a P3 that joined in a cutscene level returns without a controller and the
   real P3 pad then joins as P4. esi = character, edi = party slot. */
party_restore:
    cmp edi, 2
    jl 1f
    cmp edi, 3
    jg 1f
    test byte ptr [esi+0x1fc], 0x80
    jz 1f
    push edi
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jge 1f
    and dword ptr [esi+0x1fc], 0xffffff7f
1:  mov edx, dword ptr [0x803784]
    jmp 0x41fbb2

/* ---- frames since the current level started (world+0x128 changed) ---- */
.set M_DBGFN,     M_BASE+0x1f4c      /* loader: void party_watch(void) */
.set M_LASTLVL,   M_BASE+0x1f44
.set M_LVLFRAMES, M_BASE+0x1f48
.set JOIN_DELAY,  120
level_frames:
    mov eax, dword ptr [0x802c54]
    test eax, eax
    jz 1f
    mov eax, dword ptr [eax+0x128]
1:  cmp eax, dword ptr [M_LASTLVL]
    je 2f
    mov dword ptr [M_LASTLVL], eax
    mov dword ptr [M_LVLFRAMES], 0
    ret
2:  cmp dword ptr [M_LVLFRAMES], 0x7fffffff
    je 3f
    inc dword ptr [M_LVLFRAMES]
3:  ret

/* ---- H7: drop-in device exclusion mask (42807d) ----
   builds ebp = mask of devices already owned by ports 0..3,
   [esp+0x2c] = port0 device, ebx = port1 device (as original),
   edx = bit to re-allow (keyboard dev 10) for players 0/1; nothing for players 2/3
   which are also barred from keyboard devices 10..13. Continues at 4280c0. */
h7_dropin_mask:
    xor ebp, ebp
    xor esi, esi
h7_loop:
    push esi
    call GETPORTDEV
    add esp, 4
    cmp esi, 0
    jne h7_n0
    mov dword ptr [esp+0x2c], eax
h7_n0:
    cmp esi, 1
    jne h7_n1
    mov ebx, eax
h7_n1:
    test eax, eax
    jl  h7_next
    cmp dword ptr [esp+0x10], 2            /* P3/P4: their own port's device may (re)join */
    jl  1f                                 /* (claimed in the Free Play character select) */
    cmp esi, dword ptr [esp+0x10]
    je  h7_next
1:
    mov ecx, eax
    mov edx, 1
    shl edx, cl
    or  ebp, edx
h7_next:
    inc esi
    cmp esi, 4
    jl  h7_loop
    xor esi, esi                           /* devices another slot has just been */
h7_pend:                                   /* pressed on (drop-in record, counter) */
    cmp esi, dword ptr [esp+0x10]
    je  h7_pnext
    cmp byte ptr [esi+0x7f39d0], 0
    je  h7_pnext
    movsx ecx, word ptr [esi*2+0x7f39d4]
    test ecx, ecx
    jl  h7_pnext
    cmp ecx, 31
    ja  h7_pnext
    mov edx, 1
    shl edx, cl
    or  ebp, edx
h7_pnext:
    inc esi
    cmp esi, 4
    jl  h7_pend
    call mirror_mask
    or  ebp, eax
    mov edx, 0x400
    cmp dword ptr [esp+0x10], 2
    jl  h7_done
    or  ebp, 0x3ff0      /* P3/P4: XInput pads (devices 0-3) only */
    xor edx, edx
h7_done:
    cmp dword ptr [M_SKIPALL], 0           /* skipping a cinematic: nobody joins (the */
    jne 2f                                 /* skip press must not become a drop-in)   */
    cmp dword ptr [esp+0x10], 2            /* P3/P4: not in the first frames of a level, */
    jl 1f                                  /* before the level has set up its ports       */
    cmp dword ptr [M_LVLFRAMES], JOIN_DELAY
    jb 2f
    cmp dword ptr [0x951be0], 0            /* nor while a cutscene plays: START skips it */
    jne 2f
    mov eax, dword ptr [0x802c54]          /* nor in intro/midtro/outro levels */
    test eax, eax
    jz 1f
    mov eax, dword ptr [eax+0x128]
    test eax, eax
    jz 1f
    test byte ptr [eax+0x64], 0xe0
    jz 1f
2:  mov ebp, 0x3fff
    xor edx, edx
1:
    jmp 0x4280c0

/* ================= cutscene skip =================
   While a cutscene plays ([0x951be0], entry [0x951be8], player entry+4) and no menu is open,
   a fresh START press (any device) skips the rest of the cinematic:
   - the player is marked finished (bit 0x1000 of player+0x88, set by 0x508747 at the natural
     end); the cutscene manager 0x57ef50 then runs its own ending (next level from entry+0xec,
     chained cutscene, or gameplay);
   - the cutscene audio stream group 0x10 (loaded by 0x57ebba, played by 0x57ebdf) is stopped
     with 0x694030(0x10, 0) on the stream manager 0x924df8;
   - skip-all mode: every cutscene that starts afterwards is finished and silenced the same
     way, until no cutscene has played for SKIP_IDLE frames (i.e. gameplay has begun). */
.set M_SKIPARM,  M_BASE+0x0e0
.set M_SKIPALL,  M_BASE+0x1f34
.set M_SKIPIDLE, M_BASE+0x1f38
.set SKIP_IDLE,  90
skip_check:
    pushad
    xor esi, esi
    cmp dword ptr [0x951be0], 0
    je 1f
    mov eax, dword ptr [0x951be8]
    test eax, eax
    jz 1f
    mov esi, dword ptr [eax+4]             /* playing cutscene player or 0 */
1:  cmp dword ptr [M_SKIPALL], 0
    je sk_button
    /* skip-all mode */
    test esi, esi
    jnz 2f
    call sk_start_down                     /* keep skipping (and blocking joins) while */
    test eax, eax                          /* START is still held                      */
    jnz sk_out
    inc dword ptr [M_SKIPIDLE]
    cmp dword ptr [M_SKIPIDLE], SKIP_IDLE
    jb sk_out
    mov dword ptr [M_SKIPALL], 0
    jmp sk_disarm
2:  mov dword ptr [M_SKIPIDLE], 0
    call sk_finish
    jmp sk_out
sk_button:
    test esi, esi
    jz sk_disarm
    test dword ptr [esi+0x88], 0x1000
    jnz sk_disarm
    call 0x574e20
    cmp eax, 0xffffffff
    jne sk_out
    sub esp, 8
    push 1
    lea eax, [esp+4]
    push eax
    lea eax, [esp+0xc]
    push eax
    push 0x1a
    push 0
    call 0x6d9120
    add esp, 0x1c
    test eax, eax
    jl sk_arm
    cmp dword ptr [M_SKIPARM], 0
    je sk_out
    mov dword ptr [M_SKIPARM], 0
    mov dword ptr [M_SKIPALL], 1
    mov dword ptr [M_SKIPIDLE], 0
    call sk_finish
    jmp sk_out
sk_arm:
    mov dword ptr [M_SKIPARM], 1
    jmp sk_out
sk_disarm:
    mov dword ptr [M_SKIPARM], 0
sk_out:
    popad
    ret

/* sk_start_down() -> eax = 1 if START is held on any device */
sk_start_down:
    sub esp, 8
    push 1
    lea eax, [esp+4]
    push eax
    lea eax, [esp+0xc]
    push eax
    push 0x1a
    push 0
    call 0x6d9120
    add esp, 0x1c
    not eax
    shr eax, 31                            /* device >= 0 -> 1, -1 -> 0 */
    ret

/* sk_finish(esi = cutscene player): mark finished, stop cutscene audio */
sk_finish:
    or dword ptr [esi+0x88], 0x1000
    push 0                                 /* no fade */
    push 0x10                              /* stream group: cutscene audio */
    mov ecx, 0x924df8
    call 0x694030                          /* thiscall, ret 8 */
    ret

.ifdef DEBUG_TOOLS   /* debug logger and windowed-mode helpers: not used by the patch */
/* ================= debug logger ================= */
.set M_DBGCNT, M_BASE+0x0f0
.set M_DBGLINE, M_BASE+0x0f4
.set M_BUF,    M_BASE+0x2a00      /* debug text buffer (research builds) */
.set IAT_CreateFileA, 0x7510dc
.set IAT_SetFilePointer, 0x7510a0
.set IAT_WriteFile, 0x7510e8
.set IAT_CloseHandle, 0x7510e0

/* put_hex: eax=value, ecx=number of hex digits, edi=out ptr (advanced). appends a space */
put_hex:
    push edx
    push ebx
    mov ebx, ecx
    lea edi, [edi+ecx]
    push edi
ph_loop:
    dec edi
    mov edx, eax
    and edx, 0xf
    mov dl, byte ptr [edx+hexdigits]
    mov byte ptr [edi], dl
    shr eax, 4
    dec ebx
    jnz ph_loop
    pop edi
    mov byte ptr [edi], 0x20
    inc edi
    pop ebx
    pop edx
    ret
hexdigits: .ascii "0123456789ABCDEF"
put_tag:            /* esi = zero-terminated string */
    lodsb
    test al, al
    jz pt_end
    stosb
    jmp put_tag
pt_end:
    ret

debug_tick:
    pushad
    inc dword ptr [M_DBGCNT]
    mov eax, dword ptr [M_DBGCNT]
    cmp eax, 60
    jb dt_out
    mov dword ptr [M_DBGCNT], 0
    inc dword ptr [M_DBGLINE]
    mov edi, M_BUF
    mov eax, dword ptr [M_DBGLINE]
    mov ecx, 4
    call put_hex
    /* ports: dev,active x4 */
    mov esi, offset s_ports
    call put_tag
    xor ebx, ebx
dt_ports:
    lea edx, [ebx+ebx*2]
    mov eax, dword ptr [edx*4+M_PT+4]
    mov ecx, 2
    call put_hex
    mov eax, dword ptr [edx*4+M_PT+8]
    mov ecx, 1
    call put_hex
    inc ebx
    cmp ebx, 4
    jb dt_ports
    /* party count */
    mov esi, offset s_party
    call put_tag
    mov eax, dword ptr [0x93d818]
    mov ecx, 2
    call put_hex
    /* slots 0..3: char ptr, flags low byte, ca4, entry index */
    xor ebx, ebx
dt_slots:
    mov esi, offset s_slot
    call put_tag
    mov eax, ebx
    mov ecx, 1
    call put_hex
    mov edx, dword ptr [ebx*4+PARTY]
    mov eax, edx
    mov ecx, 8
    call put_hex
    test edx, edx
    jz dt_slot_next
    mov eax, dword ptr [edx+0x1fc]
    mov ecx, 2
    call put_hex
    mov eax, dword ptr [edx+0xca4]
    push eax
    mov ecx, 8
    call put_hex
    pop eax
    test eax, eax
    jz dt_slot_next
    /* entry->pad */
    mov eax, dword ptr [eax]
    push eax
    mov ecx, 8
    call put_hex
    pop eax
    test eax, eax
    jz dt_slot_next
    /* pad: port, sticks 90..93, buttons 70, 78 */
    push eax
    mov eax, dword ptr [eax]
    mov ecx, 1
    call put_hex
    mov eax, dword ptr [esp]
    mov eax, dword ptr [eax+0x90]
    mov ecx, 8
    call put_hex
    mov eax, dword ptr [esp]
    mov eax, dword ptr [eax+0x70]
    mov ecx, 8
    call put_hex
    pop eax
dt_slot_next:
    inc ebx
    cmp ebx, 4
    jb dt_slots
    /* my pads */
    mov esi, offset s_pads
    call put_tag
    mov eax, dword ptr [M_PADS+8]
    mov ecx, 8
    call put_hex
    mov eax, dword ptr [M_PADS+12]
    mov ecx, 8
    call put_hex
    /* raw devices 0..13: connected, owner port, sticks dword */
    mov esi, offset s_dev
    call put_tag
    xor ebx, ebx
dt_dev:
    imul edx, ebx, 0x84
    movzx eax, byte ptr [edx+0x917000]
    mov ecx, 1
    call put_hex
    mov eax, dword ptr [edx+0x917004]
    mov ecx, 2
    call put_hex
    mov eax, dword ptr [edx+0x917008]
    mov ecx, 8
    call put_hex
    mov eax, dword ptr [edx+0x917010]
    mov ecx, 4
    call put_hex
    mov byte ptr [edi], 0x7c
    inc edi
    inc ebx
    cmp ebx, 14
    jb dt_dev
    /* engine input object: per-port device binding info */
    mov esi, offset s_eng
    call put_tag
    mov ebp, dword ptr [0x2975144]
    test ebp, ebp
    jz dt_eng_done
    mov eax, dword ptr [ebp+0x67e4]
    mov ecx, 2
    call put_hex
    xor ebx, ebx
dt_e6558:
    mov eax, dword ptr [ebp+ebx*4+0x6558]
    mov ecx, 2
    call put_hex
    inc ebx
    cmp ebx, 4
    jb dt_e6558
    xor ebx, ebx
dt_eport:
    mov esi, offset s_p
    call put_tag
    lea edx, [ebx+ebx*2]
    mov eax, dword ptr [edx*4+M_PT+4]
    push eax
    mov ecx, 2
    call put_hex
    pop edx
    cmp edx, 14
    jae dt_eport_next
    imul edx, edx, 0x17c
    add edx, ebp
    mov eax, dword ptr [edx+0x4e34]
    mov ecx, 2
    call put_hex
    mov eax, dword ptr [edx+0x4e38]
    mov ecx, 8
    call put_hex
    mov eax, dword ptr [edx+0x4e3c]
    mov ecx, 8
    call put_hex
    /* bindings 0x40 bytes at +0x4ea2 */
    xor ecx, ecx
dt_bind:
    movzx eax, byte ptr [edx+ecx+0x4ea2]
    push ecx
    mov ecx, 2
    lea edi, [edi]
    call put_hex
    dec edi
    pop ecx
    inc ecx
    cmp ecx, 0x40
    jb dt_bind
    mov byte ptr [edi], 0x20
    inc edi
    /* mapped output 0x10 bytes at +0x4fa4 */
    xor ecx, ecx
dt_map:
    movzx eax, byte ptr [edx+ecx+0x4fa4]
    push ecx
    mov ecx, 2
    call put_hex
    dec edi
    pop ecx
    inc ecx
    cmp ecx, 0x10
    jb dt_map
    mov byte ptr [edi], 0x20
    inc edi
dt_eport_next:
    inc ebx
    cmp ebx, 3
    jb dt_eport
dt_eng_done:
    mov word ptr [edi], 0x0a0d
    add edi, 2
    sub edi, M_BUF
    mov dword ptr [M_DBGLEN], edi
    /* append to file */
    push 0
    push 0x80
    push 4          /* OPEN_ALWAYS */
    push 0
    push 3          /* share read|write */
    push 0x40000000 /* GENERIC_WRITE */
    push offset s_file
    call dword ptr [IAT_CreateFileA]
    cmp eax, 0xffffffff
    je dt_out
    mov esi, eax
    push 2          /* FILE_END */
    push 0
    push 0
    push esi
    call dword ptr [IAT_SetFilePointer]
    push 0
    push offset M_DBGWRITTEN
    push dword ptr [M_DBGLEN]
    push M_BUF
    push esi
    call dword ptr [IAT_WriteFile]
    push esi
    call dword ptr [IAT_CloseHandle]
dt_out:
    popad
    ret
.set M_DBGLEN, M_BASE+0x0f8
.set M_DBGWRITTEN, M_BASE+0x0fc
s_file:  .asciz "4p_debug_v06.txt"
s_ports: .asciz "| ports(dev act) "
s_party: .asciz "| party "
s_slot:  .asciz "| slot "
s_pads:  .asciz "| mypads "
s_eng:   .asciz "| eng(67e4 6558x4) "
s_p:     .asciz "| P "
s_dev:   .asciz "| devs(conn owner sticks btn) "

/* ================= windowed-mode helpers (used only by the windowed build) =================
   pcconfig WindowWidth/Height default to 0 -> 0x0 invisible window. Use 1280x720, centred. */
win_w:
    test eax, eax
    jg  1f
    mov eax, 1280
1:  mov dword ptr [0x82647c], eax
    ret
win_h:
    test eax, eax
    jg  1f
    mov eax, 720
1:  mov dword ptr [0x826480], eax
    ret
win_l:
    test eax, eax
    jnz 1f
    mov eax, 0xffffffff
1:  mov dword ptr [0x826484], eax
    ret
win_t:
    test eax, eax
    jnz 1f
    mov eax, 0xffffffff
1:  mov dword ptr [0x826488], eax
    ret

.endif /* DEBUG_TOOLS */

/* ================= HUD: second pass for P3/P4 =================
   HUD player loop 0x4b9260..0x4b9c65 runs ebp=0,1. After it, if party slot 2 or 3 is human,
   run it again (pass 1) with ebp=0,1 mapped to slots 2,3 and the HUD y moved to the bottom. */
.set M_PASS,  M_BASE+0x0e4
.set M_YSAVE, M_BASE+0x0e8
.set M_CTRY,  M_BASE+0x1f20   /* counter-row y offset for the current HUD pass (float) */
.set HUD_Y,   0x7fc318
hud_getchar:                       /* replaces mov esi,[ebp*4+0x93d7f0] @4b9266 */
    cmp dword ptr [M_PASS], 0
    jne 1f
    mov dword ptr [M_CTRY], 0x3d99999a     /* stud counter row: 0.075 (native 0.045) */
    mov esi, dword ptr [ebp*4+PARTY]
    jmp 0x4b926d
1:  mov dword ptr [M_CTRY], 0x3d99999a     /* bottom HUD: same spacing */
    mov esi, dword ptr [ebp*4+PARTY+8]
    test esi, esi
    jz 2f
    test byte ptr [esi+0x1fc], 0x80
    jnz 2f
    push ebp                               /* computer-controlled: shown dimmed with the */
    call p34_prompt                        /* join prompt (native P2 path) when P3/P4 */
    add esp, 4                             /* could join */
    test eax, eax
    jnz 2f
    xor esi, esi
2:  jmp 0x4b926d

hud_loopend:                       /* replaces cmp ebp,2 ; jl 4b9260 @4b9c62 */
    cmp ebp, 2
    jl 0x4b9260
    cmp dword ptr [M_PASS], 0
    jne 3f
    cmp dword ptr [M_MENUAGE], 2           /* a menu is drawing P3/P4 at the top */
    jae 5f
    inc dword ptr [M_MENUAGE]
    jmp 4f
5:  push 0
    call p34_visible
    add esp, 4
    mov dword ptr [M_HUDVIS], eax
    push 1
    call p34_visible
    add esp, 4
    add eax, eax
    or dword ptr [M_HUDVIS], eax
    jz 4f
2:  mov dword ptr [M_PASS], 1
    xor dword ptr [esp+0x1c], 0x80000000   /* HUD y (+-1 coords, +up) -> bottom of screen */
    mov eax, dword ptr [esp+0x1c]
    mov dword ptr [M_HUDY], eax
    mov dword ptr [M_XF], 0                /* a menu opening now cross-fades from here */
    call hud_swap                          /* P3/P4's own HUD state in the P1/P2 places */
    xor ebp, ebp
    jmp 0x4b9260
3:  mov dword ptr [M_PASS], 0
    xor dword ptr [esp+0x1c], 0x80000000   /* restore */
    call hud_swap
4:  jmp 0x4b9c6b

    .pushsection .text2, "ax"
/* p34_port_avail(k): P3 (0) / P4 (1) has a pad on its port, or enough free XInput pads
   are connected for it to join (P4 needs a second one while P3 has none). -> eax 1/0 */
p34_port_avail:
    push ecx
    mov ecx, dword ptr [esp+8]
    add ecx, 2
    push ecx
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jge 8f
    call free_pads
    mov ecx, 1
    cmp dword ptr [esp+8], 0
    je 1f
    push eax
    push 2
    call GETPORTDEV
    add esp, 4
    test eax, eax
    pop eax
    jge 1f
    inc ecx
1:  cmp eax, ecx
    jb 9f
8:  mov eax, 1
    pop ecx
    ret
9:  xor eax, eax
    pop ecx
    ret

/* p34_visible(k): party slot 2+k has a human, or a computer character whose corner the
   HUD shows (p34_prompt). -> eax 1/0 */
p34_visible:
    mov eax, dword ptr [esp+4]
    mov eax, dword ptr [eax*4+PARTY+8]
    test eax, eax
    jz 9f
    test byte ptr [eax+0x1fc], 0x80
    jnz 8f
    push dword ptr [esp+4]
    call p34_prompt
    add esp, 4
    ret
8:  mov eax, 1
9:  ret

/* p34_prompt(k): show computer-controlled P3 (k = 0) / P4 (1) like the native P2 corner
   (dimmed portrait and a flashing join prompt) while enough free XInput pads are
   connected for that player to drop in (hub levels too since v0.45). -> eax 1/0 */
p34_prompt:
    push ecx
    push edx
    call free_pads
    mov ecx, 1                             /* pads needed */
    cmp dword ptr [esp+12], 0
    je 1f
    mov edx, dword ptr [PARTY+8]           /* P4: P3 takes the first free pad when P3 */
    test edx, edx                          /* is also waiting to join */
    jz 1f
    test byte ptr [edx+0x1fc], 0x80
    jnz 1f
    inc ecx
1:  cmp eax, ecx
    jb 9f
8:  mov eax, 1
    pop edx
    pop ecx
    ret
9:  xor eax, eax
    pop edx
    pop ecx
    ret

/* free_pads -> eax = connected XInput pads (devices 0..3, connected byte at 0x917000 +
   dev*0x84) that no port 0..3 owns and that are not a mirror of an owned pad */
free_pads:
    push ebx
    push ecx
    push edx
    push esi
    push edi
    call mirror_mask
    mov edi, eax
    xor ebx, ebx                           /* count */
    xor esi, esi                           /* device */
1:  imul eax, esi, 0x84
    cmp byte ptr [eax+0x917000], 0
    je 4f
    bt edi, esi
    jc 4f
    xor ecx, ecx
2:  push ecx
    call GETPORTDEV
    add esp, 4
    cmp eax, esi
    je 4f
    inc ecx
    cmp ecx, 4
    jb 2b
    inc ebx
4:  inc esi
    cmp esi, 4
    jb 1b
    mov eax, ebx
    pop edi
    pop esi
    pop edx
    pop ecx
    pop ebx
    ret

/* hud_swap: the HUD loop reads per-player state for players 0/1 only. Around the P3/P4
   pass (ebp = 0/1 again) this exchanges it with P3/P4's, and exchanges back after:
   counter pulse M_HPULSE[0,1]<->[2,3], multiplier icon timer M_HICON[0,1]<->[2,3]
   (both moved from 0x879358/0x879360, 2 wide), multiplier bits 0/1<->2/3 of 0x87b924,
   pausing player [0x802af8] 0/1<->2/3, the join prompt text [0x800a6c]/[0x800a70], and
   the pad-light counters [0x951250]/[0x951254] (P3/P4 have none: zeros). */
hud_swap:
    push eax
    push ecx
    mov eax, dword ptr [M_HPULSE]
    xchg eax, dword ptr [M_HPULSE+8]
    mov dword ptr [M_HPULSE], eax
    mov eax, dword ptr [M_HPULSE+4]
    xchg eax, dword ptr [M_HPULSE+12]
    mov dword ptr [M_HPULSE+4], eax
    mov eax, dword ptr [M_HICON]
    xchg eax, dword ptr [M_HICON+4]
    mov dword ptr [M_HICON], eax
    mov eax, dword ptr [0x87b924]
    mov ecx, eax
    and ecx, 0xfffffff0
    push eax
    and eax, 3
    shl eax, 2
    or ecx, eax
    pop eax
    shr eax, 2
    and eax, 3
    or ecx, eax
    mov dword ptr [0x87b924], ecx
    mov eax, dword ptr [0x802af8]
    cmp eax, 3
    ja 1f
    xor eax, 2
    mov dword ptr [0x802af8], eax
1:  mov eax, dword ptr [0x951250]
    xchg eax, dword ptr [M_PADL]
    mov dword ptr [0x951250], eax
    mov eax, dword ptr [0x951254]
    xchg eax, dword ptr [M_PADL+4]
    mov dword ptr [0x951254], eax
    xor byte ptr [M_SWAPPED], 1
    jz 2f
    mov eax, dword ptr [0x800a6c]          /* swapped in: P3/P4 prompt text */
    mov dword ptr [M_JSAVE], eax
    mov eax, dword ptr [0x800a70]
    mov dword ptr [M_JSAVE+4], eax
    mov dword ptr [0x800a6c], offset s_join
    mov dword ptr [0x800a70], offset s_join
    pop ecx
    pop eax
    ret
2:  mov eax, dword ptr [M_JSAVE]
    mov dword ptr [0x800a6c], eax
    mov eax, dword ptr [M_JSAVE+4]
    mov dword ptr [0x800a70], eax
    pop ecx
    pop eax
    ret
.set M_HPULSE,  M_BASE+0x1f60          /* 8 floats: HUD counter pulse per party slot */
.set M_HICON,   M_BASE+0x1f80          /* 8 words: multiplier icon timer per player */
.set M_PADL,    M_BASE+0x1f90          /* 2 dwords */
.set M_JSAVE,   M_BASE+0x1f98          /* 2 dwords */
.set M_SWAPPED, M_BASE+0x1fa0

/* multiplier icon timers of P3/P4 (replaces mov [0x879362],dx @4b78c1): the native code
   advances the two timers by frame time * 0.5 with truncation (control word already set
   to truncate here); do the same for entries 2 and 3. */
hud_icon_timers:
    mov word ptr [M_HICON+2], dx
    fld dword ptr [0x925018]
    fmul qword ptr [0x751690]
    movzx eax, word ptr [M_HICON+4]
    mov dword ptr [M_HTMP], eax
    fild dword ptr [M_HTMP]
    fadd st, st(1)
    fistp dword ptr [M_HTMP]
    mov eax, dword ptr [M_HTMP]
    mov word ptr [M_HICON+4], ax
    movzx eax, word ptr [M_HICON+6]
    mov dword ptr [M_HTMP], eax
    fild dword ptr [M_HTMP]
    faddp st(1), st
    fistp dword ptr [M_HTMP]
    mov eax, dword ptr [M_HTMP]
    mov word ptr [M_HICON+6], ax
    jmp 0x4b78c8
    .popsection
.set M_HTMP, M_BASE+0x1fa4

/* ================= ring colours =================
   Ring icons (table [world+0x2ac0], 16-byte entries {scene, 0, node, flags}): 0xa5 green,
   0xa6 blue, 0xa7 neutral, 0xa8 gold. The ring colour is in the texture (material tint
   fields have no effect on icons). P3/P4 draw the blue ring with a copy of the blue
   material whose texture id points to a recoloured copy of the blue ring texture, made
   and registered by the DLL loader (ring_tid in loader.c), on an engine-created dynamic
   material with its own render record (ring_material). The material is supplied
   through the engine's per-draw material override [0x9738f0] (read by the icon draw at
   0x5f11d0, used by the game at 0x62fb4c) for the ring draw only. Game data is unchanged. */
.set M_RINGOVR, M_BASE+0x1f28          /* material to use for the next portrait ring, or 0 */
.set M_OLDOVR,  M_BASE+0x1f2c
.set M_RDRET,   M_BASE+0x1f30
.set M_CFUNC,   M_BASE+0x1f40          /* loader: cdecl ring_material(blue_mtl, which) */
.set M_MATRED,  M_BASE+0x2000          /* 0x2c4-byte material copies */
.set M_MATPUR,  M_BASE+0x2300
.set RGBA_RED,    0xff1a14ff           /* bytes ff 14 1a ff */
.set RGBA_PURPLE, 0xfff023a0           /* bytes a0 23 f0 ff */

/* HUD portrait call (replaces call 0x55b830 @4b9479). Second pass: arm the coloured ring. */
hud_portrait:
    cmp dword ptr [M_PASS], 0
    je 1f
    push ebp                               /* HUD slot: 0 = P3, 1 = P4 */
    call arm_ring
    add esp, 4
    cmp dword ptr [M_RINGSKIP], 0
    jne 2f
1:  call 0x55b830
2:
    mov dword ptr [M_RINGOVR], 0
    jmp 0x4b947e

/* arm_ring(which): M_RINGOVR = red (0) or purple (1) copy of the blue ring material,
   made by the loader's ring_material helper; unchanged if it is not available. */
arm_ring:
    pushad
    cmp dword ptr [0x93b28c], 0            /* loading screen: icons come from the */
    je 1f                                  /* loading icon set (as 0x55b850 does)  */
    mov eax, dword ptr [0x951bb8]
    test eax, eax
    jz 1f
    mov eax, dword ptr [eax+0xa6*8+4]      /* icon name */
    test eax, eax
    jz 1f
    push 1
    push eax
    push offset M_ICONTMP
    push dword ptr [0x924880]
    call 0x5cf5b0                          /* (scene, out {scene, ?, node}, name, 1) */
    add esp, 16
    mov ebp, dword ptr [M_ICONTMP]
    mov eax, dword ptr [M_ICONTMP+8]
    test ebp, ebp
    jz 8f
    call rc_node
    jmp 2f
1:  mov eax, dword ptr [0x802c54]
    test eax, eax
    jz 8f
    mov edi, dword ptr [eax+0x2ac0]
    test edi, edi
    jz 8f
    mov ebp, dword ptr [edi+0xa6*16]
    test ebp, ebp
    jz 8f
    mov eax, 0xa6
    call rc_mat
2:  test eax, eax
    jz 8f
    cmp dword ptr [M_CFUNC], 0             /* ring helper (DLL loader only) */
    je 8f
    push dword ptr [esp+0x24]              /* which */
    push eax                               /* blue ring material */
    call dword ptr [M_CFUNC]               /* cdecl ring_material(blue, which) -> mtl or 0 */
    add esp, 8
    mov dword ptr [M_RINGOVR], eax
    test eax, eax
    jz 7f
    mov dword ptr [M_RINGFAIL], 0
    mov dword ptr [M_RINGSKIP], 0
    popad
    ret
7:  inc dword ptr [M_RINGFAIL]             /* coloured ring not ready yet: callers skip */
    xor eax, eax                           /* the portrait for a few frames rather than */
    cmp dword ptr [M_RINGFAIL], 60         /* show it with a blue/green ring           */
    setb al
    mov dword ptr [M_RINGSKIP], eax
    popad
    ret
8:  mov dword ptr [M_RINGSKIP], 0
    popad
    ret
.set M_RINGFAIL, M_BASE+0x2770
.set M_ICONTMP,  M_BASE+0x27e8             /* 12 bytes */
.set M_RINGSKIP, M_BASE+0x2774


/* ring draw inside the portrait function (replaces call 0x552c10 @55b8fc) */
ring_draw:
    mov eax, dword ptr [M_RINGOVR]
    test eax, eax
    jz 0x552c10
    mov dword ptr [M_RINGOVR], 0
    mov ecx, dword ptr [0x9738f0]
    mov dword ptr [M_OLDOVR], ecx
    mov dword ptr [0x9738f0], eax
    pop dword ptr [M_RDRET]
    call 0x552c10
    mov ecx, dword ptr [M_OLDOVR]
    mov dword ptr [0x9738f0], ecx
    push dword ptr [M_RDRET]
    ret

/* rc_mat(eax=icon id; edi=table, ebp=scene) -> eax = material pointer or 0 */
rc_mat:
    shl eax, 4
    cmp dword ptr [edi+eax], ebp           /* same scene */
    jne 9f
    mov eax, dword ptr [edi+eax+8]         /* node */
/* rc_node(eax = node, ebp = scene) -> eax = material pointer or 0 */
rc_node:
    test eax, eax
    jz 9f
    mov eax, dword ptr [eax+0xb0]          /* parts */
    test eax, eax
    jz 9f
    mov eax, dword ptr [eax+4]             /* &material index */
    test eax, eax
    jz 9f
    mov eax, dword ptr [eax]
    cmp eax, dword ptr [ebp+0x10]          /* index < material count */
    jae 9f
    mov ecx, dword ptr [ebp+0xc]
    mov eax, dword ptr [ecx+eax*4]
    ret
9:  xor eax, eax
    ret

/* ring icon for the HUD portrait: replaces test byte [esi+0x1fc],0x80 @4b92c1 */
hud_ring:
    cmp dword ptr [M_PASS], 0
    je 1f
    mov edi, 0xa6                          /* P3/P4: blue ring, drawn red/purple (hud_portrait) */
1:  test byte ptr [esi+0x1fc], 0x80
    jmp 0x4b92c8

.ifdef RESEARCH
/* ================= one-shot icon memory dump (4p_icons.bin) =================
   record = u32 addr, u32 len, bytes. Dumps icon table entries 0xa0..0xaf of [world+0x2ac0]
   and a window around every readable pointer found in entries 0xa4..0xa8. */
.set M_DUMPDONE, M_BASE+0x0ec
.set M_DUMPCNT,  M_BASE+0x0d0
.set M_VQ,       M_BASE+0x0d4
.set M_FH,       M_BASE+0x0d8
.set M_REC,      M_BASE+0x0c0   /* 8-byte record header */
.set M_MBI,      M_BASE+0x0a0   /* 28-byte MEMORY_BASIC_INFORMATION */
.set IAT_GetModuleHandleA, 0x751154
.set IAT_GetProcAddress,   0x7511b0

/* readable(eax=addr, ecx=len) -> eax=1/0 ; preserves others */
readable:
    push ebx
    push ecx
    push edx
    push esi
    mov ebx, eax
    mov esi, ecx
    push 28
    push M_MBI
    push ebx
    call dword ptr [M_VQ]
    test eax, eax
    jz 9f
    cmp dword ptr [M_MBI+0x10], 0x1000     /* State == MEM_COMMIT */
    jne 9f
    mov eax, dword ptr [M_MBI+0x14]        /* Protect */
    test eax, 0x101                        /* NOACCESS | GUARD */
    jnz 9f
    test eax, 0xee                         /* any readable flag */
    jz 9f
    mov eax, dword ptr [M_MBI]             /* BaseAddress */
    add eax, dword ptr [M_MBI+0xc]         /* + RegionSize = end */
    lea edx, [ebx+esi]
    cmp edx, eax
    ja 9f
    mov eax, 1
    jmp 8f
9:  xor eax, eax
8:  pop esi
    pop edx
    pop ecx
    pop ebx
    ret

/* write_rec(eax=addr, ecx=len): writes header + data if readable */
write_rec:
    pushad
    mov ebx, eax
    mov esi, ecx
    call readable
    test eax, eax
    jz 1f
    mov dword ptr [M_REC], ebx
    mov dword ptr [M_REC+4], esi
    push 0
    push offset M_DBGWRITTEN
    push 8
    push M_REC
    push dword ptr [M_FH]
    call dword ptr [IAT_WriteFile]
    push 0
    push offset M_DBGWRITTEN
    push esi
    push ebx
    push dword ptr [M_FH]
    call dword ptr [IAT_WriteFile]
1:  popad
    ret

icon_dump:
    pushad
    cmp dword ptr [M_DUMPDONE], 0
    jne id_out
    mov ebx, dword ptr [0x802c54]
    test ebx, ebx
    jz id_out
    mov eax, dword ptr [ebx+0x128]
    test eax, eax
    jz id_out
    test byte ptr [eax+0x64], 0xe0         /* only in playable levels */
    jnz id_out
    mov edi, dword ptr [ebx+0x2ac0]
    test edi, edi
    jz id_out
    inc dword ptr [M_DUMPCNT]
    cmp dword ptr [M_DUMPCNT], 600         /* ~10 s into the level */
    jb id_out
    mov dword ptr [M_DUMPDONE], 1
    /* resolve VirtualQuery */
    push offset s_k32
    call dword ptr [IAT_GetModuleHandleA]
    push offset s_vq
    push eax
    call dword ptr [IAT_GetProcAddress]
    test eax, eax
    jz id_out
    mov dword ptr [M_VQ], eax
    /* open file */
    push 0
    push 0x80
    push 2          /* CREATE_ALWAYS */
    push 0
    push 3
    push 0x40000000
    push offset s_dumpfile
    call dword ptr [IAT_CreateFileA]
    cmp eax, 0xffffffff
    je id_out
    mov dword ptr [M_FH], eax
    /* record 0: world struct 0x2a00..0x2c00 */
    lea eax, [ebx+0x2a00]
    mov ecx, 0x200
    call write_rec
    /* record 1: icon table entries 0x00..0xff (0x1000 bytes) */
    mov eax, edi
    mov ecx, 0x1000
    call write_rec
    /* windows around pointers in entries 0xa4..0xa8 */
    lea esi, [edi+0xa4*16]
    mov ebp, 20                            /* 5 entries x 4 dwords */
1:  mov eax, dword ptr [esi]
    cmp eax, 0x10000
    jb 2f
    sub eax, 0x2000
    mov ecx, 0x10000
    call write_rec
    /* also first-level pointers inside the target (first 0x100 bytes) */
    mov edx, dword ptr [esi]
    mov eax, edx
    mov ecx, 0x100
    call readable
    test eax, eax
    jz 2f
    push esi
    push ebp
    mov esi, edx
    mov ebp, 64
3:  mov eax, dword ptr [esi]
    cmp eax, 0x10000
    jb 4f
    sub eax, 0x400
    mov ecx, 0x2000
    call write_rec
4:  add esi, 4
    dec ebp
    jnz 3b
    pop ebp
    pop esi
2:  add esi, 4
    dec ebp
    jnz 1b
    /* v0.8: ring materials 0x14c..0x155 of icon scene and pointers inside them */
    mov esi, dword ptr [edi+0xa6*16]       /* scene */
    test esi, esi
    jz 7f
    mov eax, esi
    mov ecx, 0x400
    call write_rec
    mov esi, dword ptr [esi+0xc]           /* material ptr array */
    mov eax, esi
    mov ecx, 0x560
    call write_rec
    mov ebp, 0x14c
5:  mov edx, dword ptr [esi+ebp*4]
    mov eax, edx
    mov ecx, 0x2c4
    call write_rec
    mov eax, edx
    call readable
    test eax, eax
    jz 6f
    push esi
    push ebp
    mov esi, edx
    mov ebp, 0xb1
8:  mov eax, dword ptr [esi]
    cmp eax, 0x10000
    jb 9f
    mov ecx, 0x200
    call write_rec
9:  add esi, 4
    dec ebp
    jnz 8b
    pop ebp
    pop esi
6:  inc ebp
    cmp ebp, 0x156
    jb 5b
7:  push dword ptr [M_FH]
    call dword ptr [IAT_CloseHandle]
id_out:
    popad
    ret
s_k32:      .asciz "kernel32.dll"
s_vq:       .asciz "VirtualQuery"
s_dumpfile: .asciz "4p_icons2.bin"

.endif /* RESEARCH */

/* ================= studs: let human P3/P4 collect =================
   replaces movsx ebx,byte [edi+0x280] @46b209. Pickup routine only accepts player 0/1;
   a human in party slot 2/3 is credited as slot&1 (P3->P1 side, P4->P2 side). */
stud_pickup:                       /* replaces movsx ebx,[edi+0x280] @46b209 */
    movsx ebx, byte ptr [edi+0x280]
    cmp ebx, 2
    jl 1f
    cmp ebx, 3
    jg 1f
    test byte ptr [edi+0x1fc], 0x80
    jz 1f
    call 0x570bb0                          /* hub: stud path keeps 2-entry arrays -> fold */
    test eax, eax
    jz 2f
    and ebx, 1
1:  jmp 0x46b210
2:  mov dword ptr [esp+0x10], ebx          /* P3/P4 own the stud (owner byte = slot) */
    jmp 0x46b221

/* flight target of a collected stud = that player's HUD counter.
   replaces cmp ebx,1 ; fld [0x7fc2e0] @46b391 (normal levels) */
stud_fly:
    fld dword ptr [0x7fc2e0]               /* x: P2/P4 right, P1/P3 left */
    test ebx, 1
    jnz 1f
    fchs
1:  fstp dword ptr [esp+0x24]
    mov dword ptr [esp+0x1c], 0
    fld dword ptr [0x7fc310]               /* HUD row y */
    cmp ebx, 2
    jl 2f
    fchs                                   /* P3/P4 HUD at the bottom */
    fadd dword ptr [f_ctr_bottom]
    jmp 3f
2:  fadd dword ptr [f_ctr_bottom]          /* counter row offset, as the HUD (M_CTRY) */
3:  fstp dword ptr [esp+0x28]
    jmp 0x46b3ba
f_ctr_bottom: .float 0.075

/* stud arrival: owner-indexed 2-entry array 0x7fc374 (hub path only) - keep owner 0/1.
   replaces movsx ecx,[esi+0xfd] @46af80 */
stud_owner2:
    movsx ecx, byte ptr [esi+0xfd]
    and ecx, 1
    jmp 0x46af87

/* level start, after the P1/P2 purse setup loop (0x41fdc0): P3/P4 purses carry over between
   parts of a chapter exactly when P1/P2's do (0x803784 == 0x95121c), otherwise reset.
   replaces mov eax,[0x93d7f4] @41fe40 */
purse_init:
    mov eax, dword ptr [0x803784]
    cmp eax, dword ptr [0x95121c]
    je 1f
    mov dword ptr [M_PURSE], 0
    mov dword ptr [M_PURSE+0x10], 0
1:  mov ax, word ptr [0x803bac]
    mov word ptr [M_PURSE+8], ax
    mov word ptr [M_PURSE+0x18], ax
    mov eax, dword ptr [0x93d7f4]
    jmp 0x41fe45

/* True Jedi meter: [0x87b994] = P1 + P2 purses -> also + P3 + P4.
   replaces mov ecx,[0x93d7f4] @4b7606 (edx = P1 studs) */
tj_sum:
    mov ecx, dword ptr [PARTY+4]
    test ecx, ecx
    jz 1f
    mov ecx, dword ptr [ecx+0x7fc]
    test ecx, ecx
    jz 1f
    add edx, dword ptr [ecx]
1:  add edx, dword ptr [M_PURSE]
    add edx, dword ptr [M_PURSE+0x10]
    mov dword ptr [0x87b994], edx
    jmp 0x4b7622

/* results screen (0x483c70): P1/P2 studs are snapshotted to 0x87a6ac/0x87a6b0 and their sum
   is banked. Add P3 to P1's entry and P4 to P2's, once.
   replaces cmp byte [0x87a6dc],2 @483d94 */
stud_bank:
    cmp dword ptr [0x951b50], 0
    jne 1f
    mov eax, dword ptr [M_PURSE]
    add dword ptr [0x87a6ac], eax
    mov eax, dword ptr [M_PURSE+0x10]
    add dword ptr [0x87a6b0], eax
    mov dword ptr [M_PURSE], 0
    mov dword ptr [M_PURSE+0x10], 0
1:  cmp byte ptr [0x87a6dc], 2
    jmp 0x483d9b

/* ================= camera: pick which two players the 2-player camera frames ================= */
.set M_CAMSEL, M_BASE+0x0c8     /* 2 char pointers */
.set M_XMM,    M_BASE+0x180     /* xmm save (no: inside code page) */
cam_pick:                         /* replaces mov esi,[edx*4+0x93d7f0] @40b6fe */
    test edx, edx
    jnz 9f
    call cam_compute
9:  mov esi, dword ptr [edx*4+M_CAMSEL]
    jmp 0x40b705
cam_pick2:                        /* replaces mov edx,[ecx*4+0x93d7f0] @40b8b7 */
    mov edx, dword ptr [ecx*4+M_CAMSEL]
    jmp 0x40b8be

/* cam_compute: eligible = party[0],party[1] (as vanilla) + human party[2],party[3].
   <=2 eligible -> keep them (party order); >=3 -> farthest-apart pair (XZ). Preserves all regs. */
cam_compute:
    pushad
    mov eax, dword ptr [PARTY]
    mov dword ptr [M_CAMSEL], eax
    mov eax, dword ptr [PARTY+4]
    mov dword ptr [M_CAMSEL+4], eax
    cmp dword ptr [0x7f3b14], 0xffffffff   /* forced focus player -> vanilla */
    jne cc_out
    /* build list of humans among slots 0..3 into M_LIST (up to 4) */
    xor ecx, ecx                            /* count */
    xor ebx, ebx                            /* slot */
1:  mov eax, dword ptr [ebx*4+PARTY]
    test eax, eax
    jz 2f
    test byte ptr [eax+0x1fc], 0x80
    jz 2f
    mov dword ptr [ecx*4+M_LIST], eax
    inc ecx
2:  inc ebx
    cmp ebx, 4
    jb 1b
    /* any human in slot 2/3? if not -> vanilla */
    mov eax, dword ptr [PARTY+8]
    test eax, eax
    jz 3f
    test byte ptr [eax+0x1fc], 0x80
    jnz 4f
3:  mov eax, dword ptr [PARTY+12]
    test eax, eax
    jz cc_out
    test byte ptr [eax+0x1fc], 0x80
    jz cc_out
4:  cmp ecx, 2
    ja 5f
    /* 1 or 2 humans: use them directly */
    mov eax, dword ptr [M_LIST]
    mov dword ptr [M_CAMSEL], eax
    xor eax, eax
    cmp ecx, 2
    jb 6f
    mov eax, dword ptr [M_LIST+4]
6:  mov dword ptr [M_CAMSEL+4], eax
    jmp cc_out
5:  /* farthest pair */
    movss dword ptr [M_XSAVE], xmm0
    movss dword ptr [M_XSAVE+4], xmm1
    movss dword ptr [M_XSAVE+8], xmm2
    mov dword ptr [M_BEST], 0xbf800000     /* -1.0 */
    xor esi, esi                            /* i */
7:  lea edi, [esi+1]                        /* j */
8:  cmp edi, ecx
    jae 11f
    mov eax, dword ptr [esi*4+M_LIST]
    mov edx, dword ptr [edi*4+M_LIST]
    movss xmm0, dword ptr [eax+0x80]
    subss xmm0, dword ptr [edx+0x80]
    mulss xmm0, xmm0
    movss xmm1, dword ptr [eax+0x88]
    subss xmm1, dword ptr [edx+0x88]
    mulss xmm1, xmm1
    addss xmm0, xmm1
    movss xmm2, dword ptr [M_BEST]
    comiss xmm0, xmm2
    jbe 10f
    movss dword ptr [M_BEST], xmm0
    mov dword ptr [M_CAMSEL], eax
    mov dword ptr [M_CAMSEL+4], edx
10: inc edi
    jmp 8b
11: inc esi
    cmp esi, ecx
    jb 7b
    movss xmm0, dword ptr [M_XSAVE]
    movss xmm1, dword ptr [M_XSAVE+4]
    movss xmm2, dword ptr [M_XSAVE+8]
cc_out:
    popad
    ret
.set M_LIST,  M_BASE+0x2780
.set M_XSAVE, M_BASE+0x27a0
.set M_BEST,  M_BASE+0x27b0

/* ================= Free Play character select: P3/P4 cursors =================
   Menu 0x12 (update 0x476da0, draw 0x47bb70). State [0x879564] = 1 is the character grid.
   The native code keeps 2-entry per-player arrays (char 0x87b6c4, active 0x87b6c8, cell
   0x87958c, ready state 0x87955c, timer 0x879b0c, ...) and loops over players 0/1 with
   control entries 0x9253b0 + p*0x60. For P3/P4 the patch keeps a copy of those arrays
   (M_FSSTASH) and runs the native loop and the grid cursor draw a second time with the
   arrays exchanged: index 0/1 then means P3/P4. The second update pass reads
   private control entries (M_FAKE) filled from the P3/P4 gamepads. The ready count of the
   native loop covers both passes, so the select ends when every joined player is ready.
   P3/P4 join the select with START on a free XInput pad (port claimed with 0x4f47f0). */
.set M_FSSTASH, M_BASE+0x2600   /* 78 bytes, layout = fs_tab order */
.set S_CHAR,  0                  /* w[2] */
.set S_STATE, 12                 /* d[2] */
.set S_ACT,   68                 /* b[2] */
.set M_FAKE,  M_BASE+0x2680      /* 2 control entries x 0x60 */
.set M_MPASS, M_BASE+0x2740      /* 1 = update pass for P3/P4, 2 = draw pass */
.set M_GRET,  M_BASE+0x2744
.set M_MPRET, M_BASE+0x2748
.set M_FSOUT, M_BASE+0x2750      /* 2 dwords, outputs of the device scan */

fs_tab:
    .long 0x87b6c4, 4, 0x87958c, 8, 0x87955c, 8, 0x879b0c, 8, 0x879538, 8
    .long 0x87b58c, 8, 0x87b584, 8, 0x87b5b8, 8, 0x87b570, 8
    .long 0x87b6c8, 2, 0x87b5b4, 2, 0x87b6d0, 2, 0x87b5a4, 2, 0x87b56c, 2
    .long 0

/* exchange the native P1/P2 arrays with M_FSSTASH */
fs_swap:
    pushad
    mov esi, offset fs_tab
    mov edi, offset M_FSSTASH
1:  mov ebx, dword ptr [esi]
    test ebx, ebx
    jz 9f
    mov ecx, dword ptr [esi+4]
    add esi, 8
2:  mov al, byte ptr [ebx]
    mov dl, byte ptr [edi]
    mov byte ptr [ebx], dl
    mov byte ptr [edi], al
    inc ebx
    inc edi
    dec ecx
    jnz 2b
    jmp 1b
9:  popad
    ret

fs_zero:
    push edi
    push ecx
    push eax
    mov edi, offset M_FSSTASH
    mov ecx, 20
    xor eax, eax
    rep stosd
    pop eax
    pop ecx
    pop edi
    ret

/* menu init (replaces mov [0x879afc],ebx @47bb5c): forget P3/P4 state */
fs_clear:
    mov dword ptr [0x879afc], ebx
    call fs_zero
    call fs_layout
    jmp 0x47bb62

/* entering the grid (replaces mov [0x879564],ebx @476e76, ebx = 1, edi = grid):
   P3/P4 cursors start on their party character, or on cells 2/3 */
fs_init:
    mov dword ptr [0x879564], ebx
    mov dword ptr [M_P2SEL], 0             /* P2 not joined through the select */
    pushad
    call fs_zero
    xor ebx, ebx
1:  or eax, -1
    mov ecx, dword ptr [ebx*4+PARTY+8]
    test ecx, ecx
    jz 2f
    movsx eax, word ptr [ecx+0x1064]
2:  movzx ecx, word ptr [edi+6]
    push ecx
    push dword ptr [edi]
    push eax
    call 0x594250                          /* cell of a character in the grid, or -1 */
    add esp, 12
    movzx ecx, word ptr [edi+6]
    test eax, eax
    jge 3f
    lea eax, [ebx+2]
    cmp eax, ecx
    jb 3f
    xor eax, eax
3:  mov dword ptr [ebx*4+M_FSSTASH+4], eax
    imul eax, eax, 0x1c
    add eax, dword ptr [edi]
    mov ax, word ptr [eax]
    mov word ptr [ebx*2+M_FSSTASH+S_CHAR], ax
    inc ebx
    cmp ebx, 2
    jb 1b
    popad
    jmp 0x476e7c

/* eax = 1 if port 2 or 3 has a device */
fs_any:
    push 2
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jge 1f
    push 3
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jge 1f
    xor eax, eax
    ret
1:  mov eax, 1
    ret

/* START on a free XInput pad claims port 2 (then 3) */
fs_join:
    pushad
    mov ebx, 2
1:  push ebx
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jge 5f
    mov ebp, 0x3ff0                        /* XInput pads (devices 0-3) only */
    xor esi, esi
2:  push esi
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jl 3f
    mov ecx, eax
    mov edx, 1
    shl edx, cl
    or ebp, edx                            /* not devices that have a port */
3:  inc esi
    cmp esi, 4
    jb 2b
    call mirror_mask
    or ebp, eax
    push 1
    push offset M_FSOUT+4
    push offset M_FSOUT
    push 0x1a                              /* START, as the drop-in */
    push ebp
    call 0x6d9120
    add esp, 0x14
    test eax, eax
    jl 5f
    push eax
    push ebx
    call 0x4f47f0                          /* claim port ebx for device eax */
    add esp, 8
    push 0
    push 0
    push 0
    push 0x30
    call 0x547930                          /* menu sound */
    add esp, 0x10
5:  inc ebx
    cmp ebx, 4
    jb 1b
    popad
    ret

/* fs_prep(grid): the native arrays hold P3/P4. Set their active flags, fill the
   private control entries from the gamepads (as 0x54ae40 does for a human slot),
   run their timers. */
fs_prep:
    pushad
    xor ebx, ebx
fsp_loop:
    lea eax, [ebx+2]
    push eax
    call GETPORTDEV
    add esp, 4
    lea edi, [ebx+ebx*2]
    shl edi, 5
    add edi, offset M_FAKE
    xor esi, esi
    test eax, eax
    jl 2f
    imul eax, eax, 0x84
    cmp byte ptr [eax+0x917000], 0         /* pad disconnected: not in the select */
    je 2f
    mov esi, dword ptr [ebx*4+M_PADS+8]
    test esi, esi
    jnz 2f
    lea eax, [ebx+2]
    push 0
    push eax
    call PAD_CREATE
    add esp, 8
    mov esi, eax
    mov dword ptr [ebx*4+M_PADS+8], eax
2:  mov dword ptr [edi], esi
    test esi, esi
    setnz byte ptr [ebx+0x87b6c8]
    jnz 3f
    xor eax, eax
    mov dword ptr [edi+4], eax
    mov dword ptr [edi+8], eax
    mov dword ptr [edi+0xc], eax
    mov dword ptr [edi+0x10], eax
    mov dword ptr [edi+0x14], eax
    mov word ptr [ebx*2+0x87b6c4], 0xffff  /* not drawn while not joined */
    jmp 7f
3:  cmp word ptr [ebx*2+0x87b6c4], 0xffff  /* just joined: character under the cursor */
    jne 4f
    mov eax, dword ptr [ebx*4+0x87958c]
    imul eax, eax, 0x1c
    mov ecx, dword ptr [esp+0x24]          /* grid */
    add eax, dword ptr [ecx]
    mov ax, word ptr [eax]
    mov word ptr [ebx*2+0x87b6c4], ax
4:  push 0
    push esi
    call 0x6d6020                          /* read the pad, as 0x54ae40 does each frame */
    add esp, 8
    mov eax, dword ptr [esi+0x70]          /* buttons held */
    mov dword ptr [edi+4], eax
    mov eax, dword ptr [esi+0x78]          /* buttons pressed */
    mov dword ptr [edi+8], eax
    xor edx, edx                           /* left stick -> direction bits (0x54af1f) */
    movzx eax, byte ptr [esi+0x92]
    cmp eax, 42
    ja 5f
    or edx, dword ptr [0x802298]
5:  cmp eax, 213
    jb 6f
    or edx, dword ptr [0x80229c]
6:  movzx eax, byte ptr [esi+0x93]
    cmp eax, 42
    ja 8f
    or edx, dword ptr [0x802290]
8:  cmp eax, 213
    jb 9f
    or edx, dword ptr [0x802294]
9:  mov dword ptr [edi+0xc], edx
    mov eax, dword ptr [edi+0x14]
    xor eax, edx
    and eax, edx
    mov dword ptr [edi+0x10], eax          /* newly pressed directions */
    mov dword ptr [edi+0x14], edx
7:  fld dword ptr [0x925018]               /* portrait scale -> 1, as 0x4775cd for P1/P2 */
    fadd st, st
    sub esp, 12
    fstp dword ptr [esp+8]
    fld1
    fstp dword ptr [esp+4]
    fld dword ptr [ebx*4+0x879538]
    fstp dword ptr [esp]
    call 0x54fad0
    add esp, 12
    fstp dword ptr [ebx*4+0x879538]
    fld dword ptr [ebx*4+0x879b0c]         /* timer, as 0x476de2 for P1/P2 */
    fldz
    fcomip st, st(1)
    jae 10f
    fsub dword ptr [0x925018]
    fstp dword ptr [ebx*4+0x879b0c]
    jmp 11f
10: fstp st(0)
11: inc ebx
    cmp ebx, 2
    jb fsp_loop
    popad
    ret

/* end of the grid player loop (replaces cmp edx,0x925470 ; 3 stores ; jl 476f10 @4773da).
   eax = next player, edx = next control entry, ecx = next "other player" counter. */
fs_loopend:
    mov dword ptr [esp+0x14], eax
    mov dword ptr [esp+0x40], edx
    mov dword ptr [esp+0x44], ecx
    cmp byte ptr [M_MPASS], 0
    jne 5f
    cmp edx, 0x925470
    jb 0x476f10                            /* native P1/P2 loop */
    push dword ptr [esp+0x10]              /* grid */
    call p2_join
    add esp, 4
    call fs_join
    call fs_any
    test eax, eax
    jnz 1f
    mov word ptr [M_FSSTASH+S_ACT], 0      /* nobody on ports 2/3 */
    call fs_layout
    jmp 0x4773f2
1:
    call fs_swap                           /* P3/P4 pass */
    mov byte ptr [M_MPASS], 1
    push dword ptr [esp+0x10]              /* grid */
    call fs_prep
    add esp, 4
    xor eax, eax
    or ecx, -1
    mov edx, offset M_FAKE
    mov dword ptr [esp+0x14], eax
    mov dword ptr [esp+0x40], edx
    mov dword ptr [esp+0x44], ecx
    mov ebx, 1
    jmp 0x476f10
5:  cmp edx, offset M_FAKE+0xc0
    jb 0x476f10
    call fs_swap
    mov byte ptr [M_MPASS], 0
    call fs_layout
    jmp 0x4773f2

/* character confirm (replaces call 0x594960 @4772c3): also refuse a character that a
   player of the other pair (in M_FSSTASH) has already picked */
fs_unlocked:
    push dword ptr [esp+4]
    call 0x594960
    add esp, 4
    test eax, eax
    jz 9f
    mov edx, dword ptr [esp+4]
    xor ecx, ecx
1:  cmp byte ptr [ecx+M_FSSTASH+S_ACT], 0
    je 2f
    cmp dword ptr [ecx*4+M_FSSTASH+S_STATE], 1
    jl 2f
    cmp word ptr [ecx*2+M_FSSTASH+S_CHAR], dx
    jne 2f
    xor eax, eax
    ret
2:  inc ecx
    cmp ecx, 2
    jb 1b
9:  ret

/* grid cursors (replaces call 0x477630 @47c2e5, 47c362, 47c55e): draw P1/P2, then P3/P4 */
fs_grid:
    pop dword ptr [M_GRET]
    call 0x477630
    cmp word ptr [M_FSSTASH+S_ACT], 0
    je 9f
    call fs_swap
    mov byte ptr [M_MPASS], 2
    push dword ptr [esp+0xc]
    push dword ptr [esp+0xc]
    push dword ptr [esp+0xc]
    push dword ptr [esp+0xc]
    call 0x477630
    add esp, 0x10
    mov byte ptr [M_MPASS], 0
    call fs_swap
9:  push dword ptr [M_GRET]
    ret

/* cursor portrait in 0x477630 (replaces call 0x55b830 @477843, 47789e; esi = ring id):
   in the P3/P4 draw pass the ring is drawn red (0xa6 = P3) or purple (0xa5 = P4) */
fs_portrait:
    push eax                               /* a player not in the select (not active, */
    mov eax, dword ptr [esp+0x48]          /* 0x87b6c8) shows no ring on the grid, as   */
    cmp eax, 1                             /* P3/P4 (v0.41; P2 used to keep its ring    */
    ja 1f                                  /* on its character while not joined)        */
    cmp byte ptr [eax+0x87b6c8], 0
    jne 1f
    pop eax
    ret
1:  pop eax
    cmp byte ptr [M_MPASS], 2
    jne 0x55b830
    xor eax, eax
    cmp esi, 0xa6
    setne al
    push eax
    call arm_ring
    add esp, 4
    cmp dword ptr [M_RINGSKIP], 0
    jne 9f
    pop dword ptr [M_MPRET]
    call 0x55b830
    mov dword ptr [M_RINGOVR], 0
    push dword ptr [M_MPRET]
    ret
9:  ret                                    /* ring not ready: skip this frame */

/* Free Play roster: add P3/P4's picks right after P1/P2's, so the level loads them.
   0x489150 runs when the grid finishes ([0x879564] = 1) and again when Free Play levels
   load ([0x93b2a4] != 0). Hooked in both of its branches. */
fp_addpicks:
    pushad
    cmp dword ptr [0x93b2a4], 0
    jne 1f
    cmp dword ptr [0x879564], 1
    jne 9f
1:  cmp byte ptr [M_FSSTASH+S_ACT], 0
    je 2f
    movsx edx, word ptr [M_FSSTASH+S_CHAR]
    call 0x4890e0
2:  cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    je 9f
    movsx edx, word ptr [M_FSSTASH+S_CHAR+2]
    call 0x4890e0
9:  popad
    ret

/* branch "all unlocked characters" (replaces cmp [0x87a9c8],0 @489278) */
fp_roster:
    call fp_addpicks
    cmp dword ptr [0x87a9c8], 0
    jmp 0x48927f

/* branch "party / level characters" (replaces mov eax,[0x87b2c4] @489327) */
fp_roster2:
    call fp_addpicks
    mov eax, dword ptr [0x87b2c4]
    jmp 0x48932c

/* select reveal list (end of 0x476840, replaces pop edi/esi/ebp/ebx/ecx @476a48): the
   characters shown in the middle after everyone is ready are P1, P2 and 0x8795a8
   (count [0x879598], dword entries {char, 1}). Put P3/P4's picks first. */
fs_extras:
    cmp dword ptr [0x879564], 1
    jne 9f
    mov ebx, 1
1:  cmp byte ptr [ebx+M_FSSTASH+S_ACT], 0
    je 8f
    movsx edx, word ptr [ebx*2+M_FSSTASH+S_CHAR]
    cmp edx, -1
    je 8f
    xor ecx, ecx                           /* remove it if listed */
2:  cmp ecx, dword ptr [0x879598]
    jge 4f
    cmp word ptr [ecx*4+0x8795a8], dx
    jne 3f
    mov esi, ecx
21: mov eax, dword ptr [esi*4+0x8795ac]
    mov dword ptr [esi*4+0x8795a8], eax
    inc esi
    cmp esi, dword ptr [0x879598]
    jl 21b
    dec dword ptr [0x879598]
    jmp 2b
3:  inc ecx
    jmp 2b
4:  mov ecx, dword ptr [0x879598]          /* insert at the front */
    cmp ecx, 0x100
    jge 8f
5:  test ecx, ecx
    jz 6f
    mov eax, dword ptr [ecx*4+0x8795a4]
    mov dword ptr [ecx*4+0x8795a8], eax
    dec ecx
    jmp 5b
6:  mov word ptr [0x8795a8], dx
    mov word ptr [0x8795aa], 1
    inc dword ptr [0x879598]
8:  dec ebx
    jge 1b
    mov eax, dword ptr [0x879598]
    mov word ptr [eax*4+0x8795a8], 0xffff
9:  pop edi
    pop esi
    pop ebp
    pop ebx
    pop ecx
    ret

/* party save for the next level (replaces mov [0x855f7c],0 @414e71; esi = saved slots).
   Entering Free Play from the grid ([0x855f7c] = 1): party slot 2 = P3's pick, slot 3 =
   P4's pick, both human (kept human by party_restore only if the port has a device). */
fp_party:
    cmp dword ptr [0x855f7c], 1
    jne 9f
    cmp dword ptr [0x93b2a4], 0
    je 9f
    cmp dword ptr [M_P2SEL], 0             /* P2 joined in the select: human in the level */
    je 0f
    cmp byte ptr [0x87b6c9], 0
    je 0f
    mov byte ptr [0x93d526], 1
0:
    cmp byte ptr [M_FSSTASH+S_ACT], 0
    je 1f
    mov ax, word ptr [M_FSSTASH+S_CHAR]
    mov edx, 2
    mov cl, 1
    call fp_setslot
1:  cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    je 9f
    cmp esi, 3
    jae 2f
    call fp_filler                         /* P4 without P3: slot 2 gets a roster character */
    mov edx, 2
    mov cl, 0
    call fp_setslot
2:  mov ax, word ptr [M_FSSTASH+S_CHAR+2]
    mov edx, 3
    mov cl, 1
    call fp_setslot
9:  mov dword ptr [0x855f7c], 0
    cmp esi, 8
    jmp 0x414e7b

/* fp_setslot: edx = slot, ax = character, cl = human; esi = slot count (may grow by 1) */
fp_setslot:
    cmp ax, 0xffff
    je 9f
    cmp esi, edx
    jb 9f
    ja 1f
    push esi                               /* new slot: copy slot 1's saved state */
    push edi
    push ecx
    mov esi, 0x93d520
    mov edi, edx
    shl edi, 4
    add edi, 0x93d510
    mov ecx, 4
    rep movsd
    pop ecx
    pop edi
    pop esi
    inc esi
1:  push ebx
    mov ebx, edx
    shl ebx, 4
    mov dword ptr [ebx+0x93d510], 0        /* studs: P3/P4 have their own purse */
    mov byte ptr [ebx+0x93d516], cl        /* human */
    mov word ptr [edx*2+0x93d590], ax      /* character */
    pop ebx
9:  ret

/* fp_filler -> ax = first roster character that is not P1's, P2's or P4's */
fp_filler:
    push ecx
    xor ecx, ecx
1:  cmp ecx, dword ptr [0x87b2c4]
    jge 3f
    mov ax, word ptr [ecx*4+0x87a840]
    cmp ax, 0xffff
    je 3f
    cmp ax, word ptr [0x93d590]
    je 2f
    cmp ax, word ptr [0x93d592]
    je 2f
    cmp ax, word ptr [M_FSSTASH+S_CHAR+2]
    jne 4f
2:  inc ecx
    jmp 1b
3:  mov ax, word ptr [0x93d592]
4:  pop ecx
    ret

/* big portraits and names (loop 0x47bf29..0x47c1fe, state 1): a second pass for P3/P4.
   The patched fld instructions read the sel_* values. Without P3/P4 they are the native
   constants. With P3/P4 the portraits form a 2x2 layout: P1/P2 on a top row, P3/P4 on a
   row below (one of them alone is centred), smaller, above the character grid.
   Visual y equals the portrait y; the ring radius is 0.6 x size; names are drawn from
   their top edge. */
sel_cx0:   .float -0.4                     /* 0x47bf9e  P1/P3 centre x       (0x755174) */
sel_cx1:   .float 0.4                      /* 0x47bfb7  P2/P4 centre x       (0x7532b8) */
sel_cy:    .float 0.745                    /* 0x47c004  corner y             (0x7fc310) */
sel_size:  .float 0.35                     /* 0x47bfe2  big portrait size    (0x7f9358) */
sel_ctry:  .float 0.35                     /* 0x47c112  big portrait y       (0x7f9354) */
sel_namey: .float 0.125                    /* 0x47c1c8  name y (top)         (0x7f935c) */
sel_namesc: .float 0.45                    /* 0x47c19a  name scale           (0x7532c4) */
lay_top:   .float -0.4, 0.4, 0.745, 0.35, 0.35, 0.125, 0.45
lay_bot:   .float -0.25, 0.25, 0.445, 0.25, 0.15, -0.015, 0.36
lay_native: .float -0.4, 0.4, 0.745, 0.35, 0.35, 0.125, 0.45
lay_4top:  .float -0.25, 0.25, 0.745, 0.25, 0.55, 0.385, 0.36

/* copy 7 floats from esi to edi */
lay_copy:
    push ecx
    mov ecx, 7
    rep movsd
    pop ecx
    ret

/* fs_layout: called once per frame from the grid update. Uses the P3/P4 active flags
   in M_FSSTASH. Sets lay_top/lay_bot and the live sel_* values (top row). */
fs_layout:
    pushad
    mov esi, offset lay_native
    cmp word ptr [M_FSSTASH+S_ACT], 0
    je 1f
    mov esi, offset lay_4top
1:  mov edi, offset lay_top
    call lay_copy
    mov dword ptr [lay_bot], 0xbe800000    /* -0.25 */
    mov dword ptr [lay_bot+4], 0x3e800000  /*  0.25 */
    cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    jne 2f
    mov dword ptr [lay_bot], 0             /* P3 alone: centred */
2:  cmp byte ptr [M_FSSTASH+S_ACT], 0
    jne 3f
    mov dword ptr [lay_bot+4], 0           /* P4 alone: centred */
3:  mov esi, offset lay_top
    mov edi, offset sel_cx0
    call lay_copy
    popad
    ret

/* replaces add esi,1 ; cmp esi,2 ; jl 47bf2b @47c1f8 */
fs_bigloop:
    add esi, 1
    cmp esi, 2
    jl 0x47bf2b
    cmp byte ptr [M_MPASS], 3
    je 2f
    cmp word ptr [M_FSSTASH+S_ACT], 0
    jne 1f
    pushad
    call fs_corners
    popad
    jmp 0x47c204
1:  call fs_swap
    mov byte ptr [M_MPASS], 3
    pushad
    mov esi, offset lay_bot
    mov edi, offset sel_cx0
    call lay_copy
    popad
    xor esi, esi
    jmp 0x47bf2b
2:  call fs_swap
    mov byte ptr [M_MPASS], 0
    pushad
    mov esi, offset lay_top
    mov edi, offset sel_cx0
    call lay_copy
    call fs_corners
    popad
    jmp 0x47c204

/* corner portraits for P3/P4 (bottom corners), like P1/P2's: the confirmed pick, or the
   party character while choosing */
fs_corners:
    cmp byte ptr [M_SELDONE], 0            /* already drawn this frame with P2's corner */
    je 7f
    mov byte ptr [M_SELDONE], 0
    ret
7:  call corner_tick
    xor ebx, ebx
1:  mov edi, 0x3f400000                    /* not joined: faded (0.75, as P2) */
    or eax, -1
    cmp byte ptr [ebx+M_FSSTASH+S_ACT], 0
    jne 61f
    push ebx                               /* only while a pad could join it */
    call p34_port_avail
    add esp, 4
    test eax, eax
    jz 5f
    or eax, -1
    jmp 6f
61:
    mov edi, 0x3f800000
    movsx eax, word ptr [ebx*2+M_FSSTASH+S_CHAR]
    cmp dword ptr [ebx*4+M_FSSTASH+S_STATE], 0
    jne 2f
6:
    mov ecx, dword ptr [ebx*4+PARTY+8]
    test ecx, ecx
    jz 2f
    movsx eax, word ptr [ecx+0x1064]
2:  cmp eax, -1
    je 5f
    mov edx, 0xbf466666                    /* x -0.775 */
    test ebx, ebx
    jz 3f
    mov edx, 0x3f466666                    /* x +0.775 */
3:  push edi                               /* alpha */
    push ebx                               /* which ring */
    push edx                               /* x */
    push eax
    call corner_draw
    add esp, 16
5:  inc ebx
    cmp ebx, 2
    jb 1b
    ret

    .pushsection .text2, "ax"
/* ================= Free Play grid: hidden cells and cursor skipping =================
   The grid (0x594c30) leaves out the cells listed at 0x879b80 ({word char, word} each,
   0xffff ends the list), because the players' cursors draw those characters popped
   out. The select listed P1 and P2 always. Now: P1, P2 only while P2 is in the select
   (0x87b6c9), and P3/P4 while they are in it, so P3/P4's hovered character no longer
   stays in the grid under their cursor, and a P2 that is not in the select leaves its
   character in the grid. Replaces call 0x594c30 @47c2d1 (state 0) and @47c34f (grid). */
grid_list:
    pushad
    mov edi, 0x879b80
    movzx eax, word ptr [0x87b6c4]         /* P1 */
    mov dword ptr [edi], eax
    add edi, 4
    cmp byte ptr [0x87b6c9], 0
    je 1f
    movzx eax, word ptr [0x87b6c6]         /* P2, only while in the select */
    mov dword ptr [edi], eax
    add edi, 4
1:  xor ebx, ebx
2:  cmp byte ptr [ebx+M_FSSTASH+S_ACT], 0
    je 3f
    movzx eax, word ptr [ebx*2+M_FSSTASH+S_CHAR]
    cmp ax, 0xffff
    je 3f
    mov dword ptr [edi], eax
    add edi, 4
3:  inc ebx
    cmp ebx, 2
    jb 2b
    mov dword ptr [edi], 0xffffffff
    popad
    jmp 0x594c30

/* cursor movement skips the other player's character (0x87b6c4[other]); not when that
   player is not in the select, so P2's hub character can be picked while P2 is out
   (replaces movzx reg, word [idx*2+0x87b6c4] @47719b, 4771e0, 477244) */
skip_other1:                               /* ebp <- [edx*2+..] */
    mov ebp, 0xffff
    cmp byte ptr [edx+0x87b6c8], 0
    je 1f
    movzx ebp, word ptr [edx*2+0x87b6c4]
1:  jmp 0x4771a3
skip_other2:                               /* edx <- [ecx*2+..] */
    mov edx, 0xffff
    cmp byte ptr [ecx+0x87b6c8], 0
    je 1f
    movzx edx, word ptr [ecx*2+0x87b6c4]
1:  jmp 0x4771e8
skip_other3:
    mov edx, 0xffff
    cmp byte ptr [ecx+0x87b6c8], 0
    je 1f
    movzx edx, word ptr [ecx*2+0x87b6c4]
1:  jmp 0x47724c

/* ================= P2 in the Free Play select =================
   The select's players are fixed when it opens (0x496740: active = party slot human).
   P2 can now join in the grid: F2 on the keyboard (P1 and P2 share it, so no P1 key
   joins P2), or START on an XInput pad no port owns (before P3/P4 are offered the
   same press). A P2 that joined here gets control entry 1 filled from its
   pad each grid frame (as fs_prep does for P3/P4) and is made human in the level's
   party (fp_party). */
p2_join:
    pushad
    cmp byte ptr [0x87b6c9], 0
    jne 9f
    cmp dword ptr [M_F2FN], 0              /* F2: P2 joins on the keyboard */
    je 2f
    call dword ptr [M_F2FN]
    test eax, eax
    jz 2f
    push 1
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jge 4f                                 /* port 1 keeps its device (keyboard half) */
    mov esi, 10                            /* else the first keyboard half nobody owns */
11: xor ecx, ecx
12: push ecx
    call GETPORTDEV
    add esp, 4
    cmp eax, esi
    je 13f
    inc ecx
    cmp ecx, 4
    jb 12b
    push esi
    push 1
    call 0x4f47f0
    add esp, 8
    jmp 4f
13: inc esi
    cmp esi, 14
    jb 11b
    jmp 9f
2:  mov ebp, 0x3ff0                        /* START on a free XInput pad claims port 1 */
    xor esi, esi
3:  push esi
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jl 31f
    mov ecx, eax
    mov edx, 1
    shl edx, cl
    or ebp, edx
31: inc esi
    cmp esi, 4
    jb 3b
    call mirror_mask
    or ebp, eax
    push 1
    push offset M_P2OUT+4
    push offset M_P2OUT
    push 0x1a                              /* START */
    push ebp
    call 0x6d9120
    add esp, 0x14
    test eax, eax
    jl 9f
    push eax
    push 1
    call 0x4f47f0
    add esp, 8
4:  mov byte ptr [0x87b6c9], 1
    mov dword ptr [M_P2SEL], 1
    mov dword ptr [0x879560], 0            /* choosing */
    mov edi, dword ptr [esp+0x24]          /* grid: {cells (0x1c each, char word), ?, count +6} */
    movzx ecx, word ptr [0x87b6c6]
    call p2_taken
    test eax, eax
    jnz 5f
    mov eax, dword ptr [0x879590]          /* its own character is free: keep it */
    jmp 7f
5:  xor esi, esi                           /* else the first free unlocked character */
6:  movzx eax, word ptr [edi+6]
    cmp esi, eax
    jae 8f
    imul eax, esi, 0x1c
    add eax, dword ptr [edi]
    movzx ecx, word ptr [eax]
    call p2_taken
    test eax, eax
    jnz 61f
    push ecx
    push ecx
    call 0x594960                          /* unlocked */
    add esp, 4
    pop ecx
    test eax, eax
    jnz 62f
61: inc esi
    jmp 6b
62: mov word ptr [0x87b6c6], cx
    mov eax, esi
7:  mov dword ptr [0x879590], eax
8:  push 0
    push 0
    push 0
    push 0x30
    call 0x547930                          /* menu sound */
    add esp, 0x10
9:  popad
    ret

/* p2_taken(ecx = character) -> eax = 1 when P1 or a joined P3/P4 has it, else 0 */
p2_taken:
    xor eax, eax
    cmp cx, word ptr [0x87b6c4]
    je 1f
    cmp byte ptr [M_FSSTASH+S_ACT], 0
    je 2f
    cmp cx, word ptr [M_FSSTASH+S_CHAR]
    je 1f
2:  cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    je 3f
    cmp cx, word ptr [M_FSSTASH+S_CHAR+2]
    je 1f
3:  ret
1:  mov eax, 1
    ret

/* every grid frame, before the players' loop (replaces mov edx,0x9253b0 @476ee8): a P2
   that joined in the select drives control entry 1 from its own pad */
p2_feed:
    cmp dword ptr [M_P2SEL], 0
    je 9f
    cmp byte ptr [0x87b6c9], 0
    je 9f
    pushad
    mov ecx, dword ptr [PARTY+4]
    test ecx, ecx
    jz 1f
    test byte ptr [ecx+0x1fc], 0x80        /* human: the native update fills it */
    jnz 8f
1:  mov esi, dword ptr [M_P2PAD]
    test esi, esi
    jnz 2f
    push 0
    push 1
    call PAD_CREATE
    add esp, 8
    mov esi, eax
    mov dword ptr [M_P2PAD], eax
    test esi, esi
    jz 8f
2:  mov edi, 0x925410
    mov dword ptr [edi], esi
    push 0
    push esi
    call 0x6d6020
    add esp, 8
    mov eax, dword ptr [esi+0x70]
    mov dword ptr [edi+4], eax
    mov eax, dword ptr [esi+0x78]
    mov dword ptr [edi+8], eax
    xor edx, edx
    movzx eax, byte ptr [esi+0x92]
    cmp eax, 42
    ja 3f
    or edx, dword ptr [0x802298]
3:  cmp eax, 213
    jb 4f
    or edx, dword ptr [0x80229c]
4:  movzx eax, byte ptr [esi+0x93]
    cmp eax, 42
    ja 5f
    or edx, dword ptr [0x802290]
5:  cmp eax, 213
    jb 6f
    or edx, dword ptr [0x802294]
6:  mov dword ptr [edi+0xc], edx
    mov eax, dword ptr [edi+0x14]
    xor eax, edx
    and eax, edx
    mov dword ptr [edi+0x10], eax
    mov dword ptr [edi+0x14], edx
8:  popad
9:  mov edx, 0x9253b0
    jmp 0x476eed

/* "Press START to join" beside the corner of every player who can still join the select
   (P2 while not in it; P3/P4 while not in it and a free XInput pad is connected) */
sel_joinmsgs:
    cmp dword ptr [0x879564], 1            /* grid state only */
    jne 9f
    pushad
    mov dword ptr [M_SELTXT], offset s_join
    cmp byte ptr [0x87b6c9], 0
    jne 1f
    mov dword ptr [M_SELTXT], offset s_joinp2
    push 8                                 /* right-side flags, as the HUD for P2 */
    push 0x3f333333                        /* y 0.7 */
    push 0x3f2f5c29                        /* x +0.685 */
    call sel_text
    add esp, 12
    mov dword ptr [M_SELTXT], offset s_join
1:  call free_pads
    mov ebx, eax
    cmp byte ptr [M_FSSTASH+S_ACT], 0
    jne 2f
    test ebx, ebx
    jz 2f
    dec ebx
    push 2
    push 0x3ecccccd                        /* y 0.4 */
    push 0xbf2f5c29                        /* x -0.685 */
    call sel_text
    add esp, 12
2:  cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    jne 8f
    test ebx, ebx
    jz 8f
    push 8
    push 0x3ecccccd
    push 0x3f2f5c29
    call sel_text
    add esp, 12
8:  popad
9:  ret

sel_text:                                  /* (x, y, side flags) */
    pushad
    fsave [M_FPUSAVE]
    push 0x60                              /* alpha (0..128) */
    push 0
    push 0
    push 2
    push 0x3e99999a
    push 0xff
    push 0xff
    push 0xff
    push dword ptr [esp+0x4c]              /* flags */
    push 0x3eb33333
    push 0x3eb33333
    push 0x3eb33333
    push 0x3f800000
    push dword ptr [esp+0x5c]              /* y */
    push dword ptr [esp+0x5c]              /* x */
    push dword ptr [M_SELTXT]
    call 0x50d910
    add esp, 0x40
    frstor [M_FPUSAVE]
    popad
    ret
s_joinp2: .asciz "Press F2 or START to join"

/* ================= switching portrait over the head, P3/P4 colour =================
   When a player takes over a character, 0x4bbfc0/0x4bc0b0 spawn the character's
   portrait and a ring (icon 0xa6 for player 0, else 0xa5) as effects (0x560b60), which
   copy the icon entry {scene, ?, node, flags}. For P3/P4 the entry is a copy whose node
   is a copy of the ring node (same data); when the effect draws (0x552c10 @56174c,
   561840) with one of those nodes, the ring is drawn red/purple through the material
   override, as the HUD does. */
part_spawn1:                               /* replaces add eax,[ecx+0x2ac0] ; mov [esp+0x60],eax */
    add eax, dword ptr [ecx+0x2ac0]
    movsx edx, byte ptr [ebp+0x280]
    call ring_fake
    mov dword ptr [esp+0x60], eax
    jmp 0x4bc095
part_spawn2:                               /* replaces add edx,[eax+0x2ac0] ; mov [esp+0x40],edx */
    add edx, dword ptr [eax+0x2ac0]
    push eax
    mov eax, edx
    movsx edx, byte ptr [ebx+0x280]
    call ring_fake
    mov edx, eax
    pop eax
    mov dword ptr [esp+0x40], edx
    jmp 0x4bc28e

/* ring_fake(eax = entry, edx = player) -> eax = entry, or for players 2/3 the copy */
ring_fake:
    cmp edx, 2
    jb 9f
    cmp edx, 3
    ja 9f
    test eax, eax
    jz 9f
    pushad
    sub edx, 2
    imul edi, edx, 16
    add edi, offset fake_entry
    mov esi, eax
    mov ecx, 4
    rep movsd
    sub edi, 16
    mov esi, dword ptr [edi+8]             /* node */
    test esi, esi
    jz 8f
    imul eax, edx, 0xd0
    add eax, offset fake_node
    mov dword ptr [edi+8], eax
    mov edi, eax
    mov ecx, 0xd0/4
    rep movsd
8:  imul eax, edx, 16
    add eax, offset fake_entry
    mov dword ptr [esp+0x1c], eax
    popad
9:  ret

part_draw:                                 /* replaces call 0x552c10 (edi = entry copy) */
    mov eax, dword ptr [edi+8]
    xor ecx, ecx
    cmp eax, offset fake_node
    je 1f
    inc ecx
    cmp eax, offset fake_node+0xd0
    jne 0x552c10
1:  push ecx
    call arm_ring
    add esp, 4
    cmp dword ptr [M_RINGSKIP], 0
    jne 0x552c10
    mov eax, dword ptr [M_RINGOVR]
    test eax, eax
    jz 0x552c10
    mov dword ptr [M_RINGOVR], 0
    mov ecx, dword ptr [0x9738f0]
    mov dword ptr [M_PIOLD], ecx
    mov dword ptr [0x9738f0], eax
    pop dword ptr [M_PIRET]
    call 0x552c10
    mov ecx, dword ptr [M_PIOLD]
    mov dword ptr [0x9738f0], ecx
    push dword ptr [M_PIRET]
    ret

    .align 4
fake_entry: .space 32
fake_node:  .space 0x1a0

/* ================= Free Play lineup without an absent P2 =================
   The lineup list (0x879b80) is P1, P2, then the roster. While P2 is not in the select,
   the list is P1 then the roster, and entry 1 is an ordinary (or P3/P4) entry. */
rv_list:                                   /* replaces mov [0x879b84],cx ; mov ebp,2 */
    pushfd
    cmp byte ptr [0x87b6c9], 0
    je 1f
    mov word ptr [0x879b84], cx
    mov ebp, 2
    popfd
    jmp 0x47c59f
1:  mov word ptr [0x879b84], 0xffff
    mov ebp, 1
    popfd
    jmp 0x47c59f
rv_idx1:                                   /* replaces cmp ebx,1 ; jne 47c843 */
    cmp ebx, 1
    jne 0x47c843
    cmp byte ptr [0x87b6c9], 0
    je 0x47c843
    jmp 0x47c7f6
rv_ring2:                                  /* replaces the ring choice @47c978 (ebx != 0) */
    mov eax, 0xa7
    cmp ebx, 1
    jne 1f
    cmp byte ptr [0x87b6c9], 0
    je 1f
    mov eax, 0xa5
1:  mov esi, eax
    jmp 0x47c989

/* ================= P3/P4 corner portraits in menus =================
   Menus draw P1/P2's corner portraits themselves, every frame and in the same place as
   the HUD (0x496650 while a door menu fades in, 0x4967b0, 0x47b160, 0x47b450, 0x497000,
   and the Free Play select 0x47bb70), so P1/P2 never disappear. P3/P4 are drawn right
   after P2's portrait in each of them (under P1/P2, y 0.445). Coming from gameplay,
   where P3/P4 sit in the bottom corners, they cross-fade: the bottom portraits fade out
   while the menu ones fade in (M_XF 0 -> 1 in 0.25 s). While menus draw them, the
   HUD's own P3/P4 pass is skipped. */
menu_corner:                               /* replaces call 0x55b830 (P2's corner) */
    pop dword ptr [M_MCRET]
    call 0x55b830
    pushad
    call corner_tick
    xor ebx, ebx
1:  mov ecx, dword ptr [ebx*4+PARTY+8]
    test ecx, ecx
    jz 3f
    mov eax, 0x3f800000                    /* joined: alpha 1 */
    test byte ptr [ecx+0x1fc], 0x80
    jnz 2f
    push ebx                               /* computer: only while a pad could join it */
    call p34_prompt
    add esp, 4
    test eax, eax
    jz 3f
    mov eax, 0x3f400000                    /* faded 0.75, as P2 */
2:  mov edx, 0xbf466666                    /* x -0.775 */
    test ebx, ebx
    jz 21f
    mov edx, 0x3f466666
21: push eax
    push ebx
    push edx
    movsx eax, word ptr [ecx+0x1064]
    push eax
    call corner_draw
    add esp, 16
3:  inc ebx
    cmp ebx, 2
    jb 1b
    popad
    push dword ptr [M_MCRET]
    ret

sel_corner:                                /* the same in the Free Play select (P2 @47bef9) */
    pop dword ptr [M_MCRET]
    call 0x55b830
    call sel_joinmsgs
    pushad
    mov byte ptr [M_SELDONE], 0
    call fs_corners
    mov byte ptr [M_SELDONE], 1            /* the grid pass (fs_bigloop) skips them */
    popad
    push dword ptr [M_MCRET]
    ret

/* corner_tick: once per menu frame. Menus are drawing P3/P4 (M_MENUAGE = 0, the HUD
   skips its P3/P4 pass); the cross-fade advances by frame time / 0.25 s. */
corner_tick:
    mov dword ptr [M_MENUAGE], 0
    fld dword ptr [0x925018]               /* frame time */
    fmul dword ptr [f_xfrate]
    fadd dword ptr [M_XF]
    fld1
    fcomi st, st(1)                        /* min(1, xf + dt*4) */
    jae 1f
    fstp st(1)
    jmp 2f
1:  fstp st(0)
2:  fstp dword ptr [M_XF]
    ret
f_xfrate: .float 4.0

/* corner_draw(char, x, which, alpha): menu corner portrait at y 0.445 with alpha * xf;
   while the cross-fade runs, also the bottom (HUD) portrait with alpha * (1 - xf) */
corner_draw:
    push eax
    fld dword ptr [esp+20]                 /* alpha */
    fmul dword ptr [M_XF]
    fstp dword ptr [M_CTMP]
    push dword ptr [M_CTMP]                /* alpha */
    push dword ptr [esp+20]                /* which */
    push 0x3ee3d70a                        /* y 0.445, under P1/P2 */
    push dword ptr [esp+24]                /* x */
    push dword ptr [esp+24]                /* char */
    call draw_portrait
    add esp, 20
    fld1
    fcomp dword ptr [M_XF]
    fnstsw ax
    test ah, 0x41                          /* xf >= 1: done */
    jnz 9f
    mov eax, dword ptr [esp+16]            /* which */
    bt dword ptr [M_HUDVIS], eax
    jnc 9f
    fld1
    fsub dword ptr [M_XF]
    fmul dword ptr [esp+20]
    fstp dword ptr [M_CTMP]
    push dword ptr [M_CTMP]
    push dword ptr [esp+20]
    push dword ptr [M_HUDY]                /* where the HUD drew them */
    push dword ptr [esp+24]
    push dword ptr [esp+24]
    call draw_portrait
    add esp, 20
9:  pop eax
    ret
    .popsection
.set M_MCRET,   M_BASE+0x1fc0
.set M_XF,      M_BASE+0x1fc4              /* float: 0 = in the HUD, 1 = in the menu */
.set M_HUDY,    M_BASE+0x1fc8              /* float: y of the HUD's P3/P4 portraits */
.set M_HUDVIS,  M_BASE+0x1fcc              /* bits: P3/P4 shown by the HUD */
.set M_MENUAGE, M_BASE+0x1fd0              /* HUD frames since a menu drew P3/P4 */
.set M_CTMP,    M_BASE+0x1fd4
.set M_SELDONE, M_BASE+0x1fd8
.set M_P2SEL,   M_BASE+0x1fdc
.set M_P2PAD,   M_BASE+0x1fe0
.set M_P2OUT,   M_BASE+0x1fe4              /* 8 bytes */
.set M_PIRET,   M_BASE+0x1fec
.set M_PIOLD,   M_BASE+0x1ff0
.set M_F2FN,    M_BASE+0x1f5c              /* loader: int key_f2(void) */
.set M_SELTXT,  M_BASE+0x1ff4

/* draw_portrait(char, x, y, which, alpha): small portrait (size 0.16) with the P3 (0) or
   P4 (1) ring colour */
draw_portrait:
    pushad
    fsave [M_FPUSAVE]                      /* the caller's x87 stack may be in use */
    mov eax, 0xa7                          /* which < 0: neutral grey ring */
    cmp dword ptr [esp+0x30], 0
    jl 1f
    push dword ptr [esp+0x30]              /* which */
    call arm_ring
    add esp, 4
    cmp dword ptr [M_RINGSKIP], 0
    jne 2f
    mov eax, 0xa6
1:  push 0
    push 1
    push dword ptr [esp+0x3c]              /* alpha */
    push dword ptr [esp+0x40]              /* alpha */
    push eax                               /* ring */
    push 0x3e23d70a                        /* size 0.16 */
    push 0                                 /* z */
    push dword ptr [esp+0x48]              /* y */
    push dword ptr [esp+0x48]              /* x */
    push dword ptr [esp+0x48]              /* char */
    call 0x55b830
    add esp, 0x28
2:  mov dword ptr [M_RINGOVR], 0
    frstor [M_FPUSAVE]
    popad
    ret
.set M_FPUSAVE, M_BASE+0x2900              /* 108 bytes */

/* replaces cmp byte [ebx+0x87b6c8],0 @47bfcc (other player active? if not, the portrait
   goes to the centre). P3/P4 always keep their side positions. */
fs_bigother:
    cmp byte ptr [M_MPASS], 3
    je 1f
    cmp byte ptr [ebx+0x87b6c8], 0
    jmp 0x47bfd3
1:  test esp, esp                          /* ZF = 0: "active" */
    jmp 0x47bfd3

/* big portrait (replaces call 0x55b830 @47c144; ebp = ring): P3/P4 rings red/purple */
fs_bigportrait:
    cmp byte ptr [M_MPASS], 3
    jne 0x55b830
    xor eax, eax
    cmp ebp, 0xa6
    setne al
    push eax
    call arm_ring
    add esp, 4
    cmp dword ptr [M_RINGSKIP], 0
    jne 9f
    pop dword ptr [M_MPRET]
    call 0x55b830
    mov dword ptr [M_RINGOVR], 0
    push dword ptr [M_MPRET]
    ret
9:  ret                                    /* ring not ready: skip this frame */

/* ================= party lists: Free Play picks, Cantina P3/P4 =================
   Party setup 0x41f940 creates one character per entry of a word list (ebp; 0x93d590 or
   0x95107c, -1 terminated). At 0x41fa84 the list is copied to M_PLIST and extended:
   - Free Play: slots 2/3 = the P3/P4 picks (a roster character in slot 2 if only P4).
   - Cantina (world+0x12c = hub area [0x951364]) with only P1/P2: slots 2/3 = Princess
     Leia and Captain Antilles (ids from the name table: [0x7f1864], [0x7f1870]).
   Characters must be loaded: Free Play loads the roster (fp_addpicks), the Cantina its
   load list (hub_list). */
.set M_PLIST,   M_BASE+0x2780+0x40     /* 10 words */
.set LEIA_ID,     0x7f1864
.set ANTILLES_ID, 0x7f1870

/* replaces xor eax,eax ; cmp word [ebp],-1 @41fa84 (edi = world) */
fp_plist:
    pushad
    mov ax, word ptr [ebp]
    cmp ax, 0xffff
    je 9f
    mov word ptr [M_PLIST], ax
    mov ax, word ptr [ebp+2]
    cmp ax, 0xffff
    je 9f
    mov word ptr [M_PLIST+2], ax
    mov ecx, offset M_PLIST+4
    cmp dword ptr [0x93b2a4], 0
    je 5f
    cmp word ptr [M_FSSTASH+S_ACT], 0       /* Free Play */
    je 9f
    cmp byte ptr [M_FSSTASH+S_ACT], 0
    je 1f
    mov ax, word ptr [M_FSSTASH+S_CHAR]
    jmp 2f
1:  call fp_filler
2:  mov word ptr [ecx], ax
    add ecx, 2
    cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    je 7f
    mov ax, word ptr [M_FSSTASH+S_CHAR+2]
    mov word ptr [ecx], ax
    add ecx, 2
    jmp 7f
5:  mov eax, dword ptr [0x951364]          /* Cantina */
    test eax, eax
    jz 9f
    cmp dword ptr [edi+0x12c], eax
    jne 9f
    cmp word ptr [ebp+4], 0xffff
    jne 9f
    mov ax, word ptr [LEIA_ID]
    call plist_add
    mov ax, word ptr [ANTILLES_ID]
    call plist_add
7:  mov word ptr [ecx], 0xffff
    mov dword ptr [esp+8], offset M_PLIST   /* ebp after popad */
    mov dword ptr [esp+0x30], offset M_PLIST /* the routine's copy at [esp+0x10] */
9:  popad
    xor eax, eax
    cmp word ptr [ebp], 0xffff
    jmp 0x41fa8b

/* plist_add: append ax at [ecx] unless -1 or already listed */
plist_add:
    cmp ax, 0xffff
    je 9f
    mov edx, offset M_PLIST
1:  cmp edx, ecx
    jae 2f
    cmp word ptr [edx], ax
    je 9f
    add edx, 2
    jmp 1b
2:  mov word ptr [ecx], ax
    add ecx, 2
9:  ret

/* Cantina load list (replaces mov word [0x93d594],-1 @47aabc, end of 0x47aa30): the
   native list 0x879520 (P1, P2 and the hub's extra characters) has no room for more, so
   it is copied to hub_listbuf with Leia and Antilles added; 0x48af40 points there. */
hub_list:
    mov word ptr [0x93d594], 0xffff
    pushad
    mov esi, 0x879520
    mov edi, offset hub_listbuf
1:  mov eax, dword ptr [esi]
    cmp ax, 0xffff
    je 2f
    mov dword ptr [edi], eax
    add esi, 4
    add edi, 4
    cmp edi, offset hub_listbuf+0x34
    jb 1b
2:  mov ax, word ptr [LEIA_ID]
    call hub_add
    mov ax, word ptr [ANTILLES_ID]
    call hub_add
    mov dword ptr [edi], 0xffff
    popad
    jmp 0x47aac5

hub_add:
    cmp ax, 0xffff
    je 9f
    mov edx, offset hub_listbuf
1:  cmp edx, edi
    jae 2f
    cmp word ptr [edx], ax
    je 9f
    add edx, 4
    jmp 1b
2:  mov word ptr [edi], ax
    mov word ptr [edi+2], 1
    add edi, 4
9:  ret


    .align 4
hub_listbuf:                               /* Cantina load list, {char, 1} entries */
    .long 0xffff
    .fill 15, 4, 0

/* ================= drop-in: P3/P4 stay on their own party slots =================
   After a player joins, if the joined character is off screen (or busy), the drop-in
   looks for a computer-controlled party member in slots 2..7 near the screen and swaps
   the player onto it (0x428419 .. 0x428523, swap 0x487ca0). With P3/P4 that let P3's
   join land on P4's character in the Cantina. Replaces mov ebp,0x93d7f8 @428419:
   P3/P4 (slot [esp+0x10] >= 2) never swap; P1/P2 only consider slots 4..7. */
dropin_cands:
    cmp dword ptr [esp+0x10], 2
    jge 0x428529
    mov ebp, 0x93d800
    jmp 0x42841e

/* ================= loading screen (Cantina): P3/P4 portraits =================
   0x48bd60..0x48bef7 draws P1 (char [0x802bd8], ring 0xa6, -x, y [0x75a21c]) and P2
   ([0x802bdc], 0xa5, +x, y [0x75a218]) while the Cantina loads. A second pass draws
   Princess Leia (P3, red) and Captain Antilles (P4, purple); the four form a 2x2 grid:
   P1 top left, P2 top right, P3 bottom left, P4 bottom right. */
ld_y0: .float 0.30                         /* read by 0x48be7b (P1/P3 y) */
ld_y1: .float 0.30                         /* read by 0x48bec4 (P2/P4 y) */

.set M_LDPASS, M_BASE+0x2760
.set M_LDSAVE, M_BASE+0x2764               /* 2 dwords */
.set M_LDRET,  M_BASE+0x276c
.set M_LDFOUR, M_BASE+0x2761
.set M_LDSHOW, M_BASE+0x2762               /* bits: P3/P4 portraits on the loading screen */
ld_kx: .float 1.5                          /* 2x2: x spread */
ld_ks: .float 0.8                          /* 2x2: portrait size */

/* replaces add esi,edi ; cmp esi,2 ; jl 48bd60 @48bef2 */
ld_loopend:
    add esi, edi
    cmp esi, 2
    jl 0x48bd60
    cmp byte ptr [M_LDPASS], 0
    jne 2f
    cmp word ptr [LEIA_ID], 0xffff
    je 9f
    cmp word ptr [ANTILLES_ID], 0xffff
    je 9f
    push 0                                 /* P3/P4 portraits only for a player who */
    call p34_port_avail                    /* has a pad or could join with one */
    add esp, 4
    mov byte ptr [M_LDSHOW], al
    push 1
    call p34_port_avail
    add esp, 4
    add al, al
    or byte ptr [M_LDSHOW], al
    jz 9f                                  /* neither: the native two-portrait layout */
    mov eax, dword ptr [0x802bd8]
    mov dword ptr [M_LDSAVE], eax
    mov eax, dword ptr [0x802bdc]
    mov dword ptr [M_LDSAVE+4], eax
    movsx eax, word ptr [LEIA_ID]
    mov dword ptr [0x802bd8], eax
    movsx eax, word ptr [ANTILLES_ID]
    mov dword ptr [0x802bdc], eax
    mov dword ptr [ld_y0], 0xbe99999a      /* -0.29 */
    mov dword ptr [ld_y1], 0xbe99999a
    mov byte ptr [M_LDPASS], 1
    mov byte ptr [M_LDFOUR], 1
    xor esi, esi
    jmp 0x48bd60
2:  mov eax, dword ptr [M_LDSAVE]
    mov dword ptr [0x802bd8], eax
    mov eax, dword ptr [M_LDSAVE+4]
    mov dword ptr [0x802bdc], eax
    mov byte ptr [M_LDPASS], 0
    mov dword ptr [ld_y0], 0x3e99999a      /* 0.29 (next frame) */
    mov dword ptr [ld_y1], 0x3e99999a
    jmp 0x48befd
9:  mov byte ptr [M_LDFOUR], 0
    mov dword ptr [ld_y0], 0x3e2a3d70      /* native diagonal: 0.16625 / -0.16625 */
    mov dword ptr [ld_y1], 0xbe2a3d70
    jmp 0x48befd

/* portrait call @48bed6 (esi = 0 left, 1 right): P3/P4 rings red/purple */
ld_portrait:
    cmp byte ptr [M_LDFOUR], 0
    je 1f
    fld dword ptr [esp+8]                  /* x */
    fmul dword ptr [ld_kx]
    fstp dword ptr [esp+8]
    fld dword ptr [esp+0x14]               /* size */
    fmul dword ptr [ld_ks]
    fstp dword ptr [esp+0x14]
1:  cmp byte ptr [M_LDPASS], 0
    je 0x55b830
    movzx eax, byte ptr [M_LDSHOW]
    bt eax, esi
    jnc 9f                                 /* no pad for this player: not shown */
    xor eax, eax
    test esi, esi
    setnz al
    push eax
    call arm_ring
    add esp, 4
    cmp dword ptr [M_RINGOVR], 0           /* draw P3/P4 only with the red/purple ring */
    je 9f
    pop dword ptr [M_LDRET]
    call 0x55b830
    mov dword ptr [M_RINGOVR], 0
    push dword ptr [M_LDRET]
    ret
9:  ret                                    /* ring not ready: skip this frame */

/* ================= select: Exit/Select prompts for P3/P4 =================
   0x4b79a0 draws the corner prompts of players 0/1 (x -+0.67, top y [0x7532b4] 0.7,
   button names for the device of port 0/1). After its call in the grid state (0x47c472),
   the prompt ids are computed again from the P3/P4 arrays (exchanged in) and the
   function runs once more for ports 2/3, 0.3 lower: under P1/P2's prompts. */
pr_y:   .float 0.7                         /* read by 0x4b7a92 */
    .align 8
pr_yd:  .double 0.7                        /* read by 0x4b7b0a (fadd qword) */
.set M_PRPASS, M_BASE+0x2778
.set M_PRADD,  M_BASE+0x277c               /* port offset: 0 or 2 */

/* replaces push ebp ; call 4f48e0 ; push eax ; call 6d67f0 ; push ebp ; call 6d6340 @4b7a80 */
pr_dev:
    mov eax, ebp
    add eax, dword ptr [M_PRADD]
    push eax
    call GETPORTDEV
    push eax
    call 0x6d67f0
    mov eax, ebp
    add eax, dword ptr [M_PRADD]
    push eax
    call 0x6d6340
    jmp 0x4b7a92

/* replaces add esp,0x38 ; pop edi ; pop esi @47c477 (after the prompt call) */
pr_again:
    add esp, 0x38
    cmp byte ptr [M_PRPASS], 0
    jne 2f
    cmp word ptr [M_FSSTASH+S_ACT], 0
    je 9f
    call fs_swap
    mov byte ptr [M_PRPASS], 1
    mov dword ptr [M_PRADD], 2
    mov dword ptr [pr_y], 0x3ecccccd       /* 0.4 */
    mov dword ptr [pr_yd], 0x9999999a      /* 0.4 (double) */
    mov dword ptr [pr_yd+4], 0x3fd99999
    fldz                                   /* x87 state at 0x47c388 */
    jmp 0x47c388
2:  call fs_swap
    mov byte ptr [M_PRPASS], 0
    mov dword ptr [M_PRADD], 0
    mov dword ptr [pr_y], 0x3f333333       /* 0.7 */
    mov dword ptr [pr_yd], 0x66666666      /* 0.7 (double) */
    mov dword ptr [pr_yd+4], 0x3fe66666
9:  pop edi
    pop esi
    jmp 0x47c47c

/* ================= select reveal (states 3/4): P3/P4 like P1/P2 =================
   0x47c763.. draws the list 0x879b80 (P1, P2, then the others; P3/P4's picks are put
   first). P1/P2 fly in from their corner portraits with their rings; the others from
   their grid cell with the brown ring 0xa7. Entries that are a P3/P4 pick fly in from
   the P3/P4 corner portrait and keep the red/purple ring. */

/* rv_which: ebx = list index -> eax = 0 (P3), 1 (P4) or -1 */
rv_which:
    or eax, -1
    cmp ebx, 1
    jl 9f
    jg 0f
    cmp byte ptr [0x87b6c9], 0             /* index 1 is P3/P4's only when P2 is out */
    jne 9f
0:
    push ecx
    mov cx, word ptr [ebx*4+0x879b80]
    cmp byte ptr [M_FSSTASH+S_ACT], 0
    je 1f
    cmp cx, word ptr [M_FSSTASH+S_CHAR]
    jne 1f
    xor eax, eax
    jmp 8f
1:  cmp byte ptr [M_FSSTASH+S_ACT+1], 0
    je 8f
    cmp cx, word ptr [M_FSSTASH+S_CHAR+2]
    jne 8f
    mov eax, 1
8:  pop ecx
9:  ret

/* state 3, other entries (replaces mov esi,0xa7 @47c8b5): start at the P3/P4 corner */
rv_start:
    mov esi, 0xa7
    call rv_which
    test eax, eax
    jl 9f
    mov dword ptr [esp+0x1c], 0xbf466666   /* x -0.775 */
    jz 1f
    mov dword ptr [esp+0x1c], 0x3f466666   /* x +0.775 */
1:  mov dword ptr [esp+0x38], 0x3ee3d70a   /* y 0.445 */
    mov dword ptr [esp+0x30], 0x3e23d70a   /* size 0.16 */
    mov esi, 0xa6
9:  jmp 0x47c8ba

/* portrait call of the list (replaces call 0x55b830 @47ca0e) */
rv_portrait:
    push eax
    call rv_which
    test eax, eax
    jl 8f
    mov dword ptr [esp+0x1c], 0xa6         /* ring argument (esp+4+0x18) */
    push eax
    call arm_ring
    add esp, 4
    pop eax
    cmp dword ptr [M_RINGSKIP], 0
    jne 9f
    pop dword ptr [M_RVRET]
    call 0x55b830
    mov dword ptr [M_RINGOVR], 0
    push dword ptr [M_RVRET]
    ret
8:  pop eax
    jmp 0x55b830
9:  ret
.set M_RVRET, M_BASE+0x27c0+0x20

/* ================= mirrored pads =================
   Some setups present one physical pad as two XInput devices (a real pad and a virtual
   copy, e.g. Steam Input). Both report the same press, so one START joined P3 on one
   device and P4 on the other (party log, 0.22). mirror_mask -> eax = XInput devices
   0..3 without a port whose held buttons (device +0x10) are non-zero and equal to those
   of a device that has a port. */
mirror_mask:
    push ebx
    push ecx
    push edx
    push esi
    push edi
    xor edi, edi                           /* result */
    xor esi, esi                           /* candidate device 0..3 */
1:  imul ebx, esi, 0x84
    mov ebx, dword ptr [ebx+0x917010]
    test ebx, ebx
    jz 5f
    xor ecx, ecx                           /* ports 0..3 */
2:  push ecx
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jl 4f
    cmp eax, esi
    je 5f                                  /* the candidate has a port itself */
    cmp eax, 14
    jae 4f
    imul edx, eax, 0x84
    cmp ebx, dword ptr [edx+0x917010]
    jne 4f
    mov ecx, esi                           /* mirror of a claimed pad */
    mov eax, 1
    shl eax, cl
    or edi, eax
    jmp 5f
4:  inc ecx
    cmp ecx, 4
    jb 2b
5:  inc esi
    cmp esi, 4
    jb 1b
    mov eax, edi
    pop edi
    pop esi
    pop edx
    pop ecx
    pop ebx
    ret

/* join prompt text for computer-controlled P3/P4 corners (hud_swap) */
s_join: .asciz "Press START to join"

/* off-screen join (replaces cmp [esp+0x14],0 ; je 428419 ; jmp 42832e @428401): when the
   joined character is off screen the drop-in would look for another party member to
   swap onto (0x428419). P3/P4 join their own character where it is instead; 0.21-0.23
   skipped the swap without joining, which left the port claimed and the character
   computer-controlled (In-game: Leia kept shooting while P3 pressed buttons). */
dropin_offscreen:
    cmp dword ptr [esp+0x10], 2
    jge 0x42832e
    cmp dword ptr [esp+0x14], 0
    je 0x428419
    jmp 0x42832e

/* ================= door / chapter menus: P3/P4 corner portraits and prompts =================
   The menus a level door opens (0x10 0x47b426, 0x11 0x47b9ec, 0xF 0x4968c0, and
   0x4c780e) draw P1/P2's corner portraits and call the prompt routine 0x4b79a0 with
   14 arguments (P1 active = arg 1, P2 active = arg 8). After the native call, P3/P4's
   corner portraits are drawn under P1/P2's (faded while computer controlled) and the
   prompt routine runs again for ports 2/3, 0.3 lower, with P3/P4's active flags. */
.set M_DPRET, M_BASE+0x27f4
door_prompts:
    pop dword ptr [M_DPRET]
    call 0x4b79a0
    pushad
    /* prompts for joined P3/P4 (their portraits: menu_corner) */
    xor eax, eax
    xor edx, edx
    mov ecx, dword ptr [PARTY+8]
    test ecx, ecx
    jz 4f
    test byte ptr [ecx+0x1fc], 0x80
    setnz al
4:  mov ecx, dword ptr [PARTY+12]
    test ecx, ecx
    jz 5f
    test byte ptr [ecx+0x1fc], 0x80
    setnz dl
5:  mov ecx, eax
    or ecx, edx
    jz 9f
    sub esp, 0x38                          /* copy the 14 arguments */
    lea esi, [esp+0x38+0x20]
    mov edi, esp
    mov ecx, 14
    rep movsd
    mov dword ptr [esp], eax               /* P3 active */
    mov dword ptr [esp+0x1c], edx          /* P4 active */
    mov dword ptr [M_PRADD], 2
    mov dword ptr [pr_y], 0x3ecccccd       /* 0.4 */
    mov dword ptr [pr_yd], 0x9999999a
    mov dword ptr [pr_yd+4], 0x3fd99999
    call 0x4b79a0
    add esp, 0x38
    mov dword ptr [M_PRADD], 0
    mov dword ptr [pr_y], 0x3f333333       /* 0.7 */
    mov dword ptr [pr_yd], 0x66666666
    mov dword ptr [pr_yd+4], 0x3fe66666
9:  popad
    push dword ptr [M_DPRET]
    ret

/* ================= pause / drop-out for P3/P4 =================
   The per-frame controller loop 0x54b0b0 handles START for players 0/1 only
   (0x54b195..0x54b33a): with the game running it opens the pause menu with
   0x55c120(player) (pausing player [0x802af8]); while paused, the pausing player's START
   resumes (0x55c560(1), 0x55c600). The pause menu finds the pausing player's party slot
   through the control entry and drops it out with 0x427cd0(slot, ...), which works for
   any slot. p34_pause(k) applies the same checks to a human P3/P4 (k = 2/3). */
p34_pause:
    pushad
    mov ebx, dword ptr [esp+0x24]          /* player = party slot = control entry */
    mov edi, dword ptr [ebx*4+PARTY]
    test edi, edi
    jz 9f
    test byte ptr [edi+0x1fc], 0x80
    jz 9f
    lea eax, [ebx+ebx*2]
    shl eax, 5
    mov esi, dword ptr [eax+CTRL_POOL]     /* pad */
    test esi, esi
    jz 9f
    mov eax, dword ptr [esi+0x78]          /* buttons pressed this frame */
    and eax, dword ptr [0x802274]          /* START */
    jz 9f
    cmp dword ptr [0x93b328], 0            /* paused: the pausing player resumes */
    je 2f
    mov eax, dword ptr [0x802af8]
    cmp eax, -1
    je 1f
    cmp eax, ebx
    jne 9f
1:  push 1
    call 0x55c560
    add esp, 4
    call 0x55c600
    jmp 9f
2:  cmp dword ptr [0x87658c], 0
    jne 9f
    cmp dword ptr [0x951b80], 0            /* level change pending */
    jne 9f
    fldz
    fcomp dword ptr [0x950780]             /* screen fade */
    fnstsw ax
    test ah, 0x44
    jp 9f
    cmp dword ptr [0x87b4d8], 0
    jne 9f
    fldz
    fcomp dword ptr [0x92505c]
    fnstsw ax
    test ah, 0x5
    jp 9f
    call 0x55f450                          /* world */
    test eax, eax
    jz 9f
    mov ecx, dword ptr [eax+0x128]
    cmp ecx, dword ptr [0x951b88]
    je 9f
    call 0x574e20                          /* no menu open */
    cmp eax, -1
    jne 9f
    mov edx, dword ptr [0x800944]
    imul edx, edx, 0xe0
    cmp word ptr [edx+0x921454], 0xffff
    jne 9f
    cmp dword ptr [0x951c58], 0
    jne 9f
    cmp dword ptr [0x951be0], 0            /* cutscene: only where the game allows */
    je 3f
    push dword ptr [0x951be8]
    call 0x57cf70
    add esp, 4
    test eax, eax
    jz 9f
3:  cmp dword ptr [0x855de0], 0
    jne 9f
    cmp dword ptr [0x921dec], 0
    jne 9f
    fldz
    fcomp dword ptr [0x921df4]
    fnstsw ax
    test ah, 0x5
    jnp 9f
    fldz
    fcomp dword ptr [0x921df0]
    fnstsw ax
    test ah, 0x5
    jnp 9f
    cmp dword ptr [0x925068], 0
    jbe 9f
    push ebx
    call 0x55c120                          /* open the pause menu for player ebx */
    add esp, 4
9:  popad
    ret

/* drop-out allowed (pause menu calls of 0x55f1a0 "P1 and P2 both human", @495929 and
   @495b55): at least two of party slots 0..3 are human, so P3/P4 (and P1/P2 in a game
   with P3/P4) can drop out */
two_humans:
    push ecx
    push edx
    xor eax, eax
    xor ecx, ecx
1:  mov edx, dword ptr [ecx*4+PARTY]
    test edx, edx
    jz 2f
    test byte ptr [edx+0x1fc], 0x80
    jz 2f
    inc eax
2:  inc ecx
    cmp ecx, 4
    jb 1b
    cmp eax, 2
    setae al
    movzx eax, al
    pop edx
    pop ecx
    ret

/* ================= Control Configuration for P3/P4 =================
   The menu object at 0x7f2900 keeps every per-player field 4 wide (devices +0x3c/+0x4c/+0x5c,
   dead zones +0x78/+0x88) and the input engine has 4 per-player binding tables
   (+0x6358 + player*0x80), so the pause menu opens it for 4 players (@493cb6) and LEFT/RIGHT
   walk through columns 0..3. The draw shows two columns at a time: for columns 2/3 the
   per-player fields are swapped with 0/1 for the duration of the draw, the binding lookups
   get +2, and the "Player 1/2" headers become "Player 3/4". */
.set KC,       0x7f2900
.set KC_LBL1,  0x855fec
.set KC_LBL2,  0x855ff0
.set M_KCIN,   M_BASE+0x2980        /* input repeat state for 4 players: f[4], d[4], d[4] */
.set M_KCADD,  M_BASE+0x29b0        /* player offset for the binding lookups: 0 or 2 */
.set M_KCLBL,  M_BASE+0x29b4        /* saved header strings */
.set M_KCSTR,  M_BASE+0x29c0        /* 2 x 32 bytes: "Player 3", "Player 4" */

kc_draw:
    cmp dword ptr [ecx+4], 4
    jne 0x422730
    push esi
    mov esi, ecx
    mov dword ptr [esi+4], 2
    mov dword ptr [M_KCADD], 0
    cmp dword ptr [esi+0x38], 2
    jl 1f
    mov dword ptr [M_KCADD], 2
    sub dword ptr [esi+0x38], 2
    call kc_swap
    mov eax, dword ptr [KC_LBL1]
    mov dword ptr [M_KCLBL], eax
    mov edx, M_KCSTR
    mov cl, '3'
    call kc_label
    mov dword ptr [KC_LBL1], eax
    mov eax, dword ptr [KC_LBL2]
    mov dword ptr [M_KCLBL+4], eax
    mov edx, M_KCSTR+32
    mov cl, '4'
    call kc_label
    mov dword ptr [KC_LBL2], eax
1:  mov ecx, esi
    call 0x422730
    cmp dword ptr [M_KCADD], 0
    je 2f
    call kc_swap
    add dword ptr [esi+0x38], 2
    mov eax, dword ptr [M_KCLBL]
    mov dword ptr [KC_LBL1], eax
    mov eax, dword ptr [M_KCLBL+4]
    mov dword ptr [KC_LBL2], eax
2:  mov dword ptr [M_KCADD], 0
    mov dword ptr [esi+4], 4
    pop esi
    ret

/* swap the per-player fields of columns 0/1 with 2/3 (esi = menu) */
kc_swap:
    push ebx
    xor ebx, ebx
1:  movzx edx, byte ptr [ebx+kc_fields]
    mov eax, dword ptr [esi+edx]
    mov ecx, dword ptr [esi+edx+8]
    mov dword ptr [esi+edx], ecx
    mov dword ptr [esi+edx+8], eax
    inc ebx
    cmp ebx, 10
    jb 1b
    pop ebx
    ret
kc_fields:
    .byte 0x3c, 0x40, 0x4c, 0x50, 0x5c, 0x60, 0x78, 0x7c, 0x88, 0x8c

/* eax = header string -> copy to edx (max 31 chars) with its last digit replaced by cl;
   returns eax = edx (or the original string if it is null) */
kc_label:
    test eax, eax
    jz 9f
    push ebx
    push esi
    push edi
    mov esi, eax
    mov edi, edx
    xor eax, eax                           /* address of the last digit */
    mov ebx, 31
1:  mov ch, byte ptr [esi]
    mov byte ptr [edi], ch
    test ch, ch
    jz 3f
    cmp ch, '0'
    jb 2f
    cmp ch, '9'
    ja 2f
    mov eax, edi
2:  inc esi
    inc edi
    dec ebx
    jnz 1b
    mov byte ptr [edi], 0
3:  test eax, eax
    jz 4f
    mov byte ptr [eax], cl
4:  mov eax, edx
    pop edi
    pop esi
    pop ebx
9:  ret

/* binding lookups in the draw: player argument + M_KCADD */
kc_bindname:                               /* 0x6d9670(dev, action, buf, 1, player, ...) */
    mov eax, dword ptr [M_KCADD]
    add dword ptr [esp+0x14], eax
    jmp 0x6d9670
kc_bound:                                  /* 0x6d68e0(dev, action, 1, player) */
    mov eax, dword ptr [M_KCADD]
    add dword ptr [esp+0x10], eax
    jmp 0x6d68e0

/* update: menu input of players 2/3 comes from their own pads (replaces
   mov edi,[esp+ecx*4+0x1c]; test edi,edi @4218ae, the frame has pads for 0/1 only) */
kc_pad:
    cmp ecx, 2
    jae 1f
    mov edi, dword ptr [esp+ecx*4+0x1c]
    jmp 2f
1:  xor edi, edi
    mov eax, dword ptr [ecx*4+PARTY]
    test eax, eax
    jz 2f
    test byte ptr [eax+0x1fc], 0x80
    jz 2f
    mov edi, dword ptr [ecx*4+M_PADS]
2:  test edi, edi
    jmp 0x4218b4

/* "Change Device" / binding: keyboards stay with players 1/2 (0x6d9510(dev, player) would map
   them to devices 14/15 for players 2/3) */
kc_devmap:
    cmp dword ptr [esp+8], 2
    jl 0x6d9510
    mov eax, dword ptr [esp+4]
    cmp eax, 10
    jl 0x6d9510
    or eax, -1
    ret

/* default layouts: players 2/3 use the presets of players 0/1 */
kc_preset:                                 /* 0x6d95b0(dev, preset player, player) */
    and dword ptr [esp+8], 1
    jmp 0x6d95b0
kc_reset:                                  /* replaces mov edi,[esi+0x38]; xor ebp,ebp @422065 */
    mov edi, dword ptr [esi+0x38]
    and edi, 1
    xor ebp, ebp
    jmp 0x42206a


/* ======================= second code area (+0x3000) ======================= */
    .section .text2, "ax"

/* ================= Cantina shop for P3/P4 =================
   0x47cfaa: the shop opens when party slot 0 or 1 is human and at the counter
   (+0x281 set, state +0x7b5 0xff/0x31/0x32, +0x285 = 0xe). Same test for slots 0..3.
   Replaces mov ecx,[0x93d7f0]; continues at 0x47d020 with esi = 1 if any. */
shop_open:
    xor esi, esi
    xor edx, edx
1:  mov ecx, dword ptr [edx*4+PARTY]
    test ecx, ecx
    jz 2f
    test byte ptr [ecx+0x1fc], 0x80
    jz 2f
    cmp byte ptr [ecx+0x281], 0
    je 2f
    mov al, byte ptr [ecx+0x7b5]
    cmp al, 0xff
    je 3f
    cmp al, 0x31
    je 3f
    cmp al, 0x32
    jne 2f
3:  cmp byte ptr [ecx+0x285], 0xe
    jne 2f
    mov esi, 1
2:  inc edx
    cmp edx, 4
    jb 1b
    jmp 0x47d020

/* 0x4c1080 gathers the shop's menu input from control entries 0/1 (players flagged in the
   menu snapshot 0x87b6c8); entries 2/3 are added for a human P3/P4.
   Replaces cmp ebp,0x925478 ; jl 0x4c10b0 @4c1196. */
shop_input:
    cmp ebp, 0x925478
    jl 0x4c10b0
    cmp ebp, 0x925538
    jge 0x4c11a2
    mov edx, dword ptr [esp+0x10]
    mov edx, dword ptr [edx*4+PARTY]
    test edx, edx
    jz 1f
    test byte ptr [edx+0x1fc], 0x80
    jnz 0x4c10c0
1:  add dword ptr [esp+0x10], 1
    add ebp, 0x60
    jmp shop_input

/* ================= character toggle: not onto P3/P4 in the Cantina =================
   0x487ca0(char, target, ...) moves a player onto a computer-controlled party member
   (the given target, else the first one in slots 0..7). In the Cantina slots 2/3 hold
   P3/P4 (Leia, Antilles): P1 toggling onto Antilles made slot 3 human (In-game 0.28:
   "P4 activated on its own"). There they are skipped. */
tg_target:                                 /* replaces test ebp,ebp; push esi; push edi; je */
    push esi
    push edi
    test ebp, ebp
    jz tg_scan
    call tg_reserved
    test eax, eax
    jnz tg_scan
    jmp 0x487cb0
tg_scan:                                   /* replaces mov ecx,0x93d7f0 and the scan loop */
    mov ecx, PARTY
1:  mov ebp, dword ptr [ecx]
    test ebp, ebp
    jz 3f
    push ecx
    call tg_reserved
    pop ecx
    test eax, eax
    jnz 3f
    mov eax, dword ptr [ebp+0x1fc]
    test al, 1
    jz 3f
    test eax, 0x1000
    jz 3f
    cmp ebp, ebx
    je 3f
    cmp byte ptr [ebp+0x28b], 0
    jne 3f
    test al, al
    js 3f
    test byte ptr [ebp+0x7c5], 2
    jz 0x487d23
3:  add ecx, 4
    cmp ecx, PARTY+0x20
    jb 1b
    jmp 0x487d1c
tg_reserved:                               /* ebp = character -> eax != 0 if P3/P4's in the hub */
    xor eax, eax
    cmp ebp, dword ptr [PARTY+8]
    je 1f
    cmp ebp, dword ptr [PARTY+12]
    jne 2f
1:  push edx
    call 0x570bb0                          /* != 0 in hub levels */
    pop edx
2:  ret

/* ================= cheat codes (Cantina: Enter Code) =================
   0x4c4700 hashes the 6 entered characters (0x650430) and compares them with the hashes
   of the character and extra codes. Replaces add esp,4 ; xor esi,esi @4c4714 (code at
   [esp+0x44] after the add); ours are checked first:
     ALLCHR  unlock and buy every character and vehicle
     STUD1M  +1,000,000 studs */
.set CH_FLAGS,  0x93b288                   /* -> byte per character: 1 owned, 2 available */
.set COLL_LIST, 0x95587c                   /* collection: 0x1c-byte entries, +0 character */
.set COLL_N,    0x955878
.set SHOPGRID,  0x855ef8                   /* shop grid: cells, count +6 */
.set SHOP_BOUGHT, 0x86e4a8                 /* bought bits of the shop's character list */
.set STUDS,     0x86e4dc
cheat_code:
    add esp, 4
    cmp dword ptr [esp+0x44], 0x434c4c41   /* "ALLC" */
    jne 1f
    cmp word ptr [esp+0x48], 0x5248        /* "HR" */
    jne 1f
    call cheat_allchars
    mov eax, offset s_allchars
    jmp 8f
1:  cmp dword ptr [esp+0x44], 0x44555453   /* "STUD" */
    jne 2f
    cmp word ptr [esp+0x48], 0x4d31        /* "1M" */
    jne 2f
    add dword ptr [STUDS], 1000000
    jnc 3f
    mov dword ptr [STUDS], 0xffffffff
3:  mov eax, offset s_studs
    jmp 8f
2:  xor esi, esi
    jmp 0x4c4720
8:  mov dword ptr [0x87ffe8], eax          /* message line, as for a native code */
    mov dword ptr [0x8804a4], 1
    push 0x880444
    push 0x758764                          /* "Shop_BuyCheat" */
    call 0x681f40
    add esp, 8
    jmp 0x4c4900

cheat_allchars:
    pushad
    mov edi, dword ptr [CH_FLAGS]
    test edi, edi
    jz 9f
    mov esi, dword ptr [COLL_LIST]
    mov ecx, dword ptr [COLL_N]
    test esi, esi
    jz 3f
1:  test ecx, ecx
    jle 3f
    movsx eax, word ptr [esi]
    test eax, eax
    jle 2f
    cmp eax, dword ptr [0x93b278]          /* character count */
    jge 2f
    or byte ptr [edi+eax], 0x83            /* owned, available, cheat (0x80: story ones too) */
2:  add esi, 0x1c
    dec ecx
    jmp 1b
3:  movzx ecx, word ptr [SHOPGRID+6]       /* the shop shows them as bought */
    cmp ecx, 100
    jbe 4f
    mov ecx, 100
4:  xor eax, eax
5:  cmp eax, ecx
    jae 6f
    bts dword ptr [SHOP_BOUGHT], eax
    inc eax
    jmp 5b
6:  mov esi, dword ptr [0x880478]          /* the open shop's character list */
    test esi, esi
    jz 9f
    mov ecx, dword ptr [0x8800d8]
7:  test ecx, ecx
    jle 9f
    mov byte ptr [esi+0x63], 1
    add esi, 0x74
    dec ecx
    jmp 7b
9:  popad
    ret

/* 0x594960(char) "owned": characters unlocked by a story chapter only count once the
   chapter is done (0x5949c4); with the cheat bit 0x80 they count as owned too. */
story_owned:                               /* replaces mov ecx,[0x95136c] @5949c4 */
    mov ecx, dword ptr [CH_FLAGS]
    test ecx, ecx
    jz 1f
    test byte ptr [ecx+esi], 0x80
    jz 1f
    pop edi
    mov eax, 1
    pop esi
    ret
1:  mov ecx, dword ptr [0x95136c]
    jmp 0x5949ca

s_allchars: .asciz "All characters and vehicles"
s_studs:    .asciz "1,000,000 studs"

/* ================= Cantina: P1/P2 never end up on P3/P4's characters =================
   In-game 0.29/0.30 (party log): after leaving the shop a keyboard press joined or moved
   P1/P2 onto Leia/Antilles (slot 2/3 human, no device on port 2/3), which then looked
   like P3/P4 had joined and blocked the real P3/P4 join. Each frame, in the Cantina with
   no menu open: if slot k (2/3) is human without a device on port k and is controlled
   through control entry 0/1, that player is moved back to its own character
   (0x487ca0(from, to, 0)). */
hub_guard:
    pushad
    mov ebx, dword ptr [esp+0x24]
    mov esi, dword ptr [ebx*4+PARTY]
    test esi, esi
    jz 9f
    test byte ptr [esi+0x1fc], 0x80
    jz 9f
    push ebx
    call GETPORTDEV
    add esp, 4
    test eax, eax
    jns 9f
    call 0x574e20                          /* no menu open */
    cmp eax, -1
    jne 9f
    call 0x570bb0                          /* Cantina */
    test eax, eax
    jz 9f
    mov eax, dword ptr [esi+0xca4]
    sub eax, CTRL_POOL
    jb 9f
    xor edx, edx
    mov ecx, 0x60
    div ecx
    test edx, edx
    jnz 9f
    cmp eax, 1
    ja 9f
    mov edi, dword ptr [eax*4+PARTY]       /* that player's own character */
    test edi, edi
    jz 9f
    test byte ptr [edi+0x1fc], 0x80
    jnz 9f
    push 0
    push edi
    push esi
    call 0x487ca0
    add esp, 12
9:  popad
    ret


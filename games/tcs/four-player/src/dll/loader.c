/* TCS PC four-player patch - dinput8.dll proxy loader.
 *
 * The game imports DINPUT8.dll, so Windows loads this file from the game
 * folder before the game starts. The Steam executable is still encrypted at
 * that point (SteamStub), so nothing can be patched yet. Two triggers apply
 * the patch once the code is decrypted, whichever comes first:
 *
 *  1. the game's import of GetSystemTimeAsFileTime, which the C runtime calls
 *     first after the original entry point;
 *  2. the game's call to DirectInput8Create (this DLL's own export). The
 *     engine makes it during start-up (0x6DC13C), before the port table and
 *     gamepads that the patch changes are initialised (0x6DC361, 0x6DC392).
 *
 * On the first trigger with decrypted code the loader checks every original
 * byte, allocates the mod area, copies and relocates the hook code and
 * patches the game. Nothing on disk is modified. Progress is written to
 * 4p_mod.log next to this DLL.
 *
 * DirectInput8Create and the COM exports are forwarded to the system
 * dinput8.dll.
 *
 * Freestanding: no C runtime, no Windows SDK headers.
 */
#include "patchdata.h"

typedef unsigned long DWORD;
typedef unsigned char BYTE;
typedef int BOOL;
typedef void *HANDLE;
typedef long HRESULT;
#define WINAPI __stdcall
#define IMPORT __declspec(dllimport)

IMPORT void *WINAPI VirtualAlloc(void *, unsigned, DWORD, DWORD);
IMPORT BOOL WINAPI VirtualFree(void *, unsigned, DWORD);
IMPORT BOOL WINAPI VirtualProtect(void *, unsigned, DWORD, DWORD *);
IMPORT HANDLE WINAPI GetCurrentProcess(void);
IMPORT BOOL WINAPI FlushInstructionCache(HANDLE, const void *, unsigned);
IMPORT unsigned WINAPI GetSystemDirectoryA(char *, unsigned);
IMPORT void *WINAPI LoadLibraryA(const char *);
IMPORT void *WINAPI GetProcAddress(void *, const char *);
IMPORT BOOL WINAPI DisableThreadLibraryCalls(void *);
IMPORT void *WINAPI GetModuleHandleA(const char *);
IMPORT DWORD WINAPI GetModuleFileNameA(void *, char *, DWORD);
IMPORT HANDLE WINAPI CreateFileA(const char *, DWORD, DWORD, void *, DWORD, DWORD, void *);
IMPORT BOOL WINAPI WriteFile(HANDLE, const void *, DWORD, DWORD *, void *);
IMPORT BOOL WINAPI CloseHandle(HANDLE);
IMPORT int WINAPI MessageBoxA(void *, const char *, const char *, unsigned);
IMPORT void *WINAPI AddVectoredExceptionHandler(DWORD, long(WINAPI *)(void *));
IMPORT DWORD WINAPI GetFileAttributesA(const char *);
IMPORT BOOL WINAPI CreateDirectoryA(const char *, void *);
IMPORT BOOL WINAPI ReadFile(HANDLE, void *, DWORD, DWORD *, void *);
IMPORT HANDLE WINAPI FindFirstFileA(const char *, void *);
IMPORT BOOL WINAPI FindNextFileA(HANDLE, void *);
IMPORT BOOL WINAPI FindClose(HANDLE);
IMPORT DWORD WINAPI GetCurrentThreadId(void);
IMPORT void WINAPI Sleep(DWORD);
IMPORT DWORD WINAPI GetTickCount(void);
IMPORT HANDLE WINAPI CreateThread(void *, unsigned, DWORD(WINAPI *)(void *), void *, DWORD, DWORD *);
IMPORT HANDLE WINAPI OpenThread(DWORD, BOOL, DWORD);
IMPORT DWORD WINAPI SuspendThread(HANDLE);
IMPORT DWORD WINAPI ResumeThread(HANDLE);
IMPORT BOOL WINAPI GetThreadContext(HANDLE, void *);
IMPORT short WINAPI GetAsyncKeyState(int);
IMPORT unsigned WINAPI GetRawInputDeviceList(void *, unsigned *, unsigned);
IMPORT unsigned WINAPI GetRawInputDeviceInfoA(HANDLE, unsigned, void *, unsigned *);
IMPORT void *WINAPI GetForegroundWindow(void);
IMPORT DWORD WINAPI GetWindowThreadProcessId(void *, DWORD *);
IMPORT DWORD WINAPI GetCurrentProcessId(void);

#define MEM_COMMIT_RESERVE 0x3000
#define PAGE_RWX 0x40
#define DLL_PROCESS_ATTACH 1
#define INVALID_HANDLE ((HANDLE)-1)

/* ---------- log ---------- */

static char log_path[300];
static int log_lines;

static void log_open(void *inst)
{
    DWORD n = GetModuleFileNameA(inst, log_path, 260);
    const char *f = "4p_mod.log";
    HANDLE h;
    if (n == 0 || n >= 260)
        return;
    while (n && log_path[n - 1] != '\\' && log_path[n - 1] != '/')
        n--;
    while (*f)
        log_path[n++] = *f++;
    log_path[n] = 0;
    h = CreateFileA(log_path, 0x40000000, 1, 0, 2 /* CREATE_ALWAYS */, 0x80, 0);
    if (h == INVALID_HANDLE)
        log_path[0] = 0;
    else
        CloseHandle(h);
}

/* append "text" or "text 0xVALUE" */
static void log_msg(const char *text, int has_val, DWORD val)
{
    char buf[160];
    unsigned n = 0;
    DWORD w;
    HANDLE h;
    if (!log_path[0] || log_lines > 60)
        return;
    log_lines++;
    while (*text && n < 140)
        buf[n++] = *text++;
    if (has_val) {
        int i;
        buf[n++] = ' ';
        buf[n++] = '0';
        buf[n++] = 'x';
        for (i = 7; i >= 0; i--)
            buf[n++] = "0123456789ABCDEF"[(val >> (i * 4)) & 15];
    }
    buf[n++] = '\r';
    buf[n++] = '\n';
    h = CreateFileA(log_path, 4 /* FILE_APPEND_DATA */, 1, 0, 4 /* OPEN_ALWAYS */, 0x80, 0);
    if (h == INVALID_HANDLE)
        return;
    WriteFile(h, buf, n, &w, 0);
    CloseHandle(h);
}

/* ---------- system dinput8 forwarding ---------- */

static void *real_dinput8;

static void *real_proc(const char *name)
{
    if (!real_dinput8) {
        char path[300];
        unsigned n = GetSystemDirectoryA(path, 260);
        const char *f = "\\dinput8.dll";
        if (n == 0 || n > 260)
            return 0;
        while (*f)
            path[n++] = *f++;
        path[n] = 0;
        real_dinput8 = LoadLibraryA(path);
        if (!real_dinput8) {
            log_msg("ERROR: system dinput8.dll not loaded", 0, 0);
            return 0;
        }
    }
    return GetProcAddress(real_dinput8, name);
}

#define E_FAIL ((HRESULT)0x80004005L)

/* ---------- recoloured ring textures ----------
 * The P3/P4 rings are the blue ring drawn with a different texture. ring_tid() makes a
 * managed copy of the blue ring texture with its hue changed (P3 red, P4 purple; HSV
 * value and saturation kept), wraps it in a copy of the game's texture object and
 * registers it in the game's texture table (0x5e5270). Called by the hook code through
 * the pointer at mod area +0x1f40; returns the new texture id or 0.
 * Game texture table: [0x97157c] (id n -> entry n-1), capacity [0x96e570];
 * texture object: +0 width, +4 height, +8 16-byte hash (sharing key), +0x18 refcount,
 * +0x1c/+0x20 pending file data, +0x24 IDirect3DTexture9*. Device: [0x29765cc].
 * Scene unloads (0x5ef880) only free the ids listed by the scene. */

#define TEX_TABLE (*(void ***)0x97157cu)
#define TEX_CAP (*(int *)0x96e570u)
#define D3D_DEVICE (*(void **)0x29765ccu)
#define VT(obj, i) ((*(void ***)(obj))[i])

typedef struct { DWORD Format, Type, Usage, Pool, MSType, MSQuality, Width, Height; } SURFDESC;
typedef struct { int Pitch; BYTE *Bits; } LOCKEDRECT;

static BYTE ring_obj[2][0x40];
static int ring_id[2];

/* hue shift with brightness and saturation kept (HSV): the blue ring becomes red
   (hue 0) for P3 or purple (hue 280) for P4. Integer maths only (no C runtime). */
static void recolour_rgb(unsigned *r, unsigned *g, unsigned *b, int which)
{
    unsigned v = *r, mn = *r, c;
    if (*g > v) v = *g;
    if (*b > v) v = *b;
    if (*g < mn) mn = *g;
    if (*b < mn) mn = *b;
    c = v - mn;                                /* chroma */
    if (!which) {                              /* red: (V, m, m) */
        *r = v;
        *g = mn;
        *b = mn;
    } else {                                   /* purple, hue 280: (m + 2C/3, m, V) */
        *r = mn + (2 * c) / 3;
        *g = mn;
        *b = v;
    }
}

static unsigned short rgb565(unsigned short px, int which)
{
    unsigned r = (px >> 11) & 31, g = (px >> 5) & 63, b = px & 31;
    r = (r << 3) | (r >> 2);                   /* expand to 8 bits */
    g = (g << 2) | (g >> 4);
    b = (b << 3) | (b >> 2);
    recolour_rgb(&r, &g, &b, which);
    return (unsigned short)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
}

static void dxt_colour_block(BYTE *p, int which)
{
    unsigned short c0 = p[0] | p[1] << 8, c1 = p[2] | p[3] << 8;
    unsigned short n0 = rgb565(c0, which), n1 = rgb565(c1, which);
    int was4 = c0 > c1, is4 = n0 > n1;
    if (was4 != is4 && n0 != n1) {
        /* keep the block mode: swap endpoints and remap the 2-bit indices */
        unsigned short t = n0;
        DWORD idx = p[4] | p[5] << 8 | p[6] << 16 | (DWORD)p[7] << 24, out = 0;
        int i;
        n0 = n1;
        n1 = t;
        for (i = 0; i < 16; i++) {
            DWORD v = (idx >> (2 * i)) & 3;
            if (v < 2)
                v ^= 1;            /* 0 <-> 1 */
            else if (was4)
                v ^= 1;            /* 4-colour: 2 <-> 3 (thirds swap); 3-colour keeps 2,3 */
            out |= v << (2 * i);
        }
        p[4] = (BYTE)out;
        p[5] = (BYTE)(out >> 8);
        p[6] = (BYTE)(out >> 16);
        p[7] = (BYTE)(out >> 24);
    }
    if (was4 && n0 == n1)                     /* would turn 3-colour: index 3 = transparent */
        p[4] = p[5] = p[6] = p[7] = 0;         /* all texels the same colour anyway */
    p[0] = (BYTE)n0;
    p[1] = (BYTE)(n0 >> 8);
    p[2] = (BYTE)n1;
    p[3] = (BYTE)(n1 >> 8);
}

static int recolour_rows(BYTE *row, int pitch, int rows, int rowbytes, DWORD fmt, int which)
{
    int y, x;
    for (y = 0; y < rows; y++, row += pitch) {
        if (fmt == 0x31545844u) {                       /* DXT1 */
            for (x = 0; x + 8 <= rowbytes; x += 8)
                dxt_colour_block(row + x, which);
        } else if (fmt == 0x33545844u || fmt == 0x35545844u) { /* DXT3 / DXT5 */
            for (x = 0; x + 16 <= rowbytes; x += 16)
                dxt_colour_block(row + x + 8, which);
        } else if (fmt == 21 || fmt == 22) {            /* A8R8G8B8 / X8R8G8B8: B,G,R,A */
            for (x = 0; x + 4 <= rowbytes; x += 4) {
                unsigned b = row[x], g = row[x + 1], r = row[x + 2];
                recolour_rgb(&r, &g, &b, which);
                row[x] = (BYTE)b;
                row[x + 1] = (BYTE)g;
                row[x + 2] = (BYTE)r;
            }
        } else
            return 0;
    }
    return 1;
}

static void *copy_texture(void *src, int which)
{
    SURFDESC d;
    LOCKEDRECT a, b;
    void *dst = 0;
    DWORD levels, lv;
    void *dev = D3D_DEVICE;
    if (!dev)
        return 0;
    levels = ((DWORD(WINAPI *)(void *))VT(src, 13))(src);
    if (((HRESULT(WINAPI *)(void *, DWORD, SURFDESC *))VT(src, 17))(src, 0, &d) < 0)
        return 0;
    if (((HRESULT(WINAPI *)(void *, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, void **, void *))
             VT(dev, 23))(dev, d.Width, d.Height, levels, 0, d.Format, 1 /* MANAGED */, &dst, 0) < 0)
        return 0;
    for (lv = 0; lv < levels; lv++) {
        SURFDESC ld;
        int dxt = d.Format == 0x31545844u || d.Format == 0x33545844u || d.Format == 0x35545844u;
        int rows, rowbytes, y;
        if (((HRESULT(WINAPI *)(void *, DWORD, SURFDESC *))VT(src, 17))(src, lv, &ld) < 0)
            break;
        if (((HRESULT(WINAPI *)(void *, DWORD, LOCKEDRECT *, void *, DWORD))VT(src, 19))(src, lv, &a, 0, 0x10) < 0)
            break;
        if (((HRESULT(WINAPI *)(void *, DWORD, LOCKEDRECT *, void *, DWORD))VT(dst, 19))(dst, lv, &b, 0, 0) < 0) {
            ((HRESULT(WINAPI *)(void *, DWORD))VT(src, 20))(src, lv);
            break;
        }
        if (dxt) {
            rows = (ld.Height + 3) / 4;
            rowbytes = (ld.Width + 3) / 4 * (d.Format == 0x31545844u ? 8 : 16);
        } else {
            rows = ld.Height;
            rowbytes = ld.Width * 4;
        }
        for (y = 0; y < rows; y++) {
            int x;
            for (x = 0; x < rowbytes; x++)
                b.Bits[y * b.Pitch + x] = a.Bits[y * a.Pitch + x];
        }
        recolour_rows(b.Bits, b.Pitch, rows, rowbytes, d.Format, which);
        ((HRESULT(WINAPI *)(void *, DWORD))VT(dst, 20))(dst, lv);
        ((HRESULT(WINAPI *)(void *, DWORD))VT(src, 20))(src, lv);
    }
    return dst;
}

static int fmt_supported(void *tex)
{
    SURFDESC d;
    if (((HRESULT(WINAPI *)(void *, DWORD, SURFDESC *))VT(tex, 17))(tex, 0, &d) < 0)
        return 0;
    return d.Format == 0x31545844u || d.Format == 0x33545844u || d.Format == 0x35545844u ||
           d.Format == 21 || d.Format == 22;
}

static int __cdecl ring_tid(int blue_tid, int which)
{
    void **table = TEX_TABLE;
    int cap = TEX_CAP, i, freeslot = 0, t;
    BYTE *src;
    void *s, *d;
    static int failed[2];
    which &= 1;
    if (!table || cap <= 0)
        return 0;
    if (ring_id[which] > 0 && ring_id[which] <= cap && table[ring_id[which] - 1] == ring_obj[which])
        return ring_id[which];
    if (failed[which] > 3 || blue_tid <= 0 || blue_tid > cap)
        return 0;
    src = table[blue_tid - 1];
    if (!src || !(s = *(void **)(src + 0x24)) || !fmt_supported(s)) {
        failed[which]++;
        return 0;
    }
    for (i = 0; i < cap; i++)
        if (!table[i]) {
            freeslot = 1;
            break;
        }
    if (!freeslot) {
        failed[which]++;
        return 0;
    }
    d = copy_texture(s, which);
    if (!d) {
        failed[which]++;
        log_msg("ring texture copy failed", 0, 0);
        return 0;
    }
    for (i = 0; i < 0x40; i++)
        ring_obj[which][i] = src[i];
    *(void **)(ring_obj[which] + 0x24) = d;
    *(void **)(ring_obj[which] + 0x1c) = 0;   /* no pending file data */
    *(DWORD *)(ring_obj[which] + 0x20) = 0;
    for (i = 0x08; i < 0x18; i++)              /* texture hash: never matched for sharing */
        ring_obj[which][i] = 0;
    *(int *)(ring_obj[which] + 0x18) = -1;     /* refcount < 0: skipped by 0x5e5390/0x5ef880 */
    t = ((int(__cdecl *)(void *, int))0x5e5270u)(ring_obj[which], 0);
    ring_id[which] = t;
    log_msg(which ? "purple ring texture id" : "red ring texture id", 1, (DWORD)t);
    return t;
}

/* ring_material(blue, which): an engine-created dynamic material (0x5e4d40(1), the way the
 * game makes its own override material at 0x62f970) with the blue ring's settings and the
 * recoloured texture. A copy that shares the blue material's render record (+0x3c) still
 * draws the blue texture, because the record resolves its material by index when it runs;
 * the engine assigns dynamic materials their own record (0x5de440). Returns the material
 * once its record exists, else 0 (the ring is then drawn normally). */
static BYTE *ring_mtl[2];
static int ring_wait[2];

static void *__cdecl ring_material(BYTE *blue, int which)
{
    BYTE *m;
    int tid, i;
    which &= 1;
    if (!blue)
        return 0;
    tid = ring_tid(*(int *)(blue + 0xb8), which);
    if (!tid)
        return 0;
    m = ring_mtl[which];
    if (m && (!(*(unsigned short *)m & 1) || *(int *)(m + 0xb8) != tid))
        m = 0;                                  /* freed or re-registered: make a new one */
    if (!m) {
        BYTE keep[0x2c4];
        m = ((BYTE * (__cdecl *)(int))0x5e4d40u)(1);
        if (!m)
            return 0;
        for (i = 0; i < 0x2c4; i++)
            keep[i] = m[i];
        for (i = 0; i < 0x2c4; i++)
            m[i] = blue[i];
        for (i = 0; i < 2; i++)                 /* pool flags word */
            m[i] = keep[i];
        for (i = 0x28; i < 0x40; i++)           /* pool links, index, render record (0) */
            m[i] = keep[i];
        *(DWORD *)(m + 0x44) &= ~0x800000u;     /* dynamic list, not the no-record pool */
        *(unsigned short *)(m + 0x1f4) = 0;
        *(unsigned short *)(m + 0x1f6) = 0;
        *(unsigned short *)(m + 0x74) = (unsigned short)tid;
        ((void(__cdecl *)(void *))0x5e4b00u)(m); /* finalise: +0xb8 from +0x74 etc. */
        ring_mtl[which] = m;
        log_msg(which ? "purple ring material" : "red ring material", 1, (DWORD)m);
    }
    if (*(void **)(m + 0x3c)) {
        ring_wait[which] = 0;
        return m;
    }
    if (++ring_wait[which] > 120) {             /* no render record for ~2 s: start over */
        ring_wait[which] = 0;
        ring_mtl[which] = 0;
        log_msg("ring material had no render record, recreating", 0, 0);
    }
    return 0;
}

/* ---------- patching ---------- */

static void (WINAPI *orig_gstaft)(void *);
static void __cdecl party_watch(void);
static int __cdecl key_f2(void);
static BYTE *mod_base;
static long WINAPI crash_handler(void *ep);
static int hooked;  /* import replaced */
static int state;   /* 0 = waiting, 1 = done (patched or given up) */

static void write_mem(BYTE *dst, const BYTE *src, unsigned n)
{
    DWORD old, tmp;
    unsigned i;
    VirtualProtect(dst, n, PAGE_RWX, &old);
    for (i = 0; i < n; i++)
        dst[i] = src[i];
    VirtualProtect(dst, n, old, &tmp);
}

static void set_iat(void *value)
{
    write_mem((BYTE *)IAT_HOOK_VA, (const BYTE *)&value, 4);
}

static void hexva(char *p, DWORD v)
{
    int i;
    for (i = 7; i >= 0; i--, v >>= 4)
        p[i] = "0123456789ABCDEF"[v & 15];
}

static int same(const BYTE *a, const BYTE *b, unsigned n)
{
    while (n--)
        if (*a++ != *b++)
            return 0;
    return 1;
}

/* ---------- message pump watch ----------
   The game's main loop calls PeekMessageA (import 0x751238, one caller 0x6DD392) every
   frame, in menus and on loading screens too. The time of each call tells a real
   freeze from a long stay in a menu. */
static volatile DWORD pump_tick, pump_gap_max, main_tid;
static BOOL(WINAPI *orig_peek)(void *, void *, unsigned, unsigned, unsigned);

static BOOL WINAPI hook_peek(void *msg, void *wnd, unsigned a, unsigned b, unsigned rm)
{
    DWORD now = GetTickCount();
    if (pump_tick && now - pump_tick > pump_gap_max)
        pump_gap_max = now - pump_tick;
    pump_tick = now;
    if (!main_tid)
        main_tid = GetCurrentThreadId();
    return orig_peek(msg, wnd, a, b, rm);
}

static void watch_pump(void)
{
    void *f = (void *)hook_peek;
    orig_peek = *(void **)0x751238;
    if (orig_peek)
        write_mem((BYTE *)0x751238, (const BYTE *)&f, 4);
}

/* ---------- XInput check without WMI ----------
   For every device DirectInput lists (keyboards, mice and game controllers), the
   enumeration callback 0x6D9DF0 asks 0x6D5080 whether it is an XInput pad. 0x6D5080
   is the old DirectX sample: it starts COM and runs a WMI query over all Plug and Play
   devices, for each device, every time. On a controller connect/disconnect the game
   re-lists all devices three times, 2 s apart (0x6DE443 / 0x6DAA87), which froze the
   game each time. Same answer from the Raw Input device list: an XInput pad is a HID
   device with "IG_" in its name and the vendor/product id of DirectInput's product
   GUID (Data1 = product << 16 | vendor). Falls back to 0x6D5080 if the list fails. */
static volatile DWORD xi_checks, xi_ms;

static int __cdecl is_xinput(const DWORD *guid_product)
{
    struct { HANDLE dev; DWORD type; } list[128];
    unsigned n = 128, got, i;
    DWORD t0 = GetTickCount();
    int r = 0;
    xi_checks++;
    got = GetRawInputDeviceList(list, &n, sizeof list[0]);
    if (got == 0xFFFFFFFFu) {
        r = ((int(__cdecl *)(const DWORD *))0x6D5080)(guid_product);
        goto done;
    }
    for (i = 0; i < got && !r; i++) {
        DWORD info[8];
        char name[300];
        unsigned sz, k;
        if (list[i].type != 2)                      /* RIM_TYPEHID */
            continue;
        info[0] = sizeof info;
        sz = sizeof info;
        if (GetRawInputDeviceInfoA(list[i].dev, 0x2000000B, info, &sz) == 0xFFFFFFFFu)
            continue;                               /* RIDI_DEVICEINFO */
        if (((info[3] & 0xFFFF) << 16 | (info[2] & 0xFFFF)) != guid_product[0])
            continue;                               /* hid.dwVendorId, dwProductId */
        sz = sizeof name - 1;
        if (GetRawInputDeviceInfoA(list[i].dev, 0x20000007, name, &sz) == 0xFFFFFFFFu)
            continue;                               /* RIDI_DEVICENAME */
        name[sizeof name - 1] = 0;
        for (k = 0; name[k] && name[k + 1] && name[k + 2]; k++)
            if ((name[k] | 0x20) == 'i' && (name[k + 1] | 0x20) == 'g' && name[k + 2] == '_') {
                r = 1;
                break;
            }
    }
done:
    xi_ms += GetTickCount() - t0;
    return r;
}

/* call 0x6D5080 @6D9E11 -> is_xinput */
static void patch_xinput_check(void)
{
    BYTE *at = (BYTE *)0x6D9E11, call[5];
    if (at[0] != 0xE8 || *(DWORD *)(at + 1) != 0x6D5080 - 0x6D9E16) {
        log_msg("XInput check not replaced: unexpected code at", 1, 0x6D9E11);
        return;
    }
    call[0] = 0xE8;
    *(DWORD *)(call + 1) = (DWORD)is_xinput - 0x6D9E16;
    write_mem(at, call, 5);
}

static void try_patch(const char *who)
{
    unsigned i, j;
    BYTE *base;

    if (state)
        return;
    /* still encrypted? the security cookie init must be readable */
    if (!same((const BYTE *)DECRYPT_CHECK_VA, decrypt_check, sizeof decrypt_check)) {
        log_msg(who, 0, 0);
        log_msg("  code still encrypted, waiting", 0, 0);
        return;
    }
    state = 1;
    log_msg(who, 0, 0);
    if (hooked && *(void **)IAT_HOOK_VA != (void *)orig_gstaft)
        set_iat((void *)orig_gstaft);

    for (i = 0; i < N_RECORDS; i++) {
        const struct rec *r = &records[i];
        if (!same((const BYTE *)r->va, patch_orig + r->off, r->len)) {
            static char msg[] = "LEGO Star Wars TCS 4-player mod:\n"
                                "unexpected game code at 0x00000000.\n\n"
                                "This game version is not supported, or the executable is "
                                "already patched. The game will run without the mod.";
            char *p = msg;
            while (*p != '0' || p[1] != 'x')
                p++;
            hexva(p + 2, r->va);
            log_msg("ERROR: unexpected game code at", 1, r->va);
            MessageBoxA(0, msg, "4-player mod", 0x30);
            return;
        }
    }

    /* one zero page in front of the mod area: the game reads the port table with
       index -1 (0x50fb65 with [0x29758f9] = -1), which is harmless in the original
       table inside .data but would fault before an allocation */
    base = VirtualAlloc(0, MOD_SIZE + 0x1000, MEM_COMMIT_RESERVE, PAGE_RWX);
    if (base)
        base += 0x1000;
    if (!base) {
        log_msg("ERROR: VirtualAlloc failed", 0, 0);
        MessageBoxA(0, "LEGO Star Wars TCS 4-player mod:\nout of memory.", "4-player mod", 0x30);
        return;
    }
    for (i = 0; i < MOD_INIT_LEN; i++)
        base[i] = mod_init[i];
    for (i = 0; i < N_BLOB_ABS; i++)
        *(DWORD *)(base + blob_abs[i]) += (DWORD)base;
    for (i = 0; i < N_BLOB_REL; i++)
        *(DWORD *)(base + blob_rel[i]) -= (DWORD)base;
    *(void **)(base + RING_FUNC_OFF) = (void *)ring_material;
    *(void **)(base + WATCH_FUNC_OFF) = (void *)party_watch;
    *(void **)(base + F2_FUNC_OFF) = (void *)key_f2;

    for (i = 0; i < N_RECORDS; i++) {
        const struct rec *r = &records[i];
        BYTE buf[64];
        for (j = 0; j < r->len; j++)
            buf[j] = patch_new[r->off + j];
        for (j = 0; j < r->nfix; j++)
            *(DWORD *)(buf + patch_fix[r->fix + j]) += (DWORD)base;
        write_mem((BYTE *)r->va, buf, r->len);
    }
    patch_xinput_check();
    watch_pump();
    FlushInstructionCache(GetCurrentProcess(), 0, 0);
    mod_base = base;
    AddVectoredExceptionHandler(1, crash_handler);
    log_msg("patched OK, mod area at", 1, (DWORD)base);
}

/* ---------- party watch: log changes of slots 0..3 and ports 0..3 ----------
   one line per change: "party" then per slot "char-id/H(uman)|A(I)/entry" and per port
   the device. Up to 40 lines. */
static int watch_lines;
static DWORD watch_last[12];

static void put_hex2(char *b, unsigned *n, DWORD v, int digits)
{
    while (digits--)
        b[(*n)++] = "0123456789ABCDEF"[(v >> (digits * 4)) & 15];
}

/* ---------- text helpers ---------- */

static unsigned str_cpy(char *d, unsigned n, const char *s)
{
    while (*s)
        d[n++] = *s++;
    d[n] = 0;
    return n;
}

static unsigned put_int(char *d, unsigned n, int v)
{
    char t[12];
    int k = 0;
    do
        t[k++] = (char)('0' + v % 10);
    while (v /= 10);
    while (k)
        d[n++] = t[--k];
    d[n] = 0;
    return n;
}

/* F2 pressed this frame (went down since the last call) while the game has the focus:
   P2 joins the Free Play select with it (the keyboard is shared with P1) */
static int __cdecl key_f2(void)
{
    static int was_down;
    DWORD pid = 0;
    void *w = GetForegroundWindow();
    int down = (GetAsyncKeyState(0x71) & 0x8000) != 0;
    int fresh = down && !was_down;
    was_down = down;
    if (!w)
        return 0;
    GetWindowThreadProcessId(w, &pid);
    return fresh && pid == GetCurrentProcessId();
}

/* ---------- long pauses ----------
   Once per frame (levels and hubs): if the game's message pump stopped for 1 s or
   more since the previous frame (a freeze, not a stay in a menu), that is logged with
   what the mod did during it (XInput checks). Level loads show
   up here only if they freeze. Up to 30 lines. */
static int stall_lines;
static DWORD stall_last;

static void stall_watch(void)
{
    DWORD now = GetTickCount(), gap = pump_gap_max;
    if (stall_last && gap >= 1000 && stall_lines < 30 && log_path[0]) {
        char line[200];
        unsigned n = 0;
        DWORD w;
        HANDLE h;
        stall_lines++;
        n = str_cpy(line, n, "pause ms ");
        n = put_int(line, n, (int)gap);
        n = str_cpy(line, n, ", XInput checks ");
        n = put_int(line, n, (int)xi_checks);
        n = str_cpy(line, n, " (");
        n = put_int(line, n, (int)xi_ms);
        n = str_cpy(line, n, " ms)\r\n");
        h = CreateFileA(log_path, 4, 1, 0, 4, 0x80, 0);
        if (h != INVALID_HANDLE) {
            WriteFile(h, line, n, &w, 0);
            CloseHandle(h);
        }
    }
    stall_last = now;
    pump_gap_max = 0;
    xi_checks = xi_ms = 0;
}

/* ---------- what the game does during a long pause ----------
   A watchdog thread: while the message pump has not run for 1.5 s, every 0.5 s it briefly stops
   the main thread and the loading thread, notes where each one is (instruction
   address and the game's return addresses on its stack) and the last file opened
   through the mod, and writes one line. Up to 150 lines. */
static int sample_lines;

static unsigned sample_thread(char *line, unsigned n, DWORD tid, const char *label)
{
    static DWORD ctx[0xCC / 4 * 4 + 0x200 / 4];   /* CONTEXT (0x2CC bytes) */
    HANDLE t;
    DWORD eip, esp, rets[8];
    int k, nr = 0;
    if (!tid || tid == GetCurrentThreadId())
        return n;
    t = OpenThread(0x0002 | 0x0008, 0, tid);      /* SUSPEND_RESUME | GET_CONTEXT */
    if (!t)
        return n;
    if (SuspendThread(t) == 0xFFFFFFFFu) {
        CloseHandle(t);
        return n;
    }
    ctx[0] = 0x10003;                             /* CONTEXT_i386 | CONTROL | INTEGER */
    if (!GetThreadContext(t, ctx)) {
        ResumeThread(t);
        CloseHandle(t);
        return n;
    }
    eip = ctx[0xB8 / 4];
    esp = ctx[0xC4 / 4];
    for (k = 0; k < 160 && nr < 8; k++) {          /* stack is this process's memory */
        DWORD v = ((DWORD *)esp)[k];
        if (v >= 0x401000 && v < 0x751000)
            rets[nr++] = v;
    }
    ResumeThread(t);
    CloseHandle(t);
    n = str_cpy(line, n, label);
    put_hex2(line, &n, eip, 8);
    for (k = 0; k < nr; k++) {
        line[n++] = ' ';
        put_hex2(line, &n, rets[k], 6);
    }
    line[n] = 0;
    return n;
}

static DWORD WINAPI watchdog(void *arg)
{
    (void)arg;
    for (;;) {
        DWORD gap;
        Sleep(500);
        gap = GetTickCount() - pump_tick;
        if (pump_tick && gap >= 1500 && sample_lines < 150 && log_path[0]) {
            char line[400];
            unsigned n = 0;
            DWORD w;
            HANDLE h;
            sample_lines++;
            n = str_cpy(line, n, "  during pause ms ");
            n = put_int(line, n, (int)gap);
            n = sample_thread(line, n, main_tid, " | main ");
            line[n++] = '\r';
            line[n++] = '\n';
            h = CreateFileA(log_path, 4, 1, 0, 4, 0x80, 0);
            if (h != INVALID_HANDLE) {
                WriteFile(h, line, n, &w, 0);
                CloseHandle(h);
            }
        }
    }
    return 0;
}

static void __cdecl party_watch(void)
{
    DWORD cur[12];
    char line[150];
    unsigned n = 0;
    int k;
    DWORD w;
    HANDLE h;
    {
        static int started;
        if (!started) {
            started = 1;
            CreateThread(0, 0x10000, watchdog, 0, 0, 0);
        }
    }
    stall_watch();
    for (k = 0; k < 4; k++) {
        BYTE *c = ((BYTE **)0x93D7F0)[k];
        cur[k * 2] = c ? *(unsigned short *)(c + 0x1064) | (*(DWORD *)(c + 0x1FC) & 0x80) << 16 : 0xFFFFFFFF;
        cur[k * 2 + 1] = c ? (*(DWORD *)(c + 0xCA4) - 0x9253B0) / 0x60 : 0xFF;
        cur[8 + k] = *(DWORD *)(mod_base + k * 12 + 8) ? *(DWORD *)(mod_base + k * 12 + 4) : 0xFF;
    }
    if (same((BYTE *)cur, (BYTE *)watch_last, sizeof cur) || watch_lines >= 40 || !log_path[0])
        return;
    for (k = 0; k < 12; k++)
        watch_last[k] = cur[k];
    watch_lines++;
    for (k = 0; k < 6; k++)
        line[n++] = "party "[k];
    for (k = 0; k < 4; k++) {
        if (cur[k * 2] == 0xFFFFFFFF) {
            line[n++] = '-';
        } else {
            put_hex2(line, &n, cur[k * 2] & 0xFFFF, 3);
            line[n++] = (cur[k * 2] >> 23) & 1 ? 'H' : 'A';
            put_hex2(line, &n, cur[k * 2 + 1] & 0xFF, 2);
        }
        line[n++] = ' ';
    }
    line[n++] = 'p';
    line[n++] = 'o';
    line[n++] = 'r';
    line[n++] = 't';
    line[n++] = 's';
    for (k = 0; k < 4; k++) {
        line[n++] = ' ';
        put_hex2(line, &n, cur[8 + k] & 0xFF, 2);
    }
    line[n++] = '\r';
    line[n++] = '\n';
    h = CreateFileA(log_path, 4, 1, 0, 4, 0x80, 0);
    if (h == INVALID_HANDLE)
        return;
    WriteFile(h, line, n, &w, 0);
    CloseHandle(h);
}

/* ---------- crash report: first exceptions go to 4p_mod.log ---------- */
static int crash_logs;

static void log_addr(const char *what, DWORD v)
{
    if (mod_base && v >= (DWORD)mod_base && v < (DWORD)mod_base + MOD_SIZE) {
        char t[48];
        unsigned n = 0;
        while (*what && n < 30)
            t[n++] = *what++;
        for (what = " (mod +)"; *what; )
            t[n++] = *what++;
        t[n] = 0;
        log_msg(t, 1, v - (DWORD)mod_base);
    } else
        log_msg(what, 1, v);
}

static long WINAPI crash_handler(void *ep)
{
    DWORD *rec = ((DWORD **)ep)[0];
    BYTE *ctx = ((BYTE **)ep)[1];
    DWORD code = rec[0], *sp;
    int i, n;
    if (code != 0xC0000005 && code != 0xC000001D && code != 0xC0000096 &&
        code != 0xC00000FD && code != 0xC0000094)
        return 0;
    if (crash_logs >= 2)
        return 0;
    crash_logs++;
    log_lines = 0;
    log_msg("EXCEPTION code", 1, code);
    log_addr("  eip", *(DWORD *)(ctx + 0xb8));
    if (rec[4] >= 2)
        log_msg("  fault address", 1, rec[6]);
    log_msg("  eax", 1, *(DWORD *)(ctx + 0xb0));
    log_msg("  ebx", 1, *(DWORD *)(ctx + 0xa4));
    log_msg("  ecx", 1, *(DWORD *)(ctx + 0xac));
    log_msg("  edx", 1, *(DWORD *)(ctx + 0xa8));
    log_msg("  esi", 1, *(DWORD *)(ctx + 0xa0));
    log_msg("  edi", 1, *(DWORD *)(ctx + 0x9c));
    log_msg("  ebp", 1, *(DWORD *)(ctx + 0xb4));
    log_msg("  esp", 1, *(DWORD *)(ctx + 0xc4));
    sp = *(DWORD **)(ctx + 0xc4);
    for (i = 0, n = 0; i < 96 && n < 12; i++) {      /* likely return addresses */
        DWORD v = sp[i];
        if ((v >= 0x401000 && v < 0x751000) ||
            (mod_base && v >= (DWORD)mod_base && v < (DWORD)mod_base + MOD_SIZE)) {
            log_addr("  stack ret?", v);
            n++;
        }
    }
    return 0;  /* EXCEPTION_CONTINUE_SEARCH */
}

static void WINAPI hook_gstaft(void *ft)
{
    try_patch("trigger: GetSystemTimeAsFileTime");
    orig_gstaft(ft);
}

HRESULT WINAPI DirectInput8Create(void *h, DWORD v, void *riid, void **out, void *u)
{
    HRESULT(WINAPI * f)(void *, DWORD, void *, void **, void *);
    try_patch("trigger: DirectInput8Create");
    f = real_proc("DirectInput8Create");
    return f ? f(h, v, riid, out, u) : E_FAIL;
}

HRESULT WINAPI DllCanUnloadNow(void)
{
    HRESULT(WINAPI * f)(void) = real_proc("DllCanUnloadNow");
    return f ? f() : 1; /* S_FALSE */
}

HRESULT WINAPI DllGetClassObject(void *a, void *b, void **c)
{
    HRESULT(WINAPI * f)(void *, void *, void **) = real_proc("DllGetClassObject");
    return f ? f(a, b, c) : E_FAIL;
}

HRESULT WINAPI DllRegisterServer(void)
{
    HRESULT(WINAPI * f)(void) = real_proc("DllRegisterServer");
    return f ? f() : E_FAIL;
}

HRESULT WINAPI DllUnregisterServer(void)
{
    HRESULT(WINAPI * f)(void) = real_proc("DllUnregisterServer");
    return f ? f() : E_FAIL;
}

BOOL WINAPI DllMain(void *inst, DWORD reason, void *reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(inst);
        log_open(inst);
        log_msg("4-player mod " MOD_VERSION " loaded at", 1, (DWORD)inst);
        /* only act inside the analysed game executable */
        if (GetModuleHandleA(0) != (void *)0x400000 ||
            *(const DWORD *)IMAGE_CHECK_VA != IMAGE_CHECK_VALUE) {
            log_msg("not the supported game executable, mod inactive", 0, 0);
            state = 1;
            return 1;
        }
        orig_gstaft = *(void (WINAPI **)(void *))IAT_HOOK_VA;
        log_msg("GetSystemTimeAsFileTime import was", 1, (DWORD)orig_gstaft);
        set_iat((void *)hook_gstaft);
        hooked = 1;
    }
    return 1;
}

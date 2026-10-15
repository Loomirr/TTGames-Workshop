"""DXT5 (BC3) texture encoding and decoding for new or edited textures, with numpy (bundled with Blender).

The originals are single-level DXT3 or DXT5 DDS files with power-of-two sides of at most 512; new
textures are written the same way as DXT5 (texture format 15 in the model file).
"""
import struct

import numpy as np

FORMAT_DXT5 = 15
MAX_SIDE = 512


def dds_file(width, height, payload):
    """A DDS file in the originals' exact header style (single level, linear size, DXT5)."""
    head = struct.pack('<4s31I', b'DDS ', 0x7C, 0x81007, height, width, len(payload), 0, 1, *([0] * 11),
                       0x20, 4, int.from_bytes(b'DXT5', 'little'), 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
    return head + payload


def _blocks(rgba):
    h, w, _ = rgba.shape
    return rgba.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)


def _to565(c):
    c = c.astype(np.uint32)
    return ((c[..., 0] >> 3) << 11) | ((c[..., 1] >> 2) << 5) | (c[..., 2] >> 3)


def _from565(v):
    v = v.astype(np.uint32)
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int32)


def encode_dxt5(rgba):
    """rgba: uint8 array (height, width, 4), top row first; sides multiples of 4. Returns the payload."""
    rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
    h, w, _ = rgba.shape
    if h % 4 or w % 4:
        raise ValueError('Texture sides must be multiples of 4')
    px = _blocks(rgba).astype(np.int32)                     # (n, 16, 4)
    n = px.shape[0]
    # alpha: endpoints are the block's max and min (a0 > a1 selects the 8-value ramp)
    a = px[..., 3]
    a0, a1 = a.max(1), a.min(1)
    ramp = np.stack([a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)], 1)   # (n, 8)
    same = a0 == a1
    aidx = np.abs(a[:, :, None] - ramp[:, None, :]).argmin(2)                           # (n, 16)
    aidx[same] = 0
    abits = np.zeros(n, dtype=np.uint64)
    for i in range(16):
        abits |= aidx[:, i].astype(np.uint64) << np.uint64(3 * i)
    # colour: endpoints along the block's principal axis
    rgb = px[..., :3].astype(np.float64)
    mean = rgb.mean(1, keepdims=True)
    centred = rgb - mean
    cov = np.einsum('nki,nkj->nij', centred, centred)
    axis = np.ones((n, 3))
    for _ in range(8):                                       # power iteration for the main axis
        axis = np.einsum('nij,nj->ni', cov, axis)
        norm = np.linalg.norm(axis, axis=1, keepdims=True)
        axis = np.where(norm > 1e-9, axis / np.maximum(norm, 1e-9), np.array([1.0, 1.0, 1.0]) / 3 ** 0.5)
    proj = np.einsum('nki,ni->nk', centred, axis)
    lo = mean[:, 0] + axis * proj.min(1, keepdims=True)
    hi = mean[:, 0] + axis * proj.max(1, keepdims=True)
    c0 = _to565(np.clip(np.rint(hi), 0, 255))
    c1 = _to565(np.clip(np.rint(lo), 0, 255))
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    p0, p1 = _from565(c0), _from565(c1)
    palette = np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], 1)             # (n, 4, 3)
    dist = ((px[:, :, None, :3] - palette[:, None, :, :]) ** 2).sum(-1)               # (n, 16, 4)
    cidx = dist.argmin(2)
    equal = c0 == c1
    cidx[equal] = 0
    cbits = np.zeros(n, dtype=np.uint32)
    for i in range(16):
        cbits |= cidx[:, i].astype(np.uint32) << np.uint32(2 * i)
    out = np.zeros((n, 16), dtype=np.uint8)
    out[:, 0] = a0
    out[:, 1] = a1
    for k in range(6):
        out[:, 2 + k] = ((abits >> np.uint64(8 * k)) & np.uint64(255)).astype(np.uint8)
    out[:, 8] = c0 & 255
    out[:, 9] = c0 >> 8
    out[:, 10] = c1 & 255
    out[:, 11] = c1 >> 8
    for k in range(4):
        out[:, 12 + k] = (cbits >> np.uint32(8 * k)) & np.uint32(255)
    return out.tobytes()


def decode_dxt5(payload, width, height):
    """DXT5 payload -> uint8 (height, width, 4); used by the checks."""
    blk = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 16)
    n = blk.shape[0]
    a0, a1 = blk[:, 0].astype(np.int32), blk[:, 1].astype(np.int32)
    ramp = np.where((a0 > a1)[:, None],
                    np.stack([a0, a1] + [((7 - k) * a0 + k * a1) // 7 for k in range(1, 7)], 1),
                    np.stack([a0, a1] + [((5 - k) * a0 + k * a1) // 5 for k in range(1, 5)] +
                             [np.zeros(n, np.int32), np.full(n, 255, np.int32)], 1))
    abits = np.zeros(n, dtype=np.uint64)
    for k in range(6):
        abits |= blk[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
    aidx = np.stack([(abits >> np.uint64(3 * i)) & np.uint64(7) for i in range(16)], 1).astype(np.int64)
    alpha = np.take_along_axis(ramp, aidx, 1)
    c0 = blk[:, 8].astype(np.uint32) | (blk[:, 9].astype(np.uint32) << 8)
    c1 = blk[:, 10].astype(np.uint32) | (blk[:, 11].astype(np.uint32) << 8)
    p0, p1 = _from565(c0), _from565(c1)
    four = (c0 > c1)[:, None, None]
    palette = np.where(four, np.stack([p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], 1),
                       np.stack([p0, p1, (p0 + p1) // 2, np.zeros_like(p0)], 1))
    cbits = blk[:, 12:16].copy().view('<u4')[:, 0]
    cidx = np.stack([(cbits >> np.uint32(2 * i)) & np.uint32(3) for i in range(16)], 1).astype(np.int64)
    rgb = np.take_along_axis(palette, cidx[:, :, None].repeat(3, 2), 1)
    px = np.concatenate([rgb, alpha[:, :, None]], 2).astype(np.uint8)
    return px.reshape(height // 4, width // 4, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(height, width, 4)


def power_of_two_size(width, height):
    """The size a texture is written at: each side the nearest power of two, from 4 to MAX_SIDE."""
    def side(x):
        p = 4
        while p * 2 <= MAX_SIDE and abs(p * 2 - x) <= abs(p - x):
            p *= 2
        return p
    return side(width), side(height)

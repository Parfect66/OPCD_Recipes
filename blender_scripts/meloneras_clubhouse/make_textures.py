"""Procedural seamless PBR sets for the Meloneras clubhouse buildings.

Every set is 2048 x 2048, tiles seamlessly, and is written as separately named maps:
    <SET>_ALBEDO.png  <SET>_NORMAL.png (OpenGL, +Y up)  <SET>_METALNESS.png
    <SET>_AO.png      <SET>_DISPLACEMENT.png            <SET>_ROUGHNESS.png (white = rough)
plus <SET>_MAHS.png for HDRP detail arrays (R = Metalness, G = AO, B = Displacement, A = Roughness).

Run:  python make_textures.py <out_dir> [size]
Needs numpy and Pillow only. Seamlessness comes from doing every filter in the frequency
domain or with wrap-around indexing, so nothing has to be cross-faded afterwards.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

N = 2048
RNG = np.random.default_rng(66)
out_dir_global = "."

# Real-world size (metres) that one tile of each set covers. The Blender build script
# reads textures_manifest.json and sizes the UVs to match.
TILE_M = {
    "Meloneras_RoofTile": 2.0,
    "Meloneras_DarkTimber": 2.0,
    "Meloneras_SlateCladding": 2.4,
    "Meloneras_Concrete": 3.0,
    "Meloneras_Paving": 2.4,
    "Meloneras_GreenRender": 3.0,
    "Meloneras_PaintedSteel": 1.0,
    "Meloneras_Glass": 2.0,
    "Meloneras_Hedge": 2.0,
    "Meloneras_Picon": 1.0,
    "Meloneras_GravelLight": 1.0,
}


# ---------------------------------------------------------------- helpers
def grid():
    y, x = np.mgrid[0:N, 0:N].astype(np.float32)
    return x / N, y / N  # 0..1, wraps at 1


def fbm(beta=2.0, lo=2, hi=None, seed=None, aniso=(1.0, 1.0)):
    """Periodic 1/f^beta noise, normalised to 0..1. aniso stretches frequencies."""
    rng = np.random.default_rng(seed) if seed is not None else RNG
    w = rng.standard_normal((N, N)).astype(np.float32)
    F = np.fft.rfft2(w)
    fy = np.fft.fftfreq(N)[:, None] * N * aniso[1]
    fx = np.fft.rfftfreq(N)[None, :] * N * aniso[0]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / f ** (beta / 2.0)
    amp[f < lo] = 0.0
    if hi:
        amp *= np.exp(-((f / hi) ** 2))
    out = np.fft.irfft2(F * amp, s=(N, N)).real
    out -= out.min()
    out /= out.max() + 1e-9
    return out.astype(np.float32)


def blur(a, sigma_px):
    """Periodic gaussian blur (wraps)."""
    fy = np.fft.fftfreq(N)[:, None]
    fx = np.fft.rfftfreq(N)[None, :]
    g = np.exp(-2 * (np.pi * sigma_px) ** 2 * (fx * fx + fy * fy))
    return np.fft.irfft2(np.fft.rfft2(a) * g, s=a.shape).real.astype(np.float32)


def normal_from_height(h, depth_m, tile_m):
    """OpenGL normal map. h is 0..1, depth_m is the physical range of h in metres."""
    px = tile_m / N
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * depth_m / (2 * px)
    drow = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * depth_m / (2 * px)
    # image rows run downwards; OpenGL green points up (+V), so dh/dv = -dh/drow
    nx, ny, nz = -dx, drow, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], -1)
    return (n * 0.5 + 0.5).clip(0, 1)


def ao_from_height(h, strength=1.0):
    """Cheap cavity AO: how far each texel sits below its multi-scale neighbourhood."""
    occ = np.zeros_like(h)
    for s, w in ((4, 0.5), (12, 0.3), (32, 0.2)):
        occ += w * np.clip(blur(h, s) - h, 0, None)
    occ /= occ.max() + 1e-9
    return np.clip(1.0 - strength * occ, 0, 1)


def cells_1d(n, lo, hi, rng):
    """Random cut points 0..1 for n-ish segments, wrapping (last ends at 1)."""
    w = rng.uniform(lo, hi, size=n)
    return np.concatenate([[0], np.cumsum(w / w.sum())])


def srgb(c):
    return np.asarray(c, np.float32)


def save(name, out_dir, albedo, height, rough, metal, depth_m, ao_strength=1.0, alpha=None):
    tile_m = TILE_M[name]
    h = np.clip(height, 0, 1).astype(np.float32)
    nrm = normal_from_height(h, depth_m, tile_m)
    ao = ao_from_height(h, ao_strength)
    metal = np.broadcast_to(np.asarray(metal, np.float32), h.shape)
    rough = np.clip(rough, 0, 1)
    alb = np.clip(albedo * (0.55 + 0.45 * ao[..., None]), 0, 1)  # bake a touch of AO into colour

    def u8(a):
        return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)

    def u16(a):
        return (np.clip(a, 0, 1) * 65535 + 0.5).astype(np.uint16)

    os.makedirs(os.path.join(out_dir, name), exist_ok=True)
    p = lambda m: os.path.join(out_dir, name, f"{name}_{m}.png")
    if alpha is not None:
        Image.fromarray(np.dstack([u8(alb), u8(alpha)]), "RGBA").save(p("ALBEDO"))
    else:
        Image.fromarray(u8(alb), "RGB").save(p("ALBEDO"))
    Image.fromarray(u8(nrm), "RGB").save(p("NORMAL"))
    Image.fromarray(u8(metal), "L").save(p("METALNESS"))
    Image.fromarray(u8(ao), "L").save(p("AO"))
    Image.fromarray(u16(h)).save(p("DISPLACEMENT"))
    Image.fromarray(u8(rough), "L").save(p("ROUGHNESS"))
    Image.fromarray(np.dstack([u8(metal), u8(ao), u8(h), u8(rough)]), "RGBA").save(p("MAHS"))
    print("wrote", name)
    return {"tile_m": tile_m, "depth_m": depth_m, "alpha": alpha is not None}


# ---------------------------------------------------------------- materials
def roof_tile(out):
    """Canarian barrel (teja árabe) clay tiles: alternating caps and channels."""
    x, y = grid()
    cols, rows = 10, 5          # 0.2 m per cap+channel pair, 0.4 m exposed course
    rng = np.random.default_rng(1)
    # per-course small lateral jitter keeps the courses from looking ruled
    row = np.floor(y * rows).astype(int) % rows
    jitter = rng.uniform(-0.04, 0.04, size=rows)[row] / cols
    u = (x + jitter) * cols % 1.0                       # 0..1 across one pair
    v = (y * rows) % 1.0                                # 0..1 down one course (0 = top)
    prof = 0.5 + 0.5 * np.cos(2 * np.pi * u)            # cap at u=0, channel at u=.5
    cap = prof > 0.5
    # each tile rises towards its lower (exposed) edge, then drops onto the next course
    lip = 0.25 * v ** 1.5
    taper = 1.0 - 0.12 * v * cap                        # caps narrow slightly downslope
    h = 0.75 * prof * taper + lip
    # tiny rounded drip edge
    edge = np.clip((v - 0.96) / 0.04, 0, 1)
    h -= 0.25 * edge ** 2
    surf = fbm(2.2, 30, seed=11)
    h = h + 0.04 * surf
    h = (h - h.min()) / (h.max() - h.min())

    # colour: each half-pair (cap or channel) in each course is its own tile
    cell_x = np.floor((x + jitter) * cols * 2 + 0.5).astype(int) % (cols * 2)
    cid = cell_x * 7 + row * 131
    tint = np.random.default_rng(2).uniform(-1, 1, size=(cols * 2 * 7 + rows * 131 + 1, 3))
    base = srgb([0.70, 0.40, 0.28])
    var = tint[cid] * srgb([0.07, 0.05, 0.04])
    fade = fbm(1.8, 2, seed=12)[..., None]
    alb = base + var + (fade - 0.5) * srgb([0.10, 0.07, 0.05])
    # weathering: dark grime in channels and at overlaps, pale bloom on caps
    grime = (1 - prof) * 0.18 + (v < 0.06) * 0.25
    alb *= (1 - 0.35 * grime)[..., None]
    lichen = (fbm(2.0, 40, seed=13) > 0.78) * cap
    alb = np.where(lichen[..., None], alb * 0.7 + srgb([0.55, 0.52, 0.42]) * 0.3, alb)
    alb = alb * (0.9 + 0.2 * surf[..., None])
    rough = 0.72 + 0.18 * fbm(2.0, 20, seed=14) + 0.08 * (1 - prof)
    return save("Meloneras_RoofTile", out, alb, h, rough, 0.0, depth_m=0.06)


def dark_timber(out):
    """Dark-stained horizontal tongue-and-groove cladding."""
    x, y = grid()
    boards = 14                                          # ~143 mm boards over 2 m
    rng = np.random.default_rng(3)
    b = np.floor(y * boards).astype(int) % boards
    v = (y * boards) % 1.0
    # board end joints: 1-2 per board per tile at random x
    joints = rng.uniform(0, 1, size=(boards, 2))
    has2 = rng.uniform(size=boards) > 0.5
    dj = np.minimum(np.abs(((x - joints[b, 0]) + 0.5) % 1 - 0.5),
                    np.where(has2[b], np.abs(((x - joints[b, 1]) + 0.5) % 1 - 0.5), 1))
    seg = (x > joints[b, 0]) ^ (has2[b] & (x > joints[b, 1]))
    groove = np.clip(np.minimum(v, 1 - v) / 0.035, 0, 1) ** 0.6
    joint = np.clip(dj * N / 3.0, 0, 1)
    # grain: noise stretched hard along x, phase shifted per board segment
    grain_a = fbm(1.6, 4, seed=31, aniso=(0.04, 1.0))
    grain_b = fbm(2.0, 30, seed=32, aniso=(0.1, 1.0))
    off = (b * 0.37 + seg * 0.21) % 1.0
    grain = 0.6 * np.take_along_axis(grain_a, ((np.arange(N)[:, None] + (off * N).astype(int)) % N), 0) \
        + 0.4 * grain_b
    h = 0.85 * groove * joint + 0.08 * grain + 0.07 * (np.sin(np.pi * v))
    h = (h - h.min()) / (h.max() - h.min())
    tint = rng.uniform(-1, 1, size=(boards, 2, 3))[b, seg.astype(int)]
    base = srgb([0.32, 0.19, 0.11])
    alb = base * (0.70 + 0.60 * grain[..., None]) + tint * srgb([0.05, 0.035, 0.022])
    sun = fbm(1.6, 2, seed=33)[..., None]                 # uneven UV fade
    alb = alb * (0.9 + 0.2 * sun)
    alb *= (0.45 + 0.55 * (groove * joint))[..., None]
    rough = 0.62 + 0.2 * grain_b + 0.15 * (1 - groove)
    return save("Meloneras_DarkTimber", out, alb, h, rough, 0.0, depth_m=0.012)


def slate_cladding(out):
    """Rusty Canarian slate / quartzite cladding in random ashlar courses."""
    x, y = grid()
    rng = np.random.default_rng(4)
    rcuts = cells_1d(7, 0.6, 1.4, rng)                    # ~7 courses over 2.4 m
    r = np.clip(np.searchsorted(rcuts, y, side="right") - 1, 0, len(rcuts) - 2)
    rv0, rv1 = rcuts[r], rcuts[r + 1]
    nr = len(rcuts) - 1
    stones = []
    for i in range(nr):
        c = cells_1d(rng.integers(3, 6), 0.5, 1.6, rng)
        c = (c + rng.uniform()) % 1.0                     # shift so joints do not line up
        stones.append(np.sort(c[:-1]))
    sid = np.zeros_like(x, dtype=np.int32)
    du = np.ones_like(x)
    for i in range(nr):
        m = r == i
        cs = stones[i]
        xi = x[m]
        k = np.searchsorted(cs, xi, side="right") - 1    # -1 wraps to last stone
        k = k % len(cs)
        left = cs[k]
        right = cs[(k + 1) % len(cs)]
        dl = (xi - left) % 1.0
        dr = (right - xi) % 1.0
        du[m] = np.minimum(dl, dr)
        sid[m] = i * 10 + k
    dv = np.minimum(y - rv0, rv1 - y)
    d = np.minimum(du, dv) * 2.4                           # metres to nearest joint
    joint = np.clip((d - 0.004) / 0.006, 0, 1)
    face = fbm(2.3, 6, seed=41)
    cleft = fbm(1.9, 3, seed=42, aniso=(1.0, 0.4))
    per = np.random.default_rng(5).uniform(-1, 1, size=(nr * 10 + 10, 4))
    tilt = per[sid, 0] * 0.15
    h = joint * (0.6 + 0.25 * cleft + 0.15 * face + tilt * (x - 0.5))
    h = (h - h.min()) / (h.max() - h.min())
    pal = srgb([[0.42, 0.40, 0.38], [0.50, 0.38, 0.28], [0.36, 0.33, 0.31], [0.55, 0.44, 0.34], [0.30, 0.27, 0.25], [0.46, 0.42, 0.37]])
    pick = (np.abs(per[sid, 1]) * len(pal)).astype(int) % len(pal)
    col = pal[pick]
    rust = np.clip((fbm(2.0, 4, seed=43) - 0.45) * 3, 0, 1)[..., None]
    col = col * (1 - 0.5 * rust) + srgb([0.60, 0.33, 0.16]) * 0.5 * rust
    col = col * (0.8 + 0.4 * face[..., None])
    col = col * (0.85 + 0.3 * fbm(2.0, 12, seed=44)[..., None])
    mortar = srgb([0.30, 0.28, 0.26])
    alb = np.where(joint[..., None] > 0.5, col, mortar)
    rough = np.where(joint > 0.5, 0.55 + 0.3 * face, 0.9)
    return save("Meloneras_SlateCladding", out, alb, h, rough, 0.0, depth_m=0.02)


def concrete(out):
    x, y = grid()
    h = 0.6 * fbm(2.2, 3, seed=51) + 0.4 * fbm(1.6, 60, seed=52)
    pores = fbm(1.0, 200, seed=53) > 0.82
    h = h - 0.25 * pores
    h = (h - h.min()) / (h.max() - h.min())
    stain = fbm(1.8, 2, seed=54)[..., None]
    alb = srgb([0.55, 0.54, 0.52]) * (0.85 + 0.25 * stain) * (0.92 + 0.12 * h[..., None])
    rough = 0.82 + 0.12 * fbm(2, 10, seed=55)
    return save("Meloneras_Concrete", out, alb, h, rough, 0.0, depth_m=0.004)


def paving(out):
    """Grey concrete block paving, stretcher bond (terrace and entrance)."""
    x, y = grid()
    rows, cols = 12, 6                                     # 0.2 x 0.4 m blocks over 2.4 m
    r = np.floor(y * rows).astype(int)
    xs = (x * cols + 0.5 * (r % 2)) % cols
    c = np.floor(xs).astype(int)
    du = np.minimum(xs % 1, 1 - xs % 1) / cols
    dv = np.minimum((y * rows) % 1, 1 - (y * rows) % 1) / rows
    d = np.minimum(du, dv) * 2.4
    edge = np.clip((d - 0.003) / 0.01, 0, 1) ** 0.5
    surf = fbm(2.0, 40, seed=61)
    h = edge * (0.8 + 0.2 * surf)
    per = np.random.default_rng(6).uniform(-1, 1, size=(rows * cols + cols, 3))
    pid = r * cols + c
    base = srgb([0.50, 0.49, 0.47]) + per[pid][:, :, :1] * srgb([0.035, 0.033, 0.03])
    dirt = fbm(1.8, 2, seed=62)[..., None]
    alb = base * (0.85 + 0.25 * dirt) * (0.85 + 0.15 * surf[..., None])
    alb = np.where(edge[..., None] > 0.3, alb, srgb([0.25, 0.24, 0.22]))
    rough = np.where(edge > 0.3, 0.78 + 0.15 * surf, 0.95)
    return save("Meloneras_Paving", out, alb, h, rough, 0.0, depth_m=0.01)


def green_render(out):
    """Sage-green painted render (west wall of the clubhouse service block)."""
    stucco = fbm(1.4, 80, seed=71)
    h = 0.7 * stucco + 0.3 * fbm(2.2, 4, seed=72)
    h = (h - h.min()) / (h.max() - h.min())
    patch = fbm(1.8, 2, seed=73)[..., None]
    alb = srgb([0.47, 0.53, 0.42]) * (0.9 + 0.15 * patch) * (0.93 + 0.1 * h[..., None])
    rough = 0.85 + 0.1 * stucco
    return save("Meloneras_GreenRender", out, alb, h, rough, 0.0, depth_m=0.003)


def painted_steel(out):
    """Dark brown powder-coated steel: posts, pergola, glass-screen frames."""
    orange = fbm(1.2, 120, seed=81)
    h = 0.5 + 0.5 * (orange - 0.5) * 0.4
    wear = fbm(2.0, 3, seed=82)[..., None]
    alb = srgb([0.16, 0.11, 0.08]) * (0.92 + 0.15 * wear)
    rough = 0.42 + 0.12 * fbm(2.0, 8, seed=83)
    return save("Meloneras_PaintedSteel", out, alb, h, rough, 0.0, depth_m=0.0005)


def glass(out):
    """Clear terrace screen / window glass. ALBEDO alpha = opacity for a transparent shader."""
    smudge = fbm(1.6, 6, seed=91)
    h = 0.5 + 0.02 * (smudge - 0.5)
    alb = np.broadcast_to(srgb([0.80, 0.86, 0.88]), (N, N, 3)).copy()
    alpha = 0.22 + 0.08 * smudge
    rough = 0.04 + 0.12 * np.clip((smudge - 0.6) * 3, 0, 1)
    return save("Meloneras_Glass", out, alb, h, rough, 0.0, depth_m=0.0002, alpha=alpha)


def worley(cells, seed):
    """Periodic Worley noise: F1, F2 distances (in cell units) and the nearest cell's id."""
    rng = np.random.default_rng(seed)
    jit = rng.uniform(0, 1, size=(cells, cells, 2)).astype(np.float32)
    y, x = np.mgrid[0:N, 0:N].astype(np.float32)
    gx, gy = x * cells / N, y * cells / N
    cx, cy = np.floor(gx).astype(int), np.floor(gy).astype(int)
    f1 = np.full((N, N), 9.0, np.float32); f2 = f1.copy(); cid = np.zeros((N, N), np.int64)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            ix, iy = (cx + ox) % cells, (cy + oy) % cells
            px = cx + ox + jit[iy, ix, 0]
            py = cy + oy + jit[iy, ix, 1]
            d = np.sqrt((gx - px) ** 2 + (gy - py) ** 2)
            closer = d < f1
            f2 = np.where(closer, f1, np.minimum(f2, d))
            cid = np.where(closer, iy * cells + ix, cid)
            f1 = np.where(closer, d, f1)
    return f1, f2, cid


def gravel(name, cells, palette, seed, rough_base):
    f1, f2, cid = worley(cells, seed)
    edge = np.clip((f2 - f1) * 4.0, 0, 1)
    per = np.random.default_rng(seed + 1).uniform(0, 1, size=(cells * cells, 3))
    dome = np.sqrt(np.clip(1 - (f1 / 0.75) ** 2, 0, 1))
    h = 0.55 * dome * edge + 0.3 * per[cid, 0] * edge + 0.15 * fbm(1.5, 200, seed=seed + 2)
    h = (h - h.min()) / (h.max() - h.min())
    pal = srgb(palette)
    col = pal[(per[cid, 1] * len(pal)).astype(int) % len(pal)]
    col = col * (0.75 + 0.5 * per[cid, 2])[..., None] * (0.85 + 0.25 * fbm(1.4, 150, seed=seed + 3))[..., None]
    alb = col * (0.6 + 0.4 * edge)[..., None]
    rough = rough_base + 0.1 * fbm(1.5, 100, seed=seed + 4)
    return save(name, out_dir_global, alb, h, rough, 0.0, depth_m=0.015)


def picon(out):
    """Red volcanic picón gravel (Canarian planters)."""
    global out_dir_global
    out_dir_global = out
    return gravel("Meloneras_Picon", 70, [[0.42, 0.16, 0.10], [0.33, 0.13, 0.09], [0.25, 0.10, 0.08], [0.48, 0.22, 0.13]], 101, 0.85)


def gravel_light(out):
    """Pale limestone gravel for the car park islands."""
    global out_dir_global
    out_dir_global = out
    return gravel("Meloneras_GravelLight", 60, [[0.62, 0.57, 0.49], [0.55, 0.50, 0.43], [0.68, 0.64, 0.56], [0.50, 0.46, 0.40]], 111, 0.8)


def hedge(out):
    """Clipped hedge (hibiscus / pittosporum): dense leaf clumps."""
    f1, f2, cid = worley(90, 121)
    per = np.random.default_rng(122).uniform(0, 1, size=(90 * 90, 3))
    leaf = np.clip(1 - f1 / 0.7, 0, 1) ** 0.7
    clump = fbm(1.8, 6, seed=123)
    h = 0.55 * leaf + 0.45 * clump
    h = (h - h.min()) / (h.max() - h.min())
    pal = srgb([[0.13, 0.26, 0.07], [0.10, 0.21, 0.06], [0.17, 0.30, 0.09], [0.20, 0.29, 0.10]])
    col = pal[(per[cid, 0] * 4).astype(int) % 4] * (0.8 + 0.4 * per[cid, 1])[..., None]
    flowers = (per[cid, 2] > 0.985) & (leaf > 0.3)
    col = np.where(flowers[..., None], srgb([0.62, 0.10, 0.10]), col)
    alb = col * (0.3 + 0.7 * h)[..., None]
    rough = 0.65 + 0.25 * (1 - leaf)
    return save("Meloneras_Hedge", out, alb, h, rough, 0.0, depth_m=0.08, ao_strength=1.4)


def main():
    global N
    out = sys.argv[1] if len(sys.argv) > 1 else "textures"
    if len(sys.argv) > 2:
        N = int(sys.argv[2])
    os.makedirs(out, exist_ok=True)
    man = {}
    only = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
    for fn in (roof_tile, dark_timber, slate_cladding, concrete, paving, green_render, painted_steel, glass,
               picon, gravel_light, hedge):
        if only and fn.__name__ not in only:
            continue
        man[fn.__name__] = fn(out)
    with open(os.path.join(out, "textures_manifest.json"), "w") as f:
        json.dump({"size": N, "sets": man}, f, indent=2)


if __name__ == "__main__":
    main()

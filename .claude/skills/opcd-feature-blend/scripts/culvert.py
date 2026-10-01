"""Culverts for OPCD V4 courses (Blender 4.5).

Workflow (each step is one blender-mcp ``execute_blender_code`` call):

    plan_culvert(...)   read the terrain, propose mouths/inverts/heights   (non-destructive)
    build(id)           create CULVERT_<id>_IN / _OUT objects              (non-destructive)
    backup(id)          .blend copy + orphan mesh copies of affected meshes
    blend(id)           densify, carve, and reshape the surface meshes     (destructive)
    verify(id)          seam / hole / buried-barrel / Unity checks
    finalise(id)        UV + colours + material, join into the Concrete mesh (destructive)
    restore(id)         put every touched mesh back and delete the culvert
    discard_backups(id) once the user has approved the result

A culvert is two *mouth units* (one per end). Each unit is built in a local frame:
origin = invert (lowest point of the opening) on the headwall front face,
+Y = outward (away from the embankment, into the channel), +Z = up, metres.
Library assets must follow the same convention (see references/culvert.md).
"""
import json
import math

import bpy  # noqa: I001 (bpy first so the pip `bpy` module exposes bmesh)
import bmesh
import numpy as np
from mathutils import Matrix, Vector

import opcd_terrain as T

KIT_VERSION = "2026.10.01-3"   # bump on every change; the skill compares it with the installed kit

KINDS = ("pipe", "corrugated", "arch", "box", "underpass", "tunnel")
# Passages carry a path or road THROUGH the embankment: open barrel end to end,
# floor follows the road grade (no minimum fall), level approach cuttings.
PASSAGE_KINDS = ("underpass", "tunnel")
SHAPE = {"underpass": "box", "tunnel": "arch"}   # opening shape used by each passage kind

DEFAULTS = dict(
    wall=0.30,          # headwall and wing wall thickness (m)
    footing=0.30,       # how far walls go below invert (hidden skirt)
    upstand=0.05,       # headwall/wing top stands this much proud of the ground
    cover_min=0.15,     # min concrete above the opening at the headwall
    max_top=1.5,        # max headwall height above the opening soffit
    wing_angle=30.0,    # flare of wing walls from the culvert axis (deg)
    wing_len=None,      # m; default max(1.0, 1.25 * headwall height)
    apron_thk=0.15,
    barrel_depth=T.YARD,  # visible barrel behind the mouth, then capped
    min_fall=0.01,      # 1 in 100
    channel_fade=4.0,   # m over which the channel cut fades into the natural ground
    channel_batter=0.5,  # rise per metre on the channel sides (1:2)
    band=None,          # m; ground-shaping falloff around the feature, default max(2, 2*headwall height)
    max_edge=0.35,      # densify target edge length near the feature
    smooth=4,           # Laplacian passes over the reshaped ground (0 = off)
    search=15.0,        # m either side of the cursor to look for the channel bed
    segments=None,      # opening resolution, default from size
    corr_pitch=0.068,   # 68 x 13 mm corrugation
    corr_depth=0.013,
    mouth_invert="point",  # a mouth given as a point (cursor, empty, coordinates): "point" = invert
                        # at the ground right there, so the structure builds up from it with no
                        # fill in front; "lowest" = lowest ground within 0.75 m or 1.5 m in front
    pad=True,           # level pad in front of each mouth, at apron level (cut and fill)
    pad_len=1.0,        # m the pad runs on past the apron / wing ends
    pad_fade=1.5,       # m over which the pad blends back into the natural ground
    deck=True,          # bridge false dips in the surface over the barrel (fill only)
    deck_reach=6.0,     # m beyond the headwall half-width, each side, to find the undipped road
    deck_step=0.5,      # m sampling step for the deck profile
)

# Named looks on top of DEFAULTS and KIND_DEFAULTS (plan_culvert(..., style="slim")).
# "slim" is the user's preferred look (C35, Meloneras, 1 Oct 2026): a plain headwall with short wings
# and a thin wall; only the opening (arch / box / pipe, any size) changes between culverts.
STYLES = {
    "slim": dict(wing_len=1.5, wing_angle=20.0, wall=0.25, apron_thk=0.1),
}

# Per-kind defaults on top of DEFAULTS (overrides still win).
KIND_DEFAULTS = {
    # precast box under a motorway / road embankment, e.g. a cart-path underpass
    "underpass": dict(wall=0.40, footing=0.50, cover_min=0.50, max_top=2.0, apron_thk=0.25,
                      channel_fade=8.0, band=4.0, search=40.0),
    # road tunnel portal through a hill or high bank: arched opening, tall portal face
    "tunnel": dict(wall=0.60, footing=0.80, cover_min=1.0, max_top=3.0, wing_angle=20.0,
                   apron_thk=0.30, channel_fade=12.0, band=4.0, search=60.0),
}


# ------------------------------------------------------------------ opening shapes

def opening_profile(kind, span, rise, segs):
    """Closed polygon (x, z) of the opening, invert at z=0, centred on x=0."""
    if kind == "underpass":
        h = min(0.30, 0.1 * min(span, rise))
        s = span / 2
        return [(-s, 0.0), (s, 0.0), (s, rise - h), (s - h, rise), (-s + h, rise), (-s, rise - h)]
    kind = SHAPE.get(kind, kind)
    if kind in ("pipe", "corrugated"):
        r = span / 2
        return [(r * math.sin(t), r - r * math.cos(t))
                for t in np.linspace(0, 2 * math.pi, segs, endpoint=False)]
    if kind == "box":
        h = min(0.15, 0.2 * min(span, rise))
        s = span / 2
        return [(-s, 0.0), (s, 0.0), (s, rise - h), (s - h, rise), (-s + h, rise), (-s, rise - h)]
    if kind == "arch":
        r = span / 2
        hs = max(rise - r, 0.0)
        arc = [(r * math.cos(a), hs + r * math.sin(a))
               for a in np.linspace(0, math.pi, max(8, segs // 2) + 1)]
        pts = [(-r, 0.0), (r, 0.0)] + arc
        return [q for i, q in enumerate(pts) if i == 0 or math.dist(q, pts[i - 1]) > 1e-6]
    raise ValueError(f"kind must be one of {KINDS}")


def _ray_poly(c, ang, poly):
    d = np.array([math.cos(ang), math.sin(ang)])
    best = None
    m = len(poly)
    for i in range(m):
        a = np.array(poly[i]); b = np.array(poly[(i + 1) % m])
        e = b - a
        den = d[0] * (-e[1]) - d[1] * (-e[0])
        if abs(den) < 1e-12:
            continue
        rhs = a - c
        t = (rhs[0] * (-e[1]) - rhs[1] * (-e[0])) / den
        s = (d[0] * rhs[1] - d[1] * rhs[0]) / den
        if t > 1e-9 and -1e-9 <= s <= 1 + 1e-9 and (best is None or t < best):
            best = t
    return c + best * d


# ------------------------------------------------------------------ mouth unit mesh

def mouth_dims(kind, span, rise, top_rel, p):
    wall = p["wall"]
    phi = math.radians(p["wing_angle"])
    side = max(0.3, 0.25 * span)
    a = span / 2 + side                      # half-width of apron at the headwall
    half_w = a + wall / math.cos(phi)        # headwall half-width
    wing_len = p["wing_len"] or max(1.0, 1.25 * top_rel)
    v_end = wing_len * math.cos(phi)
    ae = a + wing_len * math.sin(phi)        # half-width of apron at its end
    return dict(a=a, half_w=half_w, phi=phi, wing_len=wing_len, v_end=v_end, ae=ae)


def outline_local(dims, top_rel, wing_end_rel, p):
    """Footprint outline (u, v, ground_target_rel) in the mouth frame, CCW."""
    hw, v_end, ae, phi, L = dims["half_w"], dims["v_end"], dims["ae"], dims["phi"], dims["wing_len"]
    up = p["upstand"]
    wl, wr = wing_end_rel
    ox = hw + L * math.sin(phi)
    return [
        (-hw, -p["wall"], top_rel - up),
        (hw, -p["wall"], top_rel - up),
        (hw, 0.0, top_rel - up),
        (ox, v_end, wr - up),
        (ae, v_end, -0.02),
        (-ae, v_end, -0.02),
        (-ox, v_end, wl - up),
        (-hw, 0.0, top_rel - up),
    ]


def outline_limits(top_rel, wing_end_rel, p):
    """Per outline edge: (bottom_rel, top_rel_start, top_rel_end, should_be_flush).

    Ground anywhere between a wall's bottom and top is sealed; on flush edges it
    should also sit at the wall top minus the upstand.
    """
    f, wl, wr = -p["footing"], wing_end_rel[0], wing_end_rel[1]
    return [(f, top_rel, top_rel, True), (f, top_rel, top_rel, True), (f, top_rel, wr, True),
            (f, wr, wr, False), (-p["apron_thk"], 0.0, 0.0, False), (f, wl, wl, False),
            (f, wl, top_rel, True), (f, top_rel, top_rel, True)]


def build_mouth_bmesh(kind, span, rise, top_rel, wing_end_rel, p, barrel_rise=0.0, cap=True):
    """barrel_rise: floor height change (m) from the back of the headwall to the barrel end
    (passages slope to meet the other portal's half at the midpoint). cap=False leaves the
    barrel open (passages)."""
    wall, foot = p["wall"], p["footing"]
    segs = p["segments"] or int(max(16, min(48, round(math.pi * span / 0.08))))
    d = mouth_dims(kind, span, rise, top_rel, p)
    hw, phi, L, a, ae, v_end = d["half_w"], d["phi"], d["wing_len"], d["a"], d["ae"], d["v_end"]

    prof = opening_profile(kind, span, rise, segs)
    c = np.array([0.0, rise / 2])
    rect = [(-hw, -foot), (hw, -foot), (hw, top_rel), (-hw, top_rel)]
    angs = sorted({round(math.atan2(z - c[1], x - c[0]) % (2 * math.pi), 9) for x, z in prof + rect})
    inner = [_ray_poly(c, t, prof) for t in angs]
    outer = [_ray_poly(c, t, rect) for t in angs]
    n = len(angs)

    bm = bmesh.new()
    groups = []  # (faces, intended normal fn)

    def V(x, y, z):
        return bm.verts.new((float(x), float(y), float(z)))

    F_in = [V(x, 0, z) for x, z in inner]
    F_out = [V(x, 0, z) for x, z in outer]
    B_in = [V(x, -wall, z) for x, z in inner]
    B_out = [V(x, -wall, z) for x, z in outer]

    def ring(A, B):
        return [bm.faces.new((A[i], A[(i + 1) % n], B[(i + 1) % n], B[i])) for i in range(n)]

    groups.append((ring(F_out, F_in), lambda f: Vector((0, 1, 0))))
    groups.append((ring(B_out, B_in), lambda f: Vector((0, -1, 0))))
    rc = Vector((0, 0, (top_rel - foot) / 2))
    groups.append((ring(F_out, B_out),
                   lambda f: Vector((f.calc_center_median().x, 0, f.calc_center_median().z - rc.z))))

    # barrel: through the headwall and on to barrel_depth, then capped
    depth = p["barrel_depth"]
    ys = [0.0, -wall, -depth]
    radial = {0.0: 1.0, -wall: 1.0, -depth: 1.0}
    if kind == "corrugated":
        r = span / 2
        k = 1
        while k * p["corr_pitch"] / 2 < depth - 1e-6:
            y = -k * p["corr_pitch"] / 2
            if abs(y + wall) > 0.01:
                ys.append(y)
                radial[y] = 1.0 + (p["corr_depth"] / r if k % 2 else 0.0)
            k += 1
    ys = sorted(set(ys), reverse=True)
    rings = []
    for y in ys:
        if y == 0.0:
            rings.append(F_in)
        elif y == -wall:
            rings.append(B_in)
        else:
            f = radial.get(y, 1.0)
            dz = barrel_rise * (-y - wall) / max(depth - wall, 1e-6)
            rings.append([V(c[0] + (x - c[0]) * f, y, c[1] + (z - c[1]) * f + dz) for x, z in inner])
    bore = []
    for r0, r1 in zip(rings, rings[1:]):
        bore += ring(r0, r1)
    groups.append((bore, lambda f: Vector((-f.calc_center_median().x, 0, c[1] - f.calc_center_median().z))))
    if cap:
        cap_face = bm.faces.new(rings[-1])
        groups.append(([cap_face], lambda f: Vector((0, 1, 0))))

    # wing walls
    for sgn in (-1, 1):
        wend = wing_end_rel[0] if sgn < 0 else wing_end_rel[1]
        dirv = np.array([sgn * math.sin(phi), math.cos(phi)])
        os_ = np.array([sgn * hw, 0.0])
        is_ = np.array([sgn * (hw - wall / math.cos(phi)), 0.0])
        oe, ie = os_ + L * dirv, is_ + L * dirv
        osb, ost = V(os_[0], os_[1], -foot), V(os_[0], os_[1], top_rel)
        oeb, oet = V(oe[0], oe[1], -foot), V(oe[0], oe[1], wend)
        isb, ist = V(is_[0], is_[1], -foot), V(is_[0], is_[1], top_rel)
        ieb, iet = V(ie[0], ie[1], -foot), V(ie[0], ie[1], wend)
        out_n = Vector((sgn * math.cos(phi), -math.sin(phi), 0))
        groups.append(([bm.faces.new((osb, oeb, oet, ost))], lambda f, n_=out_n: n_))
        groups.append(([bm.faces.new((isb, ieb, iet, ist))], lambda f, n_=-out_n: n_))
        groups.append(([bm.faces.new((ost, oet, iet, ist))], lambda f: Vector((0, 0, 1))))
        groups.append(([bm.faces.new((oeb, ieb, iet, oet))], lambda f: Vector((0, 1, 0))))

    # apron slab between the wings, top at invert
    t = p["apron_thk"]
    a0, a1 = V(-a, 0, 0), V(a, 0, 0)
    a2, a3 = V(ae, v_end, 0), V(-ae, v_end, 0)
    b2, b3 = V(ae, v_end, -t), V(-ae, v_end, -t)
    groups.append(([bm.faces.new((a0, a1, a2, a3))], lambda f: Vector((0, 0, 1))))
    groups.append(([bm.faces.new((a3, a2, b2, b3))], lambda f: Vector((0, 1, 0))))

    bm.normal_update()
    for faces, want in groups:
        flip = [f for f in faces if f.normal.dot(want(f)) < 0]
        if flip:
            bmesh.ops.reverse_faces(bm, faces=flip)
    bm.normal_update()
    return bm, d


# ---------------------------------------------------------------------- planning

def _frame(mouth_xy, invert, outward):
    o = Vector((outward[0], outward[1], 0)).normalized()
    x = Vector((o.y, -o.x, 0))
    m = Matrix.Identity(4)
    m.col[0][:3] = x
    m.col[1][:3] = o
    m.col[2][:3] = (0, 0, 1)
    m.col[3][:3] = (mouth_xy[0], mouth_xy[1], invert)
    return m


def _to_world(frame, u, v, rel=0.0):
    w = frame @ Vector((u, v, rel))
    return w


def _axis_from_bearing(b):
    r = math.radians(b)
    return (math.sin(r), math.cos(r))


def _bearing(d):
    return (math.degrees(math.atan2(d[0], d[1])) + 360) % 360


def suggest_axis(sampler, cx, cy, search, step=5):
    """Direction through the cursor where the ground falls away on BOTH sides."""
    z0 = sampler.height(cx, cy)
    res = []
    for b in range(0, 180, step):
        d = _axis_from_bearing(b)
        lows = []
        for side in (-1, 1):
            zs = [sampler.height(cx + side * s * d[0], cy + side * s * d[1])
                  for s in np.arange(0.5, search, 0.5)]
            zs = [z for z in zs if z is not None]
            lows.append(min(zs) if zs else z0)
        res.append((min(z0 - lows[0], z0 - lows[1]), b))
    res.sort(reverse=True)
    return res[0][1], [(b, round(s, 2)) for s, b in res[:3]]


def _profile(sampler, c, d, s_from, s_to, step=0.25):
    ss = np.arange(s_from, s_to + (step if s_to > s_from else -step) * 0.5, step if s_to > s_from else -step)
    return [(float(s), sampler.height(c[0] + s * d[0], c[1] + s * d[1])) for s in ss]


def _toe_bed_index(prof, step=0.25, steep=-0.05):
    """Index of the channel bed at the toe of the embankment.

    Walk out from the crest; once the ground has been falling steeply and then
    flattens (or starts rising), the bed is the lowest point within 1.5 m of
    that toe. A ditch that keeps falling gently must not drag the invert off
    to the end of the search distance.
    """
    zs = [z for _, z in prof]
    k = max(1, int(round(1.0 / step)))
    descended = False
    for i in range(len(zs) - k):
        slope = (zs[i + k] - zs[i]) / (k * step)
        if slope < steep:
            descended = True
        elif descended:
            j1 = min(len(zs), i + int(1.5 / step) + 1)
            return min(range(i, j1), key=lambda j: zs[j])
    return min(range(len(zs)), key=lambda j: zs[j])


def nearest_path(xy, radius=40.0, window=5.0):
    """Nearest Concrete (cart path) vertex to ``xy`` and the path's local direction.

    Returns dict(name, point, tangent, dist) or None. The tangent is the principal
    axis of the path vertices within ``window`` m of the nearest one.
    """
    best = None
    for ob in T.surface_meshes(("Concrete",)):
        if T.bbox_dist_xy(ob, *xy) > radius:
            continue
        me = ob.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ np.array(ob.matrix_world.to_3x3()).T + np.array(ob.matrix_world.translation)
        d = np.hypot(co[:, 0] - xy[0], co[:, 1] - xy[1])
        i = int(np.argmin(d))
        if d[i] <= radius and (best is None or d[i] < best[0]):
            best = (d[i], ob.name, co[:, :2], i)
    if best is None:
        return None
    dist, name, xy2, i = best
    P = xy2[i]
    local = xy2[np.hypot(*(xy2 - P).T) <= window]
    if len(local) >= 3:
        _, _, vt = np.linalg.svd(local - local.mean(0))
        t = vt[0]
    else:
        t = np.array([1.0, 0.0])
    return dict(name=name, point=P, tangent=t / np.linalg.norm(t), dist=float(dist))


# ------------------------------------------------------------------ deck (dip bridging)
#
# OPCD meshes are conformed to the terrain imported from Unity, and the heightmap often
# carries a false notch where the watercourse or road runs through the embankment. The
# path / road / motorway over the feature then dips over the barrel. The deck step bridges
# that notch: across the strip between the two headwall back faces, the surface is raised
# (never lowered) to a straight chord between the highest untouched points either side.

def plan_deck(plan, sampler):
    """Profile of the deck chord over the barrel, from the untouched surface. Stored in the plan."""
    p = plan["params"]
    if not p.get("deck", True):
        return None
    a_in = np.array(plan["ends"]["in"]["mouth"], float)
    a_out = np.array(plan["ends"]["out"]["mouth"], float)
    L = float(np.linalg.norm(a_out - a_in))
    s0, s1 = p["wall"], L - p["wall"]
    if s1 - s0 < 2 * p["deck_step"]:
        return None
    ax = (a_out - a_in) / L
    nx = np.array([ax[1], -ax[0]])
    hw = max(mouth_dims(plan["kind"], plan["span"], plan["rise"], e["top_rel"], p)["half_w"]
             for e in plan["ends"].values())
    umax = hw + p["deck_reach"]
    us = np.arange(p["deck_step"], umax + 1e-6, p["deck_step"])
    rows = []
    for sk in np.linspace(s0, s1, max(3, int((s1 - s0) / p["deck_step"]) + 1)):
        base = a_in + sk * ax
        zc = sampler.height(*base)
        side = []
        for sgn in (-1, 1):
            best = (0.0, zc)
            for u in us:
                z = sampler.height(*(base + sgn * u * nx))
                if z is not None and (best[1] is None or z > best[1]):
                    best = (float(u), z)
            side.append(best)
        (uL, zL), (uR, zR) = side
        if zL is None or zR is None:
            continue
        chord0 = zL + (zR - zL) * uL / max(uL + uR, 1e-6)
        rows.append((float(sk), uL, float(zL), uR, float(zR),
                     float(max(chord0 - zc, 0.0)) if zc is not None else 0.0))
    if not rows:
        return None
    r = np.array(rows)
    # Full strength right up to the headwall back faces (a path next to a mouth must be
    # fully bridged, or the low headwall sized from the dip pulls the path down); only
    # BESIDE the headwalls (|u| > half-width) does it fade out over `ramp` past the back face.
    return dict(origin=a_in.tolist(), axis=ax.tolist(), normal=nx.tolist(), s0=s0, s1=s1,
                ramp=1.0, half_w=float(hw), s=r[:, 0].tolist(), uL=r[:, 1].tolist(),
                zL=r[:, 2].tolist(), uR=r[:, 3].tolist(), zR=r[:, 4].tolist(),
                centre_fill_max_m=round(float(r[:, 5].max()), 3), half_width_m=round(float(umax), 2))


def deck_field(deck):
    """f(xy (N,2), z (N,)) -> new z: raise to the chord inside the deck strip (fill only)."""
    o, ax, nx = (np.array(deck[k]) for k in ("origin", "axis", "normal"))
    S = np.array(deck["s"])
    cols = {k: np.array(deck[k]) for k in ("uL", "zL", "uR", "zR")}

    def f(xy, z):
        rel = xy - o
        s_, u = rel @ ax, rel @ nx
        uL, zL, uR, zR = (np.interp(s_, S, cols[k]) for k in ("uL", "zL", "uR", "zR"))
        chord = zL + (zR - zL) * (u + uL) / np.maximum(uL + uR, 1e-6)
        across = (u >= -uL) & (u <= uR)
        # distance past the nearer back face (<= 0 inside the zone between them)
        past = np.maximum(deck["s0"] - s_, s_ - deck["s1"])
        ramp = deck.get("ramp", 1.0)
        beside = np.abs(u) > deck.get("half_w", 0.0) + 0.1
        w = np.where(past <= 0.0, 1.0,
                     np.where(beside, T.smoothstep(1.0 - past / ramp), 0.0))
        w = np.where(across, w, 0.0)
        return z + w * np.maximum(chord - z, 0.0)
    return f


def deck_height(deck, x, y, z):
    """Deck-corrected height of one point (z from the untouched surface)."""
    if deck is None or z is None:
        return z
    return float(deck_field(deck)(np.array([[x, y]]), np.array([z]))[0])


def plan_culvert(kind="pipe", span=0.6, rise=None, bearing=None, inlet=None, outlet=None,
                 centre=None, flow=None, asset=None, cursor_is="crossing", name=None, **overrides):
    """Read the terrain and propose a culvert. Non-destructive.

    span/rise in metres (use T.inch(24), T.mm(600), T.yd(1) ...).
    bearing: culvert axis in degrees (0 = +Y, 90 = +X), direction of flow.
    inlet/outlet: (x, y) or the name of an empty; overrides auto mouth finding.
    centre: (x, y); default = 3D cursor.
    cursor_is: what the cursor (or ``centre``) marks -
        "crossing": the middle of the bank/path the culvert passes under;
        "outlet" / "inlet": that mouth. The culvert then runs square across the
        nearest cart path (or along ``bearing``) and the other mouth is found on
        the far side.
        "portal" (passages; same as "inlet"): one portal. With the cursor on a
        path (within 3 m of Concrete) the passage runs ALONG that path into the
        rising ground; otherwise square across the nearest path.
    kind "underpass" / "tunnel" are passages: see PASSAGE_KINDS.
    flow: None (auto: water runs from the higher bed), or "as_bearing".
    asset: optional ("/path/lib.blend", "ObjectName") to use a library mouth unit.
    """
    if cursor_is not in ("crossing", "inlet", "outlet", "portal"):
        raise ValueError('cursor_is must be "crossing", "inlet", "outlet" or "portal"')
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if cursor_is == "portal":
        cursor_is = "inlet"
    passage = kind in PASSAGE_KINDS
    style = overrides.pop("style", None)
    if style is not None and style not in STYLES:
        raise ValueError(f"style must be one of {tuple(STYLES)}")
    p = dict(DEFAULTS); p.update(KIND_DEFAULTS.get(kind, {})); p.update(STYLES.get(style, {})); p.update(overrides)
    rise = rise or (span if kind in ("pipe", "corrugated") else
                    span * 0.75 if kind in ("box", "underpass") else
                    span * 0.7 if kind == "tunnel" else span * 0.8)
    if SHAPE.get(kind, kind) == "arch" and rise < span / 2:
        rise = span / 2
    T.ensure_object_mode()
    surfaces = T.surface_meshes(exclude=T.WATER_KEYWORDS)
    sampler = T.HeightSampler(surfaces)
    cur = bpy.context.scene.cursor.location
    c = centre or (cur.x, cur.y)
    warnings = []

    def _pt(v):
        if v is None:
            return None
        if isinstance(v, str):
            ob = bpy.data.objects[v]
            return (ob.location.x, ob.location.y)
        return (float(v[0]), float(v[1]))

    pin, pout = _pt(inlet), _pt(outlet)
    if pin is None and pout is None and "CULVERT_IN" in bpy.data.objects and "CULVERT_OUT" in bpy.data.objects:
        pin, pout = _pt("CULVERT_IN"), _pt("CULVERT_OUT")

    axis_note = None
    mouth_mode = cursor_is != "crossing" and not (pin and pout)
    if mouth_mode:
        m = np.array(c, float)
        path = nearest_path(tuple(m))
        if bearing is not None:
            d = _axis_from_bearing(bearing)
            axis_note = "from given bearing"
        elif passage and path is not None and path["dist"] <= 3.0:
            # cursor on the path at a portal: run along the path, into the rising ground
            t = np.array(path["tangent"])
            rises = []
            for sgn in (1, -1):
                zs = [z for _, z in _profile(sampler, tuple(m), tuple(sgn * t), 0.0, p["search"], 1.0)
                      if z is not None]
                rises.append(max(zs) if zs else -1e9)
            t = t if rises[0] >= rises[1] else -t
            d = tuple(t if cursor_is == "inlet" else -t)
            axis_note = (f"AUTO - along {path['name']} from the cursor into the rising ground; "
                         f"confirm with the user")
            path = None   # the far portal is found from the crest below, not the path edge
        elif path is not None:
            t = path["tangent"]
            n = np.array([-t[1], t[0]])
            if (m - path["point"]) @ n < 0:
                n = -n                       # n points from the path towards the cursor
            d = tuple(n if cursor_is == "outlet" else -n)
            axis_note = (f"AUTO - square across {path['name']} ({T.fmt_len(path['dist'])} from the "
                         f"cursor); confirm with the user")
        else:
            raise RuntimeError("No Concrete mesh within 40 m of the cursor - give a bearing.")
        dv = np.array(d)
        if passage and path is None and bearing is None:
            # crossing centre = crest of the ground ahead of the portal
            into = dv if cursor_is == "inlet" else -dv
            prof = [(s_, z) for s_, z in _profile(sampler, tuple(m), tuple(into), 0.0, p["search"], 0.5)
                    if z is not None]
            s_crest = max(prof, key=lambda q: q[1])[0] if prof else 3.0
            ref = m + into * max(s_crest, 1.0)
        else:
            ref = path["point"] if path is not None else m - dv * (1 if cursor_is == "outlet" else -1) * 3.0
        c = tuple(m + ((ref - m) @ dv) * dv)  # on the axis, level with the path edge / crest
        if cursor_is == "outlet":
            pout = tuple(m)
        else:
            pin = tuple(m)
    elif pin and pout:
        dv = np.array(pout) - np.array(pin)
        d = tuple(dv / np.linalg.norm(dv))
        c = tuple((np.array(pin) + np.array(pout)) / 2)
        axis_note = "from inlet/outlet points"
    elif bearing is not None:
        d = _axis_from_bearing(bearing)
        axis_note = "from given bearing"
    else:
        b, cands = suggest_axis(sampler, c[0], c[1], p["search"])
        d = _axis_from_bearing(b)
        axis_note = f"AUTO - ground falls both ways along bearing {b} deg (candidates {cands}); confirm with the user"

    zc = sampler.height(*c)
    if zc is None:
        raise RuntimeError("No surface mesh under the culvert centre / cursor.")
    need = rise + p["cover_min"]

    def find_end(side, given):
        """side -1 = towards -d, +1 = towards +d. Returns dict for the mouth."""
        if given is not None:
            s_m = float((np.array(given) - np.array(c)) @ np.array(d))
            inv = sampler.height(*given) if p.get("mouth_invert", "point") == "point" else None
            if inv is None:
                # "lowest": lowest ground at the mouth or up to 1.5 m in front of it, so a
                # point dropped on the foot of the bank still gets the channel level
                zs = [sampler.min_in_radius(*given)]
                zs += [z for _, z in _profile(sampler, given, (side * d[0], side * d[1]), 0.0, 1.5)]
                zs = [z for z in zs if z is not None]
                inv = min(zs) if zs else None
            if inv is None:
                raise RuntimeError(f"No surface mesh under the {'inlet' if side < 0 else 'outlet'} point.")
            return dict(s=s_m, invert=inv, bed_s=s_m, note="given point")
        prof = [(s, z) for s, z in _profile(sampler, c, d, 0.0, side * p["search"]) if z is not None]
        if not prof:
            raise RuntimeError("Terrain profile along the axis is empty.")
        i_low = _toe_bed_index(prof)
        s_low, z_low = prof[i_low]
        # walk from the bed back towards the centre until the bank is high enough
        s_back = None
        for s, z in reversed(prof[:i_low + 1]):
            if z >= z_low + need:
                s_back = s
                break
        note = "auto"
        if s_back is None:
            # bank too low: put the headwall on the highest ground between the bed and
            # the crossing, but keep it clear of the crossing so the two ends (and their
            # barrels) never overlap; the blend then fills the bank up to the headwall
            min_half = max(1.5, 1.5 * span) + p["barrel_depth"]
            cands = [(s, z) for s, z in prof[:i_low + 1] if abs(s) >= min_half] or prof[i_low:i_low + 1]
            s_back = max(cands, key=lambda t: t[1])[0]
            note = "bank lower than opening + cover: headwall will need fill over it"
            warnings.append(f"{'upstream' if side < 0 else 'downstream'} bank is too low for "
                            f"{T.fmt_len(rise)} opening + cover - terrain will be raised")
        s_front = s_back + side * p["wall"]
        return dict(s=s_front, invert=z_low, bed_s=s_low, note=note)

    ends = {}
    raw = {-1: find_end(-1, pin), 1: find_end(1, pout)}
    # flow: water runs from the higher bed to the lower (passages: no flow, keep the order)
    if passage or flow == "as_bearing" or (pin and pout) or mouth_mode:
        up, dn = -1, 1
        if not passage and raw[-1]["invert"] < raw[1]["invert"]:
            warnings.append(f"inlet bed is {raw[1]['invert'] - raw[-1]['invert']:.2f} m LOWER than the outlet - "
                            "water would run the other way; confirm the flow direction or edit the inverts")
    else:
        up, dn = (-1, 1) if raw[-1]["invert"] >= raw[1]["invert"] else (1, -1)
    length = abs(raw[1]["s"] - raw[-1]["s"])
    if not passage and length < 2 * (p["barrel_depth"] + p["wall"]):
        warnings.append(f"mouths only {T.fmt_len(length)} apart - the two ends will overlap; "
                        "give inlet/outlet points or a longer crossing")
    inv_in, inv_out = raw[up]["invert"], raw[dn]["invert"]
    min_fall = length * p["min_fall"]
    if passage:
        # open barrel from each portal to the midpoint, where the two halves meet
        p["barrel_depth"] = max(length / 2.0, p["wall"] + 0.1) + 0.01
        if abs(inv_in - inv_out) / max(length, 1e-6) > 0.08:
            warnings.append(f"floor grade {abs(inv_in - inv_out) / length:.1%} is steep for a road/path - "
                            "check the portal floor levels")
    elif inv_in - inv_out < min_fall:
        warnings.append(f"natural fall {inv_in - inv_out:.3f} m < 1:{int(1 / p['min_fall'])} "
                        f"({min_fall:.3f} m): outlet invert lowered to suit, outlet channel will be cut")
        inv_out = inv_in - min_fall
    raw[up]["invert"], raw[dn]["invert"] = inv_in, inv_out

    for role, side in (("in", up), ("out", dn)):
        e = raw[side]
        s = e["s"]
        mouth = (c[0] + s * d[0], c[1] + s * d[1])
        outward = (side * d[0], side * d[1])
        inv = e["invert"]
        # ground just behind the headwall sets its height
        sb = s - side * (p["wall"] + 0.5)
        zb = sampler.height(c[0] + sb * d[0], c[1] + sb * d[1])
        top_rel = min(max((zb if zb is not None else inv + need) - inv + p["upstand"], need), rise + p["max_top"])
        dims = mouth_dims(kind, span, rise, top_rel, p)
        frame = _frame(mouth, inv, outward)
        wing_end = []
        for sgn in (-1, 1):
            ox = sgn * (dims["half_w"] + dims["wing_len"] * math.sin(dims["phi"]))
            w = _to_world(frame, ox, dims["v_end"])
            zg = sampler.height(w.x, w.y)
            wr = (zg - inv + p["upstand"]) if zg is not None else 0.3
            wing_end.append(float(min(max(wr, 0.3), top_rel)))
        ends[role] = dict(mouth=[mouth[0], mouth[1]], invert=float(inv), outward=list(outward),
                          top_rel=float(top_rel), wing_end_rel=wing_end,
                          bed_distance=abs(e["bed_s"] - s), note=e["note"])
    if passage:
        mid = (ends["in"]["invert"] + ends["out"]["invert"]) / 2.0
        for e in ends.values():
            e["barrel_rise"] = float(mid - e["invert"])
    # deck: bridge a false dip over the barrel, then size the headwalls from the bridged ground
    deck = plan_deck(dict(kind=kind, span=span, rise=rise, params=p, ends=ends), sampler)
    if deck is not None:
        for e in ends.values():
            o = np.array(e["outward"])
            sb = np.array(e["mouth"]) - o * (p["wall"] + 0.5)
            zb = deck_height(deck, sb[0], sb[1], sampler.height(*sb))
            if zb is not None:
                e["top_rel"] = float(min(max(zb - e["invert"] + p["upstand"], rise + p["cover_min"]),
                                         rise + p["max_top"]))
        if deck["centre_fill_max_m"] > 0.05:
            warnings.append(f"surface over the barrel dips up to {deck['centre_fill_max_m']:.2f} m "
                            "(false notch from the terrain) - the deck step will fill it")

    state = T.load_state()
    pid = f"C{len(state) + 1:02d}"
    while pid in state:
        pid = f"C{int(pid[1:]) + 1:02d}"
    plan = dict(id=pid, name=name or pid, kind=kind, passage=passage, span=span, rise=rise, params=p,
                centre=list(c), axis=list(d),
                bearing=_bearing(d), axis_note=axis_note, crest_z=zc, length=length, deck=deck,
                fall=ends["in"]["invert"] - ends["out"]["invert"], ends=ends, warnings=warnings,
                asset=list(asset) if asset else None, status="planned", objects={}, backup={})
    state[pid] = plan
    T.save_state(state)
    summary(pid)
    return pid


def summary(pid):
    plan = T.load_state()[pid]
    e = plan["ends"]
    T.emit({
        "id": pid, "status": plan["status"], "kind": plan["kind"],
        "opening": f"{plan['span'] / T.INCH:.0f} in span x {plan['rise'] / T.INCH:.0f} in rise "
                   f"({plan['span'] * 1000:.0f} x {plan['rise'] * 1000:.0f} mm)",
        "axis_bearing_deg": round(plan["bearing"], 1), "axis_source": plan["axis_note"],
        "length_between_headwalls": T.fmt_len(plan["length"]),
        "crest_level_m": round(plan["crest_z"], 3),
        "inlet": {"invert_m": round(e["in"]["invert"], 3),
                  "headwall_height": T.fmt_len(e["in"]["top_rel"] + plan["params"]["footing"]),
                  "top_above_invert_m": round(e["in"]["top_rel"], 3),
                  "xy": [round(v, 2) for v in e["in"]["mouth"]], "how": e["in"]["note"]},
        "outlet": {"invert_m": round(e["out"]["invert"], 3),
                   "top_above_invert_m": round(e["out"]["top_rel"], 3),
                   "xy": [round(v, 2) for v in e["out"]["mouth"]], "how": e["out"]["note"]},
        "fall": (f"floor grade {plan['fall'] / plan['length']:+.1%} (end A to end B)" if plan.get("passage") else
                 f"{plan['fall']:.3f} m (1 in {plan['length'] / plan['fall']:.0f})" if plan["fall"] > 0 else "NONE"),
        "deck": ({"max_fill_over_barrel_m": plan["deck"]["centre_fill_max_m"],
                  "half_width": T.fmt_len(plan["deck"]["half_width_m"])} if plan.get("deck") else "off"),
        "warnings": plan["warnings"],
        "objects": plan["objects"], "backup": plan["backup"],
    })


def edit_plan(pid, **changes):
    """Tweak a planned (not yet blended) culvert, e.g. edit_plan('C01', in_invert=-1.05)."""
    st = T.load_state()
    plan = st[pid]
    if plan["status"] not in ("planned", "built"):
        raise RuntimeError("Restore first - the terrain has already been changed.")
    for k, v in changes.items():
        if k.startswith(("in_", "out_")):
            role, key = k.split("_", 1)
            plan["ends"][role][key] = v
        elif k in plan["params"]:
            plan["params"][k] = v
        else:
            plan[k] = v
    plan["fall"] = plan["ends"]["in"]["invert"] - plan["ends"]["out"]["invert"]
    T.save_state(st)
    summary(pid)


def markers(pid):
    """Drop CULVERT_IN / CULVERT_OUT empties on the planned mouths for the user to drag.

    Re-plan afterwards with plan_culvert(..., inlet="CULVERT_IN", outlet="CULVERT_OUT").
    """
    plan = T.load_state()[pid]
    col = T.feature_collection()
    for role, name in (("in", "CULVERT_IN"), ("out", "CULVERT_OUT")):
        e = plan["ends"][role]
        ob = bpy.data.objects.get(name)
        if ob is None:
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = 'SINGLE_ARROW'
            ob.empty_display_size = 1.5
            col.objects.link(ob)
        ob.location = (e["mouth"][0], e["mouth"][1], e["invert"])
        o = e["outward"]
        ob.rotation_euler = (math.radians(90), 0, math.atan2(o[1], o[0]) - math.radians(90))
    T.emit({"id": pid, "markers": ["CULVERT_IN", "CULVERT_OUT"],
            "note": "arrows point outward into the channel; drag them, then re-plan with inlet/outlet"})


def preview_views(pid):
    """Camera views for test renders: {label: (location, target, lens)}.

    One close-up per mouth, looking in from the channel, plus an oblique overview.
    """
    plan = T.load_state()[pid]
    views = {}
    labels = ("PortalA", "PortalB") if plan.get("passage") else ("Inlet", "Outlet")
    for role, label, side in (("in", labels[0], 1.5), ("out", labels[1], -1.5)):
        e = plan["ends"][role]
        o = Vector((*e["outward"], 0))
        x = Vector((o.y, -o.x, 0))
        m = Vector((*e["mouth"], e["invert"]))
        back = max(5.0, (2.5 if plan.get("passage") else 6.0) * plan["span"])
        loc = m + o * back + x * side * (back / 4) + Vector((0, 0, 1.2 + plan["rise"]))
        views[label] = (tuple(loc), tuple(m + Vector((0, 0, plan["rise"] * 0.6))), 24)
    a = Vector((*plan["ends"]["in"]["mouth"], plan["ends"]["in"]["invert"]))
    b = Vector((*plan["ends"]["out"]["mouth"], plan["ends"]["out"]["invert"]))
    mid = (a + b) / 2
    ax = (b - a).normalized()
    side = Vector((ax.y, -ax.x, 0))
    L = max((b - a).length, 6.0)
    views["Overview"] = (tuple(mid + side * L * 1.1 - ax * L * 0.35 + Vector((0, 0, L * 0.9))), tuple(mid), 28)
    return views


def frame(pid, role="in", distance=None):
    """Aim the viewport(s) at one mouth, looking into it from the channel."""
    plan = T.load_state()[pid]
    e = plan["ends"][role]
    o = e["outward"]
    tgt = (e["mouth"][0], e["mouth"][1], e["invert"] + plan["rise"] / 2)
    n = T.look_at(tgt, (o[0] + 0.35 * o[1], o[1] - 0.35 * o[0], 0.45),
                  distance or max(6.0, 4.0 * plan["span"]))
    T.emit({"id": pid, "framed": role, "viewports": n})


# ----------------------------------------------------------------------- build

def _outlines_world(plan):
    """[(outline_xy (M,2), target_z (M,), frame, dims)] for both ends."""
    out = []
    p = plan["params"]
    for role in ("in", "out"):
        e = plan["ends"][role]
        dims = mouth_dims(plan["kind"], plan["span"], plan["rise"], e["top_rel"], p)
        frame = _frame(e["mouth"], e["invert"], e["outward"])
        loc = outline_local(dims, e["top_rel"], e["wing_end_rel"], p)
        pts = [_to_world(frame, u, v, 0.0) for u, v, _ in loc]
        xy = np.array([(w.x, w.y) for w in pts])
        tz = np.array([e["invert"] + rel for _, _, rel in loc])
        out.append((role, xy, tz, frame, dims))
    return out


def build(pid):
    """Create the two mouth units as separate objects in OPCD_Features. Non-destructive."""
    st = T.load_state()
    plan = st[pid]
    for name in plan["objects"].values():
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    col = T.feature_collection()
    p = plan["params"]
    objs = {}
    for role in ("in", "out"):
        e = plan["ends"][role]
        frame = _frame(e["mouth"], e["invert"], e["outward"])
        name = f"CULVERT_{pid}_{role.upper()}"
        if plan.get("asset"):
            ob = _append_asset(plan["asset"], name)
        else:
            bm, dims = build_mouth_bmesh(plan["kind"], plan["span"], plan["rise"], e["top_rel"],
                                         e["wing_end_rel"], p, barrel_rise=e.get("barrel_rise", 0.0),
                                         cap=not plan.get("passage"))
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            ob = bpy.data.objects.new(name, me)
            loc = outline_local(dims, e["top_rel"], e["wing_end_rel"], p)
            ob["opcd_outline"] = json.dumps([[round(a, 5) for a in r] for r in loc])
            ob["opcd_rise"] = plan["rise"]
            ob["opcd_kind"] = plan["kind"]
        if ob.name not in col.objects:
            col.objects.link(ob)
        ob.matrix_world = frame
        objs[role] = ob.name
    plan["objects"] = objs
    plan["status"] = "built"
    T.save_state(st)
    T.undo_push(f"Build culvert {pid}")
    summary(pid)


def _append_asset(asset, name):
    path, obname = asset[0], asset[1]
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        if obname not in src.objects:
            raise RuntimeError(f"{obname} not in {path}; objects: {list(src.objects)[:30]}")
        dst.objects = [obname]
    ob = dst.objects[0]
    ob.data = ob.data.copy()
    ob.name = name
    return ob


def _affected(plan, radius):
    outs = [o[1] for o in _outlines_world(plan)]
    lo = np.min([o.min(0) for o in outs], axis=0) - radius
    hi = np.max([o.max(0) for o in outs], axis=0) + radius
    res, water = [], []
    for ob in T.surface_meshes():
        x0, y0, x1, y1, _, _ = T.world_bbox_xy(ob)
        if x1 < lo[0] or x0 > hi[0] or y1 < lo[1] or y0 > hi[1]:
            continue
        (water if T.is_surface_name(ob.name, T.WATER_KEYWORDS) else res).append(ob)
    return res, water


def _band(plan):
    p = plan["params"]
    return p["band"] or max(2.0, 2.0 * max(plan["ends"]["in"]["top_rel"], plan["ends"]["out"]["top_rel"]))


def _reach(plan):
    """How far from the outline terrain edits extend (band or channel fade)."""
    return max(_band(plan), 1.0 + plan["params"]["channel_fade"]) + 0.5


def _finalise_target(plan, target=None):
    if target:
        return bpy.data.objects[target]
    c = plan["centre"]
    cands = [ob for ob in T.surface_meshes(("Concrete",))]
    if not cands:
        raise RuntimeError("No Concrete mesh in the scene - ask the user which mesh to join into.")
    return min(cands, key=lambda ob: T.bbox_dist_xy(ob, *c))


def backup(pid, target=None, file_copy=True):
    """Incremental .blend copy + orphan mesh copies of every mesh blend/finalise will touch.

    file_copy=False skips the .blend copy - used by background jobs, where the
    source file is only ever read and results are saved to a new file.
    """
    st = T.load_state()
    plan = st[pid]
    objs, water = _affected(plan, _reach(plan) + 0.5)
    tgt = _finalise_target(plan, target)
    if tgt not in objs:
        objs.append(tgt)
    f = T.backup_file(pid) if file_copy else None
    meshes = T.backup_meshes(objs, pid)
    plan["backup"] = dict(file=f, meshes=meshes)
    plan["target"] = tgt.name
    T.save_state(st)
    T.emit({"id": pid, "backup_file": f, "meshes_backed_up": list(meshes),
            "join_target": tgt.name, "water_meshes_in_zone": [w.name for w in water]})


def blend(pid, include_water=False):
    """Densify, carve and reshape every affected surface mesh. Destructive - backup first."""
    st = T.load_state()
    plan = st[pid]
    if not plan.get("backup"):
        raise RuntimeError("Run backup() first.")
    if plan["status"] not in ("built", "planned"):
        raise RuntimeError(f"Status is {plan['status']}; restore() before blending again.")
    p = plan["params"]
    band = _band(plan)
    reach = _reach(plan)
    objs, water = _affected(plan, reach + 0.5)
    if include_water:
        objs += water
    for ob in objs:
        if ob.name not in plan["backup"]["meshes"]:
            raise RuntimeError(f"{ob.name} would be edited but was not backed up; run backup() again.")
    ends = _outlines_world(plan)
    outlines = [xy for _, xy, _, _, _ in ends]

    def field_for(role, xy_o, tz, frame, dims):
        e = plan["ends"][role]
        inv = e["invert"]
        o = np.array(e["outward"])
        xax = np.array([o[1], -o[0]])
        m = np.array(e["mouth"])
        v_end = dims["v_end"]
        half = dims["ae"]
        slope = 0.0 if plan.get("passage") else (0.005 if role == "in" else -0.005)

        def f(xy, z):
            dist, tgt = T.nearest_on_outline(xy, xy_o, tz)
            w = T.smoothstep(1.0 - dist / band)
            z1 = z + w * (tgt - z)
            rel = xy - m
            u = rel @ xax
            v = rel @ o
            beyond = v > v_end
            lat = np.maximum(0.0, np.abs(u) - half)
            tch = inv - 0.02 + slope * (v - v_end) + lat * p["channel_batter"]
            wch = np.where(v <= v_end + 1.0, 1.0, T.smoothstep(1.0 - (v - v_end - 1.0) / p["channel_fade"]))
            wch = np.where(beyond, wch, 0.0)
            z2 = z1 + wch * (np.minimum(z1, tch) - z1)
            # level pad in front of the mouth at apron level, so the structure sits on flat
            # ground: full strength over the apron's width to pad_len past the wing ends,
            # fading out forwards and sideways; starts at the apron end so the wings still
            # meet the ground they retain
            if p.get("pad", True):
                dv_f = np.maximum(v - (v_end + p["pad_len"]), 0.0)
                du_l = np.maximum(np.abs(u) - half, 0.0)
                wp = (T.smoothstep(1.0 - dv_f / p["pad_fade"]) * T.smoothstep(1.0 - du_l / p["pad_fade"])
                      * T.smoothstep((v - v_end) / 0.3))
                z2 = z2 + wp * (inv - 0.02 - z2)
            # fill-only plateau over the barrel stub so it can never poke out of a low bank
            hw = dims["half_w"]
            v0, v1 = -(p["barrel_depth"] + 0.25), -p["wall"]
            du = np.maximum(np.abs(u) - hw, 0.0)
            dv = np.maximum(np.maximum(v0 - v, v - v1), 0.0)
            wb = T.smoothstep(1.0 - np.hypot(du, dv) / band)
            wb *= T.smoothstep(-v / p["wall"])  # only behind the headwall face, never over the wings
            top = inv + e["top_rel"] - p["upstand"]
            return z2 + wb * np.maximum(top - z2, 0.0)
        return f

    report = {}
    dfield = deck_field(plan["deck"]) if plan.get("deck") else None
    for ob in objs:
        bm = T._bm_world(ob)
        r = {"verts_before": len(bm.verts)}
        r["deck_fill_m"] = 0.0
        if dfield is not None:
            bm.verts.ensure_lookup_table()
            xy = T._vert_xy(bm)
            if len(xy):
                z = np.array([v.co.z for v in bm.verts])
                zn = dfield(xy, z)
                for i in np.nonzero(zn > z + 1e-6)[0]:
                    bm.verts[i].co.z = float(zn[i])
                r["deck_fill_m"] = round(float(max((zn - z).max(), 0.0)), 3)
        r["verts_added"] = T.densify(bm, outlines, band + 0.5, p["max_edge"])
        r["faces_removed"] = sum(T.carve(bm, xy) for xy in outlines)
        cut = fill = 0.0
        for role, xy_o, tz, frame, dims in ends:
            c_, f_ = T.apply_height_field(bm, field_for(role, xy_o, tz, frame, dims), [xy_o], reach)
            cut, fill = min(cut, c_), max(fill, f_)
        if p["smooth"]:
            T.smooth_zone(bm, outlines, band, iterations=p["smooth"])
        r["max_cut_m"], r["max_fill_m"] = round(cut, 3), round(fill, 3)
        r["verts_after"] = len(bm.verts)
        T._bm_write(bm, ob)
        r["unity_65k_warning"] = r["verts_after"] > 65535
        report[ob.name] = r
    plan["status"] = "blended"
    plan["blend_report"] = report
    T.save_state(st)
    T.undo_push(f"Blend culvert {pid}")
    T.emit({"id": pid, "meshes": report,
            "water_meshes_skipped": [w.name for w in water] if not include_water else []})


def verify(pid):
    """Checks: stray holes, buried barrel, seams at outline, fall, Unity vertex limits."""
    plan = T.load_state()[pid]
    band = _band(plan)
    objs, water = _affected(plan, _reach(plan) + 0.5)
    ends = _outlines_world(plan)
    outlines = [xy for _, xy, _, _, _ in ends]
    sampler = T.HeightSampler(objs)
    checks = {}
    baks = {n: bpy.data.meshes.get(m) for n, m in plan.get("backup", {}).get("meshes", {}).items()}
    checks["stray_open_edges"] = T.boundary_report(objs, outlines, band, baks)
    barrel = {}
    for role, xy_o, tz, frame, dims in ends:
        e = plan["ends"][role]
        # barrel end, soffit level - must be under ground
        w = _to_world(frame, 0.0, -plan["params"]["barrel_depth"], plan["rise"] + e.get("barrel_rise", 0.0))
        zg = sampler.height(w.x, w.y)
        barrel[role] = {"soffit_m": round(w.z, 3), "ground_m": None if zg is None else round(zg, 3),
                        "buried": zg is not None and zg > w.z + 0.05}
        # ground along the outline: sealed (between wall bottom and top) and flush
        lim = outline_limits(e["top_rel"], e["wing_end_rel"], plan["params"])
        unsealed, flush_err = 0.0, 0.0
        for i in range(len(xy_o)):
            a, b = xy_o[i], xy_o[(i + 1) % len(xy_o)]
            n = np.array([b[1] - a[1], a[0] - b[0]])
            n = n / (np.linalg.norm(n) or 1)
            lo, h0, h1, flush = lim[i]
            for t in (0.2, 0.5, 0.8):
                q = a + t * (b - a)
                zq = sampler.height(*(q + n * 0.05))  # just outside the outline
                if zq is None:
                    unsealed = max(unsealed, 9.99)
                    continue
                rel = zq - e["invert"]
                hi = h0 + t * (h1 - h0)
                unsealed = max(unsealed, lo - 0.02 - rel, rel - hi - 0.02, 0.0)
                if flush:
                    tgt = tz[i] + t * (tz[(i + 1) % len(tz)] - tz[i])
                    flush_err = max(flush_err, abs(zq - tgt))
        barrel[role]["unsealed_by_m"] = round(unsealed, 3)
        barrel[role]["flush_max_error_m"] = round(flush_err, 3)
    checks["mouths"] = barrel
    checks["fall_m"] = round(plan["fall"], 3)
    checks["unity_65k"] = {ob.name: len(ob.data.vertices) for ob in objs if len(ob.data.vertices) > 65535}
    checks["water_meshes_in_zone"] = [w.name for w in water]
    # A Concrete mesh (cart path, road) that was cut or filled is usually unintended: the
    # shaping band reached a path the feature doesn't cross. Warning only - passages
    # legitimately reshape the path running through them.
    checks["concrete_reshaped"] = {
        n: {"cut_m": r["max_cut_m"], "fill_m": r["max_fill_m"]}
        for n, r in (plan.get("blend_report") or {}).items()
        if "Concrete" in n and (r["max_cut_m"] < -0.10 or r["max_fill_m"] > 0.10)}
    ok = (all(v == 0 for v in checks["stray_open_edges"].values())
          and all(m["buried"] for m in barrel.values())
          and all(m["unsealed_by_m"] == 0 and m["flush_max_error_m"] < 0.1 for m in barrel.values())
          and (plan.get("passage") or plan["fall"] > 0))
    checks["ok"] = ok
    st = T.load_state()
    st[pid]["verify"] = checks
    T.save_state(st)
    T.emit({"id": pid, "status": plan["status"], "checks": checks})
    return ok


def apply_stone(pid, density=0.5):
    """Give both mouth units of a plan a procedural stone-block material and UVs.

    For culverts that stay separate objects (not joined into Concrete). The material is
    Blender-only: for Unity/GSPro put a real stone image on the UVs or bake it.
    """
    plan = T.load_state()[pid]
    mat = bpy.data.materials.get("Culvert_Stone") or bpy.data.materials.new("Culvert_Stone")
    if not mat.use_nodes or not any(n.type == "TEX_VORONOI" for n in mat.node_tree.nodes):
        mat.use_nodes = True
        N, L = mat.node_tree.nodes, mat.node_tree.links
        N.clear()
        out = N.new("ShaderNodeOutputMaterial")
        bsdf = N.new("ShaderNodeBsdfPrincipled")
        tc = N.new("ShaderNodeTexCoord")
        mp = N.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.1, 1.1, 1.1)
        vor = N.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 2.2
        vor2 = N.new("ShaderNodeTexVoronoi")
        vor2.feature = "DISTANCE_TO_EDGE"
        vor2.inputs["Scale"].default_value = 2.2
        noise = N.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 12
        noise.inputs["Detail"].default_value = 6
        ramp = N.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.05, 0.055, 0.07, 1)
        ramp.color_ramp.elements[1].color = (0.38, 0.4, 0.45, 1)
        tone = N.new("ShaderNodeMix")
        tone.data_type, tone.blend_type = "RGBA", "MULTIPLY"
        tone.inputs["Factor"].default_value = 0.5
        edge = N.new("ShaderNodeMath")
        edge.operation = "GREATER_THAN"
        edge.inputs[1].default_value = 0.015
        joint = N.new("ShaderNodeMix")
        joint.data_type = "RGBA"
        joint.inputs[6].default_value = (0.12, 0.1, 0.09, 1)
        bump = N.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.8
        L.new(tc.outputs["Object"], mp.inputs["Vector"])
        for v in (vor, vor2, noise):
            L.new(mp.outputs["Vector"], v.inputs["Vector"])
        L.new(vor.outputs["Color"], ramp.inputs["Fac"])
        L.new(ramp.outputs["Color"], tone.inputs[6])
        L.new(noise.outputs["Color"], tone.inputs[7])
        L.new(tone.outputs[2], joint.inputs[7])
        L.new(vor2.outputs["Distance"], edge.inputs[0])
        L.new(edge.outputs["Value"], joint.inputs["Factor"])
        L.new(joint.outputs[2], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.85
        L.new(vor2.outputs["Distance"], bump.inputs["Height"])
        L.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        mat.diffuse_color = (0.38, 0.4, 0.44, 1)
    for n in plan["objects"].values():
        ob = bpy.data.objects[n]
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        for p in ob.data.polygons:
            p.material_index = 0
        T.box_project_uv(ob, "UVMap", density)
    return mat.name


def _smooth01(d, d0, d1):
    """1 inside d0, 0 beyond d1, smoothstep between."""
    if d <= d0:
        return 1.0
    if d >= d1:
        return 0.0
    t = (d1 - d) / (d1 - d0)
    return t * t * (3 - 2 * t)


def tidy(pid, radius=10.0, axis_reach=8.0, iterations=8, quads=True, z_passes=8, z_clamp=0.5, z_factor=0.45):
    """Clean the topology the blend leaves round a built culvert. Call after blend(), before verify().

    blend() densifies and re-triangulates the ground, which leaves a messy fan of thin triangles. For
    every touched surface mesh this: joins triangles into quads inside the zone, relaxes the free
    vertices sideways (even spacing) while re-projecting their height onto the pre-relax surface, then
    smooths heights gently (never lowering over the barrel) and finally makes coincident vertices of
    neighbouring meshes agree exactly (cart paths, i.e. Concrete meshes, keep their heights: only quads and
    sideways relaxation). Pinned: mesh borders (seams) and anything within 0.4 m of the
    structure, so the ground still meets the walls. Zone = ``radius`` m round the mouth units plus
    ``axis_reach`` m either side of the barrel.
    """
    from mathutils.bvhtree import BVHTree
    from mathutils.kdtree import KDTree
    st = T.load_state()
    plan = st[pid]
    if plan["status"] not in ("blended", "finalised"):
        raise RuntimeError(f"Status is {plan['status']}; blend() first.")
    cobjs = [bpy.data.objects[n] for n in plan["objects"].values()]
    cv, ct = [], []
    for ob in cobjs:
        me = ob.data
        me.calc_loop_triangles()
        base = len(cv)
        cv += [tuple(ob.matrix_world @ v.co) for v in me.vertices]
        ct += [tuple(base + i for i in t.vertices) for t in me.loop_triangles]
    cbvh = BVHTree.FromPolygons(cv, ct)
    ckd = KDTree(len(cv))
    for i, q in enumerate(cv):
        ckd.insert((q[0], q[1], 0.0), i)
    ckd.balance()
    a = np.array(plan["ends"]["in"]["mouth"], float)
    b = np.array(plan["ends"]["out"]["mouth"], float)
    ab = b - a
    L2 = max(float(ab @ ab), 1e-9)
    half = plan["span"] / 2 + plan["params"]["wall"] + 0.5

    def seg(x, y):
        p = np.array([x, y]) - a
        t = min(max(float(p @ ab) / L2, 0.0), 1.0)
        return float(np.linalg.norm(p - t * ab)), t

    def weight(x, y):
        d1 = ckd.find((x, y, 0.0))[2]
        d2, _ = seg(x, y)
        return max(_smooth01(d1, 0.6 * radius, radius), _smooth01(d2, 0.6 * axis_reach, axis_reach))

    report = {}
    for name in plan["backup"]["meshes"]:
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != "MESH":
            continue
        bm = T._bm_world(ob)
        bvh0 = BVHTree.FromBMesh(bm)
        bm.verts.ensure_lookup_table()
        w = np.array([weight(v.co.x, v.co.y) for v in bm.verts])
        if not (w > 0.0).any():
            bm.free()
            continue

        def spread():
            ed = [e.calc_length() for e in bm.edges if w[e.verts[0].index] > 0.5 and w[e.verts[1].index] > 0.5]
            return (float(np.std(ed) / max(np.mean(ed), 1e-9)) if ed else 0.0), len(ed)

        cv0, _n0 = spread()
        tris0 = sum(1 for f in bm.faces if len(f.verts) == 3 and all(w[v.index] > 0.5 for v in f.verts))
        if quads:
            fs = [f for f in bm.faces if len(f.verts) == 3 and all(w[v.index] > 0.5 for v in f.verts)]
            if fs:
                bmesh.ops.join_triangles(bm, faces=fs, cmp_seam=False, cmp_sharp=False, cmp_uvs=False,
                                         cmp_vcols=False, cmp_materials=False,
                                         angle_face_threshold=math.radians(25),
                                         angle_shape_threshold=math.radians(60))
        bm.verts.ensure_lookup_table()
        w = w[:len(bm.verts)]
        free = []
        for v in bm.verts:
            wi = w[v.index]
            if wi <= 0.0 or v.is_boundary or not v.link_edges:
                continue
            if cbvh.find_nearest(v.co)[3] < 0.4:
                continue
            free.append(v)
        for _ in range(iterations):
            new = []
            for v in free:
                m = np.mean([(e.other_vert(v).co.x, e.other_vert(v).co.y) for e in v.link_edges], axis=0)
                k = 0.5 * w[v.index]
                new.append((v.co.x + k * (m[0] - v.co.x), v.co.y + k * (m[1] - v.co.y)))
            for v, (x, y) in zip(free, new):
                v.co.x, v.co.y = x, y
        z0 = {}
        for v in free:
            hit = bvh0.ray_cast(Vector((v.co.x, v.co.y, v.co.z + 30.0)), Vector((0, 0, -1)), 80.0)
            if hit[0] is not None:
                v.co.z = hit[0].z
            z0[v.index] = v.co.z
        over = set()
        for v in free:
            d, t = seg(v.co.x, v.co.y)
            if d < half and 0.0 < t < 1.0:
                over.add(v.index)
        for _ in range(0 if "Concrete" in name else z_passes):
            new = []
            for v in free:
                m = sum(e.other_vert(v).co.z for e in v.link_edges) / len(v.link_edges)
                z = v.co.z + z_factor * w[v.index] * (m - v.co.z)
                z = min(max(z, z0[v.index] - z_clamp), z0[v.index] + z_clamp)
                if v.index in over:
                    z = max(z, z0[v.index])
                new.append(z)
            for v, z in zip(free, new):
                v.co.z = z
        cv1, n1 = spread()
        quads1 = sum(1 for f in bm.faces if len(f.verts) == 4 and all(w[v.index] > 0.5 for v in f.verts))
        report[name] = {"zone_edges": n1, "edge_length_cv_before": round(cv0, 3),
                        "edge_length_cv_after": round(cv1, 3), "triangles_before": tris0,
                        "quads_after": quads1, "verts_relaxed": len(free)}
        T._bm_write(bm, ob)
    # coincident vertices of neighbouring surface meshes must agree exactly (no gaps at seams)
    surf = T.surface_meshes(exclude=T.WATER_KEYWORDS)
    mid = (a + b) / 2
    reach = float(np.sqrt(L2)) / 2 + radius + 2.0
    for _ in range(3):
        data, pts = {}, []
        for ob in surf:
            me = ob.data
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            data[ob.name] = co
            idx = np.nonzero(np.hypot(co[:, 0] - mid[0], co[:, 1] - mid[1]) < reach)[0]
            pts += [(ob.name, int(i)) for i in idx]
        kd = KDTree(max(len(pts), 1))
        for k, (n, i) in enumerate(pts):
            kd.insert((data[n][i][0], data[n][i][1], 0.0), k)
        kd.balance()
        changed, fixed = set(), 0
        for k, (n, i) in enumerate(pts):
            p = data[n][i]
            grp = [pts[j] for _, j, _ in kd.find_range((p[0], p[1], 0.0), 0.003)]
            if len({g[0] for g in grp}) > 1:
                zs = [data[g[0]][g[1]][2] for g in grp]
                if max(zs) - min(zs) > 1e-5:
                    zz = float(np.mean(zs))
                    for g in grp:
                        data[g[0]][g[1]][2] = zz
                        changed.add(g[0])
                    fixed += 1
        for n in changed:
            me = bpy.data.objects[n].data
            me.vertices.foreach_set("co", data[n].ravel())
            me.update()
        if not fixed:
            break
    plan["tidy"] = report
    T.save_state(st)
    print(json.dumps({"id": pid, "tidy": report}, indent=1))


def finalise(pid, target=None):
    """Match UV/colour/material to the Concrete mesh and join both mouth units into it."""
    st = T.load_state()
    plan = st[pid]
    if plan["status"] != "blended":
        raise RuntimeError(f"Status is {plan['status']}; blend() and verify() first.")
    tgt = bpy.data.objects[target or plan.get("target") or _finalise_target(plan).name]
    if tgt.name not in plan["backup"]["meshes"]:
        raise RuntimeError(f"{tgt.name} was not backed up; run backup(pid, target='{tgt.name}').")
    objs = [bpy.data.objects[n] for n in plan["objects"].values()]
    v0 = len(tgt.data.vertices)
    dens = None
    for ob in objs:
        dens = T.match_attributes(ob, tgt, ob.matrix_world.translation.xy)
    T.join_into(tgt, objs)
    plan["status"] = "finalised"
    plan["target"] = tgt.name
    T.save_state(st)
    T.undo_push(f"Finalise culvert {pid}")
    n = len(tgt.data.vertices)
    T.emit({"id": pid, "joined_into": tgt.name, "verts": [v0, n], "texel_density_uv_per_m": dens,
            "unity_65k_warning": n > 65535})


def restore(pid):
    """Undo everything for this culvert: meshes back from backup, culvert objects removed."""
    st = T.load_state()
    plan = st[pid]
    for name in plan["objects"].values():
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    done = T.restore_meshes(plan.get("backup", {}).get("meshes", {}))
    plan["status"] = "planned"
    plan["objects"] = {}
    plan["backup"] = {"file": plan.get("backup", {}).get("file")} if plan.get("backup") else {}
    T.save_state(st)
    T.undo_push(f"Restore culvert {pid}")
    T.emit({"id": pid, "restored": done, "note": "re-run backup() before blending again"})


def discard_backups(pid):
    st = T.load_state()
    plan = st[pid]
    n = T.discard_backups(plan.get("backup", {}).get("meshes", {}))
    plan["backup"] = {"file": plan.get("backup", {}).get("file"), "meshes_discarded": True}
    T.save_state(st)
    T.emit({"id": pid, "backup_meshes_removed": n, "backup_file_kept": plan["backup"]["file"]})

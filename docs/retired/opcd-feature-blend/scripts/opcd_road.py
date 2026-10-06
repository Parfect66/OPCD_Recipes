"""Road helpers for underpasses: close a gap in a road, flatten it, and slope the ground up to it.

Used when an underpass has to pass beneath a road whose two pieces stop short of each other (the
heightmap notch left a void). Frame: origin = the 3D cursor, ``rd`` runs along the road, ``ax`` across it.

    fr = Frame(origin_xy, road_bearing_deg)
    plane = fit_plane(road_obj, fr, s_ranges=[(-60, -30), (30, 60)], u_range=(5, 16))
    lift_ends(surface_objs, fr, plane, sA, sB, u_range)      # fill-only: raise the dipped road ends
    top = bridge_gap(road_obj, fr, plane, sA, sB, u_range)   # new deck faces; returns the free edge rows
    embankment(top["west"], fr, away=-ax, ...)               # new slope mesh that meets the deck edge

Every function works on world coordinates and only ever fills (raises) or adds faces, so the originals
can be put back from the mesh backups (``opcd_terrain.backup_meshes``).
"""

import math

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import opcd_terrain as T


class Frame:
    def __init__(self, origin, road_bearing):
        self.o = np.array(origin[:2], float)
        b = math.radians(road_bearing)
        self.rd = np.array([math.sin(b), math.cos(b)])          # along the road
        self.ax = np.array([math.sin(b + math.pi / 2), math.cos(b + math.pi / 2)])   # across, clockwise of rd

    def su(self, xy):
        r = np.asarray(xy, float)[..., :2] - self.o
        return r @ self.rd, r @ self.ax

    def xy(self, s, u):
        return self.o + np.outer(s, self.rd) + np.outer(u, self.ax) if np.ndim(s) else self.o + s * self.rd + u * self.ax


def _verts(ob):
    a = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", a)
    a = a.reshape(-1, 3)
    mw = np.array(ob.matrix_world)
    if not np.allclose(mw, np.eye(4)):
        a = (np.c_[a, np.ones(len(a))] @ mw.T)[:, :3]
    return a


def fit_plane(ob, fr, s_ranges, u_range):
    """Least-squares plane z = a + b s + c u through the road vertices in the given windows."""
    a = _verts(ob)
    s, u = fr.su(a[:, :2])
    m = np.zeros(len(a), bool)
    for lo, hi in s_ranges:
        m |= (s > lo) & (s < hi)
    m &= (u > u_range[0]) & (u < u_range[1])
    q = np.c_[np.ones(m.sum()), s[m], u[m]]
    coef, _, _, _ = np.linalg.lstsq(q, a[m, 2], rcond=None)
    rms = float(np.sqrt(np.mean((q @ coef - a[m, 2]) ** 2)))
    return {"coef": [float(x) for x in coef], "rms": rms, "n": int(m.sum())}


def plane_z(plane, s, u):
    c = plane["coef"]
    return c[0] + c[1] * s + c[2] * u


def _sm(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def lift_ends(objs, fr, plane, sA, sB, u_range, full=(6.0, 12.0), fade=4.0, lateral=8.0, into_gap=4.0):
    """Fill-only lift of every surface vertex near the two road ends to the road plane.
    sA = s of the end of the piece before the gap, sB = s of the start of the piece after it.
    ``full`` = metres from each end held at full strength (before, after), ``fade`` the ramp beyond that.
    A pure function of XY, so shoulders follow and seams stay equal."""
    report = {}
    for ob in objs:
        me = ob.data
        a = _verts(ob)
        s, u = fr.su(a[:, :2])
        tl = sA - s
        tr = s - sB
        wl = np.where(tl >= 0, 1 - _sm((tl - full[0]) / fade), _sm(1 + tl / into_gap))
        wr = np.where(tr >= 0, 1 - _sm((tr - full[1]) / fade), _sm(1 + tr / into_gap))
        du = np.maximum(np.maximum(u_range[0] - u, u - u_range[1]), 0)
        w = np.maximum(wl, wr) * (1 - _sm(du / lateral))
        plane_zs = plane_z(plane, s, u)
        d = w * np.maximum(plane_zs - a[:, 2], 0)
        if (d > 1e-4).any():
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            co[:, 2] += d      # identity transform assumed for the write-back
            me.vertices.foreach_set("co", co.ravel())
            me.update()
        report[ob.name] = (int((d > 1e-4).sum()), round(float(d.max()), 2))
    return report


def bridge_gap(ob, fr, plane, sA, sB, u_range, win=(5.0, 5.0), cut_step=2.8):
    """Bridge the gap between two road pieces inside one mesh object (join them first if they are
    separate objects). Finds the end edge chains near sA and sB, bridges them, subdivides the cross
    edges and puts the new vertices on the road plane. Returns the free edge rows ({'lo': [...], 'hi': [...]})
    as lists of (s, u, (x, y, z)) sorted by s, for the embankments."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    n0 = len(bm.verts)

    def su(v):
        s, u = fr.su((v.co.x, v.co.y))
        return float(s), float(u)

    def chain(s_lo, s_hi):
        out = []
        for e in bm.edges:
            if not e.is_boundary:
                continue
            (s0, u0), (s1, u1) = su(e.verts[0]), su(e.verts[1])
            sm, um = (s0 + s1) / 2, (u0 + u1) / 2
            if s_lo < sm < s_hi and u_range[0] - 1.0 < um < u_range[1] + 1.0 and abs(u1 - u0) > 1.5 * abs(s1 - s0):
                out.append(e)
        return out

    ca, cb = chain(sA - win[0], sA + 0.5), chain(sB - 0.5, sB + win[1])
    if not ca or not cb:
        bm.free()
        raise RuntimeError(f"end chains not found (A {len(ca)} edges, B {len(cb)} edges)")
    res = bmesh.ops.bridge_loops(bm, edges=ca + cb, use_pairs=False, use_cyclic=False, use_merge=False)
    new_faces = res["faces"]
    chain_edges = set(ca + cb)
    cross = {e for f in new_faces for e in f.edges if e not in chain_edges}
    cuts = max(1, int(round((sB - sA) / cut_step)))
    bmesh.ops.subdivide_edges(bm, edges=list(cross), cuts=cuts, use_grid_fill=True)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        if v.index >= n0:
            s, u = su(v)
            v.co.z = float(plane_z(plane, s, u))
    bm.normal_update()
    up = [f for v in bm.verts if v.index >= n0 for f in v.link_faces]
    if up and sum(1 for f in set(up) if f.normal.z < 0) > len(set(up)) / 2:
        bmesh.ops.reverse_faces(bm, faces=list(set(up)))
    # free edge rows along the two long sides of the new deck, corner to corner
    bnd = [(su(v)[0], su(v)[1], tuple(v.co)) for v in bm.verts if any(e.is_boundary for e in v.link_edges)]
    sa_ends = [su(v) for e in ca for v in e.verts]
    sb_ends = [su(v) for e in cb for v in e.verts]
    rows = {}
    for key, pick in (("lo", min), ("hi", max)):
        ua = pick(sa_ends, key=lambda t: t[1])
        ub = pick(sb_ends, key=lambda t: t[1])
        lo_s, hi_s = ua[0] - 0.05, ub[0] + 0.05
        sel = []
        for s, u, p in bnd:
            if lo_s <= s <= hi_s:
                line_u = ua[1] + (ub[1] - ua[1]) * (s - ua[0]) / max(ub[0] - ua[0], 1e-9)
                if abs(u - line_u) < 1.2:
                    sel.append((s, u, p))
        rows[key] = sorted(sel, key=lambda t: t[0])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return rows


def ground_bvh(exclude):
    """BVH of every visible mesh except those for which exclude(ob) is true; returns a ground(x, y) function."""
    verts, tris = [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.visible_get() or exclude(o):
            continue
        me = o.data
        me.calc_loop_triangles()
        mw = o.matrix_world
        base = len(verts)
        verts += [tuple(mw @ v.co) for v in me.vertices]
        tris += [tuple(base + i for i in t.vertices) for t in me.loop_triangles]
    bvh = BVHTree.FromPolygons(verts, tris)

    def ground(x, y, zmax=200.0):
        h = bvh.ray_cast(Vector((x, y, zmax)), Vector((0, 0, -1)), 400.0)
        return None if h[0] is None else float(h[0].z)
    return ground


def embankment(rows, away, name, like, ground, width=15.5, steps=18, coons_sides=False):
    """New surface mesh sloping from the deck's free edge (rows: (s, u, (x, y, z)) sorted by s) down
    ``away`` (unit XY, horizontal) for ``width`` m. The top row reuses the deck vertices' positions, so
    there is no gap; the toe height is sampled from ``ground`` (clamped 2 m under the top). With
    ``coons_sides`` the sides follow the existing ground (use where a neighbouring slope exists)."""
    P = np.array([r[2] for r in rows])
    N = len(P)
    away = np.asarray(away, float)
    XY = np.array([[P[i, :2] + away * width * j / steps for j in range(steps + 1)] for i in range(N)])
    top = P[:, 2]

    def samp(i, j, fb):
        g = ground(*XY[i, j])
        return fb if g is None else min(g, top[i])
    toe = np.array([min(samp(i, steps, top[i] - 6.5), top[i] - 2.0) for i in range(N)])
    Z = np.zeros((N, steps + 1))
    if coons_sides:
        west = np.array([samp(0, j, top[0] - 7.5 * j / steps) for j in range(steps + 1)])
        east = np.array([samp(N - 1, j, top[-1] - 7.5 * j / steps) for j in range(steps + 1)])
        west[0], east[0], west[steps], east[steps] = top[0], top[-1], toe[0], toe[-1]
    for i in range(N):
        a = i / max(N - 1, 1)
        for j in range(steps + 1):
            t = j / steps
            z = (1 - t) * top[i] + t * toe[i]
            if coons_sides:
                z += (1 - a) * (west[j] - ((1 - t) * top[0] + t * toe[0])) + a * (east[j] - ((1 - t) * top[-1] + t * toe[-1]))
            Z[i, j] = min(z, top[i])
        Z[i, 0] = top[i]
    bm = bmesh.new()
    V = [[bm.verts.new((float(XY[i, j, 0]), float(XY[i, j, 1]), float(Z[i, j]))) for j in range(steps + 1)] for i in range(N)]
    for i in range(N - 1):
        for j in range(steps):
            bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
    bm.normal_update()
    if sum(1 for f in bm.faces if f.normal.z < 0) > len(bm.faces) / 2:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    for col in like.users_collection:
        col.objects.link(ob)
    T.match_attributes(ob, like, (float(P[N // 2, 0]), float(P[N // 2, 1])))
    ca = ob.data.color_attributes.get("Col")
    lca = like.data.color_attributes.get("Col")
    if ca is not None and lca is not None:
        arr = np.empty(len(lca.data) * 4)
        lca.data.foreach_get("color", arr)
        mean = arr.reshape(-1, 4).mean(axis=0)
        ca.data.foreach_set("color", list(mean) * len(ca.data))
    ob.color = like.color          # the viewport shows Object colour
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.update()
    return ob

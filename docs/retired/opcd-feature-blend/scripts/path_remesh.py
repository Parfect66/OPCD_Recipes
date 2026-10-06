"""Re-mesh a pinched section of an OPCD cart path / road strip so it matches the regular triangulation either
side, and smooth its heights. Built for the Meloneras creek crossing (1 Oct 2026), where an earlier
``opcd_road.bridge_gap`` fill left a fan of thin slivers and a 0.25 m dip across a 3 m Concrete path.

    blender -b <in.blend> --factory-startup --python path_remesh.py -- <cfg.json> scan  <out_dir>
    blender -b <in.blend> --factory-startup --python path_remesh.py -- <cfg.json> test  <out_dir>
    blender -b <in.blend>                   --python path_remesh.py -- <cfg.json> final <out.blend>

cfg.json (only "path" is needed for scan):
    {"path": "Spline_path100_piece4_1_Concrete_-_Mesh",
     "centreline": [[x, y], ...],   # 5-8 points down the middle of the path, from >= s0 - 9 m to >= s1 + 9 m
     "s0": 11.3, "s1": 25.6,        # zone, metres along the centreline; ends must sit in regular strip
     optional: fit 7.0, row_t [1/3, 2/3], row_gap 1.1, side_gap 0.55, side_tol 0.03, clear 0.45,
               falloff 1.5, snap 0.003, win 4.0}

scan  : reports clusters of sliver triangles (10 m cells) in the path mesh, to choose the zone.
test  : rebuilds in memory, writes rebuild_report.json and saves crossing_after.blend (a copy) in out_dir.
final : the same, saved as a NEW .blend (refuses to overwrite) plus <name>_rebuild_report.json.

- Faces whose centre lies in s = [s0, s1] are removed and refilled with a constrained Delaunay triangulation of:
  the kept cut lines, thinned edge vertices (~side_gap apart, extra ones kept where the edge bends more than
  side_tol) and interior rows at row_t of the width (~row_gap apart, staggered).
- Heights: each edge gets a cubic profile fitted to the regular path `fit` m either side of the zone, pinned to
  the kept corner vertices at the zone ends; across the path z is linear between the two edges.
- Neighbour meshes: vertices that sat on a removed path-edge vertex are moved onto the new edge segment, and the
  edge height change is faded out over `falloff` m. Both are pure functions of XY, so seams stay closed.
- Verify block: seam_gap_max_m (must be 0), flipped_faces per neighbour (must be 0), non_manifold_edges,
  new_face_quality_max/median (max-edge^2 / area; equilateral 2.31, a regular 3-row strip ~3.7-4).
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt

args = sys.argv[sys.argv.index("--") + 1:]
CFG, MODE, OUT = json.load(open(args[0])), args[1], args[2]

PATH = CFG["path"]

if MODE == "scan":
    ob = bpy.data.objects[PATH]
    mw = ob.matrix_world
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    rows = []
    for f in bm.faces:
        L = [e.calc_length() for e in f.edges]
        c = mw @ f.calc_center_median()
        rows.append((c.x, c.y, max(L) ** 2 / max(f.calc_area(), 1e-9), min(L)))
    R = np.array(rows)
    bad = R[(R[:, 2] > 8) | (R[:, 3] < 0.25)]
    cells = {}
    for x, y, *_ in bad:
        k = (int(x // 10) * 10, int(y // 10) * 10)
        cells[k] = cells.get(k, 0) + 1
    rep = {"faces": len(R), "median_quality": round(float(np.median(R[:, 2])), 2), "sliver_faces": len(bad),
           "sliver_cells_xy_count": sorted([[k[0], k[1], n] for k, n in cells.items()], key=lambda t: -t[2])[:20]}
    os.makedirs(OUT, exist_ok=True)
    json.dump(rep, open(os.path.join(OUT, "scan_report.json"), "w"), indent=1)
    print("REPORT", json.dumps(rep, indent=1))
    sys.exit(0)

CL = np.array(CFG["centreline"], float)
S0, S1 = float(CFG["s0"]), float(CFG["s1"])
FIT = CFG.get("fit", 7.0)
ROW_T = tuple(CFG.get("row_t", (1 / 3, 2 / 3)))
ROW_GAP = CFG.get("row_gap", 1.1)
SIDE_GAP = CFG.get("side_gap", 0.55)
SIDE_TOL = CFG.get("side_tol", 0.03)
CLEAR = CFG.get("clear", 0.45)
FALLOFF = CFG.get("falloff", 1.5)
SNAP = CFG.get("snap", 0.003)
WIN = CFG.get("win", 4.0)
LO, HI = CL.min(0) - 20, CL.max(0) + 20


def in_box(co):
    return LO[0] < co.x < HI[0] and LO[1] < co.y < HI[1]


report = {"mode": MODE}


def su(p):
    best = None
    acc = 0.0
    for i in range(len(CL) - 1):
        a, b = CL[i], CL[i + 1]
        t = b - a
        L = float(np.linalg.norm(t))
        t = t / L
        r = np.asarray(p[:2], float) - a
        s = min(max(float(r @ t), 0.0), L)
        n = np.array([-t[1], t[0]])
        dd = float(np.linalg.norm(r - s * t))
        if best is None or dd < best[0]:
            best = (dd, acc + s, float(r @ n))
        acc += L
    return best[1], best[2], best[0]


def poly_at(P, S, s):
    """Point on polyline P (rows sorted by param S) at param s."""
    return np.array([np.interp(s, S, P[:, 0]), np.interp(s, S, P[:, 1])])


def seg_dist(p, P):
    a, b = P[:-1], P[1:]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    q = a + ab * t[:, None]
    d = np.hypot(*(p - q).T)
    k = int(d.argmin())
    return float(d[k]), q[k]


ob = bpy.data.objects[PATH]
assert np.allclose(np.array(ob.matrix_world), np.eye(4)), "path mesh has a transform"
me = ob.data
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
col_layer = bm.loops.layers.color.get("Col")

SU = {}
for v in bm.verts:
    if in_box(v.co):
        s, u, d = su(v.co)
        if d < WIN:
            SU[v] = (s, u)

# ---- original edge (boundary) verts per side, for the height fit and neighbour mapping
bnd = [v for v in SU if any(e.is_boundary for e in v.link_edges)]
orig_side = {"N": [], "S": []}
for v in bnd:
    s, u = SU[v]
    orig_side["N" if u > 0 else "S"].append((s, v.co.x, v.co.y, v.co.z))
for k in orig_side:
    orig_side[k] = np.array(sorted(orig_side[k]))

# ---- height model: cubic z(s) per edge, fitted outside the zone
fits = {}
for k, A in orig_side.items():
    m = ((A[:, 0] > S0 - FIT) & (A[:, 0] < S0)) | ((A[:, 0] > S1) & (A[:, 0] < S1 + FIT))
    c = np.polyfit(A[m, 0], A[m, 3], 3)
    fits[k] = c
    res = A[m, 3] - np.polyval(c, A[m, 0])
    zm = (A[:, 0] >= S0) & (A[:, 0] <= S1)
    dev = A[zm, 3] - np.polyval(c, A[zm, 0])
    report[f"fit_{k}"] = {"rms_m": round(float(np.sqrt((res ** 2).mean())), 4),
                          "zone_dev_min_m": round(float(dev.min()), 3), "zone_dev_max_m": round(float(dev.max()), 3)}

# ---- zone
zone_faces = [f for f in bm.faces if all(v in SU for v in f.verts)
              and S0 <= su(f.calc_center_median())[0] <= S1]
zf = set(zone_faces)
zone_verts = {v for f in zone_faces for v in f.verts}
cut_verts = {v for v in zone_verts if any(f not in zf for f in v.link_faces)}
loop_edges = set()
for f in zone_faces:
    for e in f.edges:
        if e.is_boundary or any(g not in zf for g in e.link_faces):
            loop_edges.add(e)
report["zone_faces"] = len(zone_faces)

# walk the hole outline
adj = {}
for e in loop_edges:
    a, b = e.verts
    adj.setdefault(a, []).append(b)
    adj.setdefault(b, []).append(a)
bad = [len(n) for n in adj.values() if len(n) != 2]
assert not bad, f"hole outline is not a simple loop ({bad})"
start = next(iter(adj))
loop = [start]
prev = None
while True:
    nb = [w for w in adj[loop[-1]] if w is not prev]
    nxt = nb[0]
    if nxt is start:
        break
    prev = loop[-1]
    loop.append(nxt)
assert len(loop) == len(adj), "hole outline has more than one loop"

# rotate so loop starts at a cut vert, then thin runs of edge-only verts
k0 = next(i for i, v in enumerate(loop) if v in cut_verts)
loop = loop[k0:] + loop[:k0]
keep = [True] * len(loop)
i = 0
n = len(loop)
dropped_total = 0
while i < n:
    if loop[i] in cut_verts:
        i += 1
        continue
    j = i
    while j < n and loop[j] not in cut_verts:
        j += 1
    a = loop[i - 1]
    b = loop[j % n]
    run = list(range(i, j))
    pts = [a.co.xy] + [loop[r].co.xy for r in run] + [b.co.xy]
    arc = np.concatenate([[0], np.cumsum([(pts[q + 1] - pts[q]).length for q in range(len(pts) - 1)])])
    L = arc[-1]
    m = max(int(round(L / SIDE_GAP)) - 1, 0)
    chosen = set()
    for q in range(1, m + 1):
        target = L * q / (m + 1)
        best = min(range(1, len(pts) - 1), key=lambda r: abs(arc[r] - target), default=None)
        if best is not None:
            chosen.add(best)
    # add back verts that would leave the edge off by more than SIDE_TOL
    while True:
        idx = [0] + sorted(chosen) + [len(pts) - 1]
        P = np.array([tuple(pts[r]) for r in idx])
        worst, wr = 0.0, None
        for r in range(1, len(pts) - 1):
            if r in chosen:
                continue
            d, _ = seg_dist(np.array(tuple(pts[r])), P)
            if d > worst:
                worst, wr = d, r
        if worst <= SIDE_TOL or wr is None:
            break
        chosen.add(wr)
    for q, r in enumerate(run):
        keep[r] = (q + 1) in chosen
        dropped_total += 0 if keep[r] else 1
    i = j
report["edge_verts_dropped"] = dropped_total

kept_loop = [v for v, k in zip(loop, keep) if k]
dropped = [v for v, k in zip(loop, keep) if not k]

# kept edge polylines per side (incl. corner cut verts on the boundary), param by s
def side_of(v):
    return "N" if SU[v][1] > 0 else "S"

side_pts = {"N": [], "S": []}
for v in kept_loop:
    if any(e.is_boundary for e in v.link_edges) and (v not in cut_verts or any(e.is_boundary for e in v.link_edges)):
        side_pts[side_of(v)].append((SU[v][0], v.co.x, v.co.y))
# include regular edge verts just outside the zone so interpolation is defined at S0/S1
for k, A in orig_side.items():
    for s, x, y, z in A:
        if S0 - 1.5 < s < S0 or S1 < s < S1 + 1.5:
            side_pts[k].append((s, x, y))
SIDE = {}
for k in side_pts:
    A = np.array(sorted(set(side_pts[k])))
    SIDE[k] = (A[:, 1:3], A[:, 0])

# new XY for every original zone edge vert (dropped ones snap onto the new edge)
moves = []   # (old_xy, new_xy, side, s, z0, fixed)
for r, v in enumerate(loop):
    if not any(e.is_boundary for e in v.link_edges):
        continue
    k = side_of(v)
    old = np.array([v.co.x, v.co.y])
    if v in dropped:
        a = r
        while not keep[a % n]:
            a -= 1
        b = r
        while not keep[b % n]:
            b += 1
        A2 = np.array([tuple(loop[a % n].co.xy), tuple(loop[b % n].co.xy)])
        _, q = seg_dist(old, A2)
        moves.append((old, q, k, SU[v][0], v.co.z, False))
    else:
        moves.append((old, old, k, SU[v][0], v.co.z, v in cut_verts))
report["max_snap_m"] = round(max((float(np.linalg.norm(a - b)) for a, b, *_ in moves), default=0.0), 4)

# ---- interior rows
existing = np.array([tuple(v.co.xy) for v in kept_loop])
new_xy = []
for r, t in enumerate(ROW_T):
    s = S0 + (0.55 if r == 0 else 0.0)
    while s < S1:
        pS = poly_at(*SIDE["S"], s)
        pN = poly_at(*SIDE["N"], s)
        p = pS + t * (pN - pS)
        ok = np.hypot(*(existing - p).T).min() > CLEAR and all(np.hypot(*(p - q)) > CLEAR for q in new_xy)
        if ok and S0 < su(p)[0] < S1:
            new_xy.append(p)
        s += ROW_GAP
report["new_interior_verts"] = len(new_xy)

# ---- remove zone faces + unneeded verts
old_cols = []   # for colour lookup
if col_layer is not None:
    for f in zone_faces:
        for l in f.loops:
            old_cols.append((l.vert.co.x, l.vert.co.y, tuple(l[col_layer])))
smooth_major = sum(f.smooth for f in bm.faces) > len(bm.faces) / 2
up_major = sum(1 for f in bm.faces if f.normal.z > 0) > len(bm.faces) / 2
bmesh.ops.delete(bm, geom=zone_faces, context='FACES_ONLY')
kept_set = set(kept_loop)
bmesh.ops.delete(bm, geom=[v for v in zone_verts if v not in kept_set], context='VERTS')

# ---- CDT fill
coords = [Vector((v.co.x, v.co.y)) for v in kept_loop] + [Vector((float(p[0]), float(p[1]))) for p in new_xy]
poly = list(range(len(kept_loop)))
area = sum(coords[poly[i]].x * coords[poly[(i + 1) % len(poly)]].y - coords[poly[(i + 1) % len(poly)]].x * coords[poly[i]].y for i in range(len(poly)))
if area < 0:
    poly.reverse()
vo, eo, fo, orig_v, _, _ = delaunay_2d_cdt(coords, [], [poly], 1, 1e-6)
vmap = {}
for oi, origs in enumerate(orig_v):
    assert origs, "CDT added a vertex"
    src = min(origs)
    if src < len(kept_loop):
        vmap[oi] = kept_loop[src]
    else:
        p = new_xy[src - len(kept_loop)]
        vmap[oi] = bm.verts.new((float(p[0]), float(p[1]), 0.0))
new_verts = [vmap[i] for i in vmap if vmap[i] not in kept_set]
new_faces = []
for f in fo:
    vs = [vmap[i] for i in f]
    if not up_major:
        vs.reverse()
    try:
        nf = bm.faces.new(vs)
    except ValueError:
        nf = bm.faces.get(vs)
    nf.smooth = smooth_major
    new_faces.append(nf)
wire = [e for e in bm.edges if not e.link_faces]
bmesh.ops.delete(bm, geom=wire, context='EDGES')
report["new_faces"] = len(new_faces)


# ---- heights in the zone
def t_across(p):
    dS, _ = seg_dist(p, SIDE["S"][0])
    dN, _ = seg_dist(p, SIDE["N"][0])
    return dS / max(dS + dN, 1e-9)


OFFS = {}


def prof(k, s):
    o = float(np.interp(s, *OFFS[k])) if k in OFFS else 0.0
    return float(np.polyval(fits[k], s)) + o


def model_z(p, side=None):
    s = su(p)[0]
    zS, zN = prof("S", s), prof("N", s)
    t = 0.0 if side == "S" else 1.0 if side == "N" else t_across(p)
    return float(zS + t * (zN - zS))


# pin each edge profile to the kept corner verts at the zone ends
for k in ("N", "S"):
    cs = sorted((SU[v][0], v.co.z - np.polyval(fits[k], SU[v][0])) for v in cut_verts
                if v.is_valid and side_of(v) == k and any(e.is_boundary for e in v.link_edges))
    OFFS[k] = (np.array([c[0] for c in cs]), np.array([c[1] for c in cs]))
report["end_offsets_m"] = {k: [round(float(x), 4) for x in OFFS[k][1]] for k in OFFS}

edge_zone = [v for v in kept_loop if v not in cut_verts]
for v in edge_zone:
    v.co.z = model_z(np.array([v.co.x, v.co.y]), side_of(v))
for v in new_verts:
    v.co.z = model_z(np.array([v.co.x, v.co.y]))
cut_dev = [abs(v.co.z - model_z(np.array([v.co.x, v.co.y]))) for v in cut_verts if v.is_valid]
report["cut_line_model_dev_max_m"] = round(max(cut_dev), 4)

# colours for new loops from the nearest old loop
if col_layer is not None and old_cols:
    OC = np.array([(x, y) for x, y, _ in old_cols])
    for f in new_faces:
        for l in f.loops:
            k = int(np.hypot(OC[:, 0] - l.vert.co.x, OC[:, 1] - l.vert.co.y).argmin())
            l[col_layer] = old_cols[k][2]

bm.normal_update()
report["new_faces_down"] = sum(1 for f in new_faces if (f.normal.z > 0) != up_major)
q = []
for f in new_faces:
    Ls = [e.calc_length() for e in f.edges]
    q.append(max(Ls) ** 2 / max(f.calc_area(), 1e-9))
report["new_face_quality_max"] = round(max(q), 2)
report["worst_faces"] = sorted([(round(qq, 1), round(f.calc_center_median().x, 2), round(f.calc_center_median().y, 2)) for qq, f in zip(q, new_faces)], reverse=True)[:4]       # equilateral 2.31; regular strip median ~3.7
report["new_face_quality_median"] = round(float(np.median(q)), 2)
report["non_manifold_edges"] = sum(1 for e in bm.edges if len(e.link_faces) > 2)

# edge-vert height deltas (for neighbour fade)
delta = {"N": [], "S": []}
for old, new, k, s, z0, fixed in moves:
    delta[k].append((s, 0.0 if fixed else model_z(new, k) - z0, new[0], new[1]))
for k in delta:
    delta[k] = np.array(sorted(delta[k]))
report["edge_raise_max_m"] = {k: round(float(np.abs(delta[k][:, 1]).max()), 3) for k in delta}

bm.to_mesh(me)
bm.free()
me.update()

# ---- neighbours: snap + fade, pure functions of XY
snap_from = np.array([m[0] for m in moves])
snap_to = np.array([m[1] for m in moves])
_bm = bmesh.new()
_bm.from_mesh(ob.data)
PB = np.array([[tuple(e.verts[0].co), tuple(e.verts[1].co)] for e in _bm.edges
               if e.is_boundary and in_box(e.verts[0].co)])
_bm.free()


def edge_z(p):
    a, b = PB[:, 0, :2], PB[:, 1, :2]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    d = np.hypot(*(p - (a + ab * t[:, None])).T)
    k = int(d.argmin())
    return float(PB[k, 0, 2] + t[k] * (PB[k, 1, 2] - PB[k, 0, 2])), float(d[k])


snap_z = np.array([m[4] if m[5] else edge_z(m[1])[0] for m in moves])
SIDEPOLY = {k: np.array([[x, y] for x, y in zip(*SIDE[k][0].T)]) for k in SIDE}
lo = snap_from.min(0) - FALLOFF - 1
hi = snap_from.max(0) + FALLOFF + 1
nb_report = {}
for o in bpy.data.objects:
    if o.type != 'MESH' or o is ob or o.name in ("Terrain",):
        continue
    if not np.allclose(np.array(o.matrix_world), np.eye(4)):
        continue
    md = o.data
    A = np.empty(len(md.vertices) * 3)
    md.vertices.foreach_get("co", A)
    A = A.reshape(-1, 3)
    m = (A[:, 0] > lo[0]) & (A[:, 0] < hi[0]) & (A[:, 1] > lo[1]) & (A[:, 1] < hi[1])
    if not m.any():
        continue
    nsnap = nfade = 0
    for i in np.nonzero(m)[0]:
        p = A[i, :2]
        d = np.hypot(*(snap_from - p).T)
        j = int(d.argmin())
        if d[j] < SNAP:
            A[i, 0], A[i, 1], A[i, 2] = snap_to[j][0], snap_to[j][1], snap_z[j]
            nsnap += 1
            continue
        best = None
        for k in ("N", "S"):
            dk, qk = seg_dist(p, SIDEPOLY[k])
            if best is None or dk < best[0]:
                best = (dk, k, qk)
        dk, k, qk = best
        if dk >= FALLOFF:
            continue
        s = su(qk)[0]
        if not (delta[k][0, 0] <= s <= delta[k][-1, 0]):
            continue
        dz = float(np.interp(s, delta[k][:, 0], delta[k][:, 1]))
        w = 1 - dk / FALLOFF
        w = w * w * (3 - 2 * w)
        if abs(dz * w) > 1e-5:
            A[i, 2] += dz * w
            nfade += 1
    if nsnap or nfade:
        md.calc_loop_triangles() if False else None
        nz0 = np.empty(len(md.polygons) * 3); md.polygons.foreach_get("normal", nz0); nz0 = nz0.reshape(-1, 3)[:, 2]
        md.vertices.foreach_set("co", A.ravel())
        md.update()
        nz1 = np.empty(len(md.polygons) * 3); md.polygons.foreach_get("normal", nz1); nz1 = nz1.reshape(-1, 3)[:, 2]
        flips = int(((np.sign(nz0) != np.sign(nz1)) & (np.abs(nz0) > 1e-3)).sum())
        nb_report.setdefault(o.name, {})["flipped_faces"] = flips
        md.update()
        nb_report[o.name].update({"snapped": nsnap, "faded": nfade})
report["neighbours"] = nb_report

# ---- verify: every original seam point of every neighbour now lies on the path edge
me = ob.data
bmv = bmesh.new()
bmv.from_mesh(me)
bedges = [e for e in bmv.edges if e.is_boundary and in_box(e.verts[0].co)]
B = np.array([[tuple(e.verts[0].co), tuple(e.verts[1].co)] for e in bedges])
worst = 0.0
for p in snap_to:
    z = snap_z[list(map(tuple, snap_to)).index(tuple(p))]
    a, b = B[:, 0, :2], B[:, 1, :2]
    ab = b - a
    t = np.clip(((p - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
    q = a + ab * t[:, None]
    d = np.hypot(*(p - q).T)
    k = int(d.argmin())
    zq = B[k, 0, 2] + t[k] * (B[k, 1, 2] - B[k, 0, 2])
    g = float(np.hypot(d[k], z - zq))
    if g > worst:
        worst = g
        report["seam_gap_at"] = [round(float(p[0]), 3), round(float(p[1]), 3), round(float(d[k]), 4), round(float(z - zq), 4)]
report["seam_gap_max_m"] = round(worst, 4)
report["moves_dropped"] = [[round(float(a[0]), 3), round(float(a[1]), 3), round(float(b[0]), 3), round(float(b[1]), 3)] for a, b, *_ in moves if np.hypot(*(a - b)) > 1e-6]
bmv.free()

print("REPORT", json.dumps(report, indent=1))

if MODE == "test":
    os.makedirs(OUT, exist_ok=True)
    json.dump(report, open(os.path.join(OUT, "rebuild_report.json"), "w"), indent=1)
    for o in bpy.data.objects:
        if o.type == 'MESH' and not o.users_scene:
            bpy.context.scene.collection.objects.link(o)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "crossing_after.blend"), copy=True)
else:
    assert not os.path.exists(OUT), f"{OUT} exists"
    json.dump(report, open(os.path.splitext(OUT)[0] + "_rebuild_report.json", "w"), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, copy=True)
    print("SAVED", OUT)

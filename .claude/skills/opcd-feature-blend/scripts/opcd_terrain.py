"""Generic terrain helpers for blending built features into OPCD V4 surface meshes.

Blender 4.5, run inside Blender (via blender-mcp ``execute_blender_code`` or the
Scripting tab). Everything works on world-space XY so that neighbouring surface
meshes (Rough, Fairway, Concrete ...) receive *identical* edits along their shared
borders: every height change is a pure function of (x, y, z) and every cut is a
vertical plane, so seams between meshes stay closed.

Units: 1 BU = 1 m. Distances are reported in yards (metres in brackets);
elevations in metres.
"""
import json
import math

import bpy  # noqa: I001 (bpy first so the pip `bpy` module exposes bmesh)
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SURFACE_KEYWORDS = ("Fairway", "Tee", "Rough", "Custom4", "Custom3", "Custom2",
                    "Custom1", "Bunker", "Concrete", "Lake", "Creek")
WATER_KEYWORDS = ("Lake", "Creek")
FEATURE_COLLECTION = "OPCD_Features"
STATE_KEY = "opcd_features"
BACKUP_PREFIX = "BAK_"

YARD = 0.9144
FOOT = 0.3048
INCH = 0.0254


def yd(x): return x * YARD
def ft(x): return x * FOOT
def inch(x): return x * INCH
def mm(x): return x / 1000.0


def fmt_len(m):
    return f"{m / YARD:.2f} yd ({m:.2f} m)"


def emit(obj):
    """Print a compact JSON result; blender-mcp returns captured stdout."""
    print(json.dumps(obj, indent=1, default=lambda o: round(o, 4) if isinstance(o, float) else str(o)))


# --------------------------------------------------------------------------- scene

def is_surface_name(name, keywords=SURFACE_KEYWORDS):
    return any(k in name for k in keywords)


def surface_meshes(keywords=SURFACE_KEYWORDS, exclude=()):
    """OPCD surface meshes: mesh objects whose name contains a surface keyword.

    Feature objects (in the OPCD_Features collection) are never returned.
    """
    feat = bpy.data.collections.get(FEATURE_COLLECTION)
    feat_objs = set(feat.all_objects) if feat else set()
    out = []
    for ob in bpy.context.scene.objects:
        if ob.type != 'MESH' or ob in feat_objs:
            continue
        if is_surface_name(ob.name, keywords) and not is_surface_name(ob.name, exclude or ("\0",)):
            out.append(ob)
    return out


def world_bbox_xy(ob):
    cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
    return min(xs), min(ys), max(xs), max(ys), min(zs), max(zs)


def bbox_dist_xy(ob, x, y):
    x0, y0, x1, y1, _, _ = world_bbox_xy(ob)
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    return math.hypot(dx, dy)


def ensure_object_mode():
    if bpy.context.mode != 'OBJECT':
        ob = bpy.context.view_layer.objects.active
        with bpy.context.temp_override(active_object=ob, object=ob):
            bpy.ops.object.mode_set(mode='OBJECT')


def undo_push(msg):
    try:
        bpy.ops.ed.undo_push(message=msg)
    except Exception:
        pass


def feature_collection():
    col = bpy.data.collections.get(FEATURE_COLLECTION)
    if col is None:
        col = bpy.data.collections.new(FEATURE_COLLECTION)
        bpy.context.scene.collection.children.link(col)
    return col


def load_state():
    raw = bpy.context.scene.get(STATE_KEY)
    return json.loads(raw) if raw else {}


def save_state(state):
    bpy.context.scene[STATE_KEY] = json.dumps(state)


def scene_report(keywords=SURFACE_KEYWORDS):
    """Summarise what the skill needs to know before planning anything."""
    sc = bpy.context.scene
    cur = sc.cursor
    rows = []
    for ob in surface_meshes(keywords):
        x0, y0, x1, y1, z0, z1 = world_bbox_xy(ob)
        me = ob.data
        rows.append({
            "name": ob.name, "verts": len(me.vertices), "faces": len(me.polygons),
            "under_cursor": x0 <= cur.location.x <= x1 and y0 <= cur.location.y <= y1,
            "dist_to_cursor_m": round(bbox_dist_xy(ob, cur.location.x, cur.location.y), 2),
            "materials": [m.name for m in me.materials if m],
            "uv": [u.name for u in me.uv_layers],
            "colour_attrs": [f"{a.name}:{a.domain}:{a.data_type}" for a in me.color_attributes],
            "vgroups": [g.name for g in ob.vertex_groups],
            "modifiers": [m.type for m in ob.modifiers],
            "custom_normals": bool(getattr(me, "has_custom_normals", False)),
            "unity_65k_risk": len(me.vertices) > 60000,
        })
    rows.sort(key=lambda r: r["dist_to_cursor_m"])
    empties = {n: list(bpy.data.objects[n].location) for n in ("CULVERT_IN", "CULVERT_OUT")
               if n in bpy.data.objects}
    emit({
        "blend_file": bpy.data.filepath or None,
        "saved": bool(bpy.data.filepath) and not bpy.data.is_dirty,
        "mode": bpy.context.mode,
        "unit_scale": sc.unit_settings.scale_length,
        "cursor": {"location": [round(v, 3) for v in cur.location],
                   "rotation_deg": [round(math.degrees(a), 1) for a in cur.rotation_euler]},
        "empties": empties,
        "surface_meshes_nearest_first": rows[:12],
        "surface_mesh_count": len(rows),
        "features": {k: v.get("status") for k, v in load_state().items()},
    })


def look_at(target, from_dir=(0.0, -1.0, 0.6), distance=8.0):
    """Aim every 3D viewport at ``target`` so get_viewport_screenshot shows it.

    from_dir: direction from the target towards the eye (need not be normalised).
    Returns the number of viewports changed (0 when running headless).
    """
    tgt = Vector(target)
    eye_dir = Vector(from_dir).normalized()
    rot = (-eye_dir).to_track_quat('-Z', 'Y')
    n = 0
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            r3d = area.spaces.active.region_3d
            r3d.view_perspective = 'PERSP'
            r3d.view_location = tgt
            r3d.view_rotation = rot
            r3d.view_distance = distance
            area.tag_redraw()
            n += 1
    return n


# ------------------------------------------------------------------ height sampling

class HeightSampler:
    """Ray-cast straight down onto a set of meshes (world space, top-most hit)."""

    def __init__(self, objs):
        self.trees = []
        self.top = -1e9
        for ob in objs:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.transform(ob.matrix_world)
            if bm.verts:
                self.top = max(self.top, max(v.co.z for v in bm.verts))
                self.trees.append((ob.name, BVHTree.FromBMesh(bm)))
            bm.free()
        self.top += 10.0

    def hit(self, x, y):
        best = (None, None)
        for name, tree in self.trees:
            loc, _n, _i, _d = tree.ray_cast(Vector((x, y, self.top)), Vector((0, 0, -1)))
            if loc is not None and (best[0] is None or loc.z > best[0]):
                best = (loc.z, name)
        return best

    def height(self, x, y):
        return self.hit(x, y)[0]

    def min_in_radius(self, x, y, r=0.75, step=0.25):
        zs = []
        n = int(r / step)
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                if i * i + j * j <= n * n:
                    z = self.height(x + i * step, y + j * step)
                    if z is not None:
                        zs.append(z)
        return min(zs) if zs else None


# ------------------------------------------------------------------- 2D geometry

def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def points_in_polygon(P, poly):
    """Vectorised even-odd test. P (N,2), poly (M,2) closed implicitly."""
    x, y = P[:, 0], P[:, 1]
    inside = np.zeros(len(P), dtype=bool)
    m = len(poly)
    for i in range(m):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % m]
        cond = (y0 > y) != (y1 > y)
        with np.errstate(divide='ignore', invalid='ignore'):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        inside ^= cond & (x < xc)
    return inside


def nearest_on_outline(P, poly, vals):
    """Distance from P (N,2) to closed polyline, and linearly interpolated value there."""
    best_d = np.full(len(P), np.inf)
    best_v = np.zeros(len(P))
    m = len(poly)
    for i in range(m):
        a = np.asarray(poly[i], float)
        b = np.asarray(poly[(i + 1) % m], float)
        ab = b - a
        L2 = float(ab @ ab)
        t = np.zeros(len(P)) if L2 == 0 else np.clip(((P - a) @ ab) / L2, 0.0, 1.0)
        q = a + t[:, None] * ab
        d = np.linalg.norm(P - q, axis=1)
        v = vals[i] + t * (vals[(i + 1) % m] - vals[i])
        closer = d < best_d
        best_d[closer] = d[closer]
        best_v[closer] = v[closer]
    return best_d, best_v


# ------------------------------------------------------------------- bmesh passes

def _bm_world(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    return bm


def _bm_write(bm, ob):
    bm.transform(ob.matrix_world.inverted())
    bm.normal_update()
    bm.to_mesh(ob.data)
    ob.data.update()
    bm.free()


def _vert_xy(bm):
    return np.array([(v.co.x, v.co.y) for v in bm.verts], float).reshape(-1, 2)


def _zone_mask(xy, outlines, radius):
    """True where a point is inside any outline or within ``radius`` of it."""
    mask = np.zeros(len(xy), dtype=bool)
    for poly in outlines:
        poly = np.asarray(poly, float)
        lo = poly.min(0) - radius
        hi = poly.max(0) + radius
        cand = np.all((xy >= lo) & (xy <= hi), axis=1)
        if not cand.any():
            continue
        idx = np.nonzero(cand)[0]
        d, _ = nearest_on_outline(xy[idx], poly, np.zeros(len(poly)))
        ins = points_in_polygon(xy[idx], poly)
        mask[idx[(d <= radius) | ins]] = True
    return mask


def densify(bm, outlines, radius, max_edge=0.35, passes=6):
    """Subdivide long edges near the feature so the terrain can follow it.

    Edge selection depends only on edge geometry, so a border edge shared by
    two surface meshes is split identically in both.
    """
    added = 0
    cand = list(bm.edges)
    for _ in range(passes):
        cand = [e for e in cand if e.is_valid and e.calc_length() > max_edge]
        if not cand:
            break
        mids = np.array([((e.verts[0].co.x + e.verts[1].co.x) * 0.5,
                          (e.verts[0].co.y + e.verts[1].co.y) * 0.5) for e in cand]).reshape(-1, 2)
        near = _zone_mask(mids, outlines, radius)
        edges = [cand[i] for i in np.nonzero(near)[0]]
        if not edges:
            break
        n0 = len(bm.verts)
        ret = bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
        added += len(bm.verts) - n0
        # only freshly split/created edges can still be too long
        cand = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMEdge)]
    # tidy any n-gons the partial subdivision produced
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method='BEAUTY', ngon_method='BEAUTY')
    return added


def carve(bm, outline, margin=0.6):
    """Cut the terrain cleanly along the outline with vertical planes and delete inside.

    Returns number of faces removed. The hole boundary lies exactly on the outline.
    """
    poly = np.asarray(outline, float)
    m = len(poly)
    lo_all = poly.min(0) - margin
    hi_all = poly.max(0) + margin
    cverts = {v for v in bm.verts
              if lo_all[0] <= v.co.x <= hi_all[0] and lo_all[1] <= v.co.y <= hi_all[1]}
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        ab = b - a
        L = float(np.hypot(*ab))
        if L < 1e-6:
            continue
        nrm = Vector((-ab[1] / L, ab[0] / L, 0.0))
        lo = np.minimum(a, b) - margin
        hi = np.maximum(a, b) + margin
        faces = set()
        for v in cverts:
            if not v.is_valid:
                continue
            for f in v.link_faces:
                c = f.calc_center_median()
                if lo[0] <= c.x <= hi[0] and lo[1] <= c.y <= hi[1]:
                    faces.add(f)
        if not faces:
            continue
        verts = {v for f in faces for v in f.verts}
        edges = {e for f in faces for e in f.edges}
        ret = bmesh.ops.bisect_plane(bm, geom=list(verts) + list(edges) + list(faces), dist=1e-5,
                                     plane_co=Vector((a[0], a[1], 0.0)), plane_no=nrm)
        cverts.update(g for g in ret["geom_cut"] if isinstance(g, bmesh.types.BMVert))
    faces = {f for v in cverts if v.is_valid for f in v.link_faces}
    faces = list(faces)
    if not faces:
        return 0
    cents = np.array([tuple(f.calc_center_median())[:2] for f in faces]).reshape(-1, 2)
    ins = points_in_polygon(cents, poly)
    dead = [faces[i] for i in np.nonzero(ins)[0]]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context='FACES')
    return len(dead)


def apply_height_field(bm, field, outlines, radius):
    """Set z = field(xy, z) for vertices in the zone. Returns (max_cut, max_fill)."""
    bm.verts.ensure_lookup_table()
    xy = _vert_xy(bm)
    if not len(xy):
        return 0.0, 0.0
    idx = np.nonzero(_zone_mask(xy, outlines, radius))[0]
    if not len(idx):
        return 0.0, 0.0
    z = np.array([bm.verts[i].co.z for i in idx])
    z_new = field(xy[idx], z)
    for i, zn in zip(idx, z_new):
        bm.verts[i].co.z = float(zn)
    dz = z_new - z
    return float(min(dz.min(), 0.0)), float(max(dz.max(), 0.0))


def smooth_zone(bm, outlines, radius, iterations=4, factor=0.5):
    """Laplacian-smooth z of interior vertices near the feature.

    Boundary vertices (the carved outline and borders shared with other surface
    meshes) are pinned, so seams and the wall contact line never move.
    """
    xy = _vert_xy(bm)
    if not len(xy):
        return 0
    bm.verts.ensure_lookup_table()
    idx = np.nonzero(_zone_mask(xy, outlines, radius))[0]
    verts = [bm.verts[i] for i in idx if not bm.verts[i].is_boundary and bm.verts[i].link_edges]
    for _ in range(iterations):
        new = [sum(e.other_vert(v).co.z for e in v.link_edges) / len(v.link_edges) for v in verts]
        for v, zn in zip(verts, new):
            v.co.z += factor * (zn - v.co.z)
    return len(verts)


def process_meshes(objs, fn):
    """Run fn(bm) on each object in world space, write back. Returns {name: result}."""
    out = {}
    for ob in objs:
        bm = _bm_world(ob)
        out[ob.name] = fn(bm)
        _bm_write(bm, ob)
    return out


def boundary_segments(me, mw):
    """(K, 2, 2) XY segments of the open edges of a mesh datablock, in world space."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(mw)
    seg = np.array([[tuple(e.verts[0].co)[:2], tuple(e.verts[1].co)[:2]]
                    for e in bm.edges if e.is_boundary]).reshape(-1, 2, 2)
    bm.free()
    return seg


def _dist_to_segments(P, seg):
    if not len(seg) or not len(P):
        return np.full(len(P), np.inf)
    a = seg[:, 0][None]
    ab = (seg[:, 1] - seg[:, 0])[None]
    ap = P[:, None, :] - a
    L2 = np.maximum((ab * ab).sum(-1), 1e-12)
    t = np.clip((ap * ab).sum(-1) / L2, 0, 1)
    d = np.linalg.norm(ap - t[..., None] * ab, axis=-1)
    return d.min(1)


def boundary_report(objs, outlines, radius, originals=None):
    """Open (boundary) edges near the feature that are NEW: not on an outline,
    not a border shared with another surface mesh, and not already open in the
    pre-blend mesh (``originals``: {object name: backup mesh}). A clean result
    is 0; anything else is an unexpected hole or tear.
    """
    originals = originals or {}
    from mathutils.kdtree import KDTree
    mids = {}
    for ob in objs:
        bm = _bm_world(ob)
        mids[ob.name] = np.array([tuple((e.verts[0].co + e.verts[1].co) * 0.5)[:2]
                                  for e in bm.edges if e.is_boundary]).reshape(-1, 2)
        bm.free()
    rep = {}
    for name, P in mids.items():
        if not len(P):
            rep[name] = 0
            continue
        near = _zone_mask(P, outlines, radius)
        ok = np.zeros(len(P), dtype=bool)
        for poly in outlines:
            poly = np.asarray(poly, float)
            ok |= nearest_on_outline(P, poly, np.zeros(len(poly)))[0] < 2e-3
        others = np.concatenate([Q for n, Q in mids.items() if n != name and len(Q)] or [np.zeros((0, 2))])
        if len(others):
            kd = KDTree(len(others))
            for i, q in enumerate(others):
                kd.insert((q[0], q[1], 0.0), i)
            kd.balance()
            for i in np.nonzero(near & ~ok)[0]:
                if kd.find((P[i][0], P[i][1], 0.0))[2] < 2e-3:
                    ok[i] = True
        todo = np.nonzero(near & ~ok)[0]
        ob = bpy.data.objects.get(name)
        if len(todo) and ob is not None and originals.get(name) is not None:
            seg = boundary_segments(originals[name], ob.matrix_world)
            ok[todo[_dist_to_segments(P[todo], seg) < 2e-3]] = True
        rep[name] = int(np.count_nonzero(near & ~ok))
    return rep


# ------------------------------------------------------------------ backup/restore

def backup_file(tag):
    """Save an incremental copy of the .blend next to the original. Needs a saved file."""
    path = bpy.data.filepath
    if not path:
        raise RuntimeError("The .blend has never been saved - ask the user to save it first.")
    stem = path[:-6] if path.lower().endswith(".blend") else path
    n = 1
    import os
    while os.path.exists(f"{stem}_pre-{tag}_{n:02d}.blend"):
        n += 1
    out = f"{stem}_pre-{tag}_{n:02d}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True)
    return out


def backup_meshes(objs, tag):
    """Keep a copy of each object's mesh data as an orphan (fake-user) datablock.

    No backup *objects* are created, so OPCD's name-based export can never pick
    them up.
    """
    out = {}
    for ob in objs:
        cp = ob.data.copy()
        cp.name = f"{BACKUP_PREFIX}{tag}_{ob.name}"
        cp.use_fake_user = True
        out[ob.name] = cp.name
    return out


def restore_meshes(mapping):
    restored = []
    for obname, meshname in mapping.items():
        ob = bpy.data.objects.get(obname)
        bak = bpy.data.meshes.get(meshname)
        if ob is None or bak is None:
            continue
        old = ob.data
        orig = old.name
        old.name = orig + "_discard"
        ob.data = bak
        bak.use_fake_user = False
        bak.name = orig
        if old.users == 0:
            bpy.data.meshes.remove(old)
        restored.append(obname)
    return restored


def discard_backups(mapping):
    n = 0
    for meshname in mapping.values():
        me = bpy.data.meshes.get(meshname)
        if me is not None:
            me.use_fake_user = False
            if me.users == 0:
                bpy.data.meshes.remove(me)
                n += 1
    return n


# --------------------------------------------------------------------- finalise

def texel_density(ob, samples=4000):
    """UV units per metre on the object's active UV map (sampled)."""
    me = ob.data
    uv = me.uv_layers.active
    if uv is None or not me.polygons:
        return None
    mw = ob.matrix_world
    rng = np.random.default_rng(0)
    ids = rng.choice(len(me.polygons), size=min(samples, len(me.polygons)), replace=False)
    a3 = a2 = 0.0
    for i in ids:
        p = me.polygons[int(i)]
        if p.loop_total < 3:
            continue
        pts = [mw @ me.vertices[me.loops[li].vertex_index].co for li in p.loop_indices]
        uvs = [uv.data[li].uv for li in p.loop_indices]
        for k in range(1, len(pts) - 1):
            a3 += ((pts[k] - pts[0]).cross(pts[k + 1] - pts[0])).length * 0.5
            a2 += abs((uvs[k] - uvs[0]).cross(uvs[k + 1] - uvs[0])) * 0.5
    if a3 <= 0:
        return None
    return math.sqrt(a2 / a3)


def box_project_uv(ob, uv_name, density):
    """World-space box projection at a given texel density (UV units per metre)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    layer = bm.loops.layers.uv.get(uv_name) or bm.loops.layers.uv.new(uv_name)
    mw = ob.matrix_world
    rot = mw.to_3x3()
    for f in bm.faces:
        n = (rot @ f.normal)
        ax = max(range(3), key=lambda i: abs(n[i]))
        for loop in f.loops:
            w = mw @ loop.vert.co
            if ax == 2:
                u, v = w.x, w.y
            elif ax == 1:
                u, v = w.x, w.z
            else:
                u, v = w.y, w.z
            loop[layer].uv = (u * density, v * density)
    bm.to_mesh(ob.data)
    bm.free()


def match_attributes(src, dst, sample_xy):
    """Give ``src`` (feature) the UV maps, colour attributes, material and
    PaintExclude membership of ``dst`` (surface mesh) so a join is clean."""
    me = src.data
    dme = dst.data
    density = texel_density(dst) or 0.1
    for uvl in dme.uv_layers:
        box_project_uv(src, uvl.name, density)
    # colour attributes: fill with the average colour of dst near the feature
    for ca in dme.color_attributes:
        col = _average_colour(dst, ca, sample_xy) or (1.0, 1.0, 1.0, 1.0)
        a = me.color_attributes.get(ca.name) or me.color_attributes.new(ca.name, ca.data_type, ca.domain)
        n = len(a.data)
        a.data.foreach_set("color", list(col) * n)
    if dme.color_attributes.active_color_name:
        me.color_attributes.active_color = me.color_attributes.get(dme.color_attributes.active_color_name)
    me.materials.clear()
    for m in dme.materials:
        me.materials.append(m)
    for p in me.polygons:
        p.material_index = 0
    if "PaintExclude" in dst.vertex_groups:
        g = src.vertex_groups.get("PaintExclude") or src.vertex_groups.new(name="PaintExclude")
        g.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    return density


def _average_colour(ob, ca, sample_xy, radius=4.0):
    me = ob.data
    mw = ob.matrix_world
    x, y = sample_xy
    vids = [v.index for v in me.vertices
            if (lambda w: (w.x - x) ** 2 + (w.y - y) ** 2 <= radius * radius)(mw @ v.co)]
    if not vids:
        return None
    if ca.domain == 'POINT':
        cols = [tuple(ca.data[i].color) for i in vids]
    else:
        vset = set(vids)
        cols = [tuple(ca.data[li].color) for li, l in enumerate(me.loops) if l.vertex_index in vset]
    if not cols:
        return None
    return tuple(float(c) for c in np.mean(np.array(cols), axis=0))


def join_into(target, objs):
    ensure_object_mode()
    with bpy.context.temp_override(active_object=target, object=target,
                                   selected_objects=[target] + list(objs),
                                   selected_editable_objects=[target] + list(objs)):
        bpy.ops.object.join()

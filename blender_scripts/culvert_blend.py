"""
OPCD Culvert Builder + Terrain Blend  (Blender 4.5)

Adds a precast concrete pipe culvert (default 600 mm bore) with raked-end
headwalls and aprons at the 3D cursor, then reshapes the surrounding OPCD
terrain so it sits in naturally: an outfall ditch cut in front of each
headwall, fill over the barrel to give minimum cover, and terrain tucked
onto the headwall tops.

Usage:
  1. Save the .blend first. The whole run is one Ctrl+Z step, but the terrain
     edits touch several meshes.
  2. Snap the 3D cursor to the ground at the OUTLET (the downstream end).
     Its Z becomes the pipe invert (inside bottom) at the outlet face.
  3. Check CONFIG below, especially DIRECTION_MODE and the object-name hints.
  4. Scripting workspace -> open this file -> Run Script.
  5. Read the "Culvert_Report" text block (Text Editor) for cover, cut/fill
     and warnings.

How it's laid out:
  - DIRECTION_MODE "AUTO" aims the pipe at the nearest cart-path mesh and
    measures across it. The inlet goes INLET_MARGIN_M beyond the far edge.
  - The pipe rises from the outlet at PIPE_GRADE (1 in 100 by default).
  - Headwall width is derived from the batter so the raked wall ends meet
    the ditch side slopes exactly. No wingwalls are needed.
  - Output is a single object, "Concrete_Culvert_600" (material
    "Concrete_Culvert"). The "Concrete" prefix means the markpaintexclude
    recipe op picks it up automatically.
  - The terrain is densified locally first (0.3 m round each end, 0.08 m
    across each headwall face) so the step from ditch bed to wall top lands
    inside the concrete. Shared boundaries between split OPCD meshes are
    split identically on both sides, so no cracks open up.
  - Terrain within PATH_GUARD_* of a cart path isn't moved; the path mesh
    itself is never touched.
  - Every terrain vertex the script moves gets a weight in the vertex group
    "CulvertBlend" (1.0 = moved 150 mm or more). Use it to mask a dirt or
    rough paint pass around the ditches.

The ground is assumed to be Z-up, in metres, with 1 Blender unit = 1 m.
"""

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# =============================================================================
# CONFIG (all lengths in metres)
# =============================================================================

# ---- Pipe ------------------------------------------------------------------
PIPE_BORE_M = 0.600            # internal diameter
PIPE_WALL_M = 0.075            # precast concrete wall at DN600
PIPE_SEGMENTS = 32
PIPE_GRADE = 0.01              # rise per metre from outlet towards inlet
PIPE_PROJECTION_M = 0.10       # barrel stands proud of each headwall face
INVERT_OFFSET_M = 0.0          # shift the outlet invert relative to the cursor Z
                               # (negative = sink the whole culvert)

# ---- Direction and length --------------------------------------------------
DIRECTION_MODE = "AUTO"        # "AUTO"     - towards the nearest cart path
                               # "CURSOR_Y" - along the 3D cursor's local +Y
                               # "HEADING"  - HEADING_DEG, 0 = +Y, clockwise
HEADING_DEG = 0.0
CART_PATH_OBJECT = ""          # force a specific cart-path object by name
CART_PATH_HINTS = ("cartpath", "cart_path", "cart path", "cart", "path")
CART_PATH_FALLBACK_HINTS = ("concrete",)   # only tried if no hint above matches
PATH_SEARCH_RADIUS_M = 40.0
PIPE_LENGTH_M = 0.0            # 0 = auto: across the path + INLET_MARGIN_M
INLET_MARGIN_M = 1.5           # far path edge -> inlet headwall face
BUILD_INLET = True             # headwall, apron and ditch at the upstream end too

# ---- Headwalls and aprons --------------------------------------------------
HEADWALL_THICKNESS_M = 0.20
HEADWALL_SHOULDER_M = 0.30     # flat top extends this far past the pipe OD
HEADWALL_FOOTING_M = 0.30      # wall goes this far below the ditch bed
HEADWALL_END_BURY_M = 0.15     # raked ends run this far into the batter
MIN_COVER_M = 0.30             # soil over the pipe crown; also sets wall height
APRON_LENGTH_M = 1.20
APRON_THICKNESS_M = 0.15

# ---- Terrain blend ---------------------------------------------------------
TERRAIN_OBJECTS = ()           # explicit terrain object names; empty = auto-detect
TERRAIN_EXCLUDE_HINTS = ("concrete", "cart", "path", "tree", "bush", "shrub",
                         "prop", "bridge", "sign", "bench", "water", "culvert",
                         "fence", "building")
BATTER = 1.5                   # side slopes, horizontal per 1 vertical (1:1.5)
DITCH_BED_CLEARANCE_M = 0.25   # ditch bed half-width = pipe OD/2 + this
BED_DROP_M = 0.03              # ditch bed sits this far below the apron top
DITCH_GRADE = 0.02             # bed falls away from the outlet (rises at the inlet)
DITCH_LENGTH_M = 4.0           # full-depth ditch length out from each face
DITCH_RUNOUT_M = 3.0           # then fades into the existing ground over this
FILL_ENABLED = True            # raise low ground over the barrel to MIN_COVER_M
TERRAIN_TUCK_M = 0.02          # terrain sits this far below the headwall top
MAX_REACH_M = 12.0             # hard lateral limit on terrain edits
CREASE_SOFTEN_M = 0.25         # rounds the daylight lines where cut/fill meet the ground
PATH_GUARD_INNER_M = 0.3       # terrain within this of a cart path is never moved...
PATH_GUARD_OUTER_M = 1.5       # ...and edits fade back in by this distance
LOCAL_SUBDIVIDE = True         # densify terrain round each end before shaping
TARGET_EDGE_M = 0.30           # round each end
FACE_EDGE_M = 0.08             # across each headwall face (keep < half the wall thickness)
FACE_BAND_M = 0.60
MAX_SUBDIVIDE_PASSES = 5
BLEND_GROUP = "CulvertBlend"
BLEND_FULL_M = 0.15            # |dz| at which the blend weight reaches 1.0

# ---- Material --------------------------------------------------------------
MATERIAL_NAME = "Concrete_Culvert"
TEXTURE_DIR = ""               # folder with *ALBEDO*, *NORMAL*, *ROUGHNESS*, ...
UV_TILE_M = 2.0                # one texture tile per this many metres

COLLECTION_NAME = "Culverts"
REPORT_TEXT = "Culvert_Report"

# =============================================================================

REPORT = []


def log(msg=""):
    print(msg)
    REPORT.append(msg)


class CulvertError(Exception):
    pass


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def names_of(ob):
    names = [ob.name.lower()]
    if ob.type == 'MESH':
        names += [m.name.lower() for m in ob.data.materials if m]
    return names


def matches(ob, hints):
    return any(h in n for h in hints for n in names_of(ob))


def is_culvert(ob):
    return ob.name.startswith("Concrete_Culvert")


def world_bvh(ob, depsgraph):
    ob_eval = ob.evaluated_get(depsgraph)
    me = ob_eval.to_mesh()
    mw = ob.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ob_eval.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


# -----------------------------------------------------------------------------
# Layout
# -----------------------------------------------------------------------------

class Layout:
    """Plan geometry. Axis t runs from the outlet face (t = 0) to the inlet
    face (t = L) along f; v is the lateral offset along s (right of f)."""


def find_path_objects(scene):
    if CART_PATH_OBJECT:
        ob = bpy.data.objects.get(CART_PATH_OBJECT)
        if ob is None or ob.type != 'MESH':
            raise CulvertError(f"CART_PATH_OBJECT '{CART_PATH_OBJECT}' is not a mesh in this file")
        return [ob]
    pool = [ob for ob in scene.objects
            if ob.type == 'MESH' and ob.visible_get() and not is_culvert(ob)]
    for hints in (CART_PATH_HINTS, CART_PATH_FALLBACK_HINTS):
        found = [ob for ob in pool if matches(ob, [h.lower() for h in hints])]
        if found:
            return found
    return []


def march_across(bvh, start, f, max_dist=80.0, step=0.1):
    """Walk along f from start, ray-casting straight down; return (d, z)
    for each point over the path until we've clearly left it."""
    hits, gap = [], 0.0
    down = Vector((0.0, 0.0, -1.0))
    for i in range(1, int(max_dist / step)):
        d = i * step
        p = start + f * d
        loc, *_ = bvh.ray_cast(Vector((p.x, p.y, start.z + 500.0)), down, 2000.0)
        if loc is not None:
            hits.append((d, loc.z))
            gap = 0.0
        elif hits:
            gap += step
            if gap > 1.0:
                break
    return hits


def plan_layout(scene, depsgraph):
    c = Layout()
    cur = scene.cursor.location.copy()
    if cur.length < 1e-6:
        raise CulvertError("3D cursor is at the world origin - snap it to the outlet first")
    c.O = cur

    path_obs = find_path_objects(scene)
    path_bvhs = [(ob, world_bvh(ob, depsgraph)) for ob in path_obs]

    # Direction
    path_ob = path_bvh = None
    if DIRECTION_MODE == "AUTO":
        best = None
        for ob, bvh in path_bvhs:
            loc, _n, _i, dist = bvh.find_nearest(cur)
            if loc is not None and (best is None or dist < best[3]):
                best = (ob, bvh, loc, dist)
        if best is None or best[3] > PATH_SEARCH_RADIUS_M:
            raise CulvertError(
                "No cart path found within PATH_SEARCH_RADIUS_M of the cursor. "
                "Set CART_PATH_OBJECT, or use DIRECTION_MODE 'CURSOR_Y'/'HEADING' with PIPE_LENGTH_M")
        path_ob, path_bvh, loc, _ = best
        f = Vector((loc.x - cur.x, loc.y - cur.y, 0.0))
        if f.length < 0.05:
            raise CulvertError("Cursor is on the cart path - it must sit at the outlet, off the path")
        f.normalize()
        log(f"Cart path: '{path_ob.name}' (nearest edge {best[3]:.2f} m from cursor)")
    elif DIRECTION_MODE == "CURSOR_Y":
        f = scene.cursor.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
        f.z = 0.0
        if f.length < 1e-6:
            raise CulvertError("Cursor +Y is vertical - rotate the cursor or use HEADING")
        f.normalize()
    elif DIRECTION_MODE == "HEADING":
        a = math.radians(HEADING_DEG)
        f = Vector((math.sin(a), math.cos(a), 0.0))
    else:
        raise CulvertError(f"Unknown DIRECTION_MODE '{DIRECTION_MODE}'")
    c.f = f
    c.s = f.cross(Vector((0.0, 0.0, 1.0))).normalized()

    # Length: measure across the path we're aiming at, or whichever one we cross
    hits = []
    if path_bvh is not None:
        hits = march_across(path_bvh, cur, f)
    else:
        for ob, bvh in path_bvhs:
            hits = march_across(bvh, cur, f)
            if hits:
                path_ob = ob
                log(f"Crosses cart path '{ob.name}'")
                break
    c.path_hits = hits
    c.path_bvhs = [bvh for _ob, bvh in path_bvhs]

    if PIPE_LENGTH_M > 0.0:
        c.L = PIPE_LENGTH_M
    elif hits:
        c.L = hits[-1][0] + INLET_MARGIN_M
        log(f"Path crossed from {hits[0][0]:.2f} m to {hits[-1][0]:.2f} m along the culvert")
    else:
        raise CulvertError("Culvert line doesn't cross a cart path - set PIPE_LENGTH_M")
    if c.L < 2.0 * HEADWALL_THICKNESS_M + 0.5:
        raise CulvertError(f"Culvert length {c.L:.2f} m is too short")

    # Section
    c.R_in = PIPE_BORE_M / 2.0
    c.R_out = c.R_in + PIPE_WALL_M
    c.top_hw = c.R_out + HEADWALL_SHOULDER_M
    c.bed_hw = c.R_out + DITCH_BED_CLEARANCE_M

    c.invert_out = cur.z + INVERT_OFFSET_M
    c.invert_in = c.invert_out + c.L * PIPE_GRADE
    c.top_out = c.invert_out + PIPE_BORE_M + PIPE_WALL_M + MIN_COVER_M

    height = PIPE_BORE_M + 2.0 * PIPE_WALL_M + MIN_COVER_M + BED_DROP_M   # wall top to ditch bed
    c.hw = (BATTER * height + c.top_hw + c.bed_hw) / 2.0 + HEADWALL_END_BURY_M

    c.ends = []
    specs = [("Outlet", 0.0, 1.0, c.invert_out, -1.0)]
    if BUILD_INLET:
        specs.append(("Inlet", c.L, -1.0, c.invert_in, 1.0))
    for name, t0, inward, invert, bed_sign in specs:
        e = Layout()
        e.name, e.t0, e.inward, e.invert, e.bed_sign = name, t0, inward, invert, bed_sign
        e.top = invert + PIPE_BORE_M + PIPE_WALL_M + MIN_COVER_M
        e.apron_top = invert - PIPE_WALL_M
        e.bed = e.apron_top - BED_DROP_M
        e.z_end = e.top - (c.hw - c.top_hw) / BATTER
        c.ends.append(e)

    log(f"Length {c.L:.2f} m face to face, bearing "
        f"{math.degrees(math.atan2(f.x, f.y)) % 360:.1f} deg (0 = +Y, clockwise)")
    log(f"Invert: outlet {c.invert_out:.3f}, inlet {c.invert_in:.3f} (grade 1 in {1 / PIPE_GRADE:.0f})")
    log(f"Headwall {2 * c.hw:.2f} m wide, {height:.2f} m above ditch bed; ditch bed {2 * c.bed_hw:.2f} m wide")

    # Cover under the path
    if hits:
        covers = [(z - (c.invert_out + d * PIPE_GRADE + PIPE_BORE_M + PIPE_WALL_M), d) for d, z in hits]
        cmin, dmin = min(covers)
        log(f"Minimum cover under the path: {cmin:.2f} m (at {dmin:.1f} m)")
        if cmin < MIN_COVER_M:
            log(f"WARNING: cover under the path is below MIN_COVER_M. "
                f"Try INVERT_OFFSET_M = {INVERT_OFFSET_M - (MIN_COVER_M - cmin):.2f}")
    return c


# -----------------------------------------------------------------------------
# Concrete geometry (built in local space, origin = cursor)
# -----------------------------------------------------------------------------

def local(c, t, v, z):
    """Plan coordinates + world Z -> object-local vector."""
    return c.f * t + c.s * v + Vector((0.0, 0.0, z - c.O.z))


def build_pipe(bm, c, uv):
    a0 = local(c, 0.0, 0.0, c.invert_out + c.R_in)
    b0 = local(c, c.L, 0.0, c.invert_in + c.R_in)
    axis = (b0 - a0).normalized()
    A = a0 - axis * PIPE_PROJECTION_M
    B = b0 + axis * PIPE_PROJECTION_M
    length = (B - A).length
    e1 = c.s.copy()
    e2 = e1.cross(axis).normalized()          # "up" in the pipe cross-section
    n = PIPE_SEGMENTS

    def ring(centre, r):
        return [bm.verts.new(centre + r * (math.cos(2 * math.pi * i / n) * e1 +
                                           math.sin(2 * math.pi * i / n) * e2))
                for i in range(n)]

    oA, oB = ring(A, c.R_out), ring(B, c.R_out)
    iA, iB = ring(A, c.R_in), ring(B, c.R_in)
    faces = []

    def tube(ra, rb, r, outward):
        circ = 2 * math.pi * r / UV_TILE_M
        for i in range(n):
            j = (i + 1) % n
            quad = (ra[i], rb[i], rb[j], ra[j]) if outward else (ra[i], ra[j], rb[j], rb[i])
            face = bm.faces.new(quad)
            face.smooth = True
            for loop in face.loops:
                k = ra.index(loop.vert) if loop.vert in ra else rb.index(loop.vert)
                if k == 0 and (i == n - 1):
                    k = n                      # close the seam without wrapping UVs
                at_b = loop.vert in rb
                loop[uv].uv = (circ * k / n, (length if at_b else 0.0) / UV_TILE_M)
            faces.append(face)

    def annulus(ro, ri, centre, facing_b):
        for i in range(n):
            j = (i + 1) % n
            quad = (ro[i], ro[j], ri[j], ri[i]) if facing_b else (ro[i], ri[i], ri[j], ro[j])
            face = bm.faces.new(quad)
            for loop in face.loops:
                d = loop.vert.co - centre
                loop[uv].uv = (d.dot(e1) / UV_TILE_M, d.dot(e2) / UV_TILE_M)
            faces.append(face)

    tube(oA, oB, c.R_out, True)
    tube(iA, iB, c.R_in, False)
    annulus(oA, iA, A, False)
    annulus(oB, iB, B, True)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for rng in (oA, oB, iA, iB):
        for i in range(n):
            e = bm.edges.get((rng[i], rng[(i + 1) % n]))
            if e:
                e.smooth = False
    return faces, A, B, axis


def build_prism(bm, c, profile, t_a, t_b):
    """Extrude a (v, z_world) profile polygon along the axis from t_a to t_b."""
    fa = [bm.verts.new(local(c, t_a, v, z)) for v, z in profile]
    fb = [bm.verts.new(local(c, t_b, v, z)) for v, z in profile]
    faces = [bm.faces.new(fa), bm.faces.new(list(reversed(fb)))]
    m = len(profile)
    for i in range(m):
        j = (i + 1) % m
        faces.append(bm.faces.new((fa[i], fa[j], fb[j], fb[i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def build_headwall_mesh(c, e, cutter_ob, collection):
    foot = e.bed - HEADWALL_FOOTING_M
    profile = [(-c.hw, foot), (c.hw, foot), (c.hw, e.z_end),
               (c.top_hw, e.top), (-c.top_hw, e.top), (-c.hw, e.z_end)]
    bm = bmesh.new()
    build_prism(bm, c, profile, e.t0, e.t0 + e.inward * HEADWALL_THICKNESS_M)
    me = bpy.data.meshes.new("_culvert_tmp_headwall")
    bm.to_mesh(me)
    bm.free()

    tmp = bpy.data.objects.new("_culvert_tmp_headwall", me)
    collection.objects.link(tmp)
    mod = tmp.modifiers.new("hole", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter_ob
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    result = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(me)
    return result


def make_cutter(c, A, B, axis, collection):
    bm = bmesh.new()
    mat = axis.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    mat.translation = (A + B) / 2.0
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=PIPE_SEGMENTS,
                          radius1=c.R_out - 0.004, radius2=c.R_out - 0.004,
                          depth=(B - A).length + 2.0, matrix=mat)
    me = bpy.data.meshes.new("_culvert_tmp_cutter")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("_culvert_tmp_cutter", me)
    collection.objects.link(ob)
    ob.hide_render = True
    return ob


def box_uvs(bm, faces, uv, origin):
    for face in faces:
        nx, ny, nz = (abs(x) for x in face.normal)
        for loop in face.loops:
            p = loop.vert.co + origin
            if nz >= nx and nz >= ny:
                loop[uv].uv = (p.x / UV_TILE_M, p.y / UV_TILE_M)
            elif nx >= ny:
                loop[uv].uv = (p.y / UV_TILE_M, p.z / UV_TILE_M)
            else:
                loop[uv].uv = (p.x / UV_TILE_M, p.z / UV_TILE_M)


def find_texture_maps(folder):
    maps = {}
    if not folder:
        return maps
    folder = bpy.path.abspath(folder)
    if not os.path.isdir(folder):
        log(f"WARNING: TEXTURE_DIR '{folder}' not found - using a plain concrete colour")
        return maps
    exts = (".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".exr")
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(exts):
            continue
        up = fn.upper()
        for key in ("ALBEDO", "NORMAL", "ROUGHNESS", "METALNESS", "AO", "DISPLACEMENT"):
            if key in up and key not in maps:
                if key == "AO" and not any(tok == "AO" for tok in
                                           up.replace("-", "_").replace(".", "_").split("_")):
                    continue
                maps[key] = os.path.join(folder, fn)
    return maps


def get_material():
    mat = bpy.data.materials.get(MATERIAL_NAME)
    if mat is not None:
        log(f"Material '{MATERIAL_NAME}' already exists - reusing it")
        return mat
    mat = bpy.data.materials.new(MATERIAL_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (0.42, 0.41, 0.39, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85

    maps = find_texture_maps(TEXTURE_DIR)
    y = 400
    for key, path in maps.items():
        node = nt.nodes.new("ShaderNodeTexImage")
        node.label = key
        node.location = (-450, y)
        y -= 280
        node.image = bpy.data.images.load(path, check_existing=True)
        node.image.colorspace_settings.name = 'sRGB' if key == "ALBEDO" else 'Non-Color'
        if key == "ALBEDO":
            nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        elif key == "ROUGHNESS":        # white = rough, same as Blender
            nt.links.new(node.outputs["Color"], bsdf.inputs["Roughness"])
        elif key == "METALNESS":
            nt.links.new(node.outputs["Color"], bsdf.inputs["Metallic"])
        elif key == "NORMAL":           # OpenGL (Y+) = Blender's convention
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.location = (-100, -300)
            nt.links.new(node.outputs["Color"], nmap.inputs["Color"])
            nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
        # AO and DISPLACEMENT are loaded for reference/export only
    if maps:
        log(f"Texture maps loaded: {', '.join(maps)}")
    return mat


def build_concrete(c, collection):
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    pipe_faces, A, B, axis = build_pipe(bm, c, uv)

    box_faces = []
    for e in c.ends:
        t_out = e.t0 - e.inward * APRON_LENGTH_M
        profile = [(-c.bed_hw, e.apron_top - APRON_THICKNESS_M), (c.bed_hw, e.apron_top - APRON_THICKNESS_M),
                   (c.bed_hw, e.apron_top), (-c.bed_hw, e.apron_top)]
        box_faces += build_prism(bm, c, profile, e.t0, t_out)

    cutter = make_cutter(c, A, B, axis, collection)
    try:
        for e in c.ends:
            hw_me = build_headwall_mesh(c, e, cutter, collection)
            before = set(bm.faces)
            bm.from_mesh(hw_me)
            box_faces += [fc for fc in bm.faces if fc not in before]
            bpy.data.meshes.remove(hw_me)
    finally:
        cutter_me = cutter.data
        bpy.data.objects.remove(cutter)
        bpy.data.meshes.remove(cutter_me)

    bm.normal_update()
    box_uvs(bm, box_faces, uv, c.O)
    for fc in box_faces:
        fc.smooth = False
    for fc in bm.faces:
        fc.material_index = 0

    name = f"Concrete_Culvert_{round(PIPE_BORE_M * 1000)}"
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(get_material())
    ob = bpy.data.objects.new(name, me)
    ob.location = c.O
    collection.objects.link(ob)
    log(f"Built '{ob.name}': {len(me.vertices)} verts, {len(me.polygons)} faces")
    return ob


# -----------------------------------------------------------------------------
# Terrain
# -----------------------------------------------------------------------------

def plan_coords(c, P):
    d = P[:, :2] - np.array((c.O.x, c.O.y))
    t = d @ np.array((c.f.x, c.f.y))
    v = d @ np.array((c.s.x, c.s.y))
    return t, v


def smooth_max(a, b, k):
    h = np.clip(0.5 + 0.5 * (a - b) / k, 0.0, 1.0)
    return b + (a - b) * h + k * h * (1.0 - h)


def smooth_min(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def target_heights(c, P):
    t, v = plan_coords(c, P)
    av = np.abs(v)
    z0 = P[:, 2]
    z = z0.copy()
    k = np.full(len(P), CREASE_SOFTEN_M)     # creases are only softened against existing ground

    # Fill: flat-topped embankment over the barrel, rounded past the faces
    if FILL_ENABLED:
        tc = np.clip(t, 0.0, c.L)
        zreq = c.top_out + tc * PIPE_GRADE - TERRAIN_TUCK_M
        dist = np.hypot(np.maximum(av - c.top_hw, 0.0), t - tc)
        fill = zreq - dist / BATTER
        z = smooth_max(z, fill, CREASE_SOFTEN_M)
        k = np.maximum(CREASE_SOFTEN_M * (1.0 - np.clip((fill - z0) / CREASE_SOFTEN_M, 0.0, 1.0)), 1e-6)

    # Cut: ditch in front of each face, terrain held at the wall top behind it
    for e in c.ends:
        u = (e.t0 - t) * e.inward                      # outward from the face
        bed = np.where(u <= APRON_LENGTH_M, e.bed,
                       e.bed + e.bed_sign * (u - APRON_LENGTH_M) * DITCH_GRADE)
        ditch = bed + np.hypot(np.maximum(av - c.bed_hw, 0.0), np.maximum(-u, 0.0)) / BATTER
        wall_top = e.top - TERRAIN_TUCK_M - np.maximum(av - c.top_hw, 0.0) / BATTER
        # The step from bed to wall top sits at mid-wall, hidden in the concrete
        behind = -u - HEADWALL_THICKNESS_M - 0.3
        retained = np.where(u < -HEADWALL_THICKNESS_M / 2.0,
                            wall_top + np.maximum(behind, 0.0) / BATTER, -np.inf)
        upper = np.maximum(ditch, retained)
        w = 1.0 - smoothstep(DITCH_LENGTH_M, DITCH_LENGTH_M + DITCH_RUNOUT_M, u)
        z = z - w * np.maximum(z - smooth_min(z, upper, k), 0.0)

    # Hard lateral limit so nothing spreads across the hole
    ext = DITCH_LENGTH_M + DITCH_RUNOUT_M
    lo, hi = -ext, c.L + (ext if BUILD_INLET else 0.0)
    reach = np.hypot(v, t - np.clip(t, lo, hi))
    fade = 1.0 - smoothstep(0.75 * MAX_REACH_M, MAX_REACH_M, reach)
    dz = (z - z0) * fade

    # Leave the cart path's footing alone: it isn't reshaped, so terrain under
    # or beside it must not move or the path ends up floating or buried
    guard = np.ones(len(P))
    if c.path_bvhs:
        for i in np.nonzero(np.abs(dz) > 1e-4)[0]:
            p = Vector(P[i])
            best = PATH_GUARD_OUTER_M
            for bvh in c.path_bvhs:
                hit = bvh.find_nearest(p, PATH_GUARD_OUTER_M)
                if hit[0] is not None:
                    best = min(best, hit[3])
            guard[i] = smoothstep(PATH_GUARD_INNER_M, PATH_GUARD_OUTER_M, np.array(best))
    muted = np.abs(dz) * (1.0 - guard)
    c.guard_muted = max(getattr(c, "guard_muted", 0.0), float(muted.max(initial=0.0)))
    return z0 + dz * guard


def region_bounds(c):
    ext = DITCH_LENGTH_M + DITCH_RUNOUT_M + MAX_REACH_M
    pts = [c.O + c.f * t + c.s * v for t in (-ext, c.L + ext) for v in (-MAX_REACH_M, MAX_REACH_M)]
    xs, ys = [p.x for p in pts], [p.y for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def world_coords(ob):
    me = ob.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    M = np.array(ob.matrix_world)
    return co, co @ M[:3, :3].T + M[:3, 3], M


def terrain_candidates(scene, c):
    x0, x1, y0, y1 = region_bounds(c)
    if TERRAIN_OBJECTS:
        obs = []
        for n in TERRAIN_OBJECTS:
            ob = bpy.data.objects.get(n)
            if ob is None or ob.type != 'MESH':
                log(f"WARNING: terrain object '{n}' not found")
            else:
                obs.append(ob)
        return obs

    hints = [h.lower() for h in TERRAIN_EXCLUDE_HINTS]
    obs = []
    for ob in scene.objects:
        if ob.type != 'MESH' or not ob.visible_get() or is_culvert(ob) or matches(ob, hints):
            continue
        if len(ob.data.polygons) < 8:
            continue
        corners = [ob.matrix_world @ Vector(b) for b in ob.bound_box]
        if (max(p.x for p in corners) < x0 or min(p.x for p in corners) > x1 or
                max(p.y for p in corners) < y0 or min(p.y for p in corners) > y1):
            continue
        me = ob.data
        nrm = np.empty(len(me.polygons) * 3, dtype=np.float32)
        me.polygons.foreach_get("normal", nrm)
        nm = np.array(ob.matrix_world.to_3x3().inverted_safe().transposed())
        nz = (nrm.reshape(-1, 3) @ nm.T)
        nz = nz[:, 2] / np.maximum(np.linalg.norm(nz, axis=1), 1e-9)
        if np.mean(nz > 0.3) < 0.7:
            continue                                   # not ground-like (trees, walls...)
        obs.append(ob)
    return obs


def refine_stages(c):
    """(vertex mask, target edge) per pass group: a general densify round each
    end, then a fine band across each headwall face so the terrain step from
    ditch bed to wall top always lands inside the concrete."""
    radius = max(c.hw, c.bed_hw + 3.0) + DITCH_LENGTH_M + DITCH_RUNOUT_M

    def near_ends(W):
        m = np.zeros(len(W), dtype=bool)
        for e in c.ends:
            p = c.O + c.f * e.t0
            m |= np.hypot(W[:, 0] - p.x, W[:, 1] - p.y) < radius
        return m

    def face_bands(W):
        t, v = plan_coords(c, W)
        m = np.zeros(len(W), dtype=bool)
        for e in c.ends:
            u = (e.t0 - t) * e.inward
            m |= (np.abs(u + HEADWALL_THICKNESS_M / 2.0) < FACE_BAND_M) & (np.abs(v) < c.hw + FACE_BAND_M)
        return m

    return [(near_ends, TARGET_EDGE_M), (face_bands, FACE_EDGE_M)]


def subdivide_region(ob, c):
    """Densify the terrain in stages. Region membership lives in an int vertex
    layer because bmesh ops reallocate vertices (invalidating Python refs);
    the layer survives that and is interpolated onto new midpoints."""
    me = ob.data
    all_tris = all(len(p.vertices) == 3 for p in me.polygons)
    scale = max(ob.matrix_world.to_scale())
    mw = ob.matrix_world
    _co, W, _M = world_coords(ob)

    bm = bmesh.new()
    bm.from_mesh(me)
    n_start = len(bm.verts)
    stage = bm.verts.layers.int.new("_culvert_stage")
    for level, (mask_fn, target) in enumerate(refine_stages(c), start=1):
        if level == 1:
            bm.verts.ensure_lookup_table()
            cand = [bm.verts[i] for i in np.nonzero(mask_fn(W))[0]]
        else:                              # later stages sit inside earlier ones
            prev = [vtx for vtx in bm.verts if vtx[stage] == level - 1]
            cand = [prev[i] for i in np.nonzero(mask_fn(np.array([mw @ vtx.co for vtx in prev]).reshape(-1, 3)))[0]]
        if not cand:
            break
        for vtx in cand:
            vtx[stage] = level
        for _ in range(MAX_SUBDIVIDE_PASSES):
            # Boundary edges are split too: neighbouring OPCD meshes share them and
            # split at the same world-space midpoints, so no cracks open up.
            edges = {e for vtx in bm.verts if vtx[stage] == level for e in vtx.link_edges
                     if e.other_vert(vtx)[stage] == level and e.calc_length() * scale > target}
            if not edges:
                break
            bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=True)
    added = len(bm.verts) - n_start
    if added and all_tris:
        bmesh.ops.triangulate(bm, faces=[fc for fc in bm.faces if len(fc.verts) > 3])
    bm.verts.layers.int.remove(stage)
    if added:
        bm.to_mesh(me)
        me.update()
    bm.free()
    return added


def deform_terrain(scene, c):
    obs = terrain_candidates(scene, c)
    if not obs:
        log("WARNING: no terrain meshes found near the culvert - set TERRAIN_OBJECTS")
        return
    x0, x1, y0, y1 = region_bounds(c)
    for ob in obs:
        if ob.data.shape_keys:
            log(f"WARNING: skipped '{ob.name}' - it has shape keys")
            continue
        if ob.data.users > 1:
            log(f"WARNING: '{ob.name}' shares its mesh with other objects - they will change too")
        added = subdivide_region(ob, c) if LOCAL_SUBDIVIDE else 0

        me = ob.data
        co, W, M = world_coords(ob)
        mask = (W[:, 0] >= x0) & (W[:, 0] <= x1) & (W[:, 1] >= y0) & (W[:, 1] <= y1)
        if not mask.any():
            continue
        Pm = W[mask]
        z_new = target_heights(c, Pm)
        dz = z_new - Pm[:, 2]
        moved = np.abs(dz) > 1e-4
        if not moved.any():
            if added:
                log(f"'{ob.name}': +{added} verts, no height change")
            continue

        Pm[:, 2] = z_new
        Minv = np.linalg.inv(M)
        co[mask] = Pm @ Minv[:3, :3].T + Minv[:3, 3]
        me.vertices.foreach_set("co", co.astype(np.float32).ravel())
        me.update()

        vg = ob.vertex_groups.get(BLEND_GROUP) or ob.vertex_groups.new(name=BLEND_GROUP)
        idx = np.nonzero(mask)[0][moved]
        wts = np.clip(np.abs(dz[moved]) / BLEND_FULL_M, 0.05, 1.0)
        for b in np.unique(np.round(wts, 2)):
            sel = np.round(wts, 2) == b
            vg.add(idx[sel].tolist(), float(b), 'REPLACE')

        log(f"'{ob.name}': {int(moved.sum())} verts moved (+{added} added), "
            f"cut {max(0.0, -dz.min()):.2f} m, fill {max(0.0, dz.max()):.2f} m")


# -----------------------------------------------------------------------------

def main():
    REPORT.clear()
    ctx = bpy.context
    if ctx.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    scene = ctx.scene
    if abs(scene.unit_settings.scale_length - 1.0) > 1e-6:
        log(f"WARNING: unit scale is {scene.unit_settings.scale_length} - script assumes 1 BU = 1 m")

    log(f"=== Culvert DN{round(PIPE_BORE_M * 1000)} at cursor "
        f"({scene.cursor.location.x:.2f}, {scene.cursor.location.y:.2f}, {scene.cursor.location.z:.2f}) ===")
    try:
        c = plan_layout(scene, ctx.evaluated_depsgraph_get())
        coll = bpy.data.collections.get(COLLECTION_NAME)
        if coll is None:
            coll = bpy.data.collections.new(COLLECTION_NAME)
            scene.collection.children.link(coll)
        build_concrete(c, coll)
        deform_terrain(scene, c)
        if getattr(c, "guard_muted", 0.0) > 0.10:
            log(f"WARNING: up to {c.guard_muted:.2f} m of cut/fill was held back next to the cart path. "
                f"Check the path edges; a larger INLET_MARGIN_M moves the inlet clear of the path.")
        log("Done. Ctrl+Z undoes the whole run.")
    except CulvertError as err:
        log(f"ERROR: {err}")
    finally:
        txt = bpy.data.texts.get(REPORT_TEXT) or bpy.data.texts.new(REPORT_TEXT)
        txt.clear()
        txt.write("\n".join(REPORT) + "\n")


if __name__ == "__main__":
    main()

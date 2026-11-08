"""Meloneras Golf Club: clubhouse and cart barn for GSPro (OPCD V4).

Run inside Blender 4.5 with the course file open, or headless:
    blender.exe -b "H:\\Meloneras\\Support_Files\\Blender\\meloneras.blend" --python build_clubhouse.py

What it does
- Builds separate objects, MEL_Clubhouse and MEL_CartBarn, from the
  dimensions in BUILDINGS (metres, local axes: +X along the building, +Y to its "back").
- Places each at SITE[...] (Blender world XY + heading), finds the ground under its footprint
  by ray-casting the meshes in GROUND_OBJECTS (hidden ones too), sets the floor at the highest
  ground point + FLOOR_ABOVE_GROUND, and runs a concrete plinth down to below the lowest point.
- Builds materials from the PBR sets in TEXTURE_ROOT (ALBEDO / NORMAL (OpenGL) / ROUGHNESS
  white = rough / METALNESS / AO), with UVs sized in real-world metres.
- Exports each building to OUT_DIR as <name>.fbx (pivot at the building's floor centre, placed
  at its world position) and <name>_world.fbx (geometry baked in course coordinates, pivot at
  the world origin), writes placement.json, and saves the three objects to Clubhouse.blend.
- Never saves the course .blend itself.

The course file is not touched on disk. If you run it in the open UI, Ctrl+Z or deleting the
"MEL_Clubhouse_Build" collection removes everything it added.
"""
import json
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# ------------------------------------------------------------------ settings
OUT_DIR = r"H:\Meloneras\Support_Files\Buildings\Clubhouse"
TEXTURE_ROOT = os.path.join(OUT_DIR, "Textures")
GROUND_OBJECTS = ["Spline_path383_Concrete_-_Mesh", "Terrain"]  # first hit wins, in this order
FLOOR_ABOVE_GROUND = 0.15     # m: finished floor above the highest ground under the footprint
PLINTH_BELOW_GROUND = 0.5     # m: plinth runs this far below the lowest ground point
EXPORT = True
PAD_CENTRE = (-1357.795, -964.929)   # Spline_path383_Concrete_-_Mesh bbox centre (site survey)
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:  # pasted into Blender's text editor / run over MCP
    SCRIPT_DIR = r"C:\Users\steve\Claude_Code\Blender Scripts\Meloneras\clubhouse"

# Blender world position (metres) and heading (degrees, anticlockwise from +X) of each
# building's local origin. Filled in from the site survey; None = use the 3D cursor.
SITE = {
    "MEL_Clubhouse": {"xy": None, "heading": 0.0},
    "MEL_CartBarn": {"xy": None, "heading": 0.0},
}

# material name -> (texture set folder, metres covered by one texture tile, flat colour fallback)
MATERIALS = {
    "MEL_RoofTile": ("MEL_CH_RoofTerracotta", 2.5, (0.62, 0.32, 0.22)),
    "MEL_Timber": ("MEL_CH_TimberCladding", 1.6, (0.22, 0.13, 0.08)),
    "MEL_Stone": ("MEL_CH_StoneCladding", 2.0, (0.42, 0.33, 0.27)),
    "MEL_Render": ("MEL_CH_Render", 3.0, (0.85, 0.83, 0.78)),
    "MEL_RenderGreen": ("Meloneras_GreenRender", 3.0, (0.47, 0.53, 0.42)),
    "MEL_Paving": ("MEL_CH_Paving", 2.4, (0.5, 0.48, 0.45)),
    "MEL_Concrete": ("Meloneras_Concrete", 3.0, (0.55, 0.54, 0.52)),
    "MEL_Alu": ("MEL_CH_BrushedAlu", 1.0, (0.7, 0.7, 0.72)),
    "MEL_Steel": ("Meloneras_PaintedSteel", 1.0, (0.16, 0.11, 0.08)),
    "MEL_Glass": ("Meloneras_Glass", 2.0, (0.8, 0.86, 0.88)),
    "MEL_Interior": (None, 1.0, (0.04, 0.035, 0.03)),
    "MEL_Hedge": ("Meloneras_Hedge", 2.0, (0.13, 0.25, 0.08)),
    "MEL_Picon": ("Meloneras_Picon", 2.0, (0.33, 0.13, 0.08)),
    "MEL_GravelLight": ("Meloneras_GravelLight", 2.0, (0.62, 0.55, 0.45)),
    "MEL_LineWhite": (None, 1.0, (0.78, 0.78, 0.76)),
}


# ------------------------------------------------------------------ geometry kit
class Kit:
    """Collects faces into one bmesh with per-face material indices."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def face(self, pts, mat):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.mi(mat)
        return f

    def box(self, x0, x1, y0, y1, z0, z1, mat, skip=()):
        """Axis-aligned box. skip: any of 'top','bottom','n','s','e','w'."""
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        sides = {
            "bottom": (0, 3, 2, 1), "top": (4, 5, 6, 7),
            "s": (0, 1, 5, 4), "e": (1, 2, 6, 5), "n": (2, 3, 7, 6), "w": (3, 0, 4, 7),
        }
        for k, idx in sides.items():
            if k not in skip:
                self.face([c[i] for i in idx], mat)

    def post(self, x, y, z0, z1, w, mat):
        self.box(x - w / 2, x + w / 2, y - w / 2, y + w / 2, z0, z1, mat, skip=("bottom",))

    def slab(self, pts_top, thick, mat, edge_mat=None):
        """Closed slab from a convex top polygon (CCW from above), extruded down along -Z."""
        edge_mat = edge_mat or mat
        top = [Vector(p) for p in pts_top]
        bot = [p - Vector((0, 0, thick)) for p in top]
        self.face(top, mat)
        self.face(list(reversed(bot)), edge_mat)
        n = len(top)
        for i in range(n):
            j = (i + 1) % n
            self.face([bot[i], bot[j], top[j], top[i]], edge_mat)

    def wall_with_openings(self, axis, fixed, a0, a1, z0, z1, openings, mat, out_sign, thick=0.2,
                           recess_mat="MEL_Interior", glass=None):
        """A wall in the plane axis=fixed ('x' or 'y'), spanning a0..a1 and z0..z1.
        openings: list of (b0, b1, h0, h1, kind) with kind 'glass' (pane + dark recess),
        'door' (dark recess) or 'void' (open). out_sign: +1/-1, the side the outer face looks."""
        # split the outer face into a grid around the openings
        bs = sorted({a0, a1, *[o[0] for o in openings], *[o[1] for o in openings]})
        hs = sorted({z0, z1, *[o[2] for o in openings], *[o[3] for o in openings]})

        def P(b, h, off=0.0):
            f = fixed + out_sign * off
            return (f, b, h) if axis == "x" else (b, f, h)

        def inside(bm_, hm_):
            for o in openings:
                if o[0] <= bm_ <= o[1] and o[2] <= hm_ <= o[3]:
                    return o
            return None

        flip = (axis == "y") == (out_sign > 0)
        for i in range(len(bs) - 1):
            for k in range(len(hs) - 1):
                bmid, hmid = (bs[i] + bs[i + 1]) / 2, (hs[k] + hs[k + 1]) / 2
                if inside(bmid, hmid):
                    continue
                q = [P(bs[i], hs[k]), P(bs[i + 1], hs[k]), P(bs[i + 1], hs[k + 1]), P(bs[i], hs[k + 1])]
                self.face(list(reversed(q)) if flip else q, mat)
        for (b0, b1, h0, h1, kind) in openings:
            depth = thick
            # reveals
            for (pa, pb) in (((b0, h0), (b1, h0)), ((b1, h0), (b1, h1)), ((b1, h1), (b0, h1)), ((b0, h1), (b0, h0))):
                q = [P(*pa), P(*pb), P(*pb, off=-depth), P(*pa, off=-depth)]
                self.face(list(reversed(q)) if flip else q, mat if kind != "void" else mat)
            if kind in ("glass", "door"):
                back = [P(b0, h0, -depth), P(b1, h0, -depth), P(b1, h1, -depth), P(b0, h1, -depth)]
                self.face(list(reversed(back)) if flip else back, recess_mat)
            if kind == "glass":
                g = [P(b0, h0, -0.06), P(b1, h0, -0.06), P(b1, h1, -0.06), P(b0, h1, -0.06)]
                self.face(list(reversed(g)) if flip else g, "MEL_Glass")
                # mullions every ~1.5 m
                n = max(1, round((b1 - b0) / 1.5))
                for m in range(1, n):
                    bb = b0 + (b1 - b0) * m / n
                    if axis == "x":
                        self.box(fixed + out_sign * -0.08 - 0.03, fixed + out_sign * -0.08 + 0.03, bb - 0.03, bb + 0.03, h0, h1, "MEL_Steel")
                    else:
                        self.box(bb - 0.03, bb + 0.03, fixed + out_sign * -0.08 - 0.03, fixed + out_sign * -0.08 + 0.03, h0, h1, "MEL_Steel")

    def gable_roof_y(self, x0, x1, y0, y1, eave_z, ridge_z, thick, mat, under_mat):
        """Gable roof with the ridge along Y at x=(x0+x1)/2, covering x0..x1, y0..y1."""
        xm = (x0 + x1) / 2
        for (xa, xb) in ((x0, xm), (x1, xm)):
            s = 1 if xb > xa else -1
            top = [(xa, y0, eave_z), (xb, y0, ridge_z), (xb, y1, ridge_z), (xa, y1, eave_z)]
            if s < 0:
                top = [top[3], top[2], top[1], top[0]]
            self._roof_plane(top, thick, mat, under_mat)
        self._ridge_cap_y(xm, y0, y1, ridge_z)

    def gable_roof_x(self, x0, x1, y0, y1, eave_z, ridge_z, thick, mat, under_mat):
        ym = (y0 + y1) / 2
        for (ya, yb) in ((y0, ym), (y1, ym)):
            top = [(x0, ya, eave_z), (x1, ya, eave_z), (x1, yb, ridge_z), (x0, yb, ridge_z)]
            if yb < ya:
                top = [top[1], top[0], top[3], top[2]]
            self._roof_plane(top, thick, mat, under_mat)
        self.box(x0, x1, ym - 0.13, ym + 0.13, ridge_z - 0.02, ridge_z + 0.12, mat, skip=("bottom",))

    def _ridge_cap_y(self, xm, y0, y1, z):
        self.box(xm - 0.13, xm + 0.13, y0, y1, z - 0.02, z + 0.12, "MEL_RoofTile", skip=("bottom",))

    def _roof_plane(self, top, thick, mat, under_mat):
        top = [Vector(p) for p in top]
        bot = [p - Vector((0, 0, thick)) for p in top]
        self.face(top, mat)
        self.face(list(reversed(bot)), under_mat)
        for i in range(4):
            j = (i + 1) % 4
            self.face([bot[i], bot[j], top[j], top[i]], "MEL_Timber")

    def pyramid_roof(self, cx, cy, half, eave_z, apex_z, thick, mat, under_mat):
        c = [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)]
        apex = Vector((cx, cy, apex_z))
        for i in range(4):
            a, b = c[i], c[(i + 1) % 4]
            pa, pb = Vector((*a, eave_z)), Vector((*b, eave_z))
            self.face([pa, pb, apex], mat)
            self.face([pb - Vector((0, 0, thick)), pa - Vector((0, 0, thick)), apex - Vector((0, 0, thick))], under_mat)
            self.face([pa - Vector((0, 0, thick)), pb - Vector((0, 0, thick)), pb, pa], "MEL_Timber")
        self.box(cx - 0.12, cx + 0.12, cy - 0.12, cy + 0.12, apex_z - 0.05, apex_z + 0.15, "MEL_RoofTile", skip=("bottom",))

    def finish(self, recalc=True):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(get_material(m))
        world_uvs(me)
        for p in me.polygons:
            p.use_smooth = False
        return me


def world_uvs(me):
    """Planar UVs per face in real metres / tile size. Walls: U horizontal, V up.
    Roofs: U along the eave, V up the slope. Floors: U = X, V = Y."""
    uv = me.uv_layers.new(name="UVMap")
    Z = Vector((0, 0, 1))
    for p in me.polygons:
        mat = me.materials[p.material_index]
        tile = MATERIALS.get(mat.name, (None, 2.0))[1] if mat else 2.0
        n = p.normal
        if abs(n.z) > 0.97:
            u_ax, v_ax = Vector((1, 0, 0)), Vector((0, 1 if n.z > 0 else -1, 0))
        else:
            u_ax = Z.cross(n).normalized()
            v_ax = n.cross(u_ax).normalized()
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.dot(u_ax) / tile, co.dot(v_ax) / tile)


# ------------------------------------------------------------------ materials
def _img(path, colour):
    if not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    if not colour:
        im.colorspace_settings.name = "Non-Color"
    return im


def get_material(name):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    folder, tile, flat = MATERIALS[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*flat, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.8
    if name == "MEL_Glass":
        bsdf.inputs["Roughness"].default_value = 0.05
        bsdf.inputs["Alpha"].default_value = 0.25
        mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
    if not folder:
        return mat
    base = os.path.join(TEXTURE_ROOT, folder, folder + "_")
    if not os.path.exists(base + "ALBEDO.png"):
        base = os.path.join(TEXTURE_ROOT, folder + "_")  # flat layout fallback
    x = -700
    alb = _img(base + "ALBEDO.png", True)
    if alb:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = alb; t.location = (x, 300)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        if name == "MEL_Glass":
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
    rgh = _img(base + "ROUGHNESS.png", False)
    if rgh:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = rgh; t.location = (x, 0)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Roughness"])
    met = _img(base + "METALNESS.png", False)
    if met:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = met; t.location = (x, -280)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Metallic"])
    nrm = _img(base + "NORMAL.png", False)
    if nrm:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = nrm; t.location = (x, -560)
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (x + 300, -560)
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ------------------------------------------------------------------ buildings
def build_clubhouse():
    """Main clubhouse (blue). Local origin: centre of the main hall floor.
    +X runs along the road (ESE), -Y faces the road and the terrace, +Y the car park."""
    k = Kit("MEL_Clubhouse")
    T, TL, ST, GR, IN = "MEL_Timber", "MEL_RoofTile", "MEL_Stone", "MEL_RenderGreen", "MEL_Interior"
    # --- main hall 12 x 14 m, gable ridge along Y, deep open gables at both ends
    hx0, hx1, hy0, hy1 = -6.0, 6.0, -7.0, 7.0
    eave, pitch = 3.4, math.radians(24)
    ov = 0.8
    ridge = eave + ((hx1 - hx0) / 2) * math.tan(pitch)
    k.wall_with_openings("y", hy1, hx0, hx1, 0, eave, [(-1.6, 1.6, 0, 2.6, "glass"), (2.8, 5.2, 0.9, 2.4, "glass")], T, +1)
    k.wall_with_openings("y", hy0, hx0, hx1, 0, eave, [(-5.6, 5.6, 0.0, 3.0, "glass")], T, -1)
    k.wall_with_openings("x", hx0, hy0, hy1, 0, eave, [], T, -1)
    for y, s in ((hy1, 1), (hy0, -1)):
        tri = [(hx0, y, eave), (hx1, y, eave), (0, y, ridge - 0.05)]
        k.face(tri if s < 0 else list(reversed(tri)), T)
    k.face([(hx0, hy0, eave), (hx1, hy0, eave), (hx1, hy1, eave), (hx0, hy1, eave)][::-1], IN)
    k.gable_roof_y(hx0 - ov, hx1 + ov, hy0 - 3.2, hy1 + 2.6, eave - ov * math.tan(pitch), ridge, 0.22, TL, T)
    for y in (hy0 - 3.0, hy1 + 2.4):
        for x in (-5.0, -1.7, 1.7, 5.0):
            k.post(x, y, 0, eave - 0.3, 0.28, T)
        k.box(hx0 - 0.6, hx1 + 0.6, y - 0.14, y + 0.14, eave - 0.6, eave - 0.3, T)
        k.box(-0.15, 0.15, y - 0.14, y + 0.14, eave - 0.3, ridge - 0.3, T)   # king post in the open gable
    k.box(-0.15, 0.15, hy0 - 3.2, hy1 + 2.6, ridge - 0.55, ridge - 0.22, T)  # ridge beam
    # --- east wing (restaurant) 12 x 13 m, ridge along X, lower eave, fully glazed to the terrace
    ex0, ex1, ey0, ey1 = hx1, 17.0, -6.0, 7.0
    e_eave, e_pitch = 3.0, math.radians(22)
    e_ridge = e_eave + (ey1 - ey0) / 2 * math.tan(e_pitch)
    k.wall_with_openings("y", ey0, ex0, ex1, 0, e_eave, [(ex0 + 0.4, ex1 - 0.4, 0.0, 2.7, "glass")], T, -1)
    k.wall_with_openings("y", ey1, ex0, ex1, 0, e_eave, [(8.0, 10.0, 0.9, 2.2, "glass"), (13.0, 15.0, 0, 2.2, "door")], T, +1)
    k.wall_with_openings("x", ex1, ey0, ey1, 0, e_eave, [(-3.5, 3.5, 0.9, 2.4, "glass")], T, +1)
    g = [(ex1, ey0, e_eave), (ex1, ey1, e_eave), (ex1, (ey0 + ey1) / 2, e_ridge - 0.05)]
    k.face(g, T)
    k.face([(ex0, ey0, e_eave), (ex1, ey0, e_eave), (ex1, ey1, e_eave), (ex0, ey1, e_eave)][::-1], IN)
    k.gable_roof_x(ex0 - 0.5, ex1 + 0.6, ey0 - 0.6, ey1 + 0.6, e_eave - 0.6 * math.tan(e_pitch), e_ridge, 0.2, TL, T)
    # --- west service wing 5 x 15 m, mono-pitch falling west; stone west wall, green render south
    wx0, wx1, wy0, wy1 = -11.0, hx0, -7.0, 8.0
    wh_lo, wh_hi = 2.8, 3.3
    k.wall_with_openings("x", wx0, wy0, wy1, 0, wh_lo, [], ST, -1, thick=0.3)
    k.wall_with_openings("y", wy0, wx0, wx1, 0, wh_lo, [(-9.6, -7.4, 0.9, 2.2, "glass")], GR, -1)
    k.wall_with_openings("y", wy1, wx0, wx1, 0, wh_lo, [(-10.0, -8.4, 0, 2.2, "door")], T, +1)
    k.box(wx0 - 0.05, wx0 + 0.85, wy0 - 0.45, wy0 + 0.05, 0, 3.5, ST, skip=("bottom",))   # stone pier
    k.box(wx0 - 0.1, wx0 + 0.9, wy0 - 0.5, wy0 + 0.1, 3.5, 3.65, "MEL_Concrete", skip=("bottom",))
    k.face([(wx0, wy0, wh_lo), (wx1, wy0, wh_lo), (wx1, wy1, wh_lo), (wx0, wy1, wh_lo)][::-1], IN)
    k._roof_plane([(wx0 - 0.5, wy0 - 0.5, wh_lo + 0.05), (wx1, wy0 - 0.5, wh_hi + 0.25),
                   (wx1, wy1 + 0.5, wh_hi + 0.25), (wx0 - 0.5, wy1 + 0.5, wh_lo + 0.05)], 0.2, TL, T)
    k.box(-10.2, -9.6, 5.5, 6.1, 2.9, 4.4, "MEL_Steel", skip=("bottom",))   # flue
    # --- terrace slab, pergola over the restaurant front, glass screens, planter kerb
    tx0, tx1, ty0 = -11.0, 18.0, -15.0
    k.slab([(tx0, ty0, 0), (tx1, ty0, 0), (tx1, hy0 - 0.001, 0), (tx0, hy0 - 0.001, 0)], 0.15, "MEL_Paving", "MEL_Concrete")
    k.slab([(hx1, hy0, 0), (tx1, hy0, 0), (tx1, ey0 - 0.001, 0), (hx1, ey0 - 0.001, 0)], 0.15, "MEL_Paving", "MEL_Concrete")
    px0, px1, py0, py1 = 7.0, 16.8, -12.5, -6.6
    for x in (px0, (px0 + px1) / 2, px1):
        k.post(x, py0, 0, 2.8, 0.14, "MEL_Steel")
    k.box(px0 - 0.3, px1 + 0.3, py0 - 0.07, py0 + 0.07, 2.8, 3.0, "MEL_Steel")
    k.box(px0 - 0.3, px1 + 0.3, py1 - 0.07, py1 + 0.07, 2.8, 3.0, "MEL_Steel")      # wall plate
    n = int((px1 - px0 + 0.6) / 0.45)
    for i in range(n + 1):
        x = px0 - 0.3 + i * (px1 - px0 + 0.6) / n
        k.box(x - 0.04, x + 0.04, py0 - 0.4, py1, 3.0, 3.14, "MEL_Steel")

    def screen(p0, p1):
        p0, p1 = Vector(p0), Vector(p1)
        L = (p1 - p0).length
        m = max(1, round(L / 1.4))
        d = (p1 - p0) / m
        for i in range(m + 1):
            q = p0 + d * i
            k.post(q.x, q.y, 0, 1.5, 0.07, "MEL_Alu")
        for i in range(m):
            a, b = p0 + d * i, p0 + d * (i + 1)
            k.face([(a.x, a.y, 0.1), (b.x, b.y, 0.1), (b.x, b.y, 1.4), (a.x, a.y, 1.4)], "MEL_Glass")
            k.face([(b.x, b.y, 0.1), (a.x, a.y, 0.1), (a.x, a.y, 1.4), (b.x, b.y, 1.4)], "MEL_Glass")
    screen((tx0 + 1.2, ty0 + 0.3), (tx1 - 0.3, ty0 + 0.3))
    screen((tx1 - 0.3, ty0 + 0.3), (tx1 - 0.3, ey0 - 0.3))
    screen((tx0 + 1.2, ty0 + 0.3), (tx0 + 1.2, wy0 - 0.6))
    # hedge planter outside the screens (the hibiscus line in the street views)
    k.box(tx0 + 0.6, tx1 + 0.3, ty0 - 1.0, ty0 + 0.0, 0, 0.35, "MEL_Stone")
    k.box(tx0 + 0.7, tx1 + 0.2, ty0 - 0.9, ty0 - 0.1, 0.35, 1.0, "MEL_Hedge", skip=("bottom",))
    # entrance apron on the car-park side
    k.slab([(wx0, hy1 + 0.001, 0), (hx1 + 0.5, hy1 + 0.001, 0), (hx1 + 0.5, hy1 + 3.5, 0), (wx0, hy1 + 3.5, 0)],
           0.15, "MEL_Paving", "MEL_Concrete")
    footprint = [(tx0, ty0 - 1.0), (tx1 + 0.6, ty0 - 1.0), (tx1 + 0.6, ey1 + 0.6), (wx0, hy1 + 3.5)]
    return k, footprint


def build_cart_barn():
    """Cart barn (green). 42 x 6 m, open along -Y towards the service yard, stone back wall
    along +Y, and the white-capped boundary wall 3 m behind it."""
    k = Kit("MEL_CartBarn")
    T, TL, ST = "MEL_Timber", "MEL_RoofTile", "MEL_Stone"
    x0, x1, y0, y1 = -21.0, 21.0, -3.0, 3.0
    eave, pitch = 2.8, math.radians(20)
    ridge = eave + (y1 - y0) / 2 * math.tan(pitch)
    k.slab([(x0 - 0.5, y0 - 1.0, 0), (x1 + 0.5, y0 - 1.0, 0), (x1 + 0.5, y1 + 0.3, 0), (x0 - 0.5, y1 + 0.3, 0)], 0.15, "MEL_Concrete")
    k.box(x0, x1, y1 - 0.3, y1, 0, eave, ST)                                      # back wall
    for x in (x0, x1):                                                             # timber end walls
        k.box(x - 0.15, x + 0.15, y0 + 0.4, y1 - 0.3, 0, eave, T)
        gt = [(x, y0 + 0.4, eave), (x, y1 - 0.3, eave), (x, (y0 + y1) / 2, ridge - 0.2)]
        k.face(gt if x == x1 else list(reversed(gt)), T)
        k.face(list(reversed(gt)) if x == x1 else gt, "MEL_Interior")
    for i in range(15):                                                            # front posts every 3 m
        k.post(x0 + i * 3.0, y0 + 0.2, 0, eave - 0.3, 0.16, "MEL_Steel")
    k.box(x0, x1, y0 + 0.08, y0 + 0.32, eave - 0.3, eave, T)                      # front beam
    k.box(x0 - 0.5, x1 + 0.5, y0 - 0.62, y0 - 0.56, eave - 0.75, eave - 0.05, "MEL_RenderGreen")  # green valance
    k.gable_roof_x(x0 - 0.5, x1 + 0.5, y0 - 0.6, y1 + 0.6, eave - 0.6 * math.tan(pitch), ridge, 0.2, TL, T)
    k.face([(x0 + 0.15, y1 - 0.31, 0.01), (x1 - 0.15, y1 - 0.31, 0.01), (x1 - 0.15, y1 - 0.31, eave), (x0 + 0.15, y1 - 0.31, eave)], "MEL_Interior")
    # boundary wall behind the barn, rendered with a pale cap, returning along the north end
    k.box(x0 - 1.0, x1 + 1.5, 5.9, 6.2, -0.2, 2.2, "MEL_Render", skip=("bottom",))
    k.box(x0 - 1.05, x1 + 1.55, 5.85, 6.25, 2.2, 2.3, "MEL_Concrete", skip=("bottom",))
    k.box(x1 + 1.2, x1 + 1.5, y1 + 0.3, 5.9, -0.2, 2.2, "MEL_Render", skip=("bottom",))
    footprint = [(x0 - 1.0, y0 - 1.0), (x1 + 1.5, y0 - 1.0), (x1 + 1.5, 6.25), (x0 - 1.0, 6.25)]
    return k, footprint


# ------------------------------------------------------------------ terrain fit
def ground_bvhs():
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for name in GROUND_OBJECTS:
        ob = bpy.data.objects.get(name)
        if not ob or ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        bm = bmesh.new(); bm.from_mesh(me); bm.transform(ob.matrix_world)
        out.append((name, BVHTree.FromBMesh(bm)))
        bm.free(); ev.to_mesh_clear()
    return out


def ground_z(bvhs, x, y):
    for name, t in bvhs:
        hit = t.ray_cast(Vector((x, y, 2000.0)), Vector((0, 0, -1)))
        if hit[0] is not None:
            return hit[0].z, name
    return None, None


def sample_footprint(bvhs, M, footprint, step=1.0):
    xs = [p[0] for p in footprint]; ys = [p[1] for p in footprint]
    zs, srcs = [], set()
    x = min(xs)
    while x <= max(xs) + 1e-6:
        y = min(ys)
        while y <= max(ys) + 1e-6:
            w = M @ Vector((x, y, 0))
            z, src = ground_z(bvhs, w.x, w.y)
            if z is not None:
                zs.append(z); srcs.add(src)
            y += step
        x += step
    return zs, sorted(srcs)


def add_plinth(k, footprint, depth):
    """Concrete skirt from floor level down `depth` around the footprint's bounding box."""
    xs = [p[0] for p in footprint]; ys = [p[1] for p in footprint]
    k.box(min(xs), max(xs), min(ys), max(ys), -depth, -0.15, "MEL_Concrete", skip=("top",))


# ------------------------------------------------------------------ car park markings and planters
PLANTER_MAT = {"picon": "MEL_Picon", "island_light": "MEL_GravelLight", "walkway": "MEL_Paving", "hedge": "MEL_Picon"}
MARK_LIFT = 0.02   # m: line paint sits this far above the pad (stops z-fighting in Unity)


def _drape(bvhs, x, y, fallback):
    z, _ = ground_z(bvhs, x, y) if bvhs else (None, None)
    return fallback if z is None else z


def _densify(poly, step):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = Vector(poly[i]), Vector(poly[(i + 1) % n])
        m = max(1, int((b - a).length / step))
        for j in range(m):
            out.append(a.lerp(b, j / m))
    return out


def build_markings(layout, bvhs, origin):
    """White line paint as thin draped quads, one object for the whole car park."""
    k = Kit("MEL_CarParkMarkings")
    ox, oy, oz = origin
    for quad in layout["markings"]:
        a, b, c, d = [Vector(p) for p in quad]
        L = max((b - a).length, (c - b).length)
        along_ab = (b - a).length >= (c - b).length
        m = max(1, int(L / 1.0))
        rows = []
        for j in range(m + 1):
            t = j / m
            p0, p1 = (a.lerp(b, t), d.lerp(c, t)) if along_ab else (a.lerp(d, t), b.lerp(c, t))
            rows.append([(p.x - ox, p.y - oy, _drape(bvhs, p.x, p.y, oz) - oz + MARK_LIFT) for p in (p0, p1)])
        for j in range(m):
            q = [rows[j][0], rows[j + 1][0], rows[j + 1][1], rows[j][1]] if along_ab else \
                [rows[j][0], rows[j][1], rows[j + 1][1], rows[j + 1][0]]
            f = k.face(q, "MEL_LineWhite")
            if f.normal.z < 0:
                f.normal_flip()
    return k


def build_planters(layout, bvhs, origin):
    """Raised planters and islands: kerbed edge (concrete) with picón, gravel, paving or hedge."""
    k = Kit("MEL_Planters")
    ox, oy, oz = origin
    for pl in layout["planters"]:
        poly = _densify(pl["poly"], 2.0)
        h = pl.get("height", 0.15)
        ring = []
        for p in poly:
            g = _drape(bvhs, p.x, p.y, oz) - oz
            ring.append((Vector((p.x - ox, p.y - oy, g + h)), Vector((p.x - ox, p.y - oy, g - 0.2))))
        top = k.face([t for t, _ in ring], PLANTER_MAT[pl["kind"]])
        if top.normal.z < 0:
            top.normal_flip()
            ring.reverse()
        n = len(ring)
        for i in range(n):
            t0, b0 = ring[i]; t1, b1 = ring[(i + 1) % n]
            k.face([b0, b1, t1, t0], "MEL_Concrete")
        if pl["kind"] == "hedge":
            c = sum((t for t, _ in ring), Vector()) / n
            inner = [c + (t - c) * 0.8 for t, _ in ring]
            hz = 0.9
            tf = k.face([v + Vector((0, 0, hz)) for v in inner], "MEL_Hedge")
            for i in range(n):
                a, b = inner[i], inner[(i + 1) % n]
                k.face([a, b, b + Vector((0, 0, hz)), a + Vector((0, 0, hz))], "MEL_Hedge")
    return k


# ------------------------------------------------------------------ main
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    coll = bpy.data.collections.get("MEL_Clubhouse_Build") or bpy.data.collections.new("MEL_Clubhouse_Build")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bvhs = ground_bvhs()
    report = {}
    cursor = bpy.context.scene.cursor.location
    layout = load_layout()
    for name, b in layout["buildings"].items():
        if name in SITE and SITE[name]["xy"] is None:
            SITE[name]["xy"] = tuple(b["xy"])
            SITE[name]["heading"] = b["heading"]
    for name, fn in (("MEL_Clubhouse", build_clubhouse), ("MEL_CartBarn", build_cart_barn)):
        site = SITE[name]
        xy = site["xy"] or (cursor.x, cursor.y)
        rot = math.radians(site["heading"])
        M = Matrix.Translation((xy[0], xy[1], 0)) @ Matrix.Rotation(rot, 4, "Z")
        k, fp = fn()
        zs, srcs = sample_footprint(bvhs, M, fp) if bvhs else ([], [])
        if zs:
            floor = max(zs) + FLOOR_ABOVE_GROUND if site.get("floor_z") is None else site["floor_z"]
            depth = floor - min(zs) + PLINTH_BELOW_GROUND
        else:
            floor = site.get("floor_z") or cursor.z
            depth = 1.0
        add_plinth(k, fp, depth)
        me = k.finish()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.matrix_world = Matrix.Translation((xy[0], xy[1], floor)) @ Matrix.Rotation(rot, 4, "Z")
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        report[name] = {
            "blender_xy": [round(xy[0], 3), round(xy[1], 3)], "heading_deg": site["heading"],
            "floor_z": round(floor, 3), "plinth_depth": round(depth, 3),
            "ground_min": round(min(zs), 3) if zs else None, "ground_max": round(max(zs), 3) if zs else None,
            "ground_sources": srcs, "tris": tris,
        }
        print(name, report[name])
    # markings and planters share one origin: the pad centre at ground level
    pc = PAD_CENTRE
    oz = _drape(bvhs, pc[0], pc[1], cursor.z)
    for name, fn in (("MEL_CarParkMarkings", build_markings), ("MEL_Planters", build_planters)):
        k = fn(layout, bvhs, (pc[0], pc[1], oz))
        me = k.finish(recalc=False)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.location = (pc[0], pc[1], oz)
        report[name] = {"blender_xyz": [round(pc[0], 3), round(pc[1], 3), round(oz, 3)],
                        "tris": sum(len(p.vertices) - 2 for p in me.polygons)}
        print(name, report[name])
    if EXPORT:
        export_all(coll, report)
    return report


def load_layout():
    import importlib.util
    path = os.path.join(SCRIPT_DIR, "site_layout.py")
    spec = importlib.util.spec_from_file_location("site_layout", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.layout()


def export_all(coll, report):
    for ob in coll.objects:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        common = dict(use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                      apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y",
                      bake_space_transform=True, mesh_smooth_type="FACE", use_mesh_modifiers=True,
                      path_mode="RELATIVE", embed_textures=False, add_leaf_bones=False)
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_DIR, ob.name + ".fbx"), **common)
        # world variant: geometry in course coordinates, pivot at the world origin
        saved = ob.matrix_world.copy()
        ob.data.transform(saved)
        ob.matrix_world = Matrix.Identity(4)
        bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_DIR, ob.name + "_world.fbx"), **common)
        ob.data.transform(saved.inverted())
        ob.matrix_world = saved
    with open(os.path.join(OUT_DIR, "placement.json"), "w") as f:
        json.dump(report, f, indent=2)
    bpy.data.libraries.write(os.path.join(OUT_DIR, "Clubhouse.blend"), set(coll.objects), fake_user=True,
                             path_remap="RELATIVE_ALL")


if __name__ == "__main__":
    main()

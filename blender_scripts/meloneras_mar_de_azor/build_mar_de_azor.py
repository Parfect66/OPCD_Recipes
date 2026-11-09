"""Meloneras: the informal houses on C. Mar de Azor (Pedrazo Bajo), behind the 1st and 4th
greens, for GSPro (OPCD V4). Background scenery: modest detail.

Run headless on the course file (never saved):
    blender.exe -b "H:\\Meloneras\\Support_Files\\Blender\\meloneras.blend" --python build_mar_de_azor.py

What it does
- FOOTPRINTS holds 34 buildings traced from a Google aerial of the site (pixels in that image,
  1426 x 1360, north up). FIT maps those pixels to course metres, registered against the
  course's own aerial (Assets\\Terrain Backup\\meloneras\\imagery\\meloneras_google.jpg, which
  covers the 2250 m terrain square). Blender X = -east, Y = -north (the .blend is UTM turned
  180 degrees). About 0.085 m per pixel; fit residuals about 2 m.
- Each footprint becomes a rendered block house with a flat roof and parapet (render_*), a
  block house under a low mono-pitch corrugated roof (corrugated_*), or a shack (block base,
  shade-net sides, corrugated roof). Doors face the nearest street; windows are barred; some
  flat roofs carry water tanks, a half-built blockwork upstand or a tiled eave strip. Choices
  are seeded per building, so a re-run gives the same result.
- The ground is found by ray-casting the course meshes (*_-_Mesh / *_-_Blend, then Terrain);
  the floor sits FLOOR_ABOVE_GROUND over the highest point and the walls run down past the
  lowest point as a plinth.
- Buildings are grouped into five objects (MDA_NorthRow, MDA_LaneWest, MDA_LaneEast,
  MDA_RoadWest, MDA_SouthEast), each with its pivot at the group's centre at ground level.
- RENDER_PREVIEWS: renders four views into OUT_DIR\\Previews.
- EXPORT: writes <name>.fbx (pivot on the object), <name>_world.fbx (course coordinates),
  placement.json, MarDeAzor.blend and Textures\\<set> into EXPORT_DIR. Blender -> Unity is (-x, z, -y).
"""
import json
import math
import os
import random
import shutil

import bmesh
import bpy
from mathutils import Matrix, Vector

# ------------------------------------------------------------------ settings
OUT_DIR = r"H:\Meloneras\Support_Files\Buildings\MarDeAzor"
TEXTURE_ROOTS = [
    os.path.join(OUT_DIR, "Textures"),
    r"H:\Meloneras\Meloneras_Golf_Club_v4_2025_12_02\Assets\Buildings\Meloneras Clubhouse\Latest\Textures",
    r"H:\Meloneras\Support_Files\Buildings\Clubhouse\Textures",
]
FLOOR_ABOVE_GROUND = 0.10   # m over the highest ground point under the footprint
PLINTH_BELOW_GROUND = 0.30  # m: walls run this far below the lowest ground point
EXPORT_DIR = r"H:\Meloneras\Meloneras_Golf_Club_v4_2025_12_02\Assets\Buildings\Mar de Azor"
RENDER_PREVIEWS = False
EXPORT = True
SEED = 33
PLOT_OBJECT = None          # course mesh the houses must stay inside (the walled plot); None = auto
PLOT_MARGIN = 0.30          # m: walls and eaves stay this far inside the plot edge (boundary wall)
HOUSE_GAP = 0.10            # m: gap kept between neighbouring houses
MIN_SIDE = 2.5              # m: a house squeezed below this is dropped
ENGINES = ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE")  # first that exists is used

# pixel (x right, y down) -> course metres east/north of the terrain origin:  en = A*conj(p) + B
FIT_A = complex(0.08451853255764005, 0.004287409263789746)
FIT_B = complex(1615.1743580712061, 1592.6885164587025)

GROUPS = {"N": "MDA_NorthRow", "W": "MDA_LaneWest", "E": "MDA_LaneEast",
          "NW": "MDA_RoadWest", "SE": "MDA_SouthEast"}


def _dir(deg):
    a = math.radians(deg)
    return (math.cos(a), math.sin(a))


LANE = (0.431, -0.902)   # the lane between the two southern rows, pointing NE (image px)
ROAD_E = _dir(10.7)      # C. Mar de Azor along the north row
ROAD_W = _dir(25.0)      # C. Mar de Azor at its west end

# id, group, centre px, length px (along axis), width px, axis (px), kind, storeys
FOOTPRINTS = [
    ("N1", "N", (655, 455), 150, 125, ROAD_E, "render_white", 2),
    ("N2", "N", (810, 480), 80, 115, ROAD_E, "render_cream", 2),
    ("N3", "N", (897, 522), 95, 120, ROAD_E, "corrugated_red", 1),
    ("N4", "N", (995, 527), 100, 125, ROAD_E, "render_white", 1),
    ("N5", "N", (1132, 555), 175, 135, ROAD_E, "render_cream", 2),
    ("N6", "N", (1272, 572), 105, 105, ROAD_E, "render_red", 1),
    ("N7", "N", (1252, 645), 95, 50, ROAD_E, "corrugated_red", 1),
    ("W1", "W", (625, 590), 110, 110, LANE, "render_white", 1),
    ("W2", "W", (585, 690), 170, 110, LANE, "render_white", 1),
    ("W3", "W", (540, 765), 120, 110, LANE, "render_cream", 1),
    ("W4", "W", (475, 885), 200, 120, LANE, "corrugated_red", 1),
    ("W5", "W", (430, 1000), 130, 120, LANE, "render_cream", 1),
    ("W6", "W", (455, 705), 120, 80, LANE, "corrugated_red", 1),
    ("W7", "W", (370, 795), 130, 90, LANE, "shack", 1),
    ("W8", "W", (205, 1000), 170, 60, _dir(80), "render_white", 1),
    ("W9", "W", (290, 1095), 130, 75, _dir(20), "corrugated_white", 1),
    ("W10", "W", (425, 1160), 90, 60, _dir(10), "shack", 1),
    ("E1", "E", (785, 620), 120, 130, LANE, "render_white", 1),
    ("E2", "E", (712, 705), 120, 80, LANE, "corrugated_red", 1),
    ("E3", "E", (690, 790), 110, 110, LANE, "render_white", 1),
    ("E3b", "E", (755, 850), 90, 80, LANE, "render_cream", 1),
    ("E4", "E", (630, 905), 200, 130, LANE, "corrugated_red", 1),
    ("E5", "E", (730, 955), 100, 80, LANE, "corrugated_red", 1),
    ("E6", "E", (795, 995), 110, 90, LANE, "render_cream", 1),
    ("E7", "E", (575, 1035), 140, 140, LANE, "render_white", 1),
    ("E8", "E", (700, 1095), 80, 110, LANE, "render_white", 1),
    ("NW1", "NW", (240, 215), 130, 80, ROAD_W, "render_white", 1),
    ("NW2", "NW", (340, 262), 80, 60, ROAD_W, "shack", 1),
    ("NW3", "NW", (360, 310), 130, 70, ROAD_W, "corrugated_green", 1),
    ("NW4", "NW", (390, 358), 140, 65, ROAD_W, "corrugated_red", 1),
    ("NW5", "NW", (425, 415), 150, 90, ROAD_W, "corrugated_green", 1),
    ("NW6", "NW", (455, 540), 150, 80, _dir(80), "shack", 1),
    ("SE1", "SE", (1285, 830), 170, 110, _dir(-35), "render_cream", 1),
    ("SE2", "SE", (1160, 845), 70, 60, _dir(-35), "corrugated_green", 1),
]
# street centrelines (px), used to turn each building's door to the nearest street
STREETS = [
    [(60, 120), (300, 170), (470, 250), (560, 330), (700, 370), (900, 410), (1100, 450), (1300, 490), (1400, 520)],
    [(720, 560), (480, 1040)],
    [(1200, 650), (1330, 700)],
]

# material -> (texture set, metres per tile, flat colour)
MATERIALS = {
    "MDA_RenderWhite": ("MDA_RenderWhite", 3.0, (0.80, 0.79, 0.75)),
    "MDA_RenderCream": ("MDA_RenderCream", 3.0, (0.78, 0.70, 0.56)),
    "MDA_RenderRed": ("MDA_RenderRed", 3.0, (0.55, 0.20, 0.16)),
    "MDA_Blockwork": ("MDA_Blockwork", 2.0, (0.52, 0.51, 0.48)),
    "MDA_FlatRoof": ("MDA_FlatRoof", 3.0, (0.62, 0.57, 0.50)),
    "MDA_CorrugatedRed": ("MDA_CorrugatedRed", 1.5, (0.55, 0.26, 0.24)),
    "MDA_CorrugatedGreen": ("MDA_CorrugatedGreen", 1.5, (0.22, 0.46, 0.42)),
    "MDA_CorrugatedWhite": ("MDA_CorrugatedWhite", 1.5, (0.75, 0.75, 0.72)),
    "MDA_RoofTile": ("MEL_CH_RoofTerracotta", 2.0, (0.62, 0.32, 0.22)),
    "MDA_ShadeNet": (None, 1.0, (0.08, 0.17, 0.15)),
    "MDA_Window": (None, 1.0, (0.05, 0.05, 0.06)),
    "MDA_SteelWhite": (None, 1.0, (0.78, 0.78, 0.76)),
    "MDA_SteelDark": (None, 1.0, (0.10, 0.10, 0.10)),
    "MDA_DoorWhite": ("MDA_CorrugatedWhite", 1.0, (0.80, 0.80, 0.78)),
    "MDA_DoorBrown": (None, 1.0, (0.30, 0.18, 0.10)),
    "MDA_TankCream": (None, 1.0, (0.78, 0.68, 0.52)),
    "MDA_TankBlue": (None, 1.0, (0.30, 0.42, 0.65)),
    "MDA_TankBlack": (None, 1.0, (0.06, 0.06, 0.06)),
}
WALL = {"render_white": "MDA_RenderWhite", "render_cream": "MDA_RenderCream", "render_red": "MDA_RenderRed",
        "corrugated_red": "MDA_RenderWhite", "corrugated_green": "MDA_RenderWhite",
        "corrugated_white": "MDA_RenderWhite", "shack": "MDA_Blockwork"}
ROOF = {"corrugated_red": "MDA_CorrugatedRed", "corrugated_green": "MDA_CorrugatedGreen",
        "corrugated_white": "MDA_CorrugatedWhite"}


# ------------------------------------------------------------------ registration
def px_to_xy(p):
    z = FIT_A * complex(p[0], -p[1]) + FIT_B
    return (-z.real, -z.imag)  # Blender X = -east, Y = -north


def footprint_frame(c, L, W, axis):
    """World centre, unit axis along L and across W (right-handed), and sizes in metres."""
    ux, uy = axis
    n = math.hypot(ux, uy); ux, uy = ux / n, uy / n
    vx, vy = -uy, ux
    pts = [(c[0] + su * L / 2 * ux + sv * W / 2 * vx, c[1] + su * L / 2 * uy + sv * W / 2 * vy)
           for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    w = [Vector(px_to_xy(p)) for p in pts]
    centre = (w[0] + w[1] + w[2] + w[3]) / 4
    a = (w[1] - w[0]); b = (w[3] - w[0])
    Lm, Wm = a.length, b.length
    a.normalize(); b.normalize()
    if a.x * b.y - a.y * b.x < 0:  # keep local +Y to the left of +X
        b = -b
    return centre, a, b, Lm, Wm


def street_points():
    out = []
    for line in STREETS:
        for i in range(len(line) - 1):
            p, q = Vector(px_to_xy(line[i])), Vector(px_to_xy(line[i + 1]))
            k = max(2, int((q - p).length / 2))
            out += [p.lerp(q, j / k) for j in range(k + 1)]
    return out


# ------------------------------------------------------------------ geometry kit
class Kit:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        self.M = Matrix.Identity(4)

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def face(self, pts, mat):
        vs = [self.bm.verts.new(self.M @ Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.mi(mat)
        return f

    def box(self, x0, x1, y0, y1, z0, z1, mat, skip=("bottom",)):
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        sides = {"bottom": (0, 3, 2, 1), "top": (4, 5, 6, 7), "s": (0, 1, 5, 4),
                 "e": (1, 2, 6, 5), "n": (2, 3, 7, 6), "w": (3, 0, 4, 7)}
        for k, idx in sides.items():
            if k not in skip:
                self.face([c[i] for i in idx], mat)

    def cylinder(self, cx, cy, z0, r, h, mat, seg=12):
        ring0 = [(cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg), z0) for i in range(seg)]
        ring1 = [(x, y, z0 + h) for x, y, _ in ring0]
        for i in range(seg):
            j = (i + 1) % seg
            self.face([ring0[i], ring0[j], ring1[j], ring1[i]], mat)
        self.face(ring1, mat)

    def finish(self):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
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
    uv = me.uv_layers.new(name="UVMap")
    Z = Vector((0, 0, 1))
    for p in me.polygons:
        mat = me.materials[p.material_index]
        tile = MATERIALS.get(mat.name, (None, 2.0))[1] if mat else 2.0
        n = p.normal
        if abs(n.z) > 0.97:
            u_ax, v_ax = Vector((1, 0, 0)), Vector((0, 1 if n.z > 0 else -1, 0))
        elif abs(n.z) > 0.2:   # pitched roof: U along the eave, V up the slope
            u_ax = Z.cross(n).normalized()
            v_ax = n.cross(u_ax).normalized()
        else:
            u_ax = Z.cross(n).normalized()
            v_ax = Z
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


def _set_base(folder):
    for root in TEXTURE_ROOTS:
        base = os.path.join(root, folder, folder + "_")
        if os.path.exists(base + "ALBEDO.png"):
            return base
    return None


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
    bsdf.inputs["Roughness"].default_value = 0.85
    if name == "MDA_Window":
        bsdf.inputs["Roughness"].default_value = 0.15
    base = _set_base(folder) if folder else None
    if not base:
        if folder:
            print("textures missing for", name, "-> flat colour")
        return mat
    x = -700
    for key, sock, colour, y in (("ALBEDO", "Base Color", True, 300), ("ROUGHNESS", "Roughness", False, 0),
                                 ("METALNESS", "Metallic", False, -280)):
        im = _img(base + key + ".png", colour)
        if im:
            t = nt.nodes.new("ShaderNodeTexImage"); t.image = im; t.location = (x, y)
            nt.links.new(t.outputs["Color"], bsdf.inputs[sock])
    nrm = _img(base + "NORMAL.png", False)
    if nrm:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = nrm; t.location = (x, -560)
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.location = (x + 300, -560)
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ------------------------------------------------------------------ building parts (local metres)
def window(k, side, a, z0, hx, L, W, rng, bars):
    """Barred window on wall `side` ('s','n','e','w') centred at `a` along the wall."""
    w, h, off = 1.0, 1.1, 0.03
    if side in ("s", "n"):
        y = -W / 2 - off if side == "s" else W / 2 + off
        sgn = -1 if side == "s" else 1
        p = [(a - w / 2, y, z0), (a + w / 2, y, z0), (a + w / 2, y, z0 + h), (a - w / 2, y, z0 + h)]
        k.face(p if sgn < 0 else p[::-1], "MDA_Window")
        for i in range(4):
            bx = a - w / 2 + 0.15 + i * (w - 0.3) / 3
            k.box(bx - 0.02, bx + 0.02, min(y, y + sgn * 0.04), max(y, y + sgn * 0.04), z0, z0 + h, bars, skip=("bottom", "top"))
    else:
        x = L / 2 + off if side == "e" else -L / 2 - off
        sgn = 1 if side == "e" else -1
        p = [(x, a - w / 2, z0), (x, a + w / 2, z0), (x, a + w / 2, z0 + h), (x, a - w / 2, z0 + h)]
        k.face(p if sgn > 0 else p[::-1], "MDA_Window")
        for i in range(4):
            by = a - w / 2 + 0.15 + i * (w - 0.3) / 3
            k.box(min(x, x + sgn * 0.04), max(x, x + sgn * 0.04), by - 0.02, by + 0.02, z0, z0 + h, bars, skip=("bottom", "top"))


def door(k, side, a, L, W, mat, w=0.9, h=2.05):
    off = 0.03
    if side in ("s", "n"):
        y = -W / 2 - off if side == "s" else W / 2 + off
        p = [(a - w / 2, y, 0), (a + w / 2, y, 0), (a + w / 2, y, h), (a - w / 2, y, h)]
        k.face(p if side == "s" else p[::-1], mat)
    else:
        x = L / 2 + off if side == "e" else -L / 2 - off
        p = [(x, a - w / 2, 0), (x, a + w / 2, 0), (x, a + w / 2, h), (x, a - w / 2, h)]
        k.face(p if side == "e" else p[::-1], mat)


def openings(k, L, W, front, rng, z_floor=0.0, upper=False):
    """Door (ground floor only) and windows on the front wall, windows on one other wall."""
    bars = rng.choice(["MDA_SteelWhite", "MDA_SteelDark"])
    walls = {"s": L, "n": L, "e": W, "w": W}
    others = [s for s in walls if s != front and walls[s] >= 3.0]
    use = [front] + ([rng.choice(others)] if others and rng.random() < 0.6 else [])
    for side in use:
        span = walls[side]
        n = max(1, int(span / 3.2))
        slots = [-span / 2 + span * (i + 0.5) / n for i in range(n)]
        for i, a in enumerate(slots):
            if side == front and i == 0 and not upper:
                if span > 6.0 and rng.random() < 0.35:
                    door(k, side, a, L, W, "MDA_DoorWhite", w=2.4, h=2.2)
                else:
                    door(k, side, a, L, W, rng.choice(["MDA_DoorWhite", "MDA_DoorBrown"]))
            else:
                if upper and span < 3.5:
                    continue
                window(k, side, a, z_floor + 1.0, 0, L, W, rng, bars)


def flat_block(k, x0, x1, y0, y1, z0, h, wall, rng, front, tiles=False, clutter=True):
    """Rendered block with a flat roof behind a 0.4 m parapet (top of parapet at z0 + h + 0.4)."""
    t, par = 0.15, 0.4
    zt = z0 + h + par
    k.box(x0, x1, y0, y1, z0, zt, wall, skip=("bottom", "top"))
    # parapet cap and inner faces
    ox = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    ix = [(x0 + t, y0 + t), (x1 - t, y0 + t), (x1 - t, y1 - t), (x0 + t, y1 - t)]
    for i in range(4):
        j = (i + 1) % 4
        k.face([(*ox[i], zt), (*ox[j], zt), (*ix[j], zt), (*ix[i], zt)], wall)
        k.face([(*ix[i], zt), (*ix[j], zt), (*ix[j], z0 + h), (*ix[i], z0 + h)], wall)
    k.face([(*p, z0 + h) for p in ix], "MDA_FlatRoof")
    if tiles:  # tiled eave strip on the front parapet
        d = 0.45
        if front == "s":
            k.face([(x0 - 0.1, y0 - d, zt - 0.25), (x1 + 0.1, y0 - d, zt - 0.25), (x1 + 0.1, y0, zt + 0.05), (x0 - 0.1, y0, zt + 0.05)], "MDA_RoofTile")
        elif front == "n":
            k.face([(x1 + 0.1, y1 + d, zt - 0.25), (x0 - 0.1, y1 + d, zt - 0.25), (x0 - 0.1, y1, zt + 0.05), (x1 + 0.1, y1, zt + 0.05)], "MDA_RoofTile")
        elif front == "e":
            k.face([(x1 + d, y0 - 0.1, zt - 0.25), (x1 + d, y1 + 0.1, zt - 0.25), (x1, y1 + 0.1, zt + 0.05), (x1, y0 - 0.1, zt + 0.05)], "MDA_RoofTile")
        else:
            k.face([(x0 - d, y1 + 0.1, zt - 0.25), (x0 - d, y0 - 0.1, zt - 0.25), (x0, y0 - 0.1, zt + 0.05), (x0, y1 + 0.1, zt + 0.05)], "MDA_RoofTile")
    if not clutter:
        return
    zr = z0 + h
    if rng.random() < 0.5:  # water tank on a small plinth
        cx = rng.uniform(x0 + 1.0, x1 - 1.0) if x1 - x0 > 2.2 else (x0 + x1) / 2
        cy = rng.uniform(y0 + 1.0, y1 - 1.0) if y1 - y0 > 2.2 else (y0 + y1) / 2
        k.box(cx - 0.6, cx + 0.6, cy - 0.6, cy + 0.6, zr, zr + 0.25, "MDA_Blockwork")
        k.cylinder(cx, cy, zr + 0.25, 0.55, 1.1, rng.choice(["MDA_TankCream", "MDA_TankBlue", "MDA_TankBlack"]))
    if rng.random() < 0.3:  # half-built blockwork upstand along the back
        ya, yb = (y1 - t - 0.2, y1 - t) if front == "s" else (y0 + t, y0 + t + 0.2)
        xa = rng.uniform(x0 + t, (x0 + x1) / 2)
        k.box(xa, min(x1 - t, xa + (x1 - x0) * 0.5), ya, yb, zr, zr + rng.uniform(0.8, 1.4), "MDA_Blockwork")


def mono_roof(k, x0, x1, y0, y1, zf, zb, mat, front, eave=0.15):
    """Low corrugated roof falling from the front edge (zf) to the back (zb)."""
    t = 0.06
    if front in ("s", "n"):
        yf, yb = (y0 - eave, y1 + eave) if front == "s" else (y1 + eave, y0 - eave)
        A = [(x0 - eave, yf, zf), (x1 + eave, yf, zf), (x1 + eave, yb, zb), (x0 - eave, yb, zb)]
    else:
        xf, xb = (x1 + eave, x0 - eave) if front == "e" else (x0 - eave, x1 + eave)
        A = [(xf, y0 - eave, zf), (xf, y1 + eave, zf), (xb, y1 + eave, zb), (xb, y0 - eave, zb)]
    up = Vector((0, 0, 1))
    n = (Vector(A[1]) - Vector(A[0])).cross(Vector(A[3]) - Vector(A[0]))
    top = A if n.dot(up) > 0 else A[::-1]
    bot = [(p[0], p[1], p[2] - t) for p in top]
    k.face(top, mat)
    k.face(bot[::-1], mat)
    for i in range(4):
        j = (i + 1) % 4
        k.face([bot[i], bot[j], top[j], top[i]], mat)


def sloped_walls(k, x0, x1, y0, y1, zlow, hf, hb, front, wall_lo, wall_hi=None, split=None):
    """Four walls whose tops follow a mono-pitch roof. Optional material split at `split` height."""
    def h_at(x, y):
        if front == "s": f = (y - y0) / (y1 - y0)
        elif front == "n": f = (y1 - y) / (y1 - y0)
        elif front == "e": f = (x1 - x) / (x1 - x0)
        else: f = (x - x0) / (x1 - x0)
        return hf + (hb - hf) * f
    c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        a, b = c[i], c[(i + 1) % 4]
        ha, hb_ = h_at(*a), h_at(*b)
        if split is None:
            k.face([(*a, zlow), (*b, zlow), (*b, hb_), (*a, ha)], wall_lo)
        else:
            k.face([(*a, zlow), (*b, zlow), (*b, split), (*a, split)], wall_lo)
            k.face([(*a, split), (*b, split), (*b, hb_), (*a, ha)], wall_hi)


def band(k, x0, x1, y0, y1, z0, z1, mat, off=0.012):
    """Painted dado band, a skin just proud of the four walls."""
    c = [(x0 - off, y0 - off), (x1 + off, y0 - off), (x1 + off, y1 + off), (x0 - off, y1 + off)]
    for i in range(4):
        a, b = c[i], c[(i + 1) % 4]
        k.face([(*a, z0), (*b, z0), (*b, z1), (*a, z1)], mat)


def build_house(k, fid, L, W, kind, storeys, front, rng, plinth):
    x0, x1, y0, y1 = -L / 2, L / 2, -W / 2, W / 2
    wall = WALL[kind]
    if kind != "shack" and rng.random() < 0.4:
        alt = "MDA_RenderCream" if wall != "MDA_RenderCream" else "MDA_RenderWhite"
        band(k, x0, x1, y0, y1, -plinth, rng.uniform(0.8, 1.0), rng.choice([alt, "MDA_Blockwork"]))
    if kind.startswith("render"):
        h = rng.uniform(2.7, 3.0)
        flat_block(k, x0, x1, y0, y1, -plinth, h + plinth, wall, rng, front,
                   tiles=rng.random() < 0.35, clutter=storeys == 1)
        openings(k, L, W, front, rng)
        if storeys == 2:  # upper room set back from the front
            fx, fy = 0.6, 0.6
            ux0, ux1 = x0 + L * (1 - fx) / 2, x1 - L * (1 - fx) / 2
            if front == "s": uy0, uy1 = y1 - W * fy, y1 - 0.15
            elif front == "n": uy0, uy1 = y0 + 0.15, y0 + W * fy
            else: uy0, uy1 = y0 + 0.15, y1 - 0.15
            if front in ("e", "w"):
                ux0, ux1 = (x0 + 0.15, x0 + L * fx) if front == "e" else (x1 - L * fx, x1 - 0.15)
            zb = h + 0.0
            flat_block(k, ux0, ux1, uy0, uy1, zb, 2.6, wall, rng, front, tiles=rng.random() < 0.5, clutter=True)
            ku = (ux1 - ux0, uy1 - uy0)
            k.M = k.M @ Matrix.Translation(((ux0 + ux1) / 2, (uy0 + uy1) / 2, 0))
            openings(k, ku[0], ku[1], front, rng, z_floor=zb, upper=True)
            k.M = k.M @ Matrix.Translation((-(ux0 + ux1) / 2, -(uy0 + uy1) / 2, 0))
    elif kind.startswith("corrugated"):
        hf, hb = rng.uniform(2.7, 3.0), rng.uniform(2.3, 2.5)
        sloped_walls(k, x0, x1, y0, y1, -plinth, hf, hb, front, wall)
        mono_roof(k, x0, x1, y0, y1, hf + 0.06, hb + 0.06, ROOF[kind], front)
        openings(k, L, W, front, rng)
    else:  # shack: block base, shade-net sides, corrugated roof, a white garage-type door
        hf, hb = rng.uniform(2.3, 2.6), rng.uniform(2.0, 2.2)
        sloped_walls(k, x0, x1, y0, y1, -plinth, hf, hb, front, "MDA_Blockwork", "MDA_ShadeNet", split=1.0)
        mono_roof(k, x0, x1, y0, y1, hf + 0.05, hb + 0.05, rng.choice(["MDA_CorrugatedGreen", "MDA_CorrugatedWhite"]), front, eave=0.10)
        span = L if front in ("s", "n") else W
        door(k, front, -span / 4, L, W, "MDA_DoorWhite", w=min(2.0, span / 2.5), h=1.95)


# ------------------------------------------------------------------ ground
GROUND_SUFFIX = ("_-_Mesh", "_-_Blend")


def ground_z(scene, dg, x, y):
    origin = Vector((x, y, 1000.0))
    terrain = None
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, origin, Vector((0, 0, -1)))
        if not hit:
            break
        if ob.name.endswith(GROUND_SUFFIX):
            return loc.z
        if ob.name == "Terrain" and terrain is None:
            terrain = loc.z
        origin = loc - Vector((0, 0, 0.01))
    return terrain


def ground_hit(scene, dg, x, y):
    """First course-mesh hit straight down: (z, object name) or (None, None)."""
    origin = Vector((x, y, 1000.0))
    for _ in range(12):
        hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, origin, Vector((0, 0, -1)))
        if not hit:
            break
        if ob.name.endswith(GROUND_SUFFIX):
            return loc.z, ob.name
        origin = loc - Vector((0, 0, 0.01))
    return None, None


class Rect:
    """Footprint with independent extents along its axes: x in [-l0, l1] along a, y in [-w0, w1] along b."""

    def __init__(self, centre, a, b, L, W):
        self.c, self.a, self.b = centre.copy(), a.copy(), b.copy()
        self.l0 = self.l1 = L / 2
        self.w0 = self.w1 = W / 2

    def local(self, p):
        d = p - self.c
        return d.dot(self.a), d.dot(self.b)

    def contains(self, p, grow=0.0):
        x, y = self.local(p)
        return -self.l0 - grow < x < self.l1 + grow and -self.w0 - grow < y < self.w1 + grow

    def side_points(self, side, grow, step=0.5):
        if side in ("l0", "l1"):
            x = -self.l0 - grow if side == "l0" else self.l1 + grow
            ys = (-self.w0 - grow, self.w1 + grow)
            n = max(2, int((ys[1] - ys[0]) / step) + 1)
            return [self.c + self.a * x + self.b * (ys[0] + (ys[1] - ys[0]) * i / (n - 1)) for i in range(n)]
        y = -self.w0 - grow if side == "w0" else self.w1 + grow
        xs = (-self.l0 - grow, self.l1 + grow)
        n = max(2, int((xs[1] - xs[0]) / step) + 1)
        return [self.c + self.b * y + self.a * (xs[0] + (xs[1] - xs[0]) * i / (n - 1)) for i in range(n)]

    def final(self):
        """Centre, L and W after the sides moved."""
        L, W = self.l0 + self.l1, self.w0 + self.w1
        c = self.c + self.a * ((self.l1 - self.l0) / 2) + self.b * ((self.w1 - self.w0) / 2)
        return c, L, W


def fit_rect(rect, inside, others, step=0.25, max_iter=80):
    """Pull each side in until its edge (grown by the margin) is inside the plot and clear of the
    houses already placed. Returns False if the house had to shrink below MIN_SIDE."""
    for _ in range(max_iter):
        moved = False
        for side in ("l0", "l1", "w0", "w1"):
            bad = False
            for p in rect.side_points(side, PLOT_MARGIN):
                if not inside(p):
                    bad = True; break
            if not bad:
                for p in rect.side_points(side, HOUSE_GAP / 2):
                    if any(o.contains(p, HOUSE_GAP / 2) for o in others):
                        bad = True; break
            if bad:
                setattr(rect, side, getattr(rect, side) - step)
                moved = True
        if rect.l0 + rect.l1 < MIN_SIDE or rect.w0 + rect.w1 < MIN_SIDE:
            return False
        if not moved:
            return True
    return True


def sample(scene, dg, centre, a, b, L, W, step=1.0):
    zs = []
    nx, ny = max(2, int(L / step) + 1), max(2, int(W / step) + 1)
    for i in range(nx):
        for j in range(ny):
            p = centre + a * (-L / 2 + L * i / (nx - 1)) + b * (-W / 2 + W * j / (ny - 1))
            z = ground_z(scene, dg, p.x, p.y)
            if z is not None:
                zs.append(z)
    return zs


# ------------------------------------------------------------------ main
def main():
    scene = bpy.context.scene
    # make sure Terrain can be hit as a fallback; course meshes are normally visible
    terrain = bpy.data.objects.get("Terrain")
    if terrain:
        terrain.hide_viewport = False
    coll = bpy.data.collections.get("MDA_Build") or bpy.data.collections.new("MDA_Build")
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    streets = street_points()

    # the walled plot: the course mesh under most footprint centres, unless named
    frames = {f[0]: footprint_frame(f[2], f[3], f[4], f[5]) for f in FOOTPRINTS}
    plot = PLOT_OBJECT
    if plot is None:
        counts = {}
        for centre, a, b, Lm, Wm in frames.values():
            for du in (-0.3, 0.0, 0.3):
                for dv in (-0.3, 0.0, 0.3):
                    _z, name = ground_hit(scene, dg, *(centre + a * Lm * du + b * Wm * dv))
                    if name:
                        counts[name] = counts.get(name, 0) + 1
        plot = max(counts, key=counts.get) if counts else None
        print("ground under the footprints:", sorted(counts.items(), key=lambda kv: -kv[1])[:6])
    print("plot mesh:", plot)

    def inside(p):
        return plot is None or ground_hit(scene, dg, p.x, p.y)[1] == plot

    placed, dropped, fitted = [], [], {}
    for f in FOOTPRINTS:
        centre, a, b, Lm, Wm = frames[f[0]]
        if not inside(centre):
            dropped.append(f[0]); continue
        r = Rect(centre, a, b, Lm, Wm)
        if not fit_rect(r, inside, placed):
            dropped.append(f[0]); continue
        placed.append(r)
        c2, L2, W2 = r.final()
        fitted[f[0]] = (c2, a, b, L2, W2)
        if abs(L2 - Lm) > 0.05 or abs(W2 - Wm) > 0.05:
            print(f"{f[0]}: trimmed {Lm:.1f} x {Wm:.1f} -> {L2:.1f} x {W2:.1f} m")
    if dropped:
        print("dropped (outside the plot or squeezed out):", dropped)

    plan = {}
    for fid, grp, c, L, W, axis, kind, storeys in FOOTPRINTS:
        if fid not in fitted:
            continue
        centre, a, b, Lm, Wm = fitted[fid]
        zs = sample(scene, dg, centre, a, b, Lm, Wm)
        if not zs:
            print("no ground under", fid); zs = [0.0]
        floor = max(zs) + FLOOR_ABOVE_GROUND
        plinth = floor - min(zs) + PLINTH_BELOW_GROUND
        # front = the wall whose midpoint is nearest a street
        mids = {"s": centre - b * Wm / 2, "n": centre + b * Wm / 2, "e": centre + a * Lm / 2, "w": centre - a * Lm / 2}
        front = min(mids, key=lambda s: min((mids[s].to_2d() - q).length for q in streets))
        plan[fid] = dict(group=GROUPS[grp], centre=centre, a=a, b=b, L=Lm, W=Wm, kind=kind, storeys=storeys,
                         floor=floor, plinth=plinth, front=front, ground=(min(zs), max(zs)))

    report = {}
    for gname in GROUPS.values():
        items = {k: v for k, v in plan.items() if v["group"] == gname}
        if not items:
            continue
        gx = sum(v["centre"].x for v in items.values()) / len(items)
        gy = sum(v["centre"].y for v in items.values()) / len(items)
        gz = min(v["ground"][0] for v in items.values())
        G = Matrix.Translation((gx, gy, gz))
        Ginv = G.inverted()
        k = Kit(gname)
        for fid, v in items.items():
            rng = random.Random(f"{SEED}-{fid}")
            a, b = v["a"], v["b"]
            R = Matrix(((a.x, b.x, 0, v["centre"].x), (a.y, b.y, 0, v["centre"].y), (0, 0, 1, v["floor"]), (0, 0, 0, 1)))
            k.M = Ginv @ R
            build_house(k, fid, v["L"], v["W"], v["kind"], v["storeys"], v["front"], rng, v["plinth"])
        me = k.finish()
        ob = bpy.data.objects.new(gname, me)
        coll.objects.link(ob)
        ob.matrix_world = G
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        report[gname] = {
            "blender_xyz": [round(gx, 3), round(gy, 3), round(gz, 3)],
            "unity_xyz": [round(-gx, 3), round(gz, 3), round(-gy, 3)],
            "tris": tris, "verts": len(me.vertices),
            "buildings": {fid: {"kind": v["kind"], "storeys": v["storeys"], "front": v["front"],
                                "size_m": [round(v["L"], 1), round(v["W"], 1)],
                                "floor_z": round(v["floor"], 2), "ground": [round(z, 2) for z in v["ground"]]}
                          for fid, v in items.items()},
        }
        print(gname, {kk: vv for kk, vv in report[gname].items() if kk != "buildings"})
    report["_plot"] = {"mesh": plot, "dropped": dropped}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "placement.json"), "w") as f:
        json.dump(report, f, indent=2)
    if RENDER_PREVIEWS:
        render_previews(coll)
    if EXPORT:
        export_all(coll)
    return report


# ------------------------------------------------------------------ previews
def render_previews(coll):
    scene = bpy.context.scene
    out = os.path.join(OUT_DIR, "Previews")
    os.makedirs(out, exist_ok=True)
    terrain = bpy.data.objects.get("Terrain")
    if terrain:
        terrain.hide_render = True
    for e in ENGINES:
        try:
            scene.render.engine = e
            break
        except TypeError:
            pass
    try:
        scene.eevee.taa_render_samples = 32
    except Exception:
        pass
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:
        scene.view_settings.view_transform = "Filmic"
    w = scene.world or bpy.data.worlds.new("MDA_World")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.55, 0.7, 0.9, 1)
    bg.inputs[1].default_value = 0.8
    sd = bpy.data.lights.new("MDA_Sun", "SUN"); sd.energy = 4.0; sd.angle = math.radians(1.5)
    sun = bpy.data.objects.new("MDA_Sun", sd); scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(40), 0, math.radians(150))
    cd = bpy.data.cameras.new("MDA_Cam"); cd.clip_start = 0.5; cd.clip_end = 4000
    cam = bpy.data.objects.new("MDA_Cam", cd); scene.collection.objects.link(cam)
    scene.camera = cam

    pts = [ob.matrix_world @ Vector(c) for ob in coll.objects for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    mid = (lo + hi) / 2
    dg = bpy.context.evaluated_depsgraph_get()

    def gz(x, y):
        z = ground_z(scene, dg, x, y)
        return z if z is not None else lo.z

    def look(frm, to, lens):
        cd.type = "PERSP"; cd.lens = lens
        cam.location = frm
        cam.rotation_euler = (Vector(to) - Vector(frm)).to_track_quat("-Z", "Y").to_euler()

    def render(name):
        scene.render.filepath = os.path.join(out, name)
        bpy.ops.render.render(write_still=True)
        print("rendered", name)

    # course frame: east = -X, north = -Y.  1) oblique aerial from the south-west
    look(mid + Vector((90, 110, 70)), mid, 32); render("mda_aerial_sw.png")
    # 2) from the green to the west of the houses (about 45 m west), eye height
    p = Vector(px_to_xy((60, 520))); look(Vector((p.x, p.y, gz(p.x, p.y) + 1.7)), mid + Vector((0, 0, 2)), 28)
    render("mda_from_green_west.png")
    # 3) from the fairway to the south (about 70 m south of the lane's end)
    p = Vector(px_to_xy((700, 1340))) + Vector((0, 40)); look(Vector((p.x, p.y, gz(p.x, p.y) + 1.7)), mid + Vector((0, 0, 2)), 30)
    render("mda_from_south.png")
    # 4) street level on C. Mar de Azor at the roundabout, looking west along the north row
    p = Vector(px_to_xy((1390, 512))); q = Vector(px_to_xy((600, 380)))
    look(Vector((p.x, p.y, gz(p.x, p.y) + 1.7)), Vector((q.x, q.y, gz(q.x, q.y) + 2.0)), 24)
    render("mda_street_east.png")
    # 5) overhead orthographic
    cd.type = "ORTHO"; cd.ortho_scale = max(hi.x - lo.x, (hi.y - lo.y) * 16 / 9) * 1.15
    cam.location = (mid.x, mid.y, hi.z + 300); cam.rotation_euler = (0, 0, math.pi)  # north up
    render("mda_overhead.png")


# ------------------------------------------------------------------ export
def copy_textures(coll):
    """Copy every texture set the build uses into EXPORT_DIR\\Textures and repoint the images,
    so the FBX files reference textures that sit beside them."""
    tex_out = os.path.join(EXPORT_DIR, "Textures")
    done = set()
    used = {n.image for ob in coll.objects for slot in ob.material_slots if slot.material and slot.material.node_tree
            for n in slot.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image}
    for im in used:
        src = bpy.path.abspath(im.filepath)
        if not src or not os.path.isfile(src):
            continue
        folder = os.path.dirname(src)
        name = os.path.basename(folder)
        dst_dir = os.path.join(tex_out, name)
        if folder not in done:
            os.makedirs(dst_dir, exist_ok=True)
            for f in os.listdir(folder):
                if f.lower().endswith(".png"):
                    shutil.copy2(os.path.join(folder, f), os.path.join(dst_dir, f))
            done.add(folder)
        im.filepath = os.path.join(dst_dir, os.path.basename(src))
    for root in TEXTURE_ROOTS[:1]:
        txt = os.path.join(root, "SOURCES.txt")
        if os.path.isfile(txt):
            shutil.copy2(txt, os.path.join(tex_out, "SOURCES.txt"))
    print("textures copied:", sorted(os.path.basename(d) for d in done))


def export_all(coll):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    copy_textures(coll)
    shutil.copy2(os.path.join(OUT_DIR, "placement.json"), os.path.join(EXPORT_DIR, "placement.json"))
    for ob in coll.objects:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        common = dict(use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                      apply_scale_options="FBX_SCALE_ALL", axis_forward="-Z", axis_up="Y",
                      bake_space_transform=True, mesh_smooth_type="FACE", use_mesh_modifiers=True,
                      path_mode="RELATIVE", embed_textures=False, add_leaf_bones=False)
        bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT_DIR, ob.name + ".fbx"), **common)
        saved = ob.matrix_world.copy()
        ob.data.transform(saved)
        ob.matrix_world = Matrix.Identity(4)
        bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT_DIR, ob.name + "_world.fbx"), **common)
        ob.data.transform(saved.inverted())
        ob.matrix_world = saved
    bpy.data.libraries.write(os.path.join(EXPORT_DIR, "MarDeAzor.blend"), set(coll.objects), fake_user=True,
                             path_remap="RELATIVE_ALL")


if __name__ == "__main__":
    main()

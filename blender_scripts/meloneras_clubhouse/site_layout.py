"""Site layout for the Meloneras clubhouse pad, traced from the Google aerial
(reference/aerial_carpark.png, 1767 x 1632 px, north up) and registered to the course.

Registration: a 2D similarity fitted to three matches between the aerial and the course
.blend (pad corners at the barn's north end and the car park's east corner, and the existing
LIB_Meloneras_StarterHut). About 14.6 px per metre; residuals 1.5 to 2 m. The .blend is UTM
rotated 180 degrees, so the fit has a reflection term (pixel y runs down, Blender Y runs south).

Run:  python site_layout.py <out.json>   (plain Python + numpy; no Blender needed)
Writes building origins/headings and 2D outlines (Blender world XY, metres) of the car park
markings and planters. build_clubhouse.py reads it and drapes everything onto the pad.
"""
import json
import math
import sys

import numpy as np

# pixel = A * conj(world) + B   (world as complex X + iY)
FIT_A = complex(-14.6352302, -0.191891933)
FIT_B = complex(-19338.8173, 14537.0327)
PX_PER_M = abs(FIT_A)


def w(px, py):
    """Aerial pixel -> Blender world XY."""
    z = ((complex(px, py) - FIT_B) / FIT_A).conjugate()
    return np.array([z.real, z.imag])


def wdir(dx, dy):
    """Aerial pixel direction -> unit Blender world direction."""
    z = (complex(dx, dy) / FIT_A).conjugate()
    v = np.array([z.real, z.imag])
    return v / np.linalg.norm(v)


def heading(v):
    return math.degrees(math.atan2(v[1], v[0]))


def perp_ccw(v):
    return np.array([-v[1], v[0]])


A_PIX = (0.867, 0.499)       # along the road / pad long edges, pointing ESE on the aerial
D_PIX = (-0.442, 0.897)      # main car park aisles, pointing SSW


def rect(c, u, half_u, half_v):
    """Rectangle centred at c, half sizes along u and its CCW perpendicular."""
    v = perp_ccw(u)
    return [list(c + su * half_u * u + sv * half_v * v) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def strip(p0, p1, width):
    """Rectangle of `width` along the segment p0 -> p1."""
    d = p1 - p0
    L = np.linalg.norm(d)
    u = d / L
    return rect((p0 + p1) / 2, u, L / 2, width / 2)


def teardrop(p0, p1, r0, r1, n=10):
    """Rounded island from p0 (radius r0) to p1 (radius r1); CCW polygon."""
    d = p1 - p0
    u = d / np.linalg.norm(d)
    ang = math.atan2(u[1], u[0])
    pts = []
    for i in range(n + 1):  # cap around p1
        t = ang - math.pi / 2 + math.pi * i / n
        pts.append(p1 + r1 * np.array([math.cos(t), math.sin(t)]))
    for i in range(n + 1):  # cap around p0
        t = ang + math.pi / 2 + math.pi * i / n
        pts.append(p0 + r0 * np.array([math.cos(t), math.sin(t)]))
    return [list(p) for p in pts]


def line(p, q, width=0.12):
    return strip(np.asarray(p, float), np.asarray(q, float), width)


def bay_row(origin, along, across, t0, t1, depth, bay=2.5, end_bar=True):
    """Separator lines of a row of perpendicular bays.
    origin: the row's kerb/back line point at t=0, `along` the aisle, `across` into the bay."""
    out = []
    n = int(round((t1 - t0) / bay))
    for i in range(n + 1):
        a = origin + along * (t0 + i * bay)
        out.append(line(a, a + across * depth))
    if end_bar:  # back line of the row
        out.append(line(origin + along * t0, origin + along * (t0 + n * bay)))
    return out


def layout():
    A = wdir(*A_PIX)
    D = wdir(*D_PIX)
    Ap = -perp_ccw(D)            # across the main car park, pointing ENE (towards the east edge)
    if np.dot(Ap, A) < 0:
        Ap = -Ap

    feats = {"buildings": {}, "markings": [], "planters": []}

    # ---- buildings: origin + local +X direction
    club_x = A                                   # +X along the road (ESE), -Y faces the road
    barn_x = perp_ccw(A)                         # A turned 90 deg anticlockwise -> NNE; open front (-Y) faces ESE
    feats["buildings"]["MEL_Clubhouse"] = {"xy": list(w(401, 572)), "heading": heading(club_x)}
    feats["buildings"]["MEL_CartBarn"] = {"xy": list(w(213, 396)), "heading": heading(barn_x)}
    feats["buildings"]["MEL_StarterKiosk"] = {"xy": list(w(635, 348)), "heading": heading(club_x),
                                              "note": "from the aerial; the existing LIB_Meloneras_StarterHut sits about 2 m south"}

    M = []  # marking quads

    # ---- main car park (east), referenced to the central walkway S0 -> S1
    S0, S1 = w(1210, 742), w(1030, 1105)
    L = np.linalg.norm(S1 - S0)
    feats["planters"].append({"kind": "walkway", "poly": strip(S0, S1, 1.6), "height": 0.15})
    feats["planters"].append({"kind": "island_light", "poly": teardrop(w(1158, 708), w(1282, 772), 0.9, 1.8), "height": 0.15})
    feats["planters"].append({"kind": "island_light", "poly": teardrop(w(1075, 1146), w(956, 1083), 0.9, 1.8), "height": 0.15})
    # rows (offsets across the car park in metres from the walkway centreline, +Ap = east)
    t0, t1 = 2.5, L - 2.0
    M += bay_row(S0 + Ap * 0.8, D, Ap, t0, t1, 5.0)         # row 3, east of the walkway
    M += bay_row(S0 - Ap * 0.8, D, -Ap, t0, t1, 5.0)        # row 2, west of the walkway
    M += bay_row(S0 + Ap * 17.0, D, -Ap, -4.5, L - 1.0, 5.0)  # row 4, along the east edge
    M += bay_row(S0 - Ap * 16.6, D, Ap, -6.5, 13.5, 5.0)     # row 1, against the red planter
    M += bay_row(S0 - Ap * 17.6, D, Ap, 18.5, L + 1.0, 5.0)  # row 1 continued, south of the disabled bays
    # disabled bays with hatching between them
    hb = S0 - Ap * 16.6 + D * 13.5
    for k in range(2):
        a = hb + D * (k * 2.5)
        M.append(line(a, a + Ap * 5.0))
    M.append(line(hb + D * 5.0, hb + D * 5.0 + Ap * 5.0))
    for k in range(5):  # diagonal hatch in the 1.5 m transfer zone
        a = hb + D * (2.5 + 0.0) + Ap * (k * 1.0)
        M.append(line(a, a + D * 1.0 + Ap * 0.6, 0.15))
    # direction arrows in the two aisles (simple shaft + head)
    for off, sgn in ((-8.8, 1), (8.9, -1)):
        c = S0 + Ap * off + D * (L * 0.55)
        tip = c + D * sgn * 2.5
        M.append(line(c - D * sgn * 2.5, tip, 0.3))
        M.append(line(tip, tip - D * sgn * 1.2 + Ap * 0.6, 0.25))
        M.append(line(tip, tip - D * sgn * 1.2 - Ap * 0.6, 0.25))
    # red picon planter west of row 1
    feats["planters"].append({"kind": "picon", "poly": strip(w(1040, 528), w(885, 805), 1.8), "height": 0.2})

    # ---- herringbone cart/car bays either side of a palm spine (north-west of the main car park)
    H0, H1 = w(915, 515), w(822, 752)
    feats["planters"].append({"kind": "picon", "poly": strip(H0, H1, 1.3), "height": 0.2})
    hd = (H1 - H0) / np.linalg.norm(H1 - H0)
    hp = perp_ccw(hd)
    HL = np.linalg.norm(H1 - H0)
    ang = math.radians(60)
    for side in (1, -1):
        out = hp * side
        diag = out * math.sin(ang) - side * hd * math.cos(ang)   # parallel through the spine
        n = int((HL - 2.0) / 2.9)
        for i in range(n + 1):
            a = H0 + hd * (1.0 + i * 2.9) + out * 0.65
            M.append(line(a, a + diag * 4.8))

    # ---- north service lane: angled cart bays on the north side of the lane line
    N0, N1 = w(500, 360), w(800, 525)
    M.append(line(N0, N1))
    nd = (N1 - N0) / np.linalg.norm(N1 - N0)
    north = -perp_ccw(nd)  # rotate -90 deg: from the ESE lane direction to NNE
    if north[1] > 0:       # Blender -Y is north
        north = -north
    diag = north * math.sin(math.radians(55)) + nd * math.cos(math.radians(55))
    NL = np.linalg.norm(N1 - N0)
    for i in range(11):
        a = N0 + nd * (2.0 + i * 2.4)
        if np.linalg.norm(a - N0) > NL - 1:
            break
        M.append(line(a, a + diag * 4.2))
    # clubhouse north-east hedge planter (raised, with shrubs)
    feats["planters"].append({"kind": "hedge", "poly": strip(w(515, 432), w(772, 576), 1.6), "height": 0.4})

    # ---- red picon wedge between the car park and the road
    feats["planters"].append({"kind": "picon", "poly": [list(w(*p)) for p in
                              ((832, 1122), (868, 1128), (1092, 1248), (1094, 1270), (1050, 1268), (828, 1150))][::-1],
                              "height": 0.2})

    feats["markings"] = M
    feats["fit"] = {"px_per_m": PX_PER_M, "A": [FIT_A.real, FIT_A.imag], "B": [FIT_B.real, FIT_B.imag]}
    return feats


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "site_layout.json"
    f = layout()
    with open(out, "w") as fh:
        json.dump(f, fh, indent=1)
    print(len(f["markings"]), "marking quads,", len(f["planters"]), "planters ->", out)
    for k, v in f["buildings"].items():
        print(k, [round(c, 2) for c in v["xy"]], round(v["heading"], 1))

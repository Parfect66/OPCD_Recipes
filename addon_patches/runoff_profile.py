"""
Run-off profile operator for OPCD mesh pieces (e.g. Spline_path416_0_Custom4_-_Mesh).

Shapes a run-off into a smooth flat-bottomed channel with rounded sides:

- Edge (boundary) vertices stay at their current height, so the run-off blends
  into the surrounding terrain.
- Distance to the boundary sets the profile: at the edge the offset is 0, it
  eases down over `side_radius` metres (smoothstep), then the bottom stays flat
  at `-depth`. Flat-bottom width = mesh width - 2 * side_radius.
- Optional lake end: vertices in the vertex group `lake_group` (select the
  lake-end vertices in Edit Mode and assign them to the group) are lowered by
  `lake_drop` metres, fading out over `lake_reach` metres, so water can overflow.
- Laplacian smoothing (boundary fixed) afterwards, so the result is smooth for
  the Unity texture pass.

Works on the active mesh object. Units are the object's local units (metres
when scale_length is 1.0). Z-only changes; X/Y never move.

Recipe usage:
{
  "runoffprofile": {
    "depth": 0.5,
    "side_radius": 3.0,
    "lake_group": "RunoffLake",
    "lake_drop": 0.2,
    "lake_reach": 8.0,
    "smooth_passes": 10
  }
}
"""

import bpy
import numpy as np
from mathutils.kdtree import KDTree


def _smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _boundary_edges(me):
    """Return (N,2) vertex index pairs for edges used by exactly one face."""
    counts = {}
    for poly in me.polygons:
        n = len(poly.vertices)
        for i in range(n):
            a = poly.vertices[i]
            b = poly.vertices[(i + 1) % n]
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    return np.array([k for k, c in counts.items() if c == 1], dtype=np.int64).reshape(-1, 2)


def _dist_to_segments(points_xy, seg_a, seg_b, chunk=1000):
    """Min distance from each point to the set of 2D line segments."""
    D = seg_b - seg_a
    L2 = np.maximum((D * D).sum(axis=1), 1e-12)
    out = np.empty(len(points_xy))
    for s in range(0, len(points_xy), chunk):
        P = points_xy[s:s + chunk]
        W = P[:, None, :] - seg_a[None, :, :]
        t = np.clip((W * D[None, :, :]).sum(axis=2) / L2[None, :], 0.0, 1.0)
        proj = seg_a[None, :, :] + t[:, :, None] * D[None, :, :]
        d = np.sqrt(((P[:, None, :] - proj) ** 2).sum(axis=2))
        out[s:s + chunk] = d.min(axis=1)
    return out


def apply_runoff_profile(obj, depth=0.5, side_radius=3.0, lake_group="RunoffLake",
                         lake_drop=0.0, lake_reach=8.0, smooth_passes=10):
    """Shape `obj` into a flat-bottomed run-off. Returns a short result string."""
    if obj is None or obj.type != 'MESH':
        return "No active mesh object"
    if side_radius <= 0:
        return "side_radius must be > 0"

    was_edit = obj.mode == 'EDIT'
    if was_edit:
        bpy.ops.object.mode_set(mode='OBJECT')

    me = obj.data
    n = len(me.vertices)
    co = np.empty((n, 3), dtype=np.float64)
    me.vertices.foreach_get("co", co.ravel())
    orig_z = co[:, 2].copy()

    edges = _boundary_edges(me)
    if len(edges) == 0:
        if was_edit:
            bpy.ops.object.mode_set(mode='EDIT')
        return "No boundary edges found - run-off must be an open-edged mesh piece"

    seg_a = co[edges[:, 0], :2]
    seg_b = co[edges[:, 1], :2]
    boundary_verts = np.unique(edges.ravel())
    on_boundary = np.zeros(n, dtype=bool)
    on_boundary[boundary_verts] = True

    # Distance from every vertex to the nearest boundary edge (in XY)
    dist = _dist_to_segments(co[:, :2], seg_a, seg_b)
    dist[on_boundary] = 0.0

    # Smooth edge-to-flat-bottom profile: 0 at the edge, flat at -depth past side_radius
    f = _smoothstep(dist / side_radius)
    offset = -depth * f

    # Optional lake-end lowering
    lake_applied = 0
    grp = obj.vertex_groups.get(lake_group) if lake_group else None
    if grp is not None and lake_drop > 0:
        lake_idx = []
        for v in me.vertices:
            for g in v.groups:
                if g.group == grp.index and g.weight > 0.0:
                    lake_idx.append(v.index)
                    break
        if lake_idx:
            tree = KDTree(len(lake_idx))
            for i in lake_idx:
                tree.insert((co[i, 0], co[i, 1], 0.0), i)
            tree.balance()
            dl = np.array([tree.find((co[i, 0], co[i, 1], 0.0))[2] for i in range(n)])
            fade = _smoothstep(1.0 - dl / max(lake_reach, 1e-6))
            offset += -lake_drop * fade
            lake_applied = len(lake_idx)

    # Laplacian smoothing of the OFFSET (not absolute Z), boundary offset fixed at 0,
    # so the terrain around the run-off is not pulled into the channel
    if smooth_passes > 0:
        neighbours = [[] for _ in range(n)]
        for e in me.edges:
            a, b = e.vertices
            neighbours[a].append(b)
            neighbours[b].append(a)
        interior = np.where(~on_boundary)[0]
        nb_idx = [np.array(neighbours[i], dtype=np.int64) for i in interior]
        for _ in range(smooth_passes):
            new_off = offset.copy()
            for k, i in enumerate(interior):
                nb = nb_idx[k]
                if len(nb):
                    new_off[i] = 0.5 * offset[i] + 0.5 * offset[nb].mean()
            offset = new_off

    co[:, 2] = orig_z + offset
    me.vertices.foreach_set("co", co.ravel())
    me.update()

    if was_edit:
        bpy.ops.object.mode_set(mode='EDIT')

    return (f"Run-off profile applied: depth {depth}, side_radius {side_radius}, "
            f"{len(boundary_verts)} edge verts fixed, lake verts {lake_applied}")

"""Self-test on a synthetic OPCD-style hole. Run in a NEW, EMPTY Blender scene
(it builds its own meshes) or headless:

    blender -b --python selftest.py -- /tmp/out_dir
    python selftest.py /tmp/out_dir            (with the `bpy` pip module)

Scene: a ditch running north-south (bed falls to +Y), crossed by a cart-path
embankment along X. Surface meshes 'Rough_T' and 'Concrete_T' share a border,
carry a 'Col' colour attribute and a 'UVMap', and are deliberately coarse
(0.75 m grid) so densify has work to do.
"""
import math
import os
import sys

import bpy  # noqa: I001 (bpy first so the pip `bpy` module exposes bmesh)
import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib  # noqa: E402

import opcd_terrain as T  # noqa: E402
import culvert as C  # noqa: E402
importlib.reload(T)
importlib.reload(C)


def ground(x, y):
    g = -0.01 * y
    ax = abs(x)
    if ax < 0.75:
        g -= 1.0
    elif ax < 2.75:
        g -= 1.0 * (2.75 - ax) / 2.0
    emb = 0.6 - 0.5 * max(0.0, abs(y) - 1.5)
    return max(g, emb)


def build_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    step, half = 0.75, 21.0
    n = int(2 * half / step)
    for name, keep in (("Rough_T", lambda y: abs(y) >= 1.5 - 1e-6),
                       ("Concrete_T", lambda y: abs(y) <= 1.5 + 1e-6)):
        bm = bmesh.new()
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1):
                x, y = -half + i * step, -half + j * step
                grid[i, j] = (x, y)
        verts = {}
        for i in range(n):
            for j in range(n):
                yc = -half + (j + 0.5) * step
                if not keep(yc):
                    continue
                q = []
                for key in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                    if key not in verts:
                        x, y = grid[key]
                        verts[key] = bm.verts.new((x, y, ground(x, y)))
                    q.append(verts[key])
                bm.faces.new(q)
        uv = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for lp in f.loops:
                lp[uv].uv = (lp.vert.co.x * 0.1, lp.vert.co.y * 0.1)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        ca = me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
        col = (0.2, 0.6, 0.2, 1.0) if name.startswith("Rough") else (0.8, 0.8, 0.8, 1.0)
        ca.data.foreach_set("color", list(col) * len(ca.data))
        mat = bpy.data.materials.get(name.split("_")[0]) or bpy.data.materials.new(name.split("_")[0])
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.cursor.location = (0.3, 0.2, 0.6)


def seam_gap():
    """Max z difference between Rough and Concrete verts sharing an XY position."""
    def pts(name):
        ob = bpy.data.objects[name]
        return {(round(v.co.x, 4), round(v.co.y, 4)): v.co.z for v in ob.data.vertices}
    a, b = pts("Rough_T"), pts("Concrete_T")
    common = set(a) & set(b)
    return len(common), max((abs(a[k] - b[k]) for k in common), default=0.0)


def render(path):
    sc = bpy.context.scene
    cam_d = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    cam.location = (7.5, -9.5, 5.0)
    cam.rotation_euler = (math.radians(62), 0, math.radians(38))
    cam_d.lens = 28
    sc.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN'))
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    sc.collection.objects.link(sun)
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 16
    sc.cycles.device = 'CPU'
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    for mname, rgb in (("Rough", (0.15, 0.4, 0.12)), ("Concrete", (0.6, 0.6, 0.58))):
        m = bpy.data.materials.get(mname)
        if m:
            m.use_nodes = True
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    fm = bpy.data.materials.get("_feat") or bpy.data.materials.new("_feat")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.5, 0.3, 1)
    for ob in bpy.data.collections.get(T.FEATURE_COLLECTION).objects if bpy.data.collections.get(T.FEATURE_COLLECTION) else []:
        ob.data.materials.clear()
        ob.data.materials.append(fm)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    bpy.data.objects.remove(sun)


def main(out_dir, do_render=True):
    os.makedirs(out_dir, exist_ok=True)
    build_scene()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "selftest.blend"))
    T.scene_report()
    pid = C.plan_culvert(kind="pipe", span=T.mm(600))
    plan = T.load_state()[pid]
    assert abs(abs(plan["axis"][1]) - 1) < 0.05, f"axis should run N-S, got {plan['axis']}"
    assert plan["ends"]["in"]["mouth"][1] < plan["ends"]["out"]["mouth"][1], "inlet should be upstream (-Y)"
    C.build(pid)
    if do_render:
        render(os.path.join(out_dir, "01_built.png"))
    C.backup(pid)
    C.blend(pid)
    n_common, gap = seam_gap()
    print("SEAM", n_common, "shared verts, max gap", gap)
    assert gap < 1e-4, f"Rough/Concrete seam opened by {gap} m"
    assert C.verify(pid), "verify failed"
    if do_render:
        render(os.path.join(out_dir, "02_blended.png"))
    C.finalise(pid)
    ob = bpy.data.objects["Concrete_T"]
    assert "CULVERT_" + pid + "_IN" not in bpy.data.objects
    assert [u.name for u in ob.data.uv_layers] == ["UVMap"], [u.name for u in ob.data.uv_layers]
    assert [a.name for a in ob.data.color_attributes] == ["Col"]
    assert len(ob.data.materials) == 1
    C.restore(pid)
    assert len(bpy.data.objects["Concrete_T"].data.vertices) < 2000, "restore did not put the path back"
    for kind in ("corrugated", "arch", "box"):
        k = C.plan_culvert(kind=kind, span=T.mm(900) if kind != "corrugated" else T.mm(600), bearing=0)
        C.build(k)
    if do_render:
        # separate the extra kinds so they are visible side by side
        for i, k in enumerate(("C02", "C03", "C04")):
            for r in ("IN",):
                o = bpy.data.objects[f"CULVERT_{k}_{r}"]
                o.location.x += (i + 1) * 3.2
        render(os.path.join(out_dir, "03_kinds.png"))
    print("SELFTEST OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv[0] if argv else "/tmp/opcd_selftest", do_render="--no-render" not in argv)

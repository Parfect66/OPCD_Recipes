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

import numpy as np
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


def notched(x, y):
    """ground() with a false 0.4 m notch in the embankment over the ditch, as left by
    conforming to a Unity heightmap that dips where the watercourse runs."""
    dip = 0.4 * max(0.0, 1.0 - abs(x) / 2.5) * max(0.0, min(1.0, 1.0 - (abs(y) - 2.5) / 1.0))
    return ground(x, y) - dip


def build_scene(ground_fn=None):
    ground_fn = ground_fn or ground
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
                        verts[key] = bm.verts.new((x, y, ground_fn(x, y)))
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


def embankment(x, y):
    """Motorway embankment along X: 5 m high, 12 m crest, 1:2 sides; flat ground at 0."""
    return max(0.0, min(5.0, 5.0 - (abs(y) - 6.0) / 2.0))


def build_passage_scene():
    """Rough ground + a Concrete motorway on the crest + a Concrete cart path running
    north up to the embankment toe at x = 0 (0.75 m grid, shared borders)."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    step, half = 0.75, 30.0
    n = int(2 * half / step)

    def which(xc, yc):
        if abs(yc) <= 5.25:
            return "Concrete_Motorway"
        if abs(xc) <= 1.5 and yc <= -16.5:
            return "Concrete_Path"
        return "Rough_E"
    for name in ("Rough_E", "Concrete_Motorway", "Concrete_Path"):
        bm = bmesh.new()
        verts = {}
        for i in range(n):
            for j in range(n):
                xc, yc = -half + (i + 0.5) * step, -half + (j + 0.5) * step
                if which(xc, yc) != name:
                    continue
                q = []
                for key in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                    if key not in verts:
                        x, y = -half + key[0] * step, -half + key[1] * step
                        verts[key] = bm.verts.new((x, y, embankment(x, y)))
                    q.append(verts[key])
                bm.faces.new(q)
        bm.loops.layers.uv.new("UVMap")
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
        me.materials.append(bpy.data.materials.get(name.split("_")[0]) or bpy.data.materials.new(name.split("_")[0]))
        bpy.context.scene.collection.objects.link(bpy.data.objects.new(name, me))


def deck_test(out_dir, do_render=False):
    """A false notch in the path over the culvert is bridged; nothing is lowered."""
    build_scene(notched)
    sampler0 = T.HeightSampler([bpy.data.objects["Concrete_T"]])
    before = {q: sampler0.height(*q) for q in ((0.0, 0.0), (1.0, 0.5), (-1.2, -0.6), (6.0, 0.0))}
    pid = C.plan_culvert(kind="pipe", span=T.mm(600))
    plan = T.load_state()[pid]
    assert plan["deck"] and plan["deck"]["centre_fill_max_m"] > 0.3, plan["deck"]
    C.build(pid)
    C.backup(pid, file_copy=False)
    C.blend(pid)
    sampler = T.HeightSampler([bpy.data.objects["Concrete_T"]])
    for q, z0 in before.items():
        z = sampler.height(*q)
        assert z >= z0 - 1e-4, f"deck lowered the path at {q}: {z0} -> {z}"
    z_mid = sampler.height(0.0, 0.0)
    assert abs(z_mid - ground(0.0, 0.0)) < 0.06, f"notch not bridged: {z_mid} vs {ground(0.0, 0.0)}"
    n_common, gap = seam_gap()
    assert gap < 1e-4, f"deck opened the Rough/Concrete seam by {gap} m"
    assert C.verify(pid), T.load_state()[pid]["verify"]
    if do_render:
        T.render_views(out_dir, "05_deck", C.preview_views(pid), samples=16)
    print("DECK OK", round(before[(0.0, 0.0)], 3), "->", round(z_mid, 3))


def deck_near_path_test(out_dir, do_render=False):
    """Meloneras pipe case: inlet 0.7 m from the path edge, false notch in the path over
    the barrel. The path must be bridged right up to the headwall and never lowered."""
    build_scene(notched)
    con = bpy.data.objects["Concrete_T"]
    z_before = {(round(v.co.x, 3), round(v.co.y, 3)): v.co.z for v in con.data.vertices}
    bpy.context.scene.cursor.location = (0.3, -2.2, 0.0)       # 0.7 m south of the path edge
    # the cursor here is on the bank, not in a ditch, so take the old "lowest ground" invert;
    # this test is about the deck next to a path
    pid = C.plan_culvert(kind="corrugated", span=1.0, cursor_is="inlet", mouth_invert="lowest")
    plan = T.load_state()[pid]
    C.build(pid)
    C.backup(pid, file_copy=False)
    C.blend(pid)
    sampler = T.HeightSampler([con])
    worst = min(sampler.height(0.0, y) - ground(0.0, y) for y in (-1.3, -0.8, 0.0, 0.8, 1.3))
    assert worst > -0.06, f"path over the pipe still dips by {-worst:.3f} m"
    lowered = [(k, z_before[k] - v.co.z) for v in con.data.vertices
               for k in [(round(v.co.x, 3), round(v.co.y, 3))] if k in z_before and v.co.z < z_before[k] - 0.08]
    assert not lowered, f"path lowered at {len(lowered)} verts, worst {max(d for _, d in lowered):.3f} m"
    chk = C.verify(pid) and T.load_state()[pid]["verify"]
    assert chk and not chk["concrete_reshaped"], T.load_state()[pid]["verify"]
    if do_render:
        T.render_views(out_dir, "06_deck_near_path", C.preview_views(pid), samples=16)
    print("DECK NEAR PATH OK: inlet headwall", round(plan["ends"]["in"]["top_rel"], 2), "m above invert")


def passage_test(out_dir, do_render):
    """Underpass under the motorway embankment, from the crest and from a portal on the path."""
    build_passage_scene()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "selftest_passage.blend"))
    # 1) cursor on the motorway crest
    bpy.context.scene.cursor.location = (0.3, 0.2, 5.0)
    pid = C.plan_culvert(kind="underpass", span=4.0)
    plan = T.load_state()[pid]
    assert plan["passage"] and abs(plan["rise"] - 3.0) < 1e-6, plan["rise"]
    assert abs(abs(plan["axis"][1]) - 1) < 0.05, f"underpass should run N-S, got {plan['axis']}"
    ys = sorted(e["mouth"][1] for e in plan["ends"].values())
    assert ys[0] < -6 and ys[1] > 6, f"portals should be off the crest, got {ys}"
    assert abs(plan["params"]["barrel_depth"] - (plan["length"] / 2 + 0.01)) < 1e-6
    C.build(pid)
    ob = bpy.data.objects[f"CULVERT_{pid}_IN"]
    far = min(v.co.y for v in ob.data.vertices)
    assert far < -plan["length"] / 2 + 0.05, "passage barrel should reach the midpoint"
    C.backup(pid, file_copy=False)
    C.blend(pid)
    ok = C.verify(pid)
    chk = T.load_state()[pid]["verify"]
    assert ok, f"passage verify failed: {chk}"
    if do_render:
        T.render_views(out_dir, "04_underpass", C.preview_views(pid), samples=16)
    C.finalise(pid)
    # 2) cursor on the cart path at the south portal: axis runs along the path, north
    bpy.ops.wm.open_mainfile(filepath=os.path.join(out_dir, "selftest_passage.blend"))
    importlib.reload(T)
    importlib.reload(C)
    bpy.context.scene.cursor.location = (0.0, -18.0, 0.0)
    k = C.plan_culvert(kind="underpass", span=4.0, cursor_is="portal")
    kp = T.load_state()[k]
    assert kp["axis"][1] > 0.95, f"portal mode should run north along the path, got {kp['axis']}"
    assert kp["ends"]["out"]["mouth"][1] > 6, kp["ends"]["out"]
    assert "along Concrete_Path" in kp["axis_note"], kp["axis_note"]
    # 3) road tunnel builds (bank is low for it, so it warns)
    bpy.context.scene.cursor.location = (8.0, 0.2, 5.0)
    t = C.plan_culvert(kind="tunnel", span=7.0, bearing=0)
    C.build(t)
    assert T.load_state()[t]["passage"]
    print("PASSAGES OK")


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
    # cursor on the outlet mouth: culvert must run square under the path, inlet found beyond it
    bpy.context.scene.cursor.location = (0.3, 3.8, 0.0)
    k = C.plan_culvert(kind="pipe", span=T.mm(600), cursor_is="outlet")
    kp = T.load_state()[k]
    assert abs(kp["axis"][1] - 1) < 0.05, f"outlet mode axis should point +Y, got {kp['axis']}"
    assert abs(kp["ends"]["out"]["mouth"][1] - 3.8) < 1e-6 and kp["ends"]["in"]["mouth"][1] < -1.5, kp["ends"]
    assert kp["fall"] > 0, kp["fall"]
    # the cursor is the reference: an inlet mouth's invert is the ground right at the cursor
    # (in the ditch upstream, so no minimum-fall adjustment applies to it)
    bpy.context.scene.cursor.location = (0.3, -5.5, 0.0)
    k2 = C.plan_culvert(kind="pipe", span=T.mm(600), cursor_is="inlet")
    z_cur = T.HeightSampler(T.surface_meshes()).height(0.3, -5.5)
    inv = T.load_state()[k2]["ends"]["in"]["invert"]
    assert abs(inv - z_cur) < 1e-4, f"inlet invert {inv} should be the ground at the cursor {z_cur}"
    # ...and the ground in front of it is levelled to apron height (the pad)
    C.build(k2)
    C.backup(k2, file_copy=False)
    C.blend(k2)
    e = T.load_state()[k2]["ends"]["in"]
    pp = T.load_state()[k2]["params"]
    v_end = C.mouth_dims("pipe", T.mm(600), T.mm(600), e["top_rel"], pp)["v_end"]
    samp = T.HeightSampler(T.surface_meshes())
    for off_u in (-0.3, 0.0, 0.3):
        q = (np.array(e["mouth"]) + np.array(e["outward"]) * (v_end + 0.6)
             + np.array([e["outward"][1], -e["outward"][0]]) * off_u)
        zq = samp.height(*q)
        assert abs(zq - (inv - 0.02)) < 0.05, f"pad not level at {q}: {zq} vs {inv - 0.02}"
    assert C.verify(k2), T.load_state()[k2]["verify"]
    C.restore(k2)
    print("CURSOR REFERENCE + PAD OK")
    bpy.context.scene.cursor.location = (0.3, 0.2, 0.6)
    kind_ids = []
    for kind in ("corrugated", "arch", "box"):
        k = C.plan_culvert(kind=kind, span=T.mm(900) if kind != "corrugated" else T.mm(600), bearing=0)
        C.build(k)
        kind_ids.append(k)
    if do_render:
        # separate the extra kinds so they are visible side by side
        for i, k in enumerate(kind_ids):
            for r in ("IN",):
                o = bpy.data.objects[f"CULVERT_{k}_{r}"]
                o.location.x += (i + 1) * 3.2
        render(os.path.join(out_dir, "03_kinds.png"))
    deck_test(out_dir, do_render)
    deck_near_path_test(out_dir, do_render)
    passage_test(out_dir, do_render)
    print("SELFTEST OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv[0] if argv else "/tmp/opcd_selftest", do_render="--no-render" not in argv)

"""Culvert job for one course. Copy to Blender Scripts\\<Course>\\<course>_culverts.py.

Re-runnable: each run starts again from BLEND, so change a culvert by editing its
entry here and re-running - never hand-patch a scene. Units: metres (1 BU = 1 m).
    600 mm = 0.6    24 in = 0.6096    4 ft = 1.2192    1 yd = 0.9144
"""

BLEND = r"H:\Course\Support Files\Blender\course_1_0.blend"           # read only, never saved
OUT_BLEND = r"H:\Course\Support Files\Blender\changed_blend.blend"  # final run writes here; an existing
                                                                      # one is renamed changed_blend_01 ... first
RENDER_ENGINE = "CYCLES"   # or "BLENDER_WORKBENCH" (faster on a GPU machine)

CULVERTS = [
    dict(
        name="H4_path_outlet",       # used for render / report file names
        kind="pipe",                 # pipe | corrugated | arch | box
        span=0.6,                    # opening width / diameter (m)
        # rise=0.45,                 # box/arch height; pipes = span
        cursor_is="outlet",          # what `at` marks: crossing | outlet | inlet
        at=(123.45, -67.89),         # world XY; None = the 3D cursor saved in BLEND
        # bearing=35,                # flow direction (deg, 0 = +Y); default = square across the nearest path
        # inlet=(x, y), outlet=(x, y),   # or give both mouths explicitly
        # target="Concrete.003",     # mesh to join into; default = nearest Concrete
        overrides={},                # e.g. {"wing_angle": 20, "band": 1.5, "max_edge": 0.25}
        edits={},                    # after planning, e.g. {"out_top_rel": 0.8, "in_invert": 41.20}
    ),
]

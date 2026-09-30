# Course records

One section per course: where everything lives, what has been built, and what is still
open. Update it after every final run (SKILL.md workflow step 6).

## Meloneras (Gran Canaria)

**Paths (user's PC)**
- Source `.blend` (read only): `H:\Meloneras_Latest\Support Files\Blender\Old\meloneras_latest-2.blend`
- Job script: `C:\Users\steve\Claude_Code\Blender Scripts\Meloneras\meloneras_culverts.py`
- Kit: `C:\Users\steve\Claude_Code\Blender Scripts\opcd_feature_kit\`
- Blender: `C:\Program Files\Blender Foundation\Blender 4.5\blender.exe` (4.5.9 LTS)
- Test output: `H:\Meloneras_Latest\Support Files\Blender\Old\culvert_test\`
- Final output: `H:\Meloneras_Latest\Support Files\Blender\Old\changed_blend.blend`, with
  previews and the report in `…\Old\culvert_previews\`
- Also on the PC: `Blender Scripts\Meloneras\culvert_blend.py` (the standalone fallback
  script) and `check_meshes_near_culvert.py` (a read-only check)

**Scene notes**
- Surface meshes are named `Spline_path<N>_…_<Surface>_-_Mesh` / `_-_Blend`.
  - Cart path 356 is Concrete (`Spline_path356_*`).
  - Custom4 is the main ground. Three Custom4 meshes are already over Unity's 65k
    vertex limit (522k, 323k and 195k verts), before any culvert.
- A hidden **`Terrain`** mesh (4,198,401 verts = 2049², a copy of the Unity heightmap)
  covers the course and renders. The job has `HIDE_IN_RENDERS = ["Terrain"]`.
- The Unity terrain is **edited in Unity**, not exported from Blender.

**Features**

| name | kind | size | where | settings | status |
|---|---|---|---|---|---|
| `Meloneras_box_01` | box | 2.0 × 1.5 m | under cart path 356; cursor at the inlet, in the roadside ditch 3.0 yd from the path | `cursor_is="inlet"`, `at=(-1040.473, -954.998)`, `overrides={"band": 1.5}`, `edits={"in_top_rel": 3.0}` | user reported the final run looked good (30 Sep 2026) |

Result for `Meloneras_box_01` (test 3 and final):
- Bearing 332.5° (square across path 356), 15.4 yd face to face.
- Inlet at (-1040.47, -955.00), invert 18.30 m, headwall 3.0 m above invert.
- Outlet at (-1046.97, -942.54), invert 17.33 m, headwall 1.96 m above invert.
- Fall 0.97 m. Joined into `Spline_path273_0_Concrete_-_Mesh`.
- Verify OK; flush errors 0.03 / 0.05 m; no Concrete reshaped.

History:
- Test 1: the default band (5 m) cut path 356 by up to 0.75 m, so `band` became 1.5 and
  `in_top_rel` 3.0.
- Test 2: grey ground in the mouths turned out to be the `Terrain` mesh, so it went into
  `HIDE_IN_RENDERS`.
- Before test 3 the saved cursor moved about 1.8 yd east, so `at` is now pinned.

**Note:** `Meloneras_box_01` was approved on kit 2026.09.30-4, before the **deck** step
existed. Re-running the job on kit -6 or later also bridges any dip in path 356 over the
barrel. Review the renders and `deck_fill_m` before accepting a re-run, or add
`"deck": False` to its overrides to reproduce the approved result exactly.

**Open to-dos**
- [ ] Lower the **Unity terrain** below the new beds at both mouths and their channels
  (Blender world XY; about 4 yd out along each channel):
  - Inlet: (-1040.47, -955.00), bed 18.30 m, channel to the SSE.
  - Outlet: (-1046.97, -942.54), bed 17.33 m, channel to the NNW.

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

**Current work: `meloneras_1.blend` (from 30 Sep 2026)**
- Source: `H:\Meloneras_Latest\Support Files\Blender\meloneras_1.blend`. Output:
  `…\Blender\changed_blend.blend`. Test renders: `…\Blender\culvert_test\`.
- The job now points at this file. **One culvert at a time**, at the user's request.
- In this file cart path 356 is `Spline_path100_piece1_*_Concrete_-_Mesh`.
- `Meloneras_box_01` is **not** in the job. Its fixed `at` from `meloneras_latest-2`
  gave an inlet bed 1.7 m higher on this file (19.99 m against 18.30 m), and the headwall
  came out too tall. Redo it later with a fresh cursor on this file.
- `Meloneras_pipe_01`: 1.0 m corrugated steel pipe, **final run done 30 Sep 2026** (kit -7)
  into `…\Blender\changed_blend.blend`.
  - Inlet at (-873.03, -1146.71), 0.7 yd from path `Spline_path100_piece1_3`, pinned in
    the job. Outlet at (-878.50, -1141.30). Bearing 314.7°, 8.4 yd.
  - Settings: `overrides={"band": 1.5, "footing": 1.0}`,
    `edits={"in_invert": 33.77, "out_invert": 31.68, "in_top_rel": 1.35, "out_top_rel": 1.35,
    "in_wing_end_rel": [0.3, 0.3], "out_wing_end_rel": [0.3, 0.3]}`.
  - Verify OK; path not reshaped; deck filled the path by 1.9 m.
  - The user saw fill mounded round the inlet: its invert had been raised 1.05 m above the
    ground at the cursor. That led to kit -8, where the cursor ground is the invert and a
    level pad sits in front. Future builds shouldn't raise inverts.
- Test 1 exposed the deck-taper bug, fixed in kit -7.
**Live MCP session, 30 Sep 2026** (open file `H:\Meloneras_Latest\Support Files\Blender\meloneras_1.blend`,
first as `meloneras_1.blend1`). All built live with the kit's live mode, **not saved by the user at the time
of writing** and **not in the job script**. Each has a file backup `meloneras_1_pre-C<nn>_01.blend` beside the
source. Plan ids are scene state: an undo (Ctrl+Z) in Blender drops later ids. All features are left as
separate objects (not joined into Concrete), at the user's request.

| plan | what | cursor / mouths (Blender XY) | settings | notes |
|---|---|---|---|---|
| C03 | 1.0 m concrete pipe, `CULVERT_C03` | inlet at cursor (-852.37, -1219.29) inv 36.32; outlet (-859.50, -1189.21) inv 35.03 | `flow="as_bearing"`, `band` 1.5, `footing` 1.0 | bearing 346.7, 33.8 yd, fall 1.29 m. Cursor was uphill-low, so the outlet is cut ~4 m. Joined then **unjoined** (473 verts separated) |
| C05 | 1.0 m concrete pipe, `CULVERT_C05_IN/OUT` | outlet at cursor (-877.37, -1141.49) inv 32.03; inlet (-870.70, -1148.00) inv 32.75 | `band` 1.5, `footing` 1.0 | first auto inlet (-873.56, -1145.21) sat on the path bend and cut through it; moved 4 m out. Path raised 1.8 m by deck, not cut |
| C07 | 1.5 x 1.125 m box | inlet (-908.70, -1100.82) inv 28.45; outlet dragged to (-939.37, -1046.26) inv 26.97 | `flow="as_bearing"`, `band` 1.5, `footing` 1.0 | 68 yd, fall 1 in 42; Custom4 filled up to 3.1 m |
| C09 | 1.5 x 1.125 m box | inlet at cursor (-1028.36, -952.55) inv 16.88; outlet auto (-1037.27, -935.25) inv 13.59 | `band` 1.5, `footing` 1.0 | 21 yd, fall 1 in 6; path not reshaped |
| C14 | arched buggy tunnel 3.0 x 2.6 m (`tunnel`) | portals dragged, then moved back from the path: (-1053.2, -945.4) floor 16.78; (-1041.7, -963.8) floor 17.39 | `channel_fade` 4.0, `channel_batter` 1.0 | 23.7 yd, floor grade 2.8%; path raised up to 3.75 m, not cut. Earlier tries (C11-C13) cut the path by up to 3.2 m 15 m west of the north portal; see "Passages" in live-mcp.md |

**Live MCP session, 1 Oct 2026** (same open file, kit 2026.09.30-8, still unsaved at the time of writing):

| plan | what | mouths (Blender XY) | settings | notes |
|---|---|---|---|---|
| C20 | arched buggy tunnel 3.0 x 2.4 m (`tunnel`), `CULVERT_C20_IN/OUT`, separate objects | entrance at the cursor (-398.69, -1078.06) floor 34.24; exit dragged to (-398.51, -1052.63) floor 34.45 | `flow="as_bearing"`, `channel_fade` 2.0, `channel_batter` 1.0, `band` 1.5, `footing` 1.0, `in_barrel_rise=0`, `out_barrel_rise=0` | 27.8 yd, bearing 0.4 (due north), floor falls 0.2 m. Runs under the large cart path `Spline_path318_piece1_1_Concrete` (raised 0.55 m, not cut). Stub path `Spline_path100_piece1_7` and `piece2` raised up to 2.7 m, cut up to 0.6 m at the mouths. Roof cover only 0.05-0.3 m (low hill) |
| C24 | 1.0 m round **stone-faced** pipe (`kind="pipe"`), `CULVERT_C24_IN/OUT`, separate objects | upper end (inlet) at the cursor (-422.45, -1142.85) inv 35.76; lower end dragged to (-437.53, -1120.07) inv 34.03 | `band` 1.5, `footing` 1.0 | 29.9 yd, bearing 326.5, fall 1.73 m (1 in 16). Verify OK, no Concrete reshaped. Rough `Spline_path349_piece2_7` cut 1.6 / filled 1.7 m; Custom4 `Spline_path393` filled 2.2 m. Material `Culvert_Stone` (procedural granite blocks, UVs 0.5/m). Backup `meloneras_1_pre-C24_01.blend` |


C24 notes:
- The user dragged both arrows, and the arrow nearest the cursor sat on the bank 1.6 m above the cursor ground. Plan the cursor end with `inlet=(cursor.x, cursor.y)`, not the arrow, so the invert is the cursor ground. Check which end is higher before choosing inlet/outlet (the first plan had them reversed: "inlet bed LOWER" warning).
- Stone finish is Blender-only (procedural). For Unity/GSPro give it a real stone image on the UVs or bake the material.
- It is not an arch like the user's reference photo: only the texture was asked for. Add `kind="arch"` if they want the shape too.
- Job entry `Meloneras_stone_01` added to `meloneras_culverts.py` (1 Oct 2026, kit 2026.10.01-1: new job keys `stone=True` and `join=False`, new `C.apply_stone`). With the inverts pinned (35.756 / 34.031) the geometry matches the live build exactly (soffits 36.756 / 35.031), but a background **test run reports `ok: false`**: `unsealed_by_m` 9.99 means no ground was found just outside the mouth outline in the **saved** `meloneras_1.blend`, whose ground differs from the open scene. Treat the live build as the approved result; save the open file and point `BLEND` at it before relying on the job. Also note the saved file's ground at the cursor is 37.65 m, not 35.76 m.
- To-do: lower the Unity terrain under C24.

Lessons from C20 (also in live-mcp.md):
- Cursor on a path stub: the auto "along the path" axis ran 56 m the wrong way. The user wanted the axis across the large path, so use `markers()` arrows and let them place both mouths.
- Passage floor defaults follow the crest (`barrel_rise` up to +1.6 m, a hump-backed floor that poked through the ground). Set `in_barrel_rise=0, out_barrel_rise=0` for a level floor.
- A 0.35 m back-of-headwall flush line is not a gap: those boundary verts sit on the culvert surface.
- Smoothing the ground over a built passage: average vertex Z by XY across all touched surface meshes (pure function of XY, so seams stay closed), pin verts within 0.6 m of the culvert, never lower over the barrel, then sync any coincident cross-mesh seam verts to one Z (including untouched neighbours such as `Spline_path278_island0_piece3_1_Custom4`). Result: seam dz 0, cover over roof >= 0.05 m. Mesh copies `BAK_C20smooth_*` hold the pre-smooth state.
- Abandoned plans C15-C19 (portal at the cursor running south along the stub) were restored; their `meloneras_1_pre-C16/C18/C19_01.blend` backups are still on disk.

Leftovers in the scene: `CULVERT_C02_OUT` (stray, from an abandoned plan) and `CULVERT_C05_IN/OUT`,
`CULVERT_C07_IN/OUT` etc. are the real mouth units; the marker empties `CULVERT_IN/OUT` were deleted.

**Open to-dos**
- [ ] Lower the **Unity terrain**: after importing the new meshes into Unity, run
  **Lower terrain under meshes** over the culvert. Then check that no terrain shows in
  either mouth or on the aprons, and that the channels reach their beds. Cuts are up to
  about 1 m at the outlet and 2.4 m at the inlet. For reference (Blender world XY; each
  channel runs about 4 yd out):
  - Inlet: (-1040.47, -955.00), bed 18.30 m, channel to the SSE.
  - Outlet: (-1046.97, -942.54), bed 17.33 m, channel to the NNW.
- [ ] Save the live-MCP work from 30 Sep 2026 under a proper `.blend` name (the open file began as a `.blend1`
  backup copy), then add C03, C05, C07, C09 and C14 to `meloneras_culverts.py` before any job re-run, using the
  mouths above (`at` / `inlet` / `outlet`, `flow="as_bearing"` where noted). Their Unity terrain lowering is also
  outstanding; C03's outlet and C14's portals need the deepest cuts (up to ~4 m).
- [ ] Add C20 to `meloneras_culverts.py` (mouths above, `flow="as_bearing"`, barrel rises 0) and lower the Unity terrain under it (deepest at the entrance cutting).
- [ ] Delete old `meloneras_1_pre-C*_01.blend` backup copies in `H:\Meloneras_Latest\Support Files\Blender\` once
  the user is happy (one per plan, incl. abandoned plans).

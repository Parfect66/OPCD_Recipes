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
| C26 | arched culvert 2.0 x 1.5 m (`kind="arch"`, concrete finish, textures added in Unity), `CULVERT_C26_IN/OUT`, separate objects | upper end (arrow, first cursor spot) (-564.15, -1043.71) inv 24.53; lower end dragged to (-584.58, -996.87) inv 23.04 | `band` 1.5, `footing` 1.0 | 55.9 yd, bearing 336.4, fall 1.49 m (1 in 34). Verify OK, no Concrete reshaped. Custom4 `Spline_path392` and `Spline_path393` cut up to 0.4 m, filled up to 2.2 m (deck). Buried under a bank of about 29.5 m. Backup `meloneras_1_pre-C26_01.blend` |
| C35 | arched buggy tunnel 2.8 x 3.0 m (`kind="arch"`, concrete, textures added in Unity), short wings, `CULVERT_C35_IN/OUT`, separate objects (replaces C33/C29) | upper end at the cursor (-692.75, -965.79) inv 20.04; lower end 9.0 m on bearing 338 (-696.12, -957.45) inv 19.71 | `flow="as_bearing"`, `band` 1.5, `footing` 1.0, `wing_angle` 20, `wing_len` 1.5, `wall` 0.25, `apron_thk` 0.1 | 9.8 yd, fall 0.33 m. Verify OK (flush 0.08 m), path `Spline_path100_piece1_5_Concrete` not reshaped (deck fill 0.05 m), path over it 23.6-23.8 m, roof about 23.0-23.3 m. Gentle smoothing (4 passes, 0.4, clamp 0.3 m) plus seam sync to dz 0. Headwalls 3.6-3.8 m tall (ground about 3.6 m above invert). Backups `meloneras_1_pre-C29..C35_01.blend` |
| C38 | curved buggy tunnel 2.6 x 2.6 m (`kind="tunnel"`, slim style, textures in Unity), `CULVERT_C38_IN/OUT/MID`, separate objects | entrance at the cursor (-1162.84, -1398.30) inv 43.28, travel bearing 161.3; exit (-1186.46, -1499.61) inv 46.65, travel bearing 186.8 | `plan_curved` straight 14 m, `band` 1.5, `footing` 1.0, `style="slim"`, `fill_over` cover 0.6 | 119 yd (108.7 m), floor grade 3.1% rising to the exit, min cover over roof 0.97 m (0.89 near the entrance). Verify `ok: false` only for flush 0.118 / 0.151 m (limit 0.1) on steep banks: no gaps, no open edges, no Concrete reshaped, seams dz 0. Cut up to 2.3 m, fill 3.5 m at the portals; Custom4 `Spline_path390_piece2_0` lifted 1.4 m over the route. Tidied. Backup `meloneras_1_pre-C38_01.blend` |
| C47 | arched motorway-portal underpass (replaces C44, C45, C46) 3.2 x 3.0 m (`kind="tunnel"`, **`style="portal"`**: wide wall, raised arch ring, short splayed wings; textures in Unity), `CULVERT_C44_IN/OUT`, separate objects, under the joined motorway | north portal 8.2 m north of the original cursor (-1194.01, -1584.84) on bearing 195.3 (inv 47.63); south portal 31.2 m south of it (inv 49.2, the south path's actual level); 39.4 m long | `flow="as_bearing"`, `deck=False`, `band` 2.5, `footing` 1.0, `channel_fade` 10, edits: inverts, `top_rel` 4.0/4.06 (ground 1 m behind each mouth), wing ends from ground, barrel rises for a straight floor | Verify `ok: true` (flush 0.04 / 0.02 m), no stray open edges, road not reshaped, 964 coincident seam vertex pairs with dz 0. Tidied. Pre-build backups `meloneras_1_pre-C41..C47_01.blend`. Apron areas checked by ray casts: only the culvert apron is on top. |
| C51 | 9.2 x 3.4 m box portal underpass (`kind="underpass"`, `style="portal"`, `side` 2.0, `corner` 0.9, textures in Unity) under the slip road, aligned with the two cart paths (replaces C48-C50) | west mouth 3.0 m and east mouth 24.5 m along the line through the two path centres, bearing 93.6, from the west path's end (W = cursor + 2.5 m right of the old axis at -3 m; stored in `%TEMP%xis.json`); inv 41.3 / 42.5; 21.5 m long | `flow="as_bearing"`, `deck=False`, `band` 2.5, `channel_fade` 10, edits: inverts, `top_rel` = max ground 0.6-2.0 m behind across the wall width (5.4 both, the cap), wing ends from ground | Verify `ok: false` only on the east mouth: flush 0.11 m (limit 0.10), unsealed 0.04 m, because the wall corner sits close to the slip-road deck edge. West flush 0.03. Deck repaired to its plane after the blend, 4456 coincident seam pairs dz 0, aprons clear. Tidied || C49 | (superseded by C51) two-car-width box portal underpass 5.5 x 3.4 m (`kind="underpass"`, `style="portal"`, `corner=0.9`, textures in Unity) under a slip road (replaces C48, the 3.2 x 3.0 arch), `CULVERT_C49_IN/OUT`, separate objects | west mouth 0.4 m east of the cursor (-820.12, -1207.84) on bearing 112.4 (inv 41.35); east mouth 19.1 m on (inv 42.4, the east path surface); 18.7 m long | `flow="as_bearing"`, `deck=False`, `style="portal"`, `band` 2.5, `footing` 1.0, `channel_fade` 10, edits: inverts, `top_rel` 5.32/4.87 (ground 1 m behind), wing ends from ground; wall half-width 6.78 m | Verify `ok: true` (flush 0.06 / 0.02 m), no open edges, deck exactly on its plane (deviation 0.0), 3752 coincident seam vertex pairs with dz 0, both aprons clear of other meshes. Road gap bridged with kit `opcd_road.py`. Tidied. Backups `meloneras_1_pre-C48_01.blend`, `BAK_ROAD2_*` (road work) |
| C53 | 2.0 x 1.6 m arched culvert (`kind="arch"`, `style="slim"`; textures in Unity), `CULVERT_C53_IN/OUT`, separate objects, under cart path `Spline_path100_piece1_5` (live MCP, 1 Oct 2026, file `meloneras_v4.blend`; replaces C52) | inlet at the cursor (-665.861, -955.381) inv 17.44 (ground); outlet (-677.306, -940.617) inv 17.25 (0.19 m fall); bearing 322.2, 20.4 yd (18.7 m) | `style="slim"`, `smooth=2`, explicit `inlet`/`outlet` points (C52 used smooth 4 and its inlet flush was 0.104) | Verify `ok: true`: flush 0.083 (inlet) / 0.019 m, no stray open edges, path not reshaped (deck 0.03 m). The 97,133-vert `Spline_path384_2_Custom4_-_Mesh` was already over Unity's limit and is untouched. Custom4 filled up to 2.5 m, cut up to 2.7 m. Tidied. Backup `meloneras_v4_pre-C53_01.blend` (also `_pre-C52_01`) |


**Path creek crossing re-mesh, 1 Oct 2026** (`scripts/path_remesh.py`, background job, not live):
- Source `H:\Meloneras_Latest\Support Files\Blender\meloneras_1_creek_v2.blend` (left untouched). Output
  `…\Blender\meloneras_1_creek_v3.blend`, report `meloneras_1_creek_v3_rebuild_report.json`, before/after images in
  `…\Blender\path_crossing_previews\`. Config `C:\Users\steve\Claude_Code\Blender Scripts\Meloneras\meloneras_path_crossing.json`.
- Where: the 3 m cart path `Spline_path100_piece4_1_Concrete_-_Mesh` crosses the creek `Spline_path333_Water_Base_Lake_-_Mesh`
  at about (-1663, -1446.5). An earlier gap fill had left a fan of slivers across the path (76 sliver faces in the
  10 m cell at (-1670, -1450)) and a 0.25 m dip on the north edge at the creek bank (a crease in the renders).
- Settings: centreline (-1680,-1443.0) (-1672,-1443.6) (-1666,-1445.2) (-1662,-1447.2) (-1656,-1450.8) (-1650,-1455.0),
  `s0` 11.3, `s1` 25.6 (about 16 yd of path); other keys default.
- Result: 158 faces replaced by 109, 13 crowded edge verts removed, 24 interior verts; median face quality 3.98
  (same as the regular strip), worst 13.7 at the south bank corner. North edge raised up to 0.25 m, south 0.05 m.
  Seam gap 0, no flipped or non-manifold faces. Neighbours adjusted (snapped / faded): Rough `348_piece1_2` and
  `348_piece3_2`, creek beds `333_Water_Base_Lake` and `334_Water_Base_Lake` (both are beds, not flat water), and the
  blends `333_B_Rough`, `334_B_Rough`, `334_B_Concrete`.
- Left as it was: a ~0.15 m bulge in the north path edge where the creek bank corner meets it (part of the creek
  outline); straightening it needs the creek mesh reshaped. Offered to the user, not done.
- Unity: the path and bank only went up, so the terrain stays below them; nothing to lower.

C48/C49 notes (slip-road underpass, 1 Oct 2026, cursor (-820.12, -1207.84) at the end of the west cart path):
- Layout: a cart path runs E-W (bearing about 100) and ends at the cursor; its east piece starts 18 m east. A SLIP ROAD (about 10 m wide, z about 48.1, flat) runs bearing 30.5 across it with a 39 m gap between its two pieces (south piece ends s=-17, north piece starts s=21.6 in the frame origin = cursor, rd = 30.5, ax = 120.5, road centre u about 10.4). The user said 'slip road, narrower than a motorway'. The road pieces are islands of ONE mesh (`Spline_path266_2`), found by walking edges; the E-W east cart path is a third island of the same mesh.
- New kit module `opcd_road.py` (Frame, fit_plane, lift_ends, bridge_gap, ground_bvh, embankment) does the road recipe from C47 in a few calls. Used: fit_plane on windows 18-36 m either side of the gap (z = 48.277 + 0.0055 s - 0.008 u, rms 0.24), lift_ends (full 1/3 m, fade 3, lateral 6), bridge_gap (16 free-edge verts each side), push pink vertices under the deck, `embankment` twice with `coons_sides=True` (`Spline_path920_Custom4_-_Mesh` west, `Spline_path921_Custom4_-_Mesh` east, 14 m slopes). `bridge_gap`'s `u_range` must hug the road (5.5-15.3) so the end chain excludes the side branches.
- Portals sit where the slope height equals the wall top: west at the cursor (the path end is inside the slope footprint, so the slope buries the path and the blend cuts a cutting through it), east 3.6 m inside the slope toe. Axis chosen to join the two path ends (bearing 112.4, 8 degrees off square to the road). East floor = path surface at the apron (42.4), not its end vertex.
- Paths trimmed before the blend: west path faces behind the apron (k > -2.6), east path faces k in (15.9, 22.2) with z < 45.5 (the slip road deck is in the same mesh: guard with z).
- Opening change (user: wider, squarer, two car widths): `kind="underpass"` (box) 5.5 x 3.4 m with a new `corner` param (0.9 m top chamfer; kit 2026.10.01-6, `opening_profile(..., corner)` used by the mouth meshes and the curved sweep). Same mouths, inverts and trims as C48; verify `ok: true`, aprons clear, wall 13.6 m wide.
- Alignment lesson (user: 'it needs to be as wide or wider than the concrete mesh running up to it'): the axis I used (bearing 112.4, cursor to the east path's nearest vertex) was 19 degrees off the real path line, so the opening was off-centre and narrower than the paths. Measure each path's centre line (lateral extent per axial bin) and take the line through the two centres at the gap (west path width 7.2-8.2 m, east 9.0-9.5 m, here bearing 93.6). Opening width = the widest path (9.2 m), not a vehicle count. Check alignment before building.
- A wide wall near a road edge: the blend's band lowered the slip road deck by up to 1.9 m near the east wall corner. After the blend lift the dented deck vertices back to the road plane (fill-only) and sync coincident neighbours, then tidy. `top_rel` should be the MAX ground 0.6-2.0 m behind the wall across its full width, not the centre value; it still reaches the underpass cap (rise + 2.0).
- To-do: Unity terrain must be RAISED under the slip-road deck and slopes and lowered inside the underpass. Add C48 and the road steps to the job script when it can run them. Not saved by the user yet.

C47 notes (motorway underpass, 1 Oct 2026; replaces the first C41-C43 attempt, a plain box with portals at the road edges, and C44-C46):
- Layout: the cursor sat in a 37 m gap between two wide motorway meshes (`Spline_path295_island0_3` west, `island1_0` east). The road is a flat plane z = 55.284 + 0.0062 s + 0.0428 u (s along bearing 105.3, u across, 29 m wide), rms 0.1 m. The cart path `Spline_path266_4` ends at its north side and `Spline_path292` starts at its south side. The gap had no surface mesh (void); the road ends had dipped into the heightmap notch by up to 1.3 m (west) and 4.3 m (east).
- Road, by script (no kit helper yet): backup the six surface meshes in the zone (`BAK_ROAD_*`); fill-only lift of the dipped ends to the plane as an XY field over all surface meshes (8 m lateral fade, windows at the two road ends only); `T.join_into` the two road meshes (same `Col` attribute and `Concrete` material); `bmesh.ops.bridge_loops` between the end edge chains, subdivide the cross edges 14 times, set z to the plane; push pink Custom4 vertices under the deck 0.25 m below it.
- Embankments (the 'mesh comes up to meet the road'): two new Custom4 meshes `Spline_path910_Custom4_-_Mesh` (north) and `Spline_path911_Custom4_-_Mesh` (south), each a 15.5 m slope grid whose top row IS the deck's free edge vertices (so no gap), sloping down to the sampled ground at the toe. North uses a Coons patch so its west and east sides follow the lifted pink slopes; the south uses a straight lerp (nothing to match). They need `T.match_attributes` plus object colour = the pink meshes' `.color` and smooth shading (the viewport shows `Object` colour, so without that they look grey).
- Portals sit where the slope height equals the wall top (about 8 m and 4 m out from the road edges), so the wall reads as a portal cut into a grassed slope. The kit then carves, fills and tidies as normal; `plan_culvert` reads the deck/slope as ground, so override `in_invert`, `out_invert`, `top_rel` (ground 1 m behind the mouth) and `wing_end_rel`, and set `barrel_rise` for a straight floor.
- Cart paths that run into the hill: trim their faces behind the mouth first (centre beyond the mouth plane, within 12 m of the axis). Otherwise the blend's barrel plateau lifts the path end 5 m onto the slope.
- Style `portal` (kit 2026.10.01-5): new params `side` (wall width each side of the opening, default 0.25 x span) and `ring` (width, proud) for a raised arch ring; `STYLES["portal"]` = wing 3.0 m at 20 deg, wall 0.5, apron 0.2, side 3.5, ring (0.45, 0.25).
- Base clean-up (user: meshes coming through the base of the portal): the south path's surface near its start sits 0.9-1.6 m above the end vertex I read (cross-slope), so the first south apron at invert 48.0 was buried under the path. Take the invert from the path surface at the apron (49.2) and trim path faces so the apron ends exactly where the path starts (path faces with centre within 12 m of the axis and axial distance < mouth + 2.8 m). After the blend, ray cast a grid over each apron: the topmost hit must be the CULVERT object.
- The 3D cursor moves: the user moved it while I worked, and a re-plan that read it built the underpass in the wrong place (C45, restored). Read the cursor once and hard-code the coordinates (-1194.01, -1584.84).
- To-do: Unity terrain must be RAISED (embankment) under the deck and slopes across the gap, and lowered inside the underpass; check both portals in GSPro. Add C47 and the road steps to the job script when a helper exists. Not saved by the user yet.

C38 notes:
- The user wanted a long tunnel that curves under the mesh from the cursor to a second arrow. Both arrows were laid flat pointing into the tunnel (entrance bearing 161.3, exit arrow 6.8 so travel out is 186.8). The kit could only build straight culverts, so kit 2026.10.01-4 added `plan_curved`, `build_curved`/`build_mid`, `fill_over` and `curved_cover`, and `tidy` follows `plan["centreline"]` (see culvert.md).
- First attempt (C37) had 52 m straight barrels because `plan_culvert` sets passage `barrel_depth` to half the chord; fixed by resetting it in `plan_curved`. The first sweep stopped up to 0.7 m short of the exit barrel (1 m grid); fixed by adding rings exactly at the barrel ends.
- To-do: add C38 to `meloneras_culverts.py` (documentation entry; the job can't build curved tunnels yet) and lower the Unity terrain under the whole route, deepest at the entrance bank (cut 2.3 m). No material.

C35 notes:
- Replaced C33 (and C29). The user wanted the opening to look more like an arch, filling most of the headwall face so a buggy fits. Round pipe 2.2 m made a small hole in a tall wall; `kind="arch"` 2.4 x 2.2 m verified but still looked small, so the final opening is 2.8 m wide x 3.0 m tall.
- Axis: the cart path crosses at bearing 68 degrees (PCA of its verts within 6-9 m of the crossing), so the axis is square to it, bearing 338.
- Side parts: the kit has no no-wing mode. `wing_len` 0 falls back to the default, 0.05 m with the headwall edited to the ground gave `ok: false` (flush 0.84 m), 0.8 m failed by 0.17 m, 1.5 m at 20 degrees verifies. The headwalls follow the bank, so they are tall; a truly wall-less opening would need a wide sloped cutting (not tried).
- Smoothing ran over the pipe's own frame (axis s, lateral l) and left a 0.047 m seam mismatch with one neighbour mesh, fixed by one round of seam sync over ALL surface meshes within 40 m.
- The user liked this look best (1 Oct 2026): it is now the house style, `style="slim"` in kit 2026.10.01-2 (see SKILL.md). Future culverts reuse this shape and change only the opening (arch, box or pipe sizes).
- Abandoned plans C21-C23, C25, C27-C34 left nothing in the scene.
- Geometry cleanup (1 Oct 2026, kit 2026.10.01-3): the user showed the wing banks with a messy triangle fan and a sharp V crease. `C.tidy("C35")` was run on the live scene (backup copies `BAK_C35tidy_*`): quads joined, vertices relaxed, creases softened, seams dz 0, verify `ok: true`. The job and live workflow now run `C.tidy` on every build. The earlier live builds (C03, C05, C07, C09, C14, C20, C24, C26) were tidied afterwards the same day (backup mesh copies `BAK_C<nn>tidy_*` in the open file): all that could be verified still verify as before (C05, C07, C09, C14, C24, C26 `ok`; C20 stays `ok: false` for the same reasons as before, expected approach-path reshaping and a marginal soffit check; C03 can't be verified because its mouth objects are one unjoined `CULVERT_C03`), seam dz 0 round every build. Not yet saved by the user.
- To-do: add C35 to `meloneras_culverts.py` (documentation entry) and lower the Unity terrain under it. No material (textures added in Unity).

C26 notes:
- The user set both arrows; the cursor was a spot at the bottom of a dip with no ground fall either way along Y, so the lower end came from the dragged arrow. Arrows laid along the axis need `rotation_euler=(-90 deg, 0, 0)` (IN, +Y) and `(+90 deg, 0, 0)` (OUT, -Y); the default empty arrow points up Z and the user took that as wrong.
- To-do: add C26 to `meloneras_culverts.py` (documentation entry) and lower the Unity terrain under it. The user adds textures in Unity, so no material.

C24 notes:
- The user dragged both arrows, and the arrow nearest the cursor sat on the bank 1.6 m above the cursor ground. Plan the cursor end with `inlet=(cursor.x, cursor.y)`, not the arrow, so the invert is the cursor ground. Check which end is higher before choosing inlet/outlet (the first plan had them reversed: "inlet bed LOWER" warning).
- Stone finish is Blender-only (procedural). For Unity/GSPro give it a real stone image on the UVs or bake the material.
- It is not an arch like the user's reference photo: only the texture was asked for. Add `kind="arch"` if they want the shape too.
- `Meloneras_stone_01` is in `meloneras_culverts.py` as a **commented-out, documentation-only entry** (kit 2026.10.01-1 job keys `stone=True`, `join=False`). The user saved the open file as `meloneras_1.blend` on 1 Oct 2026 with C03-C24 built live, and that file is the job's `BLEND`, so re-running the entry would build a second copy. A test run against the older saved file gave `ok: false` (`unsealed_by_m` 9.99) because its ground differed from the live scene. The saved `meloneras_1.blend` is the approved result.
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

---
name: opcd-feature-blend
description: Add built features such as culverts (concrete pipe, corrugated steel, stone/brick arch, box) and passages (motorway/road underpass, road tunnel portal) to an OPCD V4 GSPro course .blend in Blender 4.5. It carves, reshapes and joins the surrounding OPCD surface meshes (Fairway, Rough, Concrete, Custom1-4 ...) so the feature sits flush and sealed in the terrain. Each course gets a re-runnable job script, run in a background Blender with test renders, and the result is saved to a new .blend. Use this whenever the user wants to put a culvert, drain, headwall or pipe under a cart path or bank, an underpass under a motorway or road, or a tunnel through a hill, or add any structure to a run-off, ditch or burn on a course. Also use it to blend an object into OPCD meshes or edit terrain around a placed asset, or to re-mesh and smooth a pinched, creased or bumpy stretch of cart path or road (e.g. "make this circled bit look like the rest of the path"), even if they don't say "culvert" or name the skill.
---

# OPCD feature blend (Blender 4.5, background jobs)

Adds a feature (culverts, plus underpasses and road tunnels) to an OPCD V4 course that is **already meshed**, and makes
the terrain meet it cleanly. The finished feature is **joined into the nearest `Concrete`
mesh** so it exports with the course. It works like `procedural-building-blender`:

- a shared library (the kit) plus one **re-runnable job script per course**;
- runs in a **background Blender**, never in the user's open file;
- **test renders** you read back and compare;
- a **final** run saves `changed_blend.blend`, and never overwrites or deletes an earlier one.

The geometry is done by the bundled, tested kit. Don't hand-write bmesh code for steps
it covers. It already handles seams opening between meshes, Boolean failures on open
terrain sheets, low banks, and UV/colour-attribute mismatches on join.

## Paths

- **Kit:** `C:\Users\steve\Claude_Code\Blender Scripts\opcd_feature_kit\`, containing
  `opcd_terrain.py`, `culvert.py`, `culvert_job.py`, `opcd_road.py`, `path_remesh.py` and `selftest.py`.
- **Job scripts:** `C:\Users\steve\Claude_Code\Blender Scripts\<Course>\<course>_culverts.py`,
  e.g. `Blender Scripts\Meloneras\meloneras_culverts.py`. Start from
  `<SKILL_DIR>\scripts\templates\course_culverts_template.py`.
- **Blender 4.5:** `C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`. Check it
  with `Test-Path` and ask if it's missing. OPCD courses are 4.5 files. **Never run a
  course job in Blender 5.x**: saving would upgrade the file.
- **Test renders and reports:** the session scratchpad, or `<course .blend folder>\culvert_test\` when the user runs the job.
- **Final output:** `changed_blend.blend` next to the course `.blend` (the job's
  `OUT_BLEND`). If one already exists, it is renamed to `changed_blend_01.blend`,
  `_02` ... first. Previews and `culvert_report.json` go in `culvert_previews\` beside it.

### Install or update the kit (check at the start of every session)

`KIT_VERSION` is in `culvert.py`. If the kit folder is missing, or its `KIT_VERSION`
differs from `<SKILL_DIR>\scripts\culvert.py`, copy `<SKILL_DIR>\scripts\*.py` into the
kit folder (the templates are not needed there). Say so in one line. Never edit the kit
copy in place: change the skill's `scripts\` and re-copy.

## Conventions (from the user)

- 1 BU = 1 m. Talk in **yards** for lengths and **metres** for elevations. Pipe sizes
  can be given in inches or mm. Job entries are in metres: 600 mm = `0.6`, 24 in =
  `0.6096`, 4 ft = `1.2192`.
- Surface mesh names **contain** one of: `Fairway, Tee, Rough, Custom4, Custom3,
  Custom2, Custom1, Bunker, Concrete, Lake, Creek`. OPCD finds meshes by name, so
  **never create an object whose name contains those words**. Features are named
  `CULVERT_<id>_IN/OUT` until they are joined.
- The user places the **3D cursor** where the feature is to be built. **Ask what it
  marks**: the *crossing* (on the path or bank the culvert passes under) or a *mouth*.
  A common case is the cursor at the outlet in the run-off, with the culvert under the
  nearby cart path (`cursor_is="outlet"`). The run-off is usually a depression in the
  ground, and **the user identifies it**, so confirm detected channels.
- **The cursor is the reference.** When it marks a mouth, the invert is the ground right at
  the cursor, and the headwall, wings and apron build up from there. A level pad
  (`pad`, on by default) flattens the ground over the apron and about 1 m beyond it to apron
  level, so the structure sits on flat ground. Don't raise a mouth's invert above the ground
  at the cursor with `edits`: the Meloneras pipe showed that this mounds fill round the
  headwall. If a mouth's headwall comes out too tall, move the cursor rather than raising
  the invert.
- Culverts are **concrete**, joined into the Concrete mesh with its material. The barrel is
  modelled **1 yard** deep behind each mouth and then capped.
- **Passages** (`kind="underpass"` for a box under a motorway or road embankment,
  `kind="tunnel"` for an arched road tunnel portal) carry a path or road through. They
  have an open barrel end to end, a floor that follows the road, and level approach
  cuttings. For passages, the cursor marks the `crossing` (on the embankment crest) or a
  `portal` (on the path at one end, in which case the passage runs along the path). See
  `references/culvert.md` §1 "Passages".
- `Lake`/`Creek` meshes are flat water and are **left alone** by default. Ask if one is in
  the zone.
- A course `.blend` may hold a hidden **`Terrain`** mesh (2049 × 2049 = 4,198,401 verts): a
  copy of the Unity terrain heightmap. It has no surface keyword, so the kit never edits it,
  but it still renders and shows up as grey ground filling the mouths. Put it in the job's
  `HIDE_IN_RENDERS`. The real Unity terrain still sits at the old ground level; see
  workflow step 7.
- Library assets: ask at the start of a session whether a library `.blend` should be used,
  and where it is. Procedural is the default.
- **False dips over the barrel.** Meshes conformed to the Unity terrain often dip where
  the heightmap has a notch along the watercourse or through the embankment. The kit's
  **deck** step (on by default) raises every surface over the barrel, including the road
  or motorway on top, to a straight chord across the notch, and never lowers anything.
  Report the `deck.max_fill_over_barrel_m` from the plan. Tune it with
  `overrides.deck_reach`, or switch it off with `overrides.deck=False`. See
  `references/culvert.md` §1 "Deck".
- **Tidy geometry on every build (user request, 1 Oct 2026).** The blend leaves a messy fan of thin triangles and
  creases beside the wings. `C.tidy(pid)` (kit 2026.10.01-3) joins triangles into quads, relaxes the vertices
  sideways, smooths heights (cart paths keep theirs) and syncs seam vertices to dz 0. The job runs it after blend
  (`tidy=False` in an entry turns it off); live builds run it after `C.blend`, before `C.verify`.
- **Road gaps (kit module `opcd_road.py`).** For an underpass beneath a road whose pieces stop short (void gap): `Frame`, `fit_plane`, `lift_ends`, `bridge_gap`, `embankment`; see the C48 notes in `references/courses.md` and the module docstring. Find road pieces as connected islands even inside one mesh object, and ask what is the road if it is not obvious.
- **Pinched or bumpy path sections (`path_remesh.py`, 1 Oct 2026).** When the user circles a stretch of cart path
  or road whose triangles have collapsed into a fan of slivers (typically left by `bridge_gap` or a blend) and asks
  for it to look like the regular strip either side, don't hand-edit it. Run `scripts\path_remesh.py` in the background:
  1. `scan` (config needs only `"path"`): it lists 10 m cells with sliver triangles, which shows where the zone is.
  2. Write `<Course>\<course>_path_<place>.json`: the mesh, 5-8 `centreline` points down the middle of the path
     (from at least 9 m before the zone to 9 m after it), and `s0`/`s1`, the zone in metres along the centreline.
     The ends must sit in regular strip, because the height fit uses the 7 m either side.
  3. `test`: it re-meshes with even triangles (edge verts ~0.55 m, interior rows at 1/3 and 2/3, ~1.1 m apart),
     fits a smooth cubic height profile per edge pinned at the zone ends, moves neighbour seam vertices onto the new
     edge and fades the height change into them over 1.5 m. Check `seam_gap_max_m` 0, `flipped_faces` 0,
     `non_manifold_edges` 0, and a top-down wireframe plus a low-angle render, before and after.
  4. `final` to a **new** `.blend` (e.g. `_v3` after `_v2`; it refuses to overwrite).

  Usage and config keys are in the script docstring. The path outline is kept: where a creek bank corner bends the
  edge, the extra edge verts stay (`side_tol`), so small fans remain there. Straightening that bend means reshaping
  the creek mesh; offer it, don't do it unasked. The Meloneras run is recorded in `references/courses.md`.
- **Motorway portal style (kit 2026.10.01-5).** When the user wants a portal like a road tunnel (wide wall, big arch, raised arch ring), use `kind="tunnel"` with `style="portal"` (params `side`, `ring`); keep `slim` for ordinary culverts. Where a road crosses over, bridge and flatten the road, build embankment meshes up to its edge, and put the portals where the slope reaches the wall top; see the C44 notes in `references/courses.md`.
- **Curved tunnels (kit 2026.10.01-4).** For a long tunnel that bends under the ground, ask the user to lay two arrows
  flat (`CULVERT_IN` at the cursor, `CULVERT_OUT`), each pointing the way you would travel INTO the tunnel at that
  end; the exit's travel direction is its arrow bearing + 180. Then `C.plan_curved("tunnel", span, rise, P0, in_bearing,
  P3, out_bearing, straight=14, style="slim", band=1.5, footing=1.0)`, `C.build_curved`, `C.backup`, `C.blend`,
  `C.fill_over` (lifts ground that is below roof + 0.6 m), `C.tidy`, `C.verify`, `C.curved_cover`. See `references/culvert.md`.
- **House style: `style="slim"` for every new culvert (user decision, 1 Oct 2026).** The user prefers the look of
  the Meloneras C35 arch: a plain headwall with short wings and a thin wall (`wing_len` 1.5, `wing_angle` 20,
  `wall` 0.25, `apron_thk` 0.1). Always pass `style="slim"` to `plan_culvert` / the job entry and only change the
  insert: the opening kind and size (`arch`, `box` or `pipe`, any span and rise). Don't offer other wing/headwall
  shapes unless asked. The user adds textures in Unity, so no materials by default. Headwalls follow the bank, so on
  a high bank they are tall; that is expected.
- **Level the path over a culvert (kit 2026.10.06-1).** When the user asks to level a cart path or road
  over a culvert, or to close gaps under a path edge or around a culvert, use `C.level_path(pid)` after `tidy`
  and before `verify`, or `level_path=True` in the job entry. It puts the path on one smooth grade fitted
  to the path either side (cut and fill), lifts it only if cover over the barrel would drop below 0.3 m,
  makes the ground follow, raises ground that sits below a path edge, keeps the walls sealed and syncs
  seams. If the report has `suggested_edits` (the path runs up to a headwall that is now too low), apply
  them through `restore` → `edit_plan` → `build` → `backup` → `blend` → `tidy` → `level_path`; the job does
  this itself. Check `max_edge_gap_m` < 0.03 and `zone_deviation_from_grade_m` 0. Details in
  `references/culvert.md` "Level path". For a culvert that is already **finalised** (joined), restore it or
  re-run the job first: `level_path` only works on a blended, unjoined culvert.
- **Known courses** and their paths, features and open to-dos are in
  `references/courses.md`. Read it when the user names a course.

## Workflow (every culvert)

1. **Gather**, asking everything unknown in **one** AskUserQuestion:
   - the course `.blend` path;
   - what the cursor marks (crossing, outlet or inlet; for passages crossing or portal);
   - type and size;
   - anything the screenshot makes ambiguous.

   Get the cursor position one of two ways:
   - If blender-mcp is connected, read it **read-only** with
     `execute_blender_code("import bpy; print(tuple(bpy.context.scene.cursor.location))")`,
     and write it into the job as `at=(x, y)`.
   - Otherwise ask the user to save after placing the cursor, and leave `at=None`. The
     job then uses the cursor saved in the file.
2. **Write or extend the job script.** Use one file per course and add one `dict` per
   culvert to `CULVERTS`: `name`, `kind`, `span`, `rise`, `cursor_is`, `at`, `bearing`,
   `inlet`/`outlet`, `target`, `overrides`, `edits`. Keys are explained in the template and
   in `references/culvert.md`. The job is re-run from the untouched source every time, so
   **change a culvert by editing its entry and re-running**. Never hand-patch a scene.
3. **Test run in the background:**
   ```powershell
   & "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b --factory-startup `
     --python "C:\Users\steve\Claude_Code\Blender Scripts\opcd_feature_kit\culvert_job.py" -- `
     "<job.py>" test "<scratchpad>\culverts"
   ```
   It plans, builds, blends, verifies and joins every culvert in memory. It writes
   `culvert_report.json` and `<name>_Inlet / _Outlet / _Overview.png`, and saves nothing.
   In the renders the culvert is orange and each surface has a flat colour. Cycles uses
   the GPU when one is available. Exit code 0 means every culvert verified.
4. **Read the report and the PNGs yourself** before showing the user. Check
   `ok`, `warnings`, `axis_source` (anything AUTO must be confirmed), `fall_m`, and the
   `verify` block. Fix failures by editing the job (see the table below) and re-running.
   Then send the PNGs with SendUserFile, say in plain terms what was decided or guessed
   (axis, inverts, headwall heights, length in yards), and get approval. **Test-render
   after every tweak, before the final run.**
5. **Final run.** Only after approval, and **without** `--factory-startup`, so the OPCD
   addon loads and its scene data round-trips:
   ```powershell
   & "...\Blender 4.5\blender.exe" -b --python "...\opcd_feature_kit\culvert_job.py" -- `
     "<job.py>" final "<OUT_BLEND folder>\culvert_previews"
   ```
   An earlier `changed_blend.blend` is kept as `changed_blend_NN.blend`. Nothing is
   saved if any culvert fails verify. Tell the user to open the new file. Their open
   Blender still shows the old one.
6. **Pin and record.**
   - Once approved, replace `at=None` in the job with the mouth that was used, e.g.
     `at=(x, y)` from the report's `ends`. Re-runs then don't move when the saved cursor
     moves; on Meloneras the saved cursor moved between two tests.
   - Add or update the course in `references/courses.md` in the OPCD_Recipes repo, so
     every session sees it: job path, `.blend` paths, Blender exe, each feature's entry and
     result, and to-dos such as lowering the Unity terrain. Also save it to project memory
     when the session has one.
7. **Unity terrain.** Once the user has imported the new meshes into Unity, tell them to
   run Unity's **Lower terrain under meshes** command over the feature area. Otherwise the
   terrain, still at the old ground level, fills the mouths, aprons and channels in
   GSPro. Then ask them to check:
   - each mouth, looking in from the channel: no terrain inside the opening or across
     the apron;
   - each channel: deep enough at the bed. Give the cut depths from the report's
     `meshes.*.max_cut_m`, because a command that lowers by a fixed offset may not reach
     the full cut.

   A notch left in the terrain under a road the deck step raised is harmless, because it
   stays below the meshes. Tick the to-do in `references/courses.md` once it's done.

### Acting on verify

| check | meaning | typical fix (edit the job entry) |
|---|---|---|
| `stray_open_edges > 0` | new tear or hole near the feature | larger `overrides.band`, or check the source mesh near the feature for holes |
| `buried: false` | barrel pokes out of the bank | raise `edits.in_top_rel` / `out_top_rel`, or lower the invert |
| `unsealed_by_m > 0` | ground misses a wall face | larger `overrides.footing`, or smaller `overrides.smooth` |
| `flush_max_error_m >= 0.1` | ground doesn't meet the wall top | features too close together; smaller `band` or more spacing |
| `fall_m <= 0` / "inlet bed LOWER" | water would run backwards | confirm the flow; swap `cursor_is`, give `bearing`, or edit the inverts |
| "mouths only ... apart" | the two ends overlap | give `inlet`/`outlet` points further apart |
| `unity_65k` | mesh over 65,535 verts (Unity 2018) | tell the user; they may split the mesh in OPCD. Check `verts_before`: often it was already over. |
| `concrete_reshaped` not empty | a cart path or road was cut or filled (warning, not a failure) | if the feature doesn't cross that path, use `overrides.band` 1.5 and raise the headwall (`edits.in_top_rel`); expected only for the approach path into a passage |
| road over the feature still dips after blending | notch wider than the deck reach | raise `overrides.deck_reach` (default 6 m beyond the headwall half-width) |
| grey ground filling a mouth in the renders | a non-OPCD mesh (usually `Terrain`) is rendering | put it in `HIDE_IN_RENDERS`; see Conventions |
| path over the culvert wavy, or gaps under its edges | heightmap waves the deck step can't cut | `level_path=True` in the entry (live: `C.level_path(pid)` after `tidy`) |
| `level_path` `max_edge_gap_m` >= 0.03 | ground beside the path is held by a wall pin or another path | larger `skirt`, or check which mesh sits under the edge |

After the join, **Concrete-wide recipes** (`smoothmesh`, `subdividemesh`, `zshiftmesh`,
re-meshing) also act on the culvert. Tell the user to run those on the source file first,
then re-run the final job.

## When this session can't run Blender (cloud / web)

A cloud session can't reach the user's C:/H: drives or Blender. Everything still runs on
their PC:

- Write the job (and any kit update) in the scratchpad, send each file with SendUserFile,
  and give the **exact target path** for each one. A common mistake is saving the kit
  *inside* the course folder; it must be at `Blender Scripts\opcd_feature_kit\`.
- Dry-run the job on a synthetic scene first (`pip install bpy==4.5.*`, then build a
  scene with `selftest.build_scene()`), so the files you send are known to work.
- Give PowerShell commands with full paths. Ask for the three PNGs and
  `culvert_report.json` back.
- For read-only checks in the user's open file, send a small script **file** that shows
  its result in a popup and prints it. Console one-liners get mis-pasted into the Text
  Editor, where `bpy` isn't imported and nothing is shown.

## Things to avoid (and why)

- **Building in the user's open Blender.** The job runs in the background from the saved
  file. Live edits are only for an explicit request; see `references/live-mcp.md`.
- **Boolean modifiers on OPCD surface meshes.** They are open sheets, so Exact/Manifold
  booleans drop faces. The kit's vertical-plane `carve` is used instead.
- **Per-mesh hand edits.** Anything that isn't a pure function of world XY opens seams
  between neighbouring surface meshes.
- **Overwriting any `.blend`, or deleting anything**, without asking.
- **Asking whether to join a feature into Concrete.** The user doesn't want to be asked. Live builds
  stay separate objects; join only on explicit request (see `references/live-mcp.md`, lessons).
- **Saving `.blend` files under the session scratchpad.** Its path is longer than Blender's limit, so
  `libraries.write` / `save_as_mainfile` fail with "Cannot open file ... for writing". Use a short folder such as
  `%TEMP%\<job>`. To iterate quickly on a 1 GB course file, write only the meshes in the zone to a small `.blend`
  with `bpy.data.libraries.write(path, objs, fake_user=True)` and test on that; run the final on the full file.
- **Naming a scratch script `inspect.py`.** It shadows Python's `inspect` module, so numpy fails to import in the
  same folder.
- **Separate (unjoined) units without `C.bake(pid)`.** Unity places them wrongly (object transform) and may not
  render them (no material/colours). Always bake as the last step of a live build; the job does it itself.
- **Live-mode sessions:** read the "Lessons" section of `references/live-mcp.md` first (stale marker
  arrows, undo wiping plan state, mouths on paths, passage cuttings cutting hillside paths).

## Extending to other features

A feature needs a local frame (origin at ground contact, +Y outward), a footprint outline
with a ground target per vertex, and a mesh. `opcd_terrain` (`densify`, `carve`,
`apply_height_field`, `smooth_zone`, `match_attributes`, `join_into`, `render_views`,
backups) is feature-agnostic. Model new types (footbridges, drain grates, sleeper walls)
on `culvert.py` and `culvert_job.py`. Extend the kit rather than job scripts, and bump
`KIT_VERSION`.

## Self-test

`selftest.py` builds a synthetic ditch under a cart path and runs everything for all four
culvert types, plus the outlet-cursor mode, the deck, passages and `level_path`. Run it to check the kit:
`blender -b --factory-startup --python selftest.py -- <out_dir>`.

## References

- `references/culvert.md`: types (incl. passages), sizes, anatomy, how the plan is derived,
  every parameter, the library asset convention, and tuning.
- `references/courses.md`: per-course record (paths, features built, to-dos).
- `scripts/path_remesh.py`: re-mesh and smooth a pinched stretch of path or road (see Conventions).
- `references/live-mcp.md`: applying a culvert inside the open Blender through
  blender-mcp. Only on request.
- `references/blender-mcp.md`: blender-mcp behaviour, Blender 4.5 API notes, and
  performance.

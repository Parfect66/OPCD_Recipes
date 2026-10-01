# Live mode: applying a culvert inside the user's open Blender (blender-mcp)

Use this **only when the user explicitly asks** for the change to be made in the file
they have open. The default is the background job in SKILL.md, which never touches the
open file. Live mode edits the user's scene directly, so it relies on the in-file backups.

## Load the modules in every `execute_blender_code` call

```python
import sys, importlib
p = r"C:\Users\steve\Claude_Code\Blender Scripts\opcd_feature_kit"
if p not in sys.path: sys.path.insert(0, p)
import opcd_terrain as T, culvert as C
importlib.reload(T); importlib.reload(C)
```

Every function prints JSON, which blender-mcp returns. Run one step per call. The plan
state lives on the scene (`scene["opcd_features"]`), so ids `C01`, `C02`, ... survive
across calls and sessions.

## Steps and gates

1. **Recon.** `T.scene_report()`: file path and saved state, mode, cursor, surface
   meshes (UV maps, colour attributes, vertex groups, modifiers, custom normals, 65k
   risk). The file must be saved, because backups need a path. Then
   `get_viewport_screenshot`.
2. **Plan.** Non-destructive. `C.plan_culvert(...)` takes the same arguments as a job
   entry. Show the summary and confirm any AUTO axis. `C.markers(pid)` drops draggable
   `CULVERT_IN`/`CULVERT_OUT` arrows; re-plan with `inlet="CULVERT_IN",
   outlet="CULVERT_OUT"`. Tweak with `C.edit_plan(pid, out_top_rel=..., ...)`.
3. **Build.** Non-destructive. `C.build(pid)`, then `C.frame(pid, "in")` / `"out"` and a
   screenshot of each. The user approves.
4. **Backup, blend, verify.** `C.backup(pid)` writes an incremental `.blend` copy and
   orphan mesh copies. Then `C.blend(pid)` and `C.verify(pid)`. Act on the checks (see
   the table in SKILL.md). If `blend` fails partway through, run `C.restore(pid)` and
   `C.backup(pid)` before retrying.
5. **Finalise.** Only after approval. `C.finalise(pid)` joins the culvert into the
   Concrete mesh.
6. **Approve or undo.** Happy: ask, then `C.discard_backups(pid)`. Changes wanted:
   `C.restore(pid)` puts every mesh back exactly, then redo from step 2. Never save the
   user's file unasked.

See `blender-mcp.md` for tool behaviour and API gotchas.

## Lessons from the Meloneras live session (30 Sep 2026)

- **Which Blender MCP.** Two servers exist. `mcp__Blender__*` timed out; the lowercase
  `mcp__blender__*` worked (`execute_blender_code` needs `user_prompt` = the user's words).
  Return values come back only if you `print()` them; assigning `result = ...` returned nothing.
- **The user never wants a join question.** Leave mouth units as separate objects, skip
  `C.finalise`, and don't ask about joining. Only join on an explicit request. To unjoin, separate
  the appended verts (index >= the old vertex count) with `bpy.ops.mesh.separate(type='SELECTED')` and
  rename the result to `CULVERT_<id>` (never a surface keyword).
- **Stale arrows steer the next plan.** `plan_culvert` silently uses existing `CULVERT_IN` /
  `CULVERT_OUT` empties as the mouths, even when hidden. After use, delete them before planning
  somewhere else, and always check `axis_source` and the mouth coordinates in the summary.
- **Undo wipes plan state.** If the user presses Ctrl+Z, `scene["opcd_features"]` reverts and
  `C.markers("C06")` fails with `KeyError`. Re-plan, then take the new id from
  `sorted(T.load_state())[-1]`.
- **Plan ids climb.** Every `plan_culvert` call makes a new id. `C.restore(old)` before re-planning
  a failed attempt, or the old carve stays in the terrain.
- **Markers.** Set `empty_display_size = 4`, `show_in_front = True`, `hide_select = False` so the user
  can see and drag them; read `.location` after `view_layer.update()`. The user may move only one.
- **Screenshots.** `C.frame` sometimes doesn't redraw. Set `region_3d.view_location`, `view_distance`
  and `view_rotation = Euler((pitch, 0, yaw))` directly, then `area.tag_redraw()`. To look at a mouth
  from its channel, yaw = +(360 - bearing) in radians only when bearing is in the NW quadrant: just try it
  and look. Top-down is Euler((0,0,0)). Take the screenshot in a separate call.
- **Mouth on a path.** The auto mouth can land on a path bend so the headwall and apron poke through it
  (user spotted this on C04). Before blending, test clearance: nearest path vertex (from the backup
  mesh) to the mouth, and count path verts inside each unit's XY bounding box (should be 0). Fix by
  moving that mouth 4 m or more further out along its `outward` vector and re-planning with explicit
  `inlet` / `outlet`.
- **Uphill cursor.** If the cursor is the low end and the warning says the far bed is higher, ask,
  then use `flow="as_bearing"` (outlet invert lowered, deep channel cut) when the user wants the cursor
  kept as the inlet.
- **Passages cut the path on the hillside.** A tunnel's level approach cutting (`channel_fade` 12 m,
  `channel_batter` 0.5) ran across a hillside path and left a cliff 15 m away, even with the path
  a long way from the mouths. `band` did nothing; `channel_fade=4.0, channel_batter=1.0` fixed it
  (`concrete_reshaped` empty). Check the path's vertex deltas against the backup after every passage blend.
- **Verify `ok: false`** appeared when `band` was cut to 1.5 on a tunnel (flush error 0.157 m). Keep the
  passage default band.
- **Backups.** `C.backup` writes `<file>_pre-C<nn>_01.blend` next to the open `.blend`. They pile up.
- **Built-in sizes used.** Buggy tunnel: `kind="tunnel", span=3.0, rise=2.6`. "1.5 rectangular" =
  `kind="box", span=1.5` (rise 1.125 by default); confirm with the user.

## Lessons from the C20 tunnel (1 Oct 2026)

- **Cursor on a path stub:** the auto "along the path" axis can run the wrong way for the user's intent. Drop `C.markers()` arrows (cursor mouth plus a guess across the large path) and let the user place both mouths, then plan with `inlet="CULVERT_IN", outlet="CULVERT_OUT"`.
- **Level floor:** passage floors follow the crest (`barrel_rise` up to +1.6 m), which can poke through low ground. `C.edit_plan(pid, in_barrel_rise=0.0, out_barrel_rise=0.0)` makes it level.
- **`C.verify` prints and returns None**; `C.plan_culvert` returns a JSON string. Capture stdout to parse.
- **Smoothing after a build:** average Z by XY across all touched surface meshes, pin verts within 0.6 m of the culvert, never lower over the barrel, then sync coincident cross-mesh seam verts (incl. untouched neighbours) to one Z. Check seam dz = 0 and roof cover afterwards.

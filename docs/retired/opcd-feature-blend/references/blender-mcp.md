# blender-mcp and Blender 4.5 notes

The default workflow runs in a background Blender and doesn't need blender-mcp. It is
used only to read the cursor position and for live mode (`live-mcp.md`). If a background
**final** run (without `--factory-startup`) hangs, check whether the blender-mcp addon
is set to auto-start its server: two Blenders can't share port 9876.

## Tools (ahujasid/blender-mcp)

| tool | use it for |
|---|---|
| `get_scene_info` | connection check, quick object list |
| `get_object_info(object_name)` | one object's transform, materials, vertex counts |
| `execute_blender_code(code)` | **all work**: load the modules and call them |
| `get_viewport_screenshot(max_size)` | show the user and yourself; call `C.frame(...)` first |
| Poly Haven tools (`search_polyhaven_assets`, `download_polyhaven_asset`, `set_texture`) | only if the user wants a separate textured material. The joined culvert uses the Concrete material, so none is needed by default |

The Sketchfab and Hyper3D tools are not used by this skill.

## How `execute_blender_code` behaves

- The code runs with `exec()` on Blender's main thread, from a timer. **Stdout is
  captured and returned**, which is why every module function prints JSON.
- There is **no 3D-view area context**. `bpy.ops` that need one (view3d.*, mesh.knife_project,
  loopcut, selection by view) fail. Use bmesh, or `bpy.context.temp_override(...)` for
  object-level ops such as `object.join` and `object.mode_set` (the modules already do this).
- Exceptions come back as an error string. Read the traceback. The plan's `status` is
  only advanced at the end of a successful step. Non-destructive steps (plan, build,
  backup, verify) can simply be re-run. If `blend` or `finalise` fails partway through,
  some meshes may already be edited, so run `C.restore(pid)` and then `C.backup(pid)`
  before retrying.
- Long calls block Blender's UI (see timings below). If the client times out, the step
  may still finish, so run `C.summary(pid)` and check `status` before retrying.
- If a call returns nothing at all, the installed addon may be an old version that
  doesn't capture stdout. Ask the user to update blender-mcp.
- Keep each call small: load the modules and make one step call. Don't paste the modules'
  source into the call.

## If blender-mcp isn't connected

1. In Blender: N-panel → **BlenderMCP** tab → start or connect the server (default port 9876).
2. The MCP client (Claude Code / Claude Desktop) needs the `blender` server entry, usually
   `uvx blender-mcp`. Restart the client after adding it.
3. Only one client can drive Blender at a time.

## Blender 4.5 API notes used here

- `bmesh.ops.bisect_plane(bm, geom=..., plane_co=..., plane_no=..., dist=...)` interpolates
  UVs and colour attributes on the new vertices, so paint survives the carve.
- `bmesh.ops.subdivide_edges(..., use_grid_fill=True)` then `bmesh.ops.triangulate` on any
  n-gons. Partial subdivision leaves concave n-gons, which can triangulate badly on
  export, so the modules keep the zone to tris and quads.
- `bpy.ops.object.join` merges UV maps and colour attributes **by name**. A culvert
  without the target's attributes would get default values on join (black paint, UVs
  all at 0,0), which is why `match_attributes` creates matching ones first.
- `bpy.ops.wm.save_as_mainfile(filepath=..., copy=True)` writes a backup without
  changing which file is open.
- Mesh colour attribute data is read and written as linear floats via `.color`, even
  for `BYTE_COLOR`.
- The Boolean modifier in 4.5 has Exact / Float / Manifold solvers. All expect closed
  volumes, and OPCD surface meshes are open sheets, so don't use them here.

## Performance on big OPCD meshes

The modules touch only vertices and faces inside the feature's zone, and use numpy for
the height field. The costs that remain scale with the mesh:

- `bm.from_mesh` / `to_mesh` for each affected mesh.
- One scan over the vertices per `carve`.
- `HeightSampler` builds a BVH per surface mesh.

These timings were measured headless in Blender 4.5.14 on a 490,000-vertex Rough mesh:

| step | time |
|---|---|
| plan | 2.3 s |
| build / backup / finalise | under 0.1 s |
| blend | 8.9 s |
| verify | 1.3 s |

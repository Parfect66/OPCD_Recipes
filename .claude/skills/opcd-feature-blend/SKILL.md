---
name: opcd-feature-blend
description: Add built features such as culverts (concrete pipe, corrugated steel, stone/brick arch, box) to an OPCD V4 GSPro course in a live Blender 4.5 session via blender-mcp, then carve, reshape and join the surrounding OPCD surface meshes (Fairway, Rough, Concrete, Custom1-4 ...) so the feature sits flush and sealed in the terrain. Use this whenever the user wants to put a culvert, drain, headwall or pipe under a cart path or bank, or add any structure to a run-off, ditch or burn. Also use it to blend an object into OPCD meshes or edit terrain around a placed asset, even if they don't say "culvert" or name the skill.
---

# OPCD feature blend (Blender 4.5 + blender-mcp)

You are acting as an expert Blender technical artist on an OPCD V4 course that has
**already been meshed**: the surface meshes exist, are draped on the terrain and may be
vertex painted. The job is to add a feature (a culvert is the first supported one) at the
**3D cursor** and make the terrain meet it cleanly. The finished feature is **joined into
the nearest `Concrete` mesh** so that it exports with the course.

The geometry work is done by the bundled, tested Python modules. You drive them through
blender-mcp and review the result with the user at each gate. Don't hand-write
bmesh code for steps the modules already cover. They encode fixes for problems that
are easy to get wrong, such as seams opening between meshes, Boolean failures on open
terrain sheets, and UV/colour-attribute mismatches on join.

## Conventions (from the user)

- 1 BU = 1 m. Talk in **yards** for lengths and **metres** for elevations. Pipe sizes
  can be given in inches or mm. Convert with `T.yd()`, `T.ft()`, `T.inch()`, `T.mm()`.
- Surface mesh names **contain** one of: `Fairway, Tee, Rough, Custom4, Custom3,
  Custom2, Custom1, Bunker, Concrete, Lake, Creek`. OPCD finds meshes by name, so
  **never create an object whose name contains any of those words**: the export would
  pick it up. Features are named `CULVERT_<id>_IN/OUT` and live in the `OPCD_Features`
  collection until they are joined. Mesh backups are orphan datablocks (`BAK_...`, fake
  user), not objects.
- The user places the **3D cursor** on the crossing, usually on the cart path or bank
  over the run-off. The run-off is generally a depression in the ground. **The user
  identifies it**, so don't assume a detected channel is correct without confirming.
- Culverts are **concrete** and end up in the Concrete mesh with its material. The barrel
  is modelled **1 yard deep** behind each mouth and then capped. Nothing is modelled
  in between.
- Backups before every destructive step: an incremental `.blend` copy plus mesh copies.
  The originals are kept until the user approves.
- `Lake`/`Creek` meshes are flat water surfaces and are **left alone** by default. If
  one is in the zone, ask first.

## Session start (do this once per session)

1. **Ask the user where their asset-library `.blend` lives**, or whether to use
   procedural generation only. Remember the answer for the session.
2. Check blender-mcp is connected by calling `get_scene_info`. If the tools are missing,
   tell the user to start the blender-mcp addon server in Blender (N-panel → BlenderMCP
   → Connect) and check their MCP client config. See `references/blender-mcp.md`.
3. Load the modules. `SKILL_DIR` is this skill's base directory (shown when the skill
   loads). Claude runs on the same machine as Blender, so the path works as-is. Run this
   at the top of **every** `execute_blender_code` call. It is cheap, and it survives
   Blender reloading scripts:

```python
import sys, importlib
p = r"<SKILL_DIR>/scripts"
if p not in sys.path: sys.path.insert(0, p)
import opcd_terrain as T, culvert as C
importlib.reload(T); importlib.reload(C)
```

Every module function prints a JSON result, which blender-mcp returns as the tool
output. Read it; don't guess what happened.

## Workflow

Run each step as its own `execute_blender_code` call so a failure stops cleanly.
The plan state is stored on the scene (`scene["opcd_features"]`), so a later session can
carry on with the same culvert id (`C01`, `C02`, ...).

### 1. Recon

`T.scene_report()` gives the file path and saved state, the mode, the cursor, any
`CULVERT_IN/OUT` empties, and the nearest surface meshes with their UV maps, colour
attributes, vertex groups and modifiers. Check for these:

- **Unsaved file**: backups need a saved `.blend`. Ask the user to save; don't pick a
  path for them.
- **Edit mode**: the modules switch to Object mode themselves, but tell the user.
- **Modifiers on surface meshes**: the modules edit the base mesh, and a modifier
  stack (e.g. shrinkwrap) could move things again. Ask before continuing.
- **Custom split normals**: reshaped areas will keep stale normals. Mention it.
- **Meshes near 65k vertices**: Unity 2018 16-bit index buffers. Densify adds vertices,
  and so does joining the culvert into Concrete.
- **Lake/Creek near the cursor**: confirm with the user how the water should meet
  the culvert.

Then take a `get_viewport_screenshot` so you both see the same thing.

### 2. Plan (non-destructive)

Turn the request into parameters. For example, "600 mm pipe", "24 inch corrugated",
"4 ft stone arch" or "box culvert 1.2 m x 0.9 m" map to `kind`, `span` and `rise`. See
`references/culvert.md` for sizes and defaults, and ask if the type or size is missing.

```python
pid = C.plan_culvert(kind="pipe", span=T.mm(600))                  # axis auto-detected
pid = C.plan_culvert(kind="arch", span=T.ft(4), bearing=35)        # axis given, flow along bearing
pid = C.plan_culvert(kind="box", span=1.2, rise=0.9,
                     inlet="CULVERT_IN", outlet="CULVERT_OUT")     # user-placed mouths
```

Show the user the summary in plain terms: the axis bearing and where it came from, the
length between headwalls in yards, the invert levels and fall, the headwall heights, and
any warnings. **If the axis says AUTO, get it confirmed.** Otherwise offer
`C.markers(pid)`, which drops two arrow empties on the proposed mouths. The user drags
them, and you re-plan with `inlet="CULVERT_IN", outlet="CULVERT_OUT"`. For small tweaks
(levels, heights, wing angle) use `C.edit_plan(pid, in_invert=..., out_top_rel=...,
wing_angle=...)`.

### 3. Build and look (non-destructive)

`C.build(pid)` creates the two mouth units as separate objects. `C.frame(pid, "in")` aims
the viewport at a mouth, then take a screenshot; do the same for `"out"`. Ask the user if
the size, position and look are right before touching the terrain. Rebuilding after
`edit_plan` is free.

To use a library asset instead, re-plan with `asset=("<library>.blend", "ObjectName")`.
The asset must follow the mouth-unit convention in `references/culvert.md`.

### 4. Backup, blend, verify (destructive)

```python
C.backup(pid)    # incremental .blend copy + mesh copies; also picks the Concrete join target
C.blend(pid)     # densify -> carve -> reshape -> smooth, on every affected surface mesh
C.verify(pid)    # prints checks; returns True when everything passes
```

`blend` does four things:

- It densifies the terrain near the feature to about 0.35 m edges.
- It cuts the footprint out with vertical planes, so the hole edge lies exactly on the
  wall faces.
- It pulls the ground to the headwall and wing tops (minus a 50 mm upstand) with a
  smooth falloff. It also cuts a trapezoidal channel from the apron that fades into the
  natural run-off.
- It smooths the interior, with boundaries pinned.

Height edits depend only on world XY, and smoothing never moves a boundary vertex, so
shared borders between Rough, Fairway, Concrete and the rest stay welded. The self-test
checks this: the seam gap is 0.0 m. On a 490k-vertex Rough mesh, `blend` takes about
9 s. If `blend` or `finalise` fails partway through, run `C.restore(pid)` and
`C.backup(pid)` before retrying.

Read the `verify` output and act on it. Don't just report it:

| check | meaning | typical fix |
|---|---|---|
| `stray_open_edges > 0` | a tear or hole in the terrain near the feature | `restore`, then re-run with a larger `band`, or check the source mesh for pre-existing holes |
| `buried: false` | the barrel pokes out of the bank | raise `top_rel` for that end or lower the invert, then `restore` and redo |
| `unsealed_by_m > 0` | the ground misses a wall face (gap or overhang) | increase `footing`, or reduce `smooth` |
| `flush_max_error_m >= 0.1` | the ground doesn't meet the wall top | usually two features too close together; increase spacing or reduce `band` |
| `fall_m <= 0` | water would run backwards | swap inlet/outlet or edit the inverts |
| `unity_65k` | mesh over 65,535 verts | tell the user; they may want to split the mesh in OPCD |

Frame both mouths and take screenshots. The user approves before finalising.

### 5. Finalise (destructive)

`C.finalise(pid)` box-maps UVs on the culvert at the Concrete mesh's own texel density,
using the same UV map names. It creates the same colour attributes, filled with the
average colour of nearby Concrete, and gives the culvert the Concrete material. If the
Concrete mesh has a `PaintExclude` vertex group, the culvert vertices go into it so paint
recipes leave them alone. Finally it joins both mouth units into the Concrete mesh. Take
a final screenshot.

Warn the user about one thing: after the join, **Concrete-wide mesh recipes**
(`smoothmesh`, `subdividemesh`, `zshiftmesh`, OPCD re-meshing) will also act on the
culvert. They should run those first, or `restore` → re-run → finalise again.

### 6. Approve or undo

- The user is happy: ask, then `C.discard_backups(pid)`. The `.blend` copy on disk is
  always kept. Saving the main file is the user's call, so offer it but don't do it
  unasked.
- The user wants changes: `C.restore(pid)` puts every touched mesh back exactly and
  deletes the culvert objects. Then `edit_plan` → `build` → `backup` → `blend` again.
  Ctrl+Z also works, because each step pushes an undo step, but `restore` is exact.

## Things to avoid (and why)

- **Boolean modifiers on OPCD surface meshes.** They are open sheets, not solids, so
  Exact/Manifold booleans produce slivers or drop faces. The vertical-plane `carve` is
  used instead.
- **Operators that need a 3D-view context** (knife project, loop cut, view-dependent
  selection) from blender-mcp. Code runs from a timer with no area context. The modules
  use bmesh and `temp_override`.
- **Editing one surface mesh by hand next to another.** Anything that isn't a pure
  function of XY (e.g. a proportional edit in one mesh) opens seams. If you must add a
  custom tweak, apply the same XY function to every mesh returned by `C._affected`.
- **Saving over the user's .blend or deleting backups** without asking.

## Extending to other features

A feature needs only a local frame (origin at the ground contact, +Y outward), a
footprint outline with a ground target at each vertex, and a mesh. `opcd_terrain`
(`densify`, `carve`, `apply_height_field`, `smooth_zone`, `match_attributes`,
`join_into`, backups) is feature-agnostic. Model new types (footbridges, drain grates,
sleeper walls) on `culvert.py`, and keep the plan → build → backup → blend → verify →
finalise gates.

## Self-test

`scripts/selftest.py` builds a synthetic hole (a ditch under a cart-path embankment) and
runs the whole pipeline for all four types. Run it in a **new, empty** Blender file to
check the install: open it in the Scripting tab and press Run, or use
`blender -b --python selftest.py -- <out_dir>`.

## References

- `references/culvert.md`: types, default dimensions, anatomy, every parameter, the
  library asset convention, and tuning notes. Read it before planning an unusual size or
  type, or when using library assets.
- `references/blender-mcp.md`: tool list, how `execute_blender_code` behaves, Blender 4.5
  API gotchas, and performance on big OPCD meshes. Read it if a call errors or times out.

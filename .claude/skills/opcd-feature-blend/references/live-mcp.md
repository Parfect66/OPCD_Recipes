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

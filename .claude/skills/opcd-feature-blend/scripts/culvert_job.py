"""Run a course culvert job in a BACKGROUND Blender 4.5 - never in the user's open file.

    blender -b --factory-startup --python culvert_job.py -- <job.py> test  <out_dir>
    blender -b                   --python culvert_job.py -- <job.py> final <out_dir>

test   opens the job's BLEND read-only, plans/builds/blends/verifies every culvert,
       renders review PNGs (<name>_Inlet / _Outlet / _Overview) and writes
       <out_dir>/culvert_report.json. Nothing is saved.
final  does the same, joins each culvert into its Concrete mesh and saves the
       result to the job's OUT_BLEND (default: changed_blend.blend next to BLEND).
       An existing OUT_BLEND is never overwritten: it is renamed to
       changed_blend_01.blend, _02 ... first. Previews and the
       report go to <out_dir> (normally next to OUT_BLEND). Run it WITHOUT
       --factory-startup so the OPCD addon is loaded and its scene data round-trips.

The job file is plain Python defining BLEND, OUT_BLEND and CULVERTS - see
templates/course_culverts_template.py. Optional HIDE_IN_RENDERS lists objects
(e.g. a hidden reference 'Terrain' heightmap mesh) to leave out of the review
renders; their render visibility is restored before a final save. Exit code 0 = every culvert verified.
"""
import json
import os
import runpy
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402

import opcd_terrain as T  # noqa: E402
import culvert as C  # noqa: E402

PLAN_KEYS = ("kind", "span", "rise", "bearing", "inlet", "outlet", "flow", "asset", "cursor_is")


def _keep_previous(path):
    """Rename an existing output to <stem>_01.blend, _02 ... (never overwrite or delete)."""
    stem = path[:-6]
    n = 1
    while os.path.exists(f"{stem}_{n:02d}.blend"):
        n += 1
    new = f"{stem}_{n:02d}.blend"
    os.replace(path, new)
    return new


def run(job_path, mode, out_dir):
    job = runpy.run_path(job_path)
    blend = job["BLEND"]
    out_blend = job.get("OUT_BLEND") or os.path.join(os.path.dirname(blend), "changed_blend.blend")
    os.makedirs(out_dir, exist_ok=True)
    if mode == "final" and os.path.abspath(out_blend) == os.path.abspath(blend):
        raise SystemExit("REFUSED: OUT_BLEND must differ from BLEND")
    bpy.ops.wm.open_mainfile(filepath=blend)
    report = {"blender": bpy.app.version_string, "blend": blend, "mode": mode, "culverts": {}}
    hidden = []
    for n in job.get("HIDE_IN_RENDERS", ()):
        ob = bpy.data.objects.get(n)
        if ob is None:
            report.setdefault("hide_in_renders_missing", []).append(n)
        elif not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    if hidden:
        report["hidden_in_renders"] = [ob.name for ob in hidden]
    if not bpy.app.version_string.startswith("4.5"):
        report["warning"] = f"Blender {bpy.app.version_string}: OPCD courses are 4.5 files - use 4.5"
    cursor = tuple(bpy.context.scene.cursor.location)[:2]
    all_ok = True
    for spec in job["CULVERTS"]:
        name = spec["name"]
        entry = report["culverts"][name] = {}
        try:
            args = {k: spec[k] for k in PLAN_KEYS if k in spec}
            at = spec.get("at") or cursor
            pid = C.plan_culvert(centre=tuple(at[:2]), name=name, **args, **spec.get("overrides", {}))
            if spec.get("edits"):
                C.edit_plan(pid, **spec["edits"])
            C.build(pid)
            C.backup(pid, target=spec.get("target"), file_copy=False)
            C.blend(pid, include_water=spec.get("include_water", False))
            ok = C.verify(pid)
            entry["renders"] = T.render_views(out_dir, name, C.preview_views(pid),
                                              engine=job.get("RENDER_ENGINE", "CYCLES"))
            if mode == "final" or spec.get("finalise_in_test", True):
                C.finalise(pid, target=spec.get("target"))
            plan = T.load_state()[pid]
            entry.update(id=pid, ok=ok, status=plan["status"], axis_bearing=round(plan["bearing"], 1),
                         axis_source=plan["axis_note"], length_m=round(plan["length"], 3),
                         fall_m=round(plan["fall"], 3), warnings=plan["warnings"],
                         ends=plan["ends"], verify=plan.get("verify"), meshes=plan.get("blend_report"),
                         joined_into=plan.get("target"))
            all_ok &= ok
        except Exception as exc:  # keep going so one bad culvert doesn't hide the others
            entry.update(ok=False, error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc())
            all_ok = False
    for ob in hidden:
        ob.hide_render = False
    if mode == "final":
        for pid in T.load_state():
            C.discard_backups(pid)
        if all_ok or job.get("SAVE_EVEN_IF_FAILED"):
            if os.path.exists(out_blend):
                report["previous_kept_as"] = _keep_previous(out_blend)
            bpy.ops.wm.save_as_mainfile(filepath=out_blend, copy=True)
            report["saved"] = out_blend
        else:
            report["saved"] = None
            report["not_saved_because"] = "a culvert failed verify - fix the job and re-run"
    path = os.path.join(out_dir, "culvert_report.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    print("CULVERT_JOB", "OK" if all_ok else "FAILED", path)
    return all_ok


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if len(argv) != 3 or argv[1] not in ("test", "final"):
        raise SystemExit(__doc__)
    ok = run(*argv)
    sys.exit(0 if ok else 1)

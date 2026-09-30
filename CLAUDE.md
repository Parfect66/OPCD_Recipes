# OPCD_Recipes: notes for Claude

- User's toolchain: OPCD V4 → GSPro; Unity 2018.2.8f1, Blender 4.5
  (`C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`), Inkscape, GreenKeeper V4.
  Use UK English. Lengths in yards; elevations in metres.
- Blender helper scripts and course jobs live on the user's PC under
  `C:\Users\steve\Claude_Code\Blender Scripts\`:
  - `opcd_feature_kit\` holds the opcd-feature-blend kit;
  - `<Course>\` holds each course's job scripts.
- Built features (culverts, underpasses, road tunnels): use the `opcd-feature-blend`
  skill. Per-course paths, features and to-dos are recorded in
  `.claude/skills/opcd-feature-blend/references/courses.md`; read it when a course is
  named, and update it after every final run.
- Cloud sessions can't reach the user's drives or Blender: send files with their exact
  target paths and give PowerShell commands (see SKILL.md, "When this session can't run
  Blender").
- `blender_scripts/culvert_blend.py` is a paste-into-Blender fallback only.

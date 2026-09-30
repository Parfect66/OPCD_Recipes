# OPCD_Recipes

Central repository for OPCD Mesh Editing Tools recipe files and infrastructure. Recipes automate complex mesh editing workflows (painting, erosion, subdivision, etc.) for GSPro golf courses.

## Quick Start

1. **Write a recipe** — start with a template in `recipes/TEMPLATE_*.json`
2. **Validate** — run `python validation/validate_recipes.py recipes/`
3. **Test in Blender** — open the addon, **OPCD panel → Apply Recipes → Apply Recipe**, browse to your file
4. **Commit** — add to this repo and push

## Repository Structure

```
OPCD_Recipes/
├── recipes/                    # Recipe JSON files (reusable across courses)
│   ├── TEMPLATE_*.json        # Starting templates
│   └── course_specific/        # Course-tuned recipes (optional subdirs)
├── schema/                     # Recipe schema and documentation
│   ├── recipe_schema.json      # JSON Schema for validation
│   └── RECIPE_SCHEMA.md        # Full operator reference
├── addon_patches/              # Addon patches (e.g., PaintExclude)
│   └── paint_exclude.py        # Vertex-group exclusion for paint ops
├── .claude/skills/
│   └── opcd-feature-blend/     # Claude skill: add culverts etc. via blender-mcp and blend into OPCD meshes
├── blender_scripts/            # Standalone Blender 4.5 scripts (Run Script)
│   └── culvert_blend.py        # Pipe culvert + headwalls + terrain blend at the 3D cursor
├── validation/                 # Recipe validation tools
│   ├── validate_recipes.py     # Validator script (JSON + linting)
│   └── recipe_schema.json      # Schema reference (symlink or copy)
└── docs/                       # Additional documentation
    ├── TESTING.md              # How to test recipes
    └── TROUBLESHOOTING.md      # Common issues
```

## What is an OPCD Recipe?

A recipe is a JSON array of operations executed sequentially on a mesh. Each operation is a single-key object:

```json
[
  {"operationName": {...properties}},
  {"anotherOp": {...properties}}
]
```

Recipes are applied via **OPCD panel → Apply Recipes → Apply Recipe**, which calls the `wm.readoperations` operator. Only keys present in an entry are set on the scene; omitted keys retain their current panel values.

## Supported Operations

### Vertex Paint
- `fillvertexpaint` — cumulative paint from inset inward
- `randomvertexpaintloop` — hard-edged ring at specific inset
- `growcolor` — soften/blend painted edges
- `slopevertexpaint` — paint based on mesh slope
- `changecolors`, `swapcolors` — colour manipulation

### Mesh Modification
- `smoothmesh`, `subdividemesh` — geometry refinement
- `zshiftmesh`, `zshiftloop` — Z-axis translation
- `loopcut`, `straightenloops`, `spaceloops` — loop operations

### Bunkers
- `bunkeredit`, `bunkereditlip`, `bunkereditangle` — bunker shape
- `widenbunkerinterior`, `flattenbunker`, `addpotwall` — bunker details

### Blend Meshes
- `meshblendjoin`, `meshblendseparate` — blend mesh control
- `meshblendjoinpermanent`, `addblendinset` — permanent blends

### Material & Mesh
- `renamematerial` — rename material
- `separatemesh`, `invertselection` — mesh management

### Special
- `erosion` — erosion operator (requires community patch; see `addon_patches/`)

See `schema/RECIPE_SCHEMA.md` for full reference.

## Common Patterns

### Simple loop paint + soften
Paint a hard ring, then soften with a single `growcolor` pass.

```json
[
  {
    "randomvertexpaintloop": {
      "vertex_paint_type": "green",
      "paint_strength": 1.0,
      "paint_loop_inset": 2,
      "random_amt": 1.0,
      "skip_longest_loop": false
    }
  },
  {
    "growcolor": {
      "paint_strength": 0.5,
      "grow_repeat": 1
    }
  }
]
```

See `recipes/TEMPLATE_*.json` for more examples.

## Validation

### Prerequisites
```bash
pip install jsonschema
```

### Run validation
```bash
python validation/validate_recipes.py recipes/
```

This checks:
- **JSON structure** — valid syntax, proper array/object nesting
- **Schema compliance** — required keys, correct types
- **Lint rules** — invalid colours, out-of-range values, typos

### Example output
```
✓ TEMPLATE_simple_loop_paint.json
❌ my_recipe.json
   Entry 0 (randomvertexpaintloop): missing required keys: skip_longest_loop
   Entry 1 (growcolor): invalid color 'purple' in 'vertex_paint_type', must be one of: red, green, blue, black, white
```

## File Formatting Rules

- **Comments** — strip `#` lines before use; JSON parser rejects them
- **Decimals** — always use leading zero: `0.01`, not `.01`
- **Trailing commas** — no comma after last array element
- **Validation** — use [jsonlint.com](https://jsonlint.com) if load fails

## Addon Patches

### PaintExclude (paint_exclude.py)
Allows recipes to exclude boundary vertices bordering certain materials (e.g., "Concrete") without painting them. Useful for fairway edges that border cart paths or other non-paint surfaces.

**Status:** Manual vertex-group implementation validated; automated detection (via distance + material names) in progress.

**Installation:**
1. Open the OPCD addon's `operators/afrod/afrod_operators.py`
2. Find the `color_to_vertices()` function
3. After `sel_vindexs` is built, insert the exclusion logic (see `addon_patches/paint_exclude.py`)

**Usage in recipes:**
1. Create a `"PaintExclude"` vertex group on your mesh
2. Assign boundary vertices you want to skip
3. Run paint recipes; excluded vertices stay unpainted

See `addon_patches/paint_exclude.py` for code and validation test plan.

## Blender Scripts

### Culvert builder (culvert_blend.py)
**Fallback only.** Prefer the `opcd-feature-blend` skill below. Use this script when Claude can't reach your Blender, e.g. from a cloud session: it's a paste-into-Blender version, with no verify step and no join into the Concrete mesh.

Builds a precast concrete pipe culvert under a cart path and blends the OPCD terrain around it. The default is a 600 mm bore with raked-end headwalls and aprons at both ends.

1. Save the .blend, then snap the 3D cursor to the ground at the culvert **outlet**.
2. Open `blender_scripts/culvert_blend.py` in the Scripting workspace. Adjust the CONFIG block if needed: bore, grade, cover, direction mode, texture folder.
3. Run Script, then read the `Culvert_Report` text block for length, inverts, cover under the path and warnings.

The pipe aims at the nearest cart-path mesh and runs across it. The script then:
- cuts an outfall ditch in front of each headwall;
- fills low ground over the barrel to minimum cover;
- tucks the terrain onto the wall tops;
- leaves the cart path's footing alone.

The output object is named `CULVERT_600`. Following the OPCD naming rule, it contains no surface-mesh word, so join it into the Concrete mesh yourself if it should export with the course. Moved terrain vertices are weighted in a `CulvertBlend` vertex group for follow-up painting.

## Testing

Before committing a recipe, test it in Blender:

1. Create a test mesh (or use an existing one)
2. OPCD panel → Apply Recipes → Apply Recipe
3. Browse to your `.json` file
4. Run and visually inspect the result
5. Verify no errors in Blender console

For more detail, see `docs/TESTING.md`.

## Contributing

1. Write your recipe (start from a template)
2. Validate: `python validation/validate_recipes.py recipes/`
3. Test in Blender
4. Commit with a clear message describing the recipe's purpose
5. Push to the repo

### Naming Conventions
- Reusable recipes: `RECIPE_<purpose>.json` (e.g., `RECIPE_fairway_3colour_blend.json`)
- Course-specific recipes: `RECIPE_<course>_<feature>.json` (e.g., `RECIPE_meloneras_green_blend.json`)
- Templates: `TEMPLATE_<pattern>.json` (e.g., `TEMPLATE_simple_loop_paint.json`)

## Known Limitations

### Paint recipes can't respect mesh adjacency
Paint operators (`fillvertexpaint`, `randomvertexpaintloop`, `growcolor`, etc.) unconditionally select all vertices, ignoring pre-narrowed Edit Mode selections. This means recipes can't selectively exclude boundaries bordering other materials.

**Workaround:** Use the `PaintExclude` vertex-group patch (see above).

## References

- [RECIPE_SCHEMA.md](schema/RECIPE_SCHEMA.md) — Full operator and property reference
- [recipe_schema.json](schema/recipe_schema.json) — JSON Schema for validation
- [addon_patches/paint_exclude.py](addon_patches/paint_exclude.py) — Vertex-group exclusion patch
- [validate_recipes.py](validation/validate_recipes.py) — Validation tool

## Example Recipes Included

- `TEMPLATE_simple_loop_paint.json` — Baseline: hard ring + single growcolor
- `TEMPLATE_3colour_blend.json` — Three hard-banded rings
- `TEMPLATE_heavy_texture_variation.json` — Deep/rough mesh with splotch variation

## Related Repositories

- [opcd-erosion-recipes](https://github.com/opcd-dev/opcd-erosion-recipes) — Erosion recipe examples and patch
- [OPCD Mesh Editing Tools](https://github.com/opcd-dev/OPCD) — Main addon

## Troubleshooting

- **Recipe won't load** → Check JSON syntax at [jsonlint.com](https://jsonlint.com)
- **Operation not recognized** → Verify operation name in `schema/RECIPE_SCHEMA.md`
- **Missing required keys error** → See error message for required keys; check template
- **Paint excluded unwanted areas** → Use `PaintExclude` vertex group to mark boundaries

See `docs/TROUBLESHOOTING.md` for more.

## Claude Skill: opcd-feature-blend

`.claude/skills/opcd-feature-blend/` is a Claude skill that adds built features to an OPCD V4 course `.blend`: culverts (pipe, corrugated, arch, box) and passages (motorway underpass, road tunnel). It carves and reshapes the surrounding surface meshes, then joins the feature into the nearest `Concrete` mesh. It works like `procedural-building-blender`:

- **Job script:** each course gets a re-runnable script, e.g. `Blender Scripts\<Course>\<course>_culverts.py`, built from `scripts/templates/`.
- **Background runs:** the job runs in a background Blender 4.5 via `scripts/culvert_job.py`, never in the open file. `test` mode renders review PNGs; `final` mode saves a new `.blend` and refuses to overwrite.
- **Kit location:** the kit is copied to `Blender Scripts\opcd_feature_kit\` on first use.
- **Checking the kit:** run `blender -b --factory-startup --python scripts/selftest.py -- <out_dir>`.

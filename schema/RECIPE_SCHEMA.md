# OPCD Recipe Schema Documentation

## Overview

OPCD recipes are JSON files that automate mesh editing operations through the addon's recipe dispatcher. Each recipe is executed by the **OPCD panel → Apply Recipes → Apply Recipe** workflow, which calls the `wm.readoperations` operator.

## Recipe Structure

Every recipe file must be a **JSON array**. Each array element is a single-key object with the operation name as the key:

```json
[
  {"operationName": {...properties}},
  {"anotherOp": {...properties}}
]
```

Operations execute in file order. Only keys present in an entry are set on the scene properties; omitted keys retain their current panel values.

## File Formatting Rules

- **Comments**: Strip all `#`-comment lines before use — the JSON parser rejects them.
- **Decimals**: Always include a leading zero: `0.01`, never `.01`.
- **Trailing commas**: No trailing comma after the last array element.
- **Validation**: Use [jsonlint.com](https://jsonlint.com) if a recipe won't load.

## Vertex Paint Operations

### fillvertexpaint
Fills cumulatively from a given `paint_loop_inset` inward. Good for soft nested fills, NOT crisp banded looks — later calls paint over earlier ones from that inset onward.

**Required keys:**
- `vertex_paint_type`: `red`, `green`, `blue`, `black`, or `white`
- `paint_strength`: 0.0–1.0 (opacity)
- `paint_loop_inset`: numeric inset from boundary
- `random_amt`: 0.0–1.0 (randomization)

**Example:**
```json
{
  "fillvertexpaint": {
    "vertex_paint_type": "green",
    "paint_strength": 1.0,
    "paint_loop_inset": 0,
    "random_amt": 0.0
  }
}
```

### randomvertexpaintloop
Paints only the **single discrete ring** at `paint_loop_inset`. Use this for hard-edged bands (e.g., a 3-colour green with distinct outer/middle/inner rings).

**Required keys:**
- `vertex_paint_type`: `red`, `green`, `blue`, `black`, or `white`
- `paint_strength`: 0.0–1.0
- `paint_loop_inset`: numeric loop index
- `random_amt`: 0.0–1.0
- `skip_longest_loop`: `false` (outer boundary) or `true` (inner hole loop for meshes with interior holes, like fairways with cut-out greens)

**Example:**
```json
{
  "randomvertexpaintloop": {
    "vertex_paint_type": "blue",
    "paint_strength": 1.0,
    "paint_loop_inset": 3,
    "random_amt": 1.0,
    "skip_longest_loop": false
  }
}
```

### growcolor
Softens and blends hard-painted edges by diffusing colour across neighbouring vertices. Use after `randomvertexpaintloop` for a soft transition.

**Required keys:**
- `vertex_paint_type`: `red`, `green`, `blue`, or `black` (color context)
- `paint_strength`: 0.0–1.0 (blend intensity per pass)
- `random_amt`: 0.0–1.0 (randomization in blend)
- `grow_mode`: string (e.g., `"normal"`)
- `grow_repeat`: integer ≥ 1 (number of passes)

**Example:**
```json
{
  "growcolor": {
    "vertex_paint_type": "red",
    "paint_strength": 0.5,
    "random_amt": 0.0,
    "grow_mode": "normal",
    "grow_repeat": 1
  }
}
```

### slopevertexpaint
Paints vertices based on mesh slope/angle.

**Required keys:**
- `vertex_paint_type`: `red`, `green`, `blue`, `black`, or `white`
- `paint_strength`: 0.0–1.0

**Example:**
```json
{
  "slopevertexpaint": {
    "vertex_paint_type": "red",
    "paint_strength": 0.8
  }
}
```

## Colour Operations

### changecolors
Replace all instances of one colour with another.

**Required keys:**
- `from_color`: source colour (`red`, `green`, `blue`, `black`, `white`)
- `to_color`: target colour

**Example:**
```json
{
  "changecolors": {
    "from_color": "black",
    "to_color": "white"
  }
}
```

### swapcolors
Swap two colours throughout the mesh.

**Required keys:**
- `color_a`: first colour
- `color_b`: second colour

**Example:**
```json
{
  "swapcolors": {
    "color_a": "red",
    "color_b": "blue"
  }
}
```

## Mesh Modification Operations

### smoothmesh
Smooth mesh geometry.

### subdividemesh
Subdivide mesh faces (increase vertex density).

### zshiftmesh
Shift entire mesh along Z-axis.

**Keys:**
- `z_shift`: numeric Z offset

**Example:**
```json
{
  "zshiftmesh": {
    "z_shift": 0.5
  }
}
```

### zshiftloop
Shift a specific loop along Z-axis.

**Required keys:**
- `z_shift`: numeric Z offset

**Example:**
```json
{
  "zshiftloop": {
    "z_shift": 1.2
  }
}
```

## Bunker Operations

- **bunkeredit**: Edit bunker shape
- **bunkereditlip**: Edit bunker lip
- **bunkereditangle**: Edit bunker angle
- **widenbunkerinterior**: Widen bunker interior
- **flattenbunker**: Flatten bunker floor
- **addpotwall**: Add pot bunker wall

These operations have no documented schema — refer to panel controls in the addon.

## Loop/Selection Operations

- **randomslideloop**: Randomly slide loop positions
- **straightenloops**: Straighten edge loops
- **spaceloops**: Space loops evenly
- **loopcut**: Cut a new loop into the mesh
- **invertselection**: Invert the current selection

## Blend Operations

- **meshblendjoin**: Join mesh with blend mesh
- **meshblendseparate**: Separate mesh from blend
- **meshblendjoinpermanent**: Permanently join with blend mesh
- **addblendinset**: Add inset to blend mesh

## Mesh Management

- **separatemesh**: Separate mesh into multiple objects
- **renamematerial**: Rename material

**Keys:**
- `material_name`: new material name

**Example:**
```json
{
  "renamematerial": {
    "material_name": "CustomMaterial"
  }
}
```

## Special Operations

### markpaintexclude
Automatically mark boundary vertices for exclusion from paint operations by finding vertices near meshes matching specified names (e.g., "Concrete", "CartPath").

**Must run as the first entry in a recipe** before any paint operations.

**Keys:**
- `exclude_patterns`: array of strings to match in mesh names (case-insensitive). Default: `["Concrete"]`
- `distance_threshold`: numeric max distance to mark vertex as excluded. Default: `2.0`

**How it works:**
1. Scans scene for meshes with names containing any pattern (e.g., "Concrete")
2. For each vertex on the active mesh, finds minimum distance to any candidate mesh
3. If distance < threshold, marks vertex in "PaintExclude" vertex group
4. Subsequent paint operations respect the exclusion group (with patch installed)

**Example:**
```json
{
  "markpaintexclude": {
    "exclude_patterns": ["Concrete", "CartPath"],
    "distance_threshold": 2.5
  }
}
```

**Example recipe with markpaintexclude:**
```json
[
  {
    "markpaintexclude": {
      "exclude_patterns": ["Concrete"],
      "distance_threshold": 2.0
    }
  },
  {
    "randomvertexpaintloop": {
      "vertex_paint_type": "red",
      "paint_strength": 1.0,
      "paint_loop_inset": 0,
      "random_amt": 0.0,
      "skip_longest_loop": false
    }
  }
]
```

### erosion
Erosion operator (requires community patch). Applies the erosion algorithm configured in `scene.opcd_erosion_props`.

**Optional keys** (read from scene if omitted):
- `erosion_strength`: numeric strength
- `erosion_iterations`: integer pass count

**Example:**
```json
{
  "erosion": {
    "erosion_strength": 0.5,
    "erosion_iterations": 3
  }
}
```

## Common Recipe Patterns

### Simple loop-paint-and-soften
The baseline template: paint the whole ring at full coverage, then a single `growcolor` pass to soften the hard edge.

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

### Heavier texture variation
For deep/rough meshes with multiple splotch sizes:
1. Fill base colour fully
2. Sparse random black paint
3. `growcolor` multiple times with decreasing `paint_strength` (1.0 → 0.3 → 0.2 → 0.125)
4. Repeat random-paint-then-grow cycle 2–3 times with different ratios

```json
[
  {
    "fillvertexpaint": {
      "vertex_paint_type": "blue",
      "paint_strength": 1.0,
      "paint_loop_inset": 0,
      "random_amt": 0.0
    }
  },
  {
    "randomvertexpaintloop": {
      "vertex_paint_type": "black",
      "paint_strength": 1.0,
      "paint_loop_inset": 1,
      "random_amt": 0.3,
      "skip_longest_loop": false
    }
  },
  {
    "growcolor": {
      "paint_strength": 1.0,
      "grow_repeat": 1
    }
  },
  {
    "growcolor": {
      "paint_strength": 0.3,
      "grow_repeat": 1
    }
  }
]
```

## Known Limitations

### Paint recipes cannot respect mesh adjacency
All paint operators (`fillvertexpaint`, `randomvertexpaintloop`, `growcolor`, `changecolors`, `swapcolors`, `slopevertexpaint`) call `bpy.ops.mesh.select_all(action='SELECT')` unconditionally at the start of `execute()`, wiping any pre-narrowed Edit Mode selection. This means paint recipes cannot selectively exclude boundary vertices bordering an excluded material (e.g., "Concrete").

**Workaround:** The `PaintExclude` vertex-group patch (see `addon_patches/paint_exclude.py`) allows marking vertices to skip via a `"PaintExclude"` vertex group, enabling recipes to paint fairway edges without touching concrete boundaries.

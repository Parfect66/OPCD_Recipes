# Testing OPCD Recipes

## Before Committing

Every recipe should be tested in Blender before committing to this repo.

### Quick Test Checklist

- [ ] Recipe loads without errors (OPCD panel → Apply Recipes → Apply Recipe → browse file)
- [ ] Operation executes (no Blender console errors)
- [ ] Visual result matches expectation
- [ ] No unwanted side effects on other mesh properties

### Detailed Test Plan

#### 1. Setup
- Open a test Blender project (or start fresh)
- Import a test mesh (e.g., a simple plane, green, fairway, etc.)
- Ensure the mesh is the active object

#### 2. Load and Execute
1. Open the OPCD panel (if not visible: `Layout → N key → OPCD`)
2. Go to **Apply Recipes** tab
3. Click **Apply Recipe**
4. Browse to your recipe file (`.json`)
5. Click **Open**
6. The recipe should execute immediately

#### 3. Check for Errors
- **Blender console** (top-right corner of Blender)
  - Look for red ERROR messages
  - If present, note the line and operation name
- **Modal dialog** — may show validation errors before execution
- No errors = good; if errors occur, debug and retest

#### 4. Visual Inspection
For paint recipes:
- Did the expected loop(s) paint?
- Are colours correct?
- Is the transition sharp or soft (as expected)?
- Does the result match the reference image/pattern you were aiming for?

For mesh operations:
- Did vertices/faces modify as expected?
- Is the geometry intact (no artifacts, holes, or inversions)?

#### 5. Edge Cases
Test the following variants to ensure robustness:

**For paint recipes:**
- `random_amt: 0.0` (deterministic, should paint solidly)
- `random_amt: 1.0` (full randomness, grainy look)
- `paint_loop_inset` at different values (does inset logic hold?)
- `skip_longest_loop: false` and `true` (both boundary modes)

**For mesh operations:**
- Empty or simple meshes (plane, cube)
- Complex topology (high subdiv count)
- Multiple separate objects (should it affect all? just active?)

## Testing the PaintExclude Patch

### Prerequisites
- OPCD addon with `paint_exclude.py` patch applied
- Test mesh with a `"PaintExclude"` vertex group

### Test Case 1: randomvertexpaintloop with exclusion

1. **Setup:**
   - Create a simple mesh (e.g., plane with loop cuts)
   - Create a vertex group named `"PaintExclude"`
   - Select a few boundary vertices and add them to the group
   - Switch to object mode

2. **Recipe:**
   ```json
   [
     {
       "randomvertexpaintloop": {
         "vertex_paint_type": "red",
         "paint_strength": 1.0,
         "paint_loop_inset": 0,
         "random_amt": 1.0,
         "skip_longest_loop": false
       }
     }
   ]
   ```

3. **Expected result:**
   - Boundary loop paints normally, **except** vertices in PaintExclude group stay unpainted
   - Clear visual distinction between excluded (no colour) and included (solid red) vertices

4. **Pass/Fail:**
   - ✓ Excluded vertices remain unpainted
   - ✓ Rest of loop paints at full opacity
   - ✗ If excluded vertices painted anyway → patch not applied correctly

### Test Case 2: fillvertexpaint with paint_loop_inset > 0 and exclusion

1. **Setup:**
   - Same as Test Case 1

2. **Recipe:**
   ```json
   [
     {
       "fillvertexpaint": {
         "vertex_paint_type": "green",
         "paint_strength": 1.0,
         "paint_loop_inset": 2,
         "random_amt": 0.0
       }
     }
   ]
   ```

3. **Expected result:**
   - Fill starts at inset 2 and fills cumulatively inward
   - Excluded vertices are skipped even during the cumulative fill

4. **Pass/Fail:**
   - ✓ Excluded vertices stay unpainted during cumulative fill
   - ✓ Interior fill still works around the exclusion
   - ✗ If exclusion is ignored → exclusion filtering not working during fillvertexpaint

### Test Case 3: growcolor with exclusion

1. **Setup:**
   - Apply a paint operation first (e.g., randomvertexpaintloop to lay down a hard ring)
   - Create PaintExclude group with boundary vertices
   - Same mesh as Test Case 1

2. **Recipe:**
   ```json
   [
     {
       "randomvertexpaintloop": {
         "vertex_paint_type": "blue",
         "paint_strength": 1.0,
         "paint_loop_inset": 1,
         "random_amt": 0.0,
         "skip_longest_loop": false
       }
     },
     {
       "growcolor": {
         "paint_strength": 1.0,
         "grow_repeat": 1
       }
     }
   ]
   ```

3. **Expected result:**
   - Hard blue ring paints at loop inset 1
   - growcolor softens the edge **but does not touch excluded vertices**
   - Excluded boundary stays clean, interior blend looks natural

4. **Pass/Fail:**
   - ✓ Excluded vertices stay untouched by growcolor
   - ✓ Growth/blend occurs on included vertices
   - ✗ If excluded vertices blend anyway → exclusion not honored in growcolor

## Regression Testing

When changes are made to `validate_recipes.py` or `paint_exclude.py`, ensure:

1. **Existing templates still pass validation:**
   ```bash
   python validation/validate_recipes.py recipes/
   ```
   All TEMPLATE files should show ✓

2. **Intentionally invalid recipes still fail validation:**
   - Create a test recipe with missing required keys
   - Run validation
   - Ensure it reports the error correctly

3. **Previous recipes still work in Blender:**
   - Test at least one recipe from prior commits in Blender
   - Ensure no behavioural regression

## Common Issues During Testing

### "JSON parse error"
- **Cause:** Syntax error (trailing comma, unclosed bracket, etc.)
- **Fix:** Validate at [jsonlint.com](https://jsonlint.com), check formatting rules in README

### "Schema validation error"
- **Cause:** Missing required key or invalid type
- **Fix:** Check error message, refer to `schema/RECIPE_SCHEMA.md`, copy structure from template

### "Operation not recognized"
- **Cause:** Typo in operation name
- **Fix:** Verify name against `schema/RECIPE_SCHEMA.md`

### "Missing required keys" error from validator
- **Cause:** Recipe is missing a required key for a paint operation
- **Fix:** See `schema/RECIPE_SCHEMA.md` for required keys per operation; copy from template

### Paint doesn't appear
- **Cause:** `paint_loop_inset` is out of range (mesh doesn't have that many loops)
- **Fix:** Adjust inset to a valid loop index (start with 0, 1, 2, etc.)

### Excluded vertices still painted (after PaintExclude patch)
- **Cause:** Patch not applied, or vertex group not named exactly `"PaintExclude"`
- **Fix:** Check patch installation; verify group name in Blender

## Documenting Results

When committing a new recipe, include test results in the commit message:

```
Add RECIPE_fairway_3colour_blend.json

Tested on:
- Simple fairway mesh (384 verts, 3-loop boundary)
- Hard rings at insets 0, 2, 4 with single growcolor softening
- Visual result matches reference photo from Coeur d'Alene

✓ Loads without error
✓ Paints expected rings at correct insets
✓ growcolor softens edges naturally
✓ No console errors
```

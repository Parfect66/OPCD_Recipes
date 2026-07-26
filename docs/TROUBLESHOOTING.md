# OPCD Recipe Troubleshooting

## Recipe Won't Load

### "JSON parse error" / File not readable in Apply Recipe dialog

**Symptoms:**
- File doesn't appear in the recipe browser, or appears but can't be opened
- Error message shows "parse error" or "invalid JSON"

**Solutions:**

1. **Validate JSON syntax:**
   - Paste your recipe into [jsonlint.com](https://jsonlint.com)
   - Look for "Parse error" message
   - Common issues:
     - Trailing comma after last array element: `[...}, ]` → remove the comma
     - Unclosed brackets/braces: `{"op": {...}` → add closing `}`
     - Missing quotes around strings: `{color: "red"}` → should be `{"color": "red"}`

2. **Check file encoding:**
   - Ensure the file is saved as **UTF-8** (not UTF-16 or ANSI)
   - In most editors: File → Save with Encoding → UTF-8

3. **Verify file extension:**
   - Must be `.json`, not `.txt` or `.JSON`

4. **Check file location:**
   - Ensure the file is in an accessible directory
   - Avoid paths with special characters or very long paths
   - Try saving to a simple location like `C:\recipes\`

### Recipe loads but produces "missing required keys" error

**Symptoms:**
- File loads, you click Open, but an error dialog appears before execution

**Solutions:**

1. **Check operation name:**
   - Refer to `schema/RECIPE_SCHEMA.md`
   - Verify the operation name is spelled correctly (case-sensitive)
   - Example: `randomvertexpaintloop` not `RandomVertexPaintLoop`

2. **Ensure all required keys are present:**
   - For `randomvertexpaintloop`, you must have:
     - `vertex_paint_type`
     - `paint_strength`
     - `paint_loop_inset`
     - `random_amt`
     - `skip_longest_loop`
   - See `schema/RECIPE_SCHEMA.md` for all required keys per operation
   - Copy structure from `recipes/TEMPLATE_*.json` to ensure completeness

3. **Check for typos in key names:**
   - `paint_loop_inset` not `paint_loop_offset`
   - `skip_longest_loop` not `skip_longest_loops`

4. **Run the validator:**
   ```bash
   python validation/validate_recipes.py recipes/
   ```
   This will show exactly which keys are missing in which entries.

## Recipe Loads but Does Nothing

**Symptoms:**
- File loads, operation appears to run, but mesh doesn't change

**Solutions:**

1. **Check that the mesh is active:**
   - Click on the mesh in the 3D viewport or outliner
   - It should be highlighted in orange (active object)

2. **Verify the operation is applicable:**
   - Some operations only work on specific mesh types
   - Example: bunker operations only work on bunker meshes
   - Try with a simple test mesh first

3. **Check paint operation parameters:**
   - For `randomvertexpaintloop`: is `paint_loop_inset` valid for your mesh?
     - If your mesh has only 2 boundary loops, inset 5 won't paint anything
     - Start with `paint_loop_inset: 0` for the outermost loop
   - For `growcolor`: does the mesh already have painted vertices?
     - growcolor softens existing paint; it won't paint an unpainted mesh

4. **Check Blender console for silent errors:**
   - Open Blender console (if not visible: Window → Toggle System Console on Windows)
   - Look for ERROR or WARNING messages
   - Red text = serious error; orange = warning

5. **Test with a known-good recipe:**
   - Try `recipes/TEMPLATE_simple_loop_paint.json`
   - If it works, the issue is with your specific recipe
   - If it doesn't work, there may be a setup issue (addon not loaded, etc.)

## Paint Colors Wrong

**Symptoms:**
- Recipe runs, but paints the wrong colour
- Example: you specified `"red"` but mesh shows blue

**Solutions:**

1. **Verify colour name:**
   - Valid colours are: `red`, `green`, `blue`, `black`, `white`
   - Check spelling exactly
   - Case-sensitive: `Red` or `RED` won't work

2. **Check if colours are being swapped elsewhere:**
   - Look for `changecolors` or `swapcolors` operations earlier in the recipe
   - They may have changed the colour before the paint operation

3. **Confirm material/shader supports vertex colours:**
   - The mesh's material must use vertex colour as input
   - If using a standard material without vertex colour nodes, paint won't be visible

4. **Check previous operations:**
   - If another recipe was run previously, it may have painted the mesh already
   - Try:
     1. Undo previous operation (Ctrl+Z)
     2. Or, delete all vertex colour data and start fresh

## Paint Covers Unwanted Areas

**Symptoms:**
- Recipe paints everywhere, including areas that should be excluded
- Example: fairway edge painted, but also painted the concrete boundary

**Solutions:**

1. **Use the PaintExclude vertex group (if patch is installed):**
   - Create a vertex group named `"PaintExclude"`
   - In Edit Mode, select boundary vertices you want to skip
   - Add selection to the group (Ctrl+G → Add to Group)
   - Run your recipe; those vertices will be skipped

2. **Separate the mesh manually:**
   - If PaintExclude patch is not available, split the mesh at the boundary
   - Example: separate the concrete edge into its own object
   - Run the recipe on the fairway object only
   - This workaround is tedious but guaranteed to work

3. **Use a narrower `paint_loop_inset`:**
   - If paint is spilling past where you want it, try a higher inset value
   - Example: `paint_loop_inset: 2` instead of `paint_loop_inset: 0`

## Validation Says "Invalid Color" or "Missing Keys" but File Looks Correct

**Symptoms:**
- Validator rejects recipe as invalid, but it looks right to you
- Error message: "invalid color 'red'" or "missing required keys"

**Solutions:**

1. **Check for JSON type issues:**
   - Values must match their expected type:
     - `paint_strength`: number, not string
     - `paint_strength: "1.0"` ✗ (string)
     - `paint_strength: 1.0` ✓ (number)
   - Booleans must be lowercase: `true`, `false` not `True`, `False`
   - This often happens if you copy from Python code

2. **Check for hidden/invisible characters:**
   - Sometimes copy-paste introduces hidden Unicode characters
   - Try retyping the problematic line from scratch
   - Or, use an editor with visible whitespace (VS Code, Sublime Text)

3. **Validate at jsonlint.com first:**
   - Paste your recipe there
   - It should show "Valid JSON"
   - If jsonlint rejects it, fix the JSON structure first

4. **Run validator with verbose output:**
   - Check the exact error message
   - Example: `missing required keys: skip_longest_loop` tells you exactly what's missing

## Blender Crashes or Hangs

**Symptoms:**
- Running recipe causes Blender to freeze, crash, or become unresponsive

**Solutions:**

1. **Check mesh complexity:**
   - Very large meshes (millions of vertices) + heavy operations may exhaust memory
   - Try on a simpler test mesh first
   - Monitor memory usage while recipe runs

2. **Check for infinite loops in validate_recipes.py:**
   - If you modified the validator, ensure no `while True` loops without exit conditions

3. **Check addon for bugs:**
   - If the issue happens with all recipes, there may be a bug in the addon or patch
   - Try the original addon without any patches
   - If that works, the issue is with the patch

4. **Disable modifiers temporarily:**
   - If the mesh has modifiers (Subdivision Surface, etc.), disable them
   - Run the recipe
   - Re-enable modifiers
   - Modifiers sometimes interfere with mesh operations

## PaintExclude Not Working

**Symptoms:**
- You created a `"PaintExclude"` vertex group, but excluded vertices still paint
- Or, paint operation complains about missing attributes

**Solutions:**

1. **Verify the patch is installed:**
   - Open `operators/afrod/afrod_operators.py`
   - Search for "PaintExclude" or the exclusion code
   - If not found, the patch was not applied
   - Apply the patch from `addon_patches/paint_exclude.py`

2. **Check vertex group name:**
   - Must be exactly `"PaintExclude"` (case-sensitive)
   - In Blender, open Object Data Properties → Vertex Groups
   - Verify the group is named exactly `PaintExclude` (no spaces, exact case)

3. **Ensure vertices are assigned to the group:**
   - In Edit Mode, select some vertices
   - Go to Object Data Properties → Vertex Groups
   - Select the `PaintExclude` group
   - Click "Assign"
   - Switch back to Object Mode and run the recipe

4. **Test with a simple case first:**
   - Create a minimal mesh (plane with 1 loop cut = 2 loops)
   - Add `PaintExclude` group, assign 1 vertex
   - Run `randomvertexpaintloop` with `paint_loop_inset: 0`
   - If the excluded vertex stays unpainted, the patch works

## Performance Issues

**Symptoms:**
- Recipe runs very slowly, or takes much longer than expected

**Solutions:**

1. **Check for multiple expensive operations:**
   - Operations like `subdividemesh` or `smoothmesh` are slow on complex meshes
   - Try reducing mesh complexity before running recipe

2. **Check grow_repeat:**
   - High `grow_repeat` on `growcolor` multiplies passes
   - Example: `grow_repeat: 10` = 10 blend passes
   - Try `grow_repeat: 1` or `grow_repeat: 2` for faster results

3. **Disable other viewport features:**
   - Disable ray-tracing, Bloom, other expensive renders
   - Simplify viewport shading (Solid instead of Material Preview)
   - This won't speed up recipe execution, but makes Blender more responsive

## Still Stuck?

1. **Check the full schema:**
   - Read `schema/RECIPE_SCHEMA.md` carefully
   - Find your operation and verify all required keys

2. **Compare against a working template:**
   - Copy `recipes/TEMPLATE_simple_loop_paint.json`
   - Modify only one thing at a time
   - Test after each change
   - This isolates which change causes the issue

3. **Enable Blender debug console:**
   - Windows: Blender → Toggle System Console
   - Other OS: Run Blender from terminal to see console output
   - Look for ERROR/WARNING messages during recipe execution

4. **Run the validator:**
   ```bash
   python validation/validate_recipes.py recipes/
   ```
   This will catch most problems before testing in Blender.

5. **Check your Blender version:**
   - Some operations may be version-specific
   - Ensure OPCD addon is compatible with your Blender version
   - Test with LTS (Long-Term Support) version if unsure

6. **Ask for help:**
   - Share your recipe JSON and the full error message
   - Include Blender version, OS, and a screenshot of the issue

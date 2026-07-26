"""
PaintExclude Vertex Group Patch for OPCD Mesh Editing Tools

This patch allows recipes to skip boundary vertices bordering excluded materials
(e.g., "Concrete") without touching every paint operator individually.

Installation:
1. Locate the OPCD addon's operators/afrod/afrod_operators.py
2. Find the color_to_vertices() function (shared by all paint operators)
3. After sel_vindexs is built, add the exclusion logic (see PATCH POINT below)
4. Recipes can now use vertex groups named "PaintExclude" to mark boundary vertices

Usage in recipes:
- Manually create a "PaintExclude" vertex group on your mesh
- Assign boundary vertices you want to skip (e.g., edges bordering Concrete)
- Run paint recipes; excluded vertices will be skipped

Future enhancement:
- Add a markpaintexclude operation to auto-detect boundaries via distance comparison
  and material names, populating the vertex group automatically.
"""

def patch_color_to_vertices():
    """
    Patch point for color_to_vertices() function in afrod_operators.py

    Insert this code after sel_vindexs is built (typically after line ~1850):

    ```python
    # PATCH: PaintExclude vertex group filtering
    exclude_group = obj.vertex_groups.get("PaintExclude")
    if exclude_group:
        exclude_vindexs = set(v.index for v in obj.data.vertices if exclude_group.index in [g.group for g in v.groups])
        sel_vindexs = sel_vindexs - exclude_vindexs
    ```

    This subtracts any vertex indices in the "PaintExclude" group from sel_vindexs.
    If the group doesn't exist, this is a no-op (identical to stock behavior).
    """
    pass

def validation_code():
    """
    Pseudocode for validating the patch works correctly.
    See docs/TESTING.md for full test plan.
    """
    test_cases = [
        {
            "name": "randomvertexpaintloop with exclusion",
            "setup": "Create vertex group 'PaintExclude', assign boundary vertices",
            "recipe": {
                "randomvertexpaintloop": {
                    "vertex_paint_type": "red",
                    "paint_strength": 1.0,
                    "paint_loop_inset": 0,
                    "random_amt": 1.0,
                    "skip_longest_loop": False
                }
            },
            "expected": "Excluded vertices show no colour change; rest of loop paints normally"
        },
        {
            "name": "fillvertexpaint with paint_loop_inset > 0 and exclusion",
            "setup": "Create vertex group, assign boundary vertices",
            "recipe": {
                "fillvertexpaint": {
                    "vertex_paint_type": "green",
                    "paint_strength": 1.0,
                    "paint_loop_inset": 2,
                    "random_amt": 0.0
                }
            },
            "expected": "Excluded vertices remain unpainted, inset-based fill works"
        },
        {
            "name": "growcolor with exclusion",
            "setup": "Paint some vertices, assign boundary subset to PaintExclude",
            "recipe": [
                {
                    "randomvertexpaintloop": {
                        "vertex_paint_type": "blue",
                        "paint_strength": 1.0,
                        "paint_loop_inset": 1,
                        "random_amt": 0.0,
                        "skip_longest_loop": False
                    }
                },
                {
                    "growcolor": {
                        "paint_strength": 1.0,
                        "grow_repeat": 1
                    }
                }
            ],
            "expected": "growcolor respects exclusion; excluded boundary stays clean"
        }
    ]
    return test_cases

# Inline reference implementation (for testing the exclusion logic)
def exclude_vertices(sel_vindexs, obj):
    """
    Apply PaintExclude vertex group filtering.

    Args:
        sel_vindexs: set of vertex indices from paint operation
        obj: the active mesh object

    Returns:
        Filtered set with PaintExclude vertices removed
    """
    exclude_group = obj.vertex_groups.get("PaintExclude")
    if exclude_group:
        exclude_vindexs = set(
            v.index for v in obj.data.vertices
            if exclude_group.index in [g.group for g in v.groups]
        )
        sel_vindexs = sel_vindexs - exclude_vindexs
    return sel_vindexs

"""
FUTURE ENHANCEMENT: mark_paint_exclude_group()

Once the manual-group patching is validated, build automated detection:

1. Walk the mesh's boundary loop
2. For each boundary vertex, find nearest neighbouring Spline mesh
3. Check neighbour's material against exclusion list
4. Populate "PaintExclude" group automatically

Recipe usage would then be:
{
  "markpaintexclude": {
    "exclude_materials": ["Concrete", "Water_Base"],
    "exclude_inset": 2
  }
}

This runs as the first entry in a recipe, before paint ops.

Implementation notes:
- Use distance comparison approach similar to separateblend
- Reuse addon's build_kdtree_for_object_2d for cart path smoothing
- Naive nearest-neighbour is O(vertices × candidate objects), acceptable
  for one boundary during testing, but needs KDTree per candidate for course-wide
"""

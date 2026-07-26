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

def mark_paint_exclude_group_automated(obj, exclude_patterns=None, distance_threshold=2.0):
    """
    Automatically populate PaintExclude vertex group by finding boundary vertices
    near meshes matching exclusion patterns (e.g., names containing "Concrete").

    Args:
        obj: Active mesh object (semi-rough, fairway, etc.)
        exclude_patterns: List of strings to match in mesh names (e.g., ["Concrete", "CartPath"])
        distance_threshold: Max distance to mark vertex as excluded

    Returns:
        Count of vertices marked for exclusion

    Usage in recipe via dispatcher:
    {
      "markpaintexclude": {
        "exclude_patterns": ["Concrete"],
        "distance_threshold": 2.0
      }
    }
    """
    if exclude_patterns is None:
        exclude_patterns = ["Concrete"]

    # Get or create PaintExclude vertex group
    exclude_group = obj.vertex_groups.get("PaintExclude")
    if not exclude_group:
        exclude_group = obj.vertex_groups.new(name="PaintExclude")

    # Find all candidate exclusion meshes (by name pattern)
    scene = obj.id_data  # Get scene from object data
    candidate_meshes = []
    for other_obj in scene.objects:
        if other_obj == obj or other_obj.type != 'MESH':
            continue
        # Check if mesh name contains any exclusion pattern
        if any(pattern.lower() in other_obj.name.lower() for pattern in exclude_patterns):
            candidate_meshes.append(other_obj)

    if not candidate_meshes:
        return 0  # No exclusion meshes found

    # For each boundary vertex on active mesh, check distance to candidate meshes
    excluded_count = 0
    for vertex in obj.data.vertices:
        vert_pos = obj.matrix_world @ vertex.co

        # Find minimum distance to any candidate mesh
        min_distance = distance_threshold
        for candidate in candidate_meshes:
            # Simple nearest-vertex search (naive O(n) per vertex, acceptable for boundaries)
            for other_vert in candidate.data.vertices:
                other_pos = candidate.matrix_world @ other_vert.co
                distance = (vert_pos - other_pos).length
                if distance < min_distance:
                    min_distance = distance

        # If vertex is within threshold of a candidate mesh, mark for exclusion
        if min_distance < distance_threshold:
            exclude_group.add([vertex.index], 1.0, 'REPLACE')
            excluded_count += 1

    return excluded_count


# RECIPE INTEGRATION EXAMPLE:
# Add this as a new elif branch in the recipe dispatcher (afrod_operators.py WM_OT_readoperations):
#
# elif "markpaintexclude" in entry:
#     config = entry["markpaintexclude"]
#     exclude_patterns = config.get("exclude_patterns", ["Concrete"])
#     distance_threshold = config.get("distance_threshold", 2.0)
#     count = mark_paint_exclude_group_automated(
#         obj,
#         exclude_patterns=exclude_patterns,
#         distance_threshold=distance_threshold
#     )
#     print(f"Marked {count} vertices for paint exclusion")
#
# Then in recipes, use as first entry before paint operations:
# [
#   {
#     "markpaintexclude": {
#       "exclude_patterns": ["Concrete"],
#       "distance_threshold": 2.0
#     }
#   },
#   {
#     "randomvertexpaintloop": {...}
#   },
#   ...
# ]

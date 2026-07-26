#!/usr/bin/env python3
"""
OPCD Recipe Validator
Validates recipe JSON files against schema and checks for common issues.
"""

import json
import sys
from pathlib import Path
import jsonschema

def load_schema(schema_path):
    """Load the JSON schema."""
    with open(schema_path) as f:
        return json.load(f)

def validate_recipe(recipe_path, schema):
    """Validate a recipe file against schema."""
    errors = []

    try:
        with open(recipe_path) as f:
            content = f.read()
            recipe = json.loads(content)
    except json.JSONDecodeError as e:
        return [f"JSON parse error: {e}"]
    except FileNotFoundError:
        return [f"File not found: {recipe_path}"]

    # Schema validation
    try:
        jsonschema.validate(recipe, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation error at item {e.path if e.path else 'root'}: {e.message}")

    # Lint checks
    if not isinstance(recipe, list):
        errors.append("Recipe root must be an array")
        return errors

    if len(recipe) == 0:
        errors.append("Recipe array is empty")

    for i, entry in enumerate(recipe):
        if not isinstance(entry, dict):
            errors.append(f"Entry {i}: must be an object, got {type(entry).__name__}")
            continue

        if len(entry) != 1:
            errors.append(f"Entry {i}: must have exactly one key, got {len(entry)}")
            continue

        op_name = list(entry.keys())[0]
        op_config = entry[op_name]

        # Check for common mistakes
        if not isinstance(op_config, dict):
            errors.append(f"Entry {i} ({op_name}): config must be an object")
            continue

        # Check for trailing commas (won't happen in valid JSON but worth warning about)

        # Validate required keys for specific operations
        required_keys = {
            "fillvertexpaint": ["vertex_paint_type", "paint_strength", "paint_loop_inset", "random_amt"],
            "randomvertexpaintloop": ["vertex_paint_type", "paint_strength", "paint_loop_inset", "random_amt", "skip_longest_loop"],
            "growcolor": ["paint_strength", "grow_repeat"],
            "changecolors": ["from_color", "to_color"],
            "swapcolors": ["color_a", "color_b"],
            "slopevertexpaint": ["vertex_paint_type", "paint_strength"],
            "zshiftmesh": ["z_shift"],
            "zshiftloop": ["z_shift"],
            "renamematerial": ["material_name"],
        }

        if op_name in required_keys:
            missing = set(required_keys[op_name]) - set(op_config.keys())
            if missing:
                errors.append(f"Entry {i} ({op_name}): missing required keys: {', '.join(sorted(missing))}")

        # Check for invalid color values
        color_keys = ["vertex_paint_type", "from_color", "to_color", "color_a", "color_b"]
        valid_colors = {"red", "green", "blue", "black", "white"}

        for key in color_keys:
            if key in op_config:
                if op_config[key] not in valid_colors:
                    errors.append(f"Entry {i} ({op_name}): invalid color '{op_config[key]}' in '{key}', must be one of: {', '.join(sorted(valid_colors))}")

        # Check for improper decimal formatting
        numeric_keys = ["paint_strength", "paint_loop_inset", "random_amt", "grow_repeat", "z_shift", "erosion_strength"]
        for key in numeric_keys:
            if key in op_config:
                val = op_config[key]
                if isinstance(val, str):
                    errors.append(f"Entry {i} ({op_name}): '{key}' must be numeric, got string '{val}'")
                # Check for leading zero on decimals (only lint if < 1)
                elif isinstance(val, float) and 0 < val < 1:
                    # This is harder to check after parsing, so skip
                    pass

        # Validate ranges
        if "paint_strength" in op_config:
            val = op_config["paint_strength"]
            if isinstance(val, (int, float)) and not (0 <= val <= 1):
                errors.append(f"Entry {i} ({op_name}): paint_strength must be 0.0-1.0, got {val}")

        if "random_amt" in op_config:
            val = op_config["random_amt"]
            if isinstance(val, (int, float)) and not (0 <= val <= 1):
                errors.append(f"Entry {i} ({op_name}): random_amt must be 0.0-1.0, got {val}")

        if "skip_longest_loop" in op_config:
            val = op_config["skip_longest_loop"]
            if not isinstance(val, bool):
                errors.append(f"Entry {i} ({op_name}): skip_longest_loop must be true/false, got {type(val).__name__}")

    return errors

def validate_directory(recipe_dir, schema_path):
    """Validate all recipes in a directory."""
    recipe_dir = Path(recipe_dir)
    schema = load_schema(schema_path)

    recipe_files = sorted(recipe_dir.glob("*.json"))

    if not recipe_files:
        print(f"No recipe files found in {recipe_dir}")
        return True

    all_valid = True

    for recipe_file in recipe_files:
        errors = validate_recipe(recipe_file, schema)
        if errors:
            all_valid = False
            print(f"\n❌ {recipe_file.name}")
            for error in errors:
                print(f"   {error}")
        else:
            print(f"✓ {recipe_file.name}")

    return all_valid

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_recipes.py <recipe_dir> [schema_path]")
        print("  recipe_dir: directory containing .json recipe files")
        print("  schema_path: path to recipe_schema.json (default: ./schema/recipe_schema.json)")
        sys.exit(1)

    recipe_dir = sys.argv[1]
    schema_path = sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent.parent / "schema" / "recipe_schema.json"

    if not Path(schema_path).exists():
        print(f"Schema file not found: {schema_path}")
        sys.exit(1)

    valid = validate_directory(recipe_dir, schema_path)
    sys.exit(0 if valid else 1)

# Meloneras clubhouse (GSPro / OPCD V4)

Builds the Meloneras Golf Club clubhouse complex onto the course pad
`Spline_path383_Concrete_-_Mesh` and exports FBX for Unity 2018.2.8f1.

| object | what |
|---|---|
| `MEL_Clubhouse` | main hall (open gables, glazed terrace front), east restaurant wing, west service wing, terrace with pergola, glass screens and hedge |
| `MEL_CartBarn` | 42 × 6 m open-fronted cart barn, stone back wall, boundary wall behind |
| `MEL_StarterKiosk` | 4 m timber starter's kiosk with a tiled pyramid roof |
| `MEL_CarParkMarkings` | bay lines, disabled bays, arrows, herringbone and angled cart bays (lifted 0.02 m) |
| `MEL_Planters` | red picón planters, light gravel islands, central walkway, hedge planter |

## Files
- `site_layout.py`: positions, headings and 2D outlines traced from the Google aerial and
  registered to the course (similarity fit, about 14.6 px/m, 1.5–2 m residuals). Plain Python.
- `build_clubhouse.py`: run in Blender 4.5 on the course file. Ray-casts the pad (then
  `Terrain`) under each footprint, sets the floor 0.15 m above the highest point, runs a
  concrete plinth 0.5 m below the lowest, drapes markings and planters, builds materials from
  `Textures\<SET>\<SET>_<MAP>.png`, and exports `<name>.fbx` (pivot at the object) and
  `<name>_world.fbx` (course coordinates), `placement.json` and `Clubhouse.blend`.
  It never saves the course file.
- `make_textures.py`: procedural 2048² seamless PBR sets (ALBEDO, NORMAL OpenGL, METALNESS,
  AO, DISPLACEMENT 16-bit, ROUGHNESS white = rough, plus MAHS). Used for concrete, glass,
  painted steel, green render, picón, light gravel and hedge; the roof tile, timber, stone,
  render, paving and aluminium come from the CC0 `MEL_CH_*` sets.

## Run
```
blender.exe -b "H:\Meloneras\Support_Files\Blender\meloneras.blend" --python "H:\Meloneras\Support_Files\Buildings\Clubhouse\Scripts\build_clubhouse.py"
```
Blender → Unity is (−x, z, −y), yaw_u = −yaw_b.

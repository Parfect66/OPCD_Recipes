# Meloneras: C. Mar de Azor houses (GSPro / OPCD V4)

The cluster of informal houses on C. Mar de Azor (Pedrazo Bajo, San Bartolomé de Tirajana),
behind the 1st and 4th greens. Background scenery, so the detail level is modest
(about 5k triangles for all 34 buildings).

| object | what |
|---|---|
| `MDA_NorthRow` | 7 houses along the south side of C. Mar de Azor, two with upper rooms |
| `MDA_LaneWest` | 10 houses and shacks west of the lane, including the curved white block by the green |
| `MDA_LaneEast` | 9 houses east of the lane |
| `MDA_RoadWest` | 6 sheds and small houses at the road's west end (green and red corrugated roofs) |
| `MDA_SouthEast` | the detached house and green-roofed shed by the roundabout |

## How it is placed
- Footprints are traced from a Google aerial of the site (1426 × 1360 px, north up) and
  registered to the course's own aerial (`meloneras_google.jpg`, which covers the 2250 m
  terrain square) with a 2D similarity fit: about 0.085 m per pixel, residuals about 2 m.
- Blender X = −east, Y = −north (the course .blend is UTM turned 180°).
- The ground is ray-cast from the course meshes (`*_-_Mesh`, `*_-_Blend`, then `Terrain`).
  The floor is set 0.1 m over the highest point and the walls run 0.3 m below the lowest.

## Run
```
blender.exe -b "H:\Meloneras\Support_Files\Blender\meloneras.blend" --python "H:\Meloneras\Support_Files\Buildings\MarDeAzor\Scripts\build_mar_de_azor.py"
```
`RENDER_PREVIEWS` writes five views into `OUT_DIR\Previews`. `EXPORT` writes into
`EXPORT_DIR` (`Assets\Buildings\Mar de Azor`): `<name>.fbx` (pivot on the object),
`<name>_world.fbx` (course coordinates, place at 0,0,0), `placement.json`, `MarDeAzor.blend`
and a copy of every texture set used under `Textures\<set>`. The course file is never saved.
Blender → Unity is (−x, z, −y), yaw_u = −yaw_b.

## Textures
2048² CC0 sets, one folder per set with ALBEDO, NORMAL (OpenGL), METALNESS, AO,
DISPLACEMENT, ROUGHNESS (white = rough) and MAHS: `MDA_RenderWhite`, `MDA_RenderCream`,
`MDA_RenderRed`, `MDA_Blockwork`, `MDA_CorrugatedRed/Green/White`, `MDA_FlatRoof`, plus
`MEL_CH_RoofTerracotta` from the clubhouse. Sources are in `Textures\SOURCES.txt`.

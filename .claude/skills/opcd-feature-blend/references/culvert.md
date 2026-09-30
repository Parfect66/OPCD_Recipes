# Culvert reference

## Contents
1. Types and typical sizes
2. Anatomy of a mouth unit
3. How the plan is derived
4. Parameters (`plan_culvert` / `edit_plan`)
5. Library asset convention
6. Tuning notes

## 1. Types and typical sizes

| `kind` | what it is | `span` | `rise` default | common sizes |
|---|---|---|---|---|
| `pipe` | precast concrete pipe, circular | internal diameter | = span | 300, 450, 600, 900, 1200 mm (12–48 in) |
| `corrugated` | corrugated steel pipe (68 × 13 mm corrugations), in a concrete headwall | internal diameter | = span | 450–1500 mm (18–60 in) |
| `arch` | masonry arch: vertical sides to the springing line, semicircular crown | clear span | 0.8 × span (min span/2) | 0.9–2.5 m (3–8 ft) |
| `box` | precast concrete box with internal haunches | clear width | 0.75 × span | 1.0 × 0.6 to 3.0 × 2.0 m |

Parsing the user: "18 inch" → `T.inch(18)`; "600mm" → `T.mm(600)`; "a 4 foot arch" →
`kind="arch", span=T.ft(4)`; "box, 1.5 by 1 m" → `kind="box", span=1.5, rise=1.0`. If the
user gives only a hole or crossing and no size, ask. A 600 mm pipe is the usual choice for
a field ditch under a cart path. Burns and larger watercourses want arches or boxes.

Everything is a single concrete material once joined, so stone/brick arches read as
concrete unless the user later gives the culvert its own material. Mention this when
they choose `arch`.

## 2. Anatomy of a mouth unit

Local frame: origin = invert on the headwall front face; +Y outward into the channel;
+Z up; metres.

```
            plan view (looking down)                   section on the axis
   channel  ^ +Y (outward)
            |       apron end (ground -> invert-0.02)
    \------------------/   <- wing ends (height = ground there)      headwall top  ___
     \    apron (z=0) /                                          top_rel  |   |______ ground behind
      \  wing   wing /     wing walls flare at wing_angle        opening  |   |=====  barrel 1 yd, capped
       \____________/      from the headwall ends                invert 0 |___|=====
       |  headwall  |  <- front face y=0, back face y=-wall      footing  |___| (-0.3, buried)
       |____________|                                                       ^ y=0
     ground behind = headwall top - upstand
```

- Headwall: opening + `max(0.3, span/4)` of face each side, plus the wing thickness.
  Thickness 0.3 m. Goes `footing` (0.3 m) below invert as a buried skirt.
- Wing walls: `wing_len = max(1.0, 1.25 × headwall height)`. Their tops taper from the
  headwall top to the ground level found at the wing end.
- Apron: a 150 mm slab, top at invert, between the wings. It hides the carve line and
  gives the water a clean floor.
- Barrel: visible for `barrel_depth` (1 yd) behind the mouth, then capped. Corrugated
  barrels get real corrugations.
- The object carries custom props `opcd_outline` (footprint JSON), `opcd_rise` and
  `opcd_kind`. So a procedural unit can be hand-edited and saved into the library.

## 3. How the plan is derived

1. **Axis.** One of four sources, in order of preference:
   - the `inlet`/`outlet` points or the `CULVERT_IN`/`CULVERT_OUT` empties;
   - `bearing`;
   - with `cursor_is="outlet"` or `"inlet"`: square across the nearest Concrete (cart
     path) mesh. The cursor becomes that mouth, and the other mouth is found on the far
     side of the path;
   - AUTO (cursor on the crossing): the bearing through the cursor where the ground falls
     away on *both* sides, i.e. along the run-off.

   Anything marked AUTO needs confirming with the user.
2. **Bed at each side.** Walking out from the crest, it finds where the embankment
   stops falling steeply (the toe) and takes the lowest point within 1.5 m of it. It
   deliberately does *not* take the lowest point in the search distance, which on a
   falling ditch would be 15 m away.
   For a mouth given as a point (cursor, empty or coordinates), the bed is the lowest
   ground at the point or up to 1.5 m in front of it. So a cursor dropped on the foot of
   the bank still gets the channel level.
3. **Mouth position.** Walking back from the bed, the first point where the bank is at
   least opening + `cover_min` high becomes the headwall *back* face. The front face is
   one wall thickness outward. If the bank never gets that high, a warning is raised and
   the terrain will be filled.
4. **Flow.** Water runs from the higher bed to the lower, unless `flow="as_bearing"` is
   passed or inlet/outlet were given. If the fall is less than 1 in 100, the outlet
   invert is lowered to suit (with a warning) and the outlet channel is cut to match.
5. **Headwall height.** The ground 0.5 m behind the back face, plus the upstand. It is
   clamped to between opening + 150 mm and opening + 1.5 m.
6. **Wing ends.** The ground height at each wing end, clamped to between 0.3 m and the
   headwall top.

## 4. Parameters

`plan_culvert(kind, span, rise=None, bearing=None, inlet=None, outlet=None, centre=None,
flow=None, asset=None, **overrides)`. Overrides (all metres/degrees):

| key | default | effect |
|---|---|---|
| `wall` | 0.30 | headwall/wing thickness |
| `footing` | 0.30 | buried skirt below invert, which is what keeps the seal |
| `upstand` | 0.05 | wall tops stand this much proud of the ground |
| `cover_min` | 0.15 | min headwall above the soffit |
| `max_top` | 1.5 | max headwall above the soffit |
| `wing_angle` | 30 | flare from the axis; 0 = parallel U-walls |
| `wing_len` | auto | wing length |
| `apron_thk` | 0.15 | apron slab thickness |
| `barrel_depth` | 0.9144 | visible barrel (1 yd) |
| `min_fall` | 0.01 | 1 in 100 |
| `channel_fade` | 4.0 | how far the channel cut fades into the run-off |
| `channel_batter` | 0.5 | side slope of the cut channel (1:2) |
| `band` | auto | ground-shaping falloff distance (≥ 2 m, 2 × headwall height) |
| `max_edge` | 0.35 | densify target near the feature |
| `smooth` | 4 | Laplacian passes (0 = off) |
| `search` | 15 | how far either side of the cursor to look for the bed |
| `segments` | auto | opening resolution (16–48) |

### Job entry keys (`CULVERTS` in the course job script)

| key | maps to |
|---|---|
| `name` | render and report file names, and the plan's name |
| `kind`, `span`, `rise`, `bearing`, `inlet`, `outlet`, `flow`, `asset`, `cursor_is` | `plan_culvert` arguments |
| `at` | the point the cursor marks, as `(x, y)`. `None` = the 3D cursor saved in the `.blend` |
| `overrides` | dict of the parameters above, e.g. `{"band": 1.5}` |
| `edits` | applied after planning with `edit_plan`, e.g. `{"out_top_rel": 0.8}` |
| `target` | mesh to join into (default: nearest Concrete) |
| `include_water` | also reshape Lake/Creek meshes (default `False`) |

`edit_plan(pid, ...)` works before `blend`. Use `in_invert`, `out_invert`, `in_top_rel`,
`out_top_rel`, `in_wing_end_rel=[l, r]`, or any override key. Then call `build` again.

## 5. Library asset convention

A library asset is **one mouth unit** in the local frame above: origin at the invert on
the front face, +Y outward, Z up, metres, applied transforms. Store:

- `opcd_rise` (float): opening height. Pass `rise=` to `plan_culvert` as well.
- `opcd_outline` (JSON string): `[[u, v, ground_rel], ...]`, a CCW footprint with the ground
  height (relative to invert) wanted at each vertex. It **must** have 8 vertices in the
  same order as `culvert.outline_local` if you rely on `verify`'s seal/flush checks.
  The easiest way is to build a procedural unit, edit it by hand, and save it to the
  library. It keeps its outline.

`plan_culvert(..., asset=("/path/lib.blend", "ObjectName"))` appends a copy for each end.
The terrain blend still uses the planned procedural outline, so keep the asset's footprint
close to the procedural one for the same span. Ask at the start of each session where the
library lives.

## 6. Tuning notes

- **Short culverts** (under about 2 × band between headwalls): the two blend zones
  overlap over the crest. Reduce `band` so the cart path on top isn't reshaped.
- **Deep embankments**: the headwall is capped at `max_top` above the soffit. The bank
  above it is benched down to the headwall top within `band`. That is realistic, but if
  the user wants a taller headwall, raise `max_top`.
- **Very coarse source mesh** (OPCD Rough at 1–2 m): lower `max_edge` to 0.25 for a
  smoother bank. Expect more vertices.
- **Bed lower than the apron** (scour hole): the channel cut only ever lowers, so a step
  down from the apron is kept. It looks natural.

# Campus build validation report

RESULT: PASS

Blender: 5.2.2 LTS
Input: `/home/michael/workspace/unity/tools/campus_builder/input/campus_1.jpg`
Reference: `/home/michael/workspace/unity/tools/campus_builder/input/campus_2.jpg`
Input size: [900, 1037] px
Method: Visual polygon/centreline digitization + Shapely union/difference + constrained triangulation

Scale: **0.75 m/px, provisional**. Neither map contains a readable scale bar or measured length. 0.75 m/px is a modeling choice, not a survey measurement.
1 Blender unit = 1 modeled metre. X = image right, Y = image up, Z = height. Image Y is flipped; north = +Y.
Origin pixel: [482.5, 525.0]. All dimensions, including default heights, scale through campus_config.json.

Campus Ground bbox (m): [-271.875, -326.25, -0.30000001192092896] to [271.875, 326.25, 12.0]
Campus dimensions (m): [543.75, 652.5, 12.300000011920929]
Buildings: 70; road surface Mesh components: 1; annotated road routes: 38
Other object counts: {"GRASS": 37, "Ground": 1, "LANDMARK": 4, "PLAZA": 5, "WATER": 8}
Meshes: 126; vertices: 57158; faces: 85585
Road widths (provisional metres): [3.75, 7.5]

## Automated acceptance

| Check | Result / evidence |
|---|---|
| Original scene | PASS: required categories; finite coordinates; applied transforms; manifold solids; positive heights; normals and face areas |
| Planar road/building overlap | 0.0 m² |
| Unbridged road/water overlap | 0.0 m² |
| FBX export | PASS: -Z forward / Y up; meshes only; unit handling recorded in JSON |
| Fresh FBX import | PASS: 126 Mesh objects; same object names/material slots |
| Bbox deviation | 2.463119017193094e-05 m |
| Bidirectional vertex deviation | 2.463119017193094e-05 m |
| Dimension ratios XYZ | [1.0, 1.0, 1.0000038621871414] |
| Direction | PASS: world-space geometry matches, Z remains height; no axis swap or inversion |
| Render camera framing | PASS: all eight bbox corners lie inside every automatic camera frame |
| Reimport render RGB mean error | [0.0003159722222222222, 0.00034166666666666666, 0.0002784722222222222] |
| Original images preserved | True (SHA256 verified) |
| Clean repeated build | PASS: 2 full run(s) |

## Render checks

| Image | Resolution | Mean RGB | Variance RGB | Non-background ratio | Result |
|---|---|---|---|---|---|
| top.png | [1200, 1200] | [179.7, 192.63, 184.42] | [1618.28, 699.27, 1194.14] | 0.647 | PASS |
| perspective_01.png | [1200, 1200] | [181.39, 190.74, 191.78] | [685.1, 325.44, 601.71] | 0.291 | PASS |
| perspective_02.png | [1200, 1200] | [181.54, 190.53, 192.33] | [595.37, 290.04, 551.67] | 0.258 | PASS |
| reimported_fbx.png | [1200, 1200] | [181.39, 190.74, 191.78] | [685.09, 325.43, 601.71] | 0.291 | PASS |

## Map facts versus modeling assumptions

### Read from the supplied maps

- Relative layout and visible footprints
- Canals, bridges, athletics field, plazas
- Numbered building labels cross-checked against campus_2

### Modeling assumptions

- Scale is provisional, not surveyed
- Building height is a modeling default, not measured real-world height.
- Stylized planning map may differ from current built campus
- Widths and boundaries are approximate manual traces
- Grass represents generalized parcel landscaping
- Ground is a rectangular supporting slab; external city streets are not modeled
- No guessed walls; parcel boundaries are not confirmed physical walls

## Problems found and automatic repairs

- Merged overlapping same-label wings: 74 traces -> 70 disjoint building solids
- Unioned road intersections; trimmed approximate road corridors against building clearance and unbridged water
- Re-routed annotated corridors locally around full-width clearance obstacles
- Normalized vertices on a 0.001 m grid with 0.002 m boundary simplification for stable Blender float32 meshes
- Closed point-touching road rings by a 0.02 m expansion to prevent four-face non-manifold extrusion edges
- Subtracted the central pool from its plaza to eliminate overlapping coplanar faces seen as a black patch in renders
- Fixed overhead camera roll explicitly so north is at the top, matching the source map

Maximum local road-centreline correction: 46.615 pixels. Corrected paths are visible in map_debug_overlay.png.
Road component areas: [36486.394184303375] m².

## Remaining limitations

- Scale is provisional, not surveyed
- Building height is a modeling default, not measured real-world height.
- Stylized planning map may differ from current built campus
- Widths and boundaries are approximate manual traces
- Grass represents generalized parcel landscaping
- Ground is a rectangular supporting slab; external city streets are not modeled
- No guessed walls; parcel boundaries are not confirmed physical walls
- No Unity/Tuanjie runtime was available; Blender FBX round-trip is verified, actual engine import remains a next-stage check.
- Collider components, layers, water exclusion and walkable masks must be configured in the engine.
- No collision components, vehicle logic, navigation bake, interiors or fine facade details are generated.
- Road slab tops are 0.045 m above ground at the current scale; engine collision design should account for these small transitions.

## Reproduce

```bash
python3 tools/campus_builder/run_pipeline.py --verify-idempotency
```

Only tool-owned data/output artifacts are cleared; source images and configuration are preserved.
Detailed object checks, camera positions, hashes and repeated-run evidence are in validation_report.json and output/idempotency_runs.json.

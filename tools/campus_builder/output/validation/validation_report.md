# Campus build validation report

RESULT: PARTIAL

Blender: 5.2.2 LTS
Input: `/home/michael/workspace/unity/tools/campus_builder/input/campus_1.jpg`
Reference: `/home/michael/workspace/unity/tools/campus_builder/input/campus_2.jpg`
Input size: [900, 1037] px
Method: Visual polygon/centreline digitization + Shapely union/difference + constrained triangulation

Scale: **1.268715271735978 m/px, conditional**. INSUFFICIENT SCALE EVIDENCE
1 Blender unit = 1 modeled metre. X = image right, Y = image up, Z = height. Image Y is flipped; north = +Y.
Origin pixel: [482.5, 525.0]. XY reads the calibration matrix; Z parameters are independent modeled metres.

Campus Ground bbox (m): [-459.90899658203125, -551.8909912109375, -0.30000001192092896] to [459.90899658203125, 551.8909912109375, 44.20000076293945]
Campus dimensions (m): [919.8179931640625, 1103.781982421875, 44.50000077486038]
Buildings: 70; road surface Mesh components: 16; annotated road routes: 38
Other object counts: {"BRIDGE": 3, "GRASS": 24, "Ground": 1, "LANDMARK": 4, "PLAZA": 5, "WATER": 8}
Meshes: 131; vertices: 11313; faces: 16753
Road widths (provisional metres): [6.34357635867989, 12.68715271735978]

## Automated acceptance

| Check | Result / evidence |
|---|---|
| Original scene | PASS: required categories; finite coordinates; applied transforms; manifold solids; positive heights; normals and face areas |
| Planar road/building overlap | 0.0 m² |
| Unbridged road/water overlap | 0.0 m² |
| FBX export | PASS: -Z forward / Y up; meshes only; unit handling recorded in JSON |
| Fresh FBX import | PASS: 131 Mesh objects; same object names/material slots |
| Bbox deviation | 4.166661165072583e-05 m |
| Bidirectional vertex deviation | 4.166661165072583e-05 m |
| Dimension ratios XYZ | [1.0, 1.0, 1.0000003361969794] |
| Direction | PASS: world-space geometry matches, Z remains height; no axis swap or inversion |
| Render camera framing | PASS: all eight bbox corners lie inside every automatic camera frame |
| Reimport render RGB mean error | [0.0005430555555555555, 0.0006104166666666667, 0.0004888888888888889] |
| Original images preserved | True (SHA256 verified) |
| Clean repeated build | PASS: 2 full run(s) |

## Render checks

| Image | Resolution | Mean RGB | Variance RGB | Non-background ratio | Result |
|---|---|---|---|---|---|
| top.png | [1200, 1200] | [176.74, 191.6, 184.82] | [1491.79, 628.57, 1165.09] | 0.632 | PASS |
| perspective_01.png | [1200, 1200] | [179.32, 189.83, 191.81] | [712.74, 352.77, 616.4] | 0.287 | PASS |
| perspective_02.png | [1200, 1200] | [179.54, 189.6, 192.29] | [634.36, 326.77, 572.77] | 0.254 | PASS |
| reimported_fbx.png | [1200, 1200] | [179.32, 189.83, 191.81] | [712.73, 352.76, 616.39] | 0.287 | PASS |
| building_administration.png | [1200, 1200] | [161.29, 170.89, 178.34] | [1653.12, 1384.14, 1272.12] | 0.367 | PASS |
| building_teaching.png | [1200, 1200] | [174.08, 182.2, 189.9] | [643.67, 566.59, 587.94] | 0.143 | PASS |
| building_gym.png | [1200, 1200] | [175.33, 183.35, 191.06] | [594.09, 556.06, 626.28] | 0.137 | PASS |
| building_library.png | [1200, 1200] | [176.39, 184.35, 191.99] | [434.48, 384.23, 408.76] | 0.131 | PASS |

## Map facts versus modeling assumptions

### Read from the supplied maps

- Relative layout and visible footprints
- Canals, bridges, athletics field, plazas
- Numbered building labels cross-checked against campus_2

### Modeling assumptions

- XY scale is a conditional fit to unverified standard-facility dimensions; not surveyed
- Building height is a modeling default, not measured real-world height.
- Stylized planning map may differ from current built campus
- Widths and boundaries are approximate manual traces
- Grass represents generalized parcel landscaping
- Ground is a rectangular supporting slab; external city streets are not modeled
- No guessed walls; parcel boundaries are not confirmed physical walls

## Problems found and automatic repairs

- Merged overlapping same-label wings: 74 traces -> 70 disjoint building solids
- Unioned road intersections; trimmed approximate road corridors against building clearance and unbridged water
- Removed V0.1 large-detour repair; translations are bounded by min(3 px, half road width); conflicting traces are explicitly FLAGGED, not rerouted
- Normalized vertices on a 0.001 m grid with 0.002 m boundary simplification for stable Blender float32 meshes
- Opened point-touching rings with 0.003 m inward cleanup; avoids invading neighbouring bridge surfaces
- Subtracted the central pool from its plaza to eliminate overlapping coplanar faces seen as a black patch in renders
- Fixed overhead camera roll explicitly so north is at the top, matching the source map

Maximum local road-centreline correction: 2.121 pixels. Corrected paths are visible in map_debug_overlay.png.
Road component areas: [77045.42864822708, 1931.1163049161762, 1244.451567276664, 354.4970776731234, 269.4066213023123, 260.7397981869541, 206.15762466794106, 122.49230435700771, 67.48142938184456, 65.02188988616324] m².

## Remaining limitations

- XY scale is a conditional fit to unverified standard-facility dimensions; not surveyed
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

## Stage acceptance

| Stage | Result |
|---|---|
| GEOMETRY | PASS |
| SCALE | FAIL / FLAG |
| ROADS | FAIL / FLAG |
| NAVIGATION | FAIL / FLAG |
| FBX | PASS |
| RENDER | PASS |
| BUILDINGS | PASS |
| IDEMPOTENCY | PASS |

Overall result reasons:
- INSUFFICIENT SCALE EVIDENCE
- SOURCE ROAD TRACE CONFLICTS: ROUTE_021, ROUTE_022, ROUTE_023, ROUTE_024, ROUTE_025, ROUTE_026, ROUTE_027, ROUTE_028, ROUTE_032, ROUTE_033, ROUTE_035, ROUTE_036, ROUTE_037, ROUTE_038, ROUTE_039
- Navigation graph retains flagged source-trace nodes/edges; not approved for vehicle routing

## Metric calibration

Model: uniform_scale; scale X/Y: 1.268715272 / 1.268715272 m/px; confidence: LOW
Anchor count: 4; independent source documents: 2; independent physical groups: 1; actual verified campus sources: 0
Weighted RMSE: 0.7978 m / 0.8794%; max relative residual: 1.2673%
Scale change versus V0.1 arbitrary 0.75 m/px: +69.1620%
Ground area: 1015278.552 m²; generalized campus parcel area: 481838.829 m². Both remain conditional on unverified facility assumptions.
Building floor counts, storey heights, roof forms and provenance are in building_profiles.json; Z remains independent of XY calibration.
Full anchor table, provenance and competing model residuals: [scale_calibration_report.md](scale_calibration_report.md).

## FBX absolute metres

Source Ground width/length: 919.817985 / 1103.781964 m
Reimport Ground width/length: 919.817985 / 1103.781964 m
Anchor endpoints are registered against actual Ground Mesh corners; measured world lengths must match calibrated expected lengths within 0.01 m.
1 m / 10 m / 50 m references are measured as real Blender meshes; validation-only collection is explicitly excluded from FBX/GLB.
Bridge objects: 3; bridge properties surface_type/driveable/collidable checked again after import.

## Road correction gate

Maximum accepted automatic adjustment: 2.1213 px. Each route is bounded by min(3 px, half width).
Flagged traces are NOT silently re-planned. Review meshes clip overlapping areas for inspection only; this is not a successful trace repair.
| Route | Status | Allowed px | Accepted shift px | Collision length px |
|---|---|---|---|---|
| ROUTE_001 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_002 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_003 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_004 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_005 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_006 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_007 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_008 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_009 | BOUNDED_FIX | 3.00 | 1.414 | 0.000 |
| ROUTE_010 | BOUNDED_FIX | 3.00 | 2.121 | 0.000 |
| ROUTE_011 | UNCHANGED | 2.50 | 0.000 | 0.000 |
| ROUTE_012 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_013 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_014 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_015 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_016 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_017 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_018 | BOUNDED_FIX | 2.50 | 1.000 | 0.000 |
| ROUTE_019 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_020 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_021 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 131.186 |
| ROUTE_022 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 55.118 |
| ROUTE_023 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 100.282 |
| ROUTE_024 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 11.012 |
| ROUTE_025 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 50.583 |
| ROUTE_026 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 233.500 |
| ROUTE_027 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 62.825 |
| ROUTE_028 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 75.239 |
| ROUTE_029 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_030 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_031 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_032 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 24.357 |
| ROUTE_033 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 87.898 |
| ROUTE_035 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 61.939 |
| ROUTE_036 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 11.732 |
| ROUTE_037 | FLAG_RETRACE_REQUIRED | 2.50 | 0.000 | 30.850 |
| ROUTE_038 | FLAG_RETRACE_REQUIRED | 3.00 | 0.000 | 76.911 |
| ROUTE_039 | FLAG_RETRACE_REQUIRED | 2.50 | 0.000 | 21.205 |

## Navigation graph

Nodes: 85; edges: 101; connected components: 2.
Verified driveable nodes/edges/components: 14 / 13 / 2.
Validation: FLAG; detailed errors are in navigation_validation.json and navigation_graph.json.
Dijkstra checks executed: 2. Zero means no approved driveable connected pair is available; it is not a connectivity PASS.
Undirected structural checks only. Unknown road access/direction is not promoted to a legal driving route.
Nodes are created at endpoints, centreline intersections and bridge boundaries. Curvature vertices remain edge polyline geometry.
Unknown vehicle permissions/directions remain null. Invalid trace edges are marked validation_pass=false.

## Complexity and reproducibility

{"v01_vertices": 57158, "v02_vertices": 11313, "v01_faces": 85585, "v02_faces": 16753, "vertex_ratio": 0.19792504986178663, "face_ratio": 0.19574691826838816}
{"git_commit": "90951d6a2b58cff3f724dcec5372a29fd464c2cd", "python": "3.13.12", "shapely": "2.1.2", "pillow": "12.1.1", "blender": "5.2.2 LTS"}
Regression tests: {'pass_': True, 'log': '/home/michael/workspace/unity/tools/campus_builder/output/logs/test_v02.log', 'command': 'python3 -m unittest discover -s tools/campus_builder/tests -v'}; tests cover outliers/conflicting evidence, evidence gate, XY/Z independence, bounded repair, shared junctions and Dijkstra on known valid routes.
JSON data hashes and source Mesh summaries are identical across two independent clean builds.

## Additional evidence needed

Provide the measured north-to-south length in metres between the outer track boundary at these endpoints, or two independently measured long campus baselines for HIGH confidence.

## V0.3 building reconstruction

Buildings: 70; photo-referenced: 13; measured heights: 0.
Building heights are differentiated using official minimum floor references, visible photo levels, or explicit typology assumptions. No building height is claimed to be surveyed.
Flat, gabled and swept roofs remain closed solids. Small authored facade tiles are packed in blend, embedded in FBX and included in GLB.
Source and FBX checks include finite UV coordinates, loaded image textures and preserved height/roof provenance.
See [building_reconstruction_report.md](building_reconstruction_report.md) for every building and its source.
Additional close-up renders: building_administration.png, building_teaching.png, building_gym.png, building_library.png.

### Other repairs

Source-image manual road edits are recorded separately in config/source_geometry_changes.json; they are not reported as automatic shifts.
Bridge decks use the explicit bridge masks, including the water gap drawn beneath a bridge symbol.
Zero-area polygon self-touches after bridge cuts are repaired only when area stays within a strict tolerance.
V0.2 to current mesh counts: {"before_vertices": 11896, "after_vertices": 11313, "before_faces": 17664, "after_faces": 16753}

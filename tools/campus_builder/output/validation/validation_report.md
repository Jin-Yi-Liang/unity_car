# Campus build validation report

RESULT: PARTIAL

Blender: 5.2.2 LTS
Input: `/home/michael/.codex/worktrees/0878/unity_car/tools/campus_builder/input/campus_1.jpg`
Reference: `/home/michael/.codex/worktrees/0878/unity_car/tools/campus_builder/input/campus_2.jpg`
Input size: [900, 1037] px
Method: Visual polygon/centreline digitization + Shapely union/difference + constrained triangulation

Scale: **1.268715271735978 m/px, conditional**. INSUFFICIENT SCALE EVIDENCE
1 Blender unit = 1 modeled metre. X = image right, Y = image up, Z = height. Image Y is flipped; north = +Y.
Origin pixel: [482.5, 525.0]. XY reads the calibration matrix; Z parameters are independent modeled metres.

Campus Ground bbox (m): [-459.90899658203125, -551.8909912109375, -0.30000001192092896] to [459.90899658203125, 551.8909912109375, 44.20000076293945]
Campus dimensions (m): [919.8179931640625, 1103.781982421875, 44.50000077486038]
Buildings: 69; road surface Mesh components: 7; annotated road routes: 40
Other object counts: {"ACCESS": 4, "BRIDGE": 4, "DOCK": 4, "ENTRANCE": 4, "GRASS": 34, "Ground": 1, "LANDMARK": 4, "PLAZA": 7, "ROBOT": 45, "WATER": 9}
Meshes: 192; vertices: 10327; faces: 13988
Road widths (provisional metres): [6.34357635867989, 12.68715271735978]

## Automated acceptance

| Check | Result / evidence |
|---|---|
| Original scene | PASS: required categories; finite coordinates; applied transforms; manifold solids; positive heights; normals and face areas |
| Planar road/building overlap | 0.0 m² |
| Unbridged road/water overlap | 0.0 m² |
| FBX export | PASS: -Z forward / Y up; formal meshes and robot root/joint/reference empties; unit handling recorded in JSON |
| Fresh FBX import | PASS: 192 Mesh objects; same object names/material slots |
| Bbox deviation | 8.991445793071762e-05 m |
| Bidirectional vertex deviation | 8.991445793071762e-05 m |
| Dimension ratios XYZ | [1.0, 1.0, 1.0000006489539301] |
| Direction | PASS: world-space geometry matches, Z remains height; no axis swap or inversion |
| Render camera framing | PASS: all eight bbox corners lie inside every automatic camera frame |
| Reimport render RGB mean error | [0.0006020833333333334, 0.0007118055555555556, 0.00054375] |
| Original images preserved | True (SHA256 verified) |
| Clean repeated build | PASS: 2 full run(s) |

## Render checks

| Image | Resolution | Mean RGB | Variance RGB | Non-background ratio | Result |
|---|---|---|---|---|---|
| top.png | [1200, 1200] | [176.5, 191.16, 184.44] | [1496.8, 647.75, 1175.21] | 0.632 | PASS |
| perspective_01.png | [1200, 1200] | [179.22, 189.65, 191.65] | [712.45, 356.95, 618.99] | 0.287 | PASS |
| perspective_02.png | [1200, 1200] | [179.48, 189.48, 192.21] | [632.0, 327.5, 569.46] | 0.253 | PASS |
| reimported_fbx.png | [1200, 1200] | [179.22, 189.65, 191.65] | [712.45, 356.94, 618.99] | 0.287 | PASS |
| building_administration.png | [1200, 1200] | [161.28, 170.88, 178.33] | [1651.24, 1383.26, 1271.91] | 0.366 | PASS |
| building_teaching.png | [1200, 1200] | [174.08, 182.2, 189.89] | [644.93, 567.56, 588.74] | 0.143 | PASS |
| building_gym.png | [1200, 1200] | [174.17, 182.25, 189.59] | [491.3, 456.73, 552.96] | 0.150 | PASS |
| building_library.png | [1200, 1200] | [176.02, 184.02, 191.7] | [481.29, 426.2, 447.48] | 0.129 | PASS |
| building_exhibition.png | [1200, 1200] | [162.17, 170.12, 177.7] | [1922.89, 1926.77, 1996.02] | 0.277 | PASS |
| roads_south.png | [1200, 1200] | [164.31, 183.93, 176.3] | [1607.48, 690.96, 1310.4] | 0.640 | PASS |
| roads_northeast.png | [1200, 1200] | [182.85, 195.53, 185.39] | [2252.5, 1146.63, 1592.94] | 0.972 | PASS |
| delivery_robot_closeup.png | [1200, 1200] | [110.41, 120.76, 127.94] | [481.55, 389.22, 510.21] | 0.127 | PASS |
| delivery_robot_on_campus.png | [1200, 1200] | [136.17, 152.6, 141.52] | [943.2, 1036.11, 1014.11] | 0.728 | PASS |
| delivery_robot_reimported.png | [1200, 1200] | [110.41, 120.76, 127.94] | [480.88, 388.64, 509.77] | 0.127 | PASS |
| delivery_robot_asset.png | [1200, 1200] | [159.97, 174.35, 184.37] | [2230.48, 1390.81, 1518.8] | 0.245 | PASS |
| delivery_site_LIBRARY.png | [1200, 1200] | [135.9, 150.77, 147.76] | [2185.48, 1849.77, 1236.3] | 0.708 | PASS |
| delivery_site_TEACHING_3.png | [1200, 1200] | [138.34, 164.25, 138.66] | [718.8, 863.14, 665.73] | 0.838 | PASS |
| delivery_site_CANTEEN_20.png | [1200, 1200] | [115.29, 130.39, 123.9] | [1420.92, 1212.46, 1588.57] | 0.789 | PASS |
| delivery_site_DORM_11.png | [1200, 1200] | [114.76, 130.82, 109.39] | [1013.07, 1323.39, 564.77] | 0.672 | PASS |

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
- Delivery entrances are unconfirmed facade-access candidates; bays and pedestrian connectors are modeled assumptions.
- Scenario vehicle permission and bidirectionality are explicitly assumed; base map permissions remain unchanged.
- Swept-disk validation checks complete body clearance, not actual steering, dynamics or traffic safety.

## Problems found and automatic repairs

- Merged overlapping same-label wings: 76 traces -> 69 disjoint building solids
- Unioned road intersections; trimmed approximate road corridors against building clearance and unbridged water
- Removed V0.1 large-detour repair; translations are bounded by min(3 px, half road width); conflicting traces are explicitly FLAGGED, not rerouted
- Normalized vertices on a 0.001 m grid with 0.002 m boundary simplification for stable Blender float32 meshes
- Opened point-touching rings with 0.003 m inward cleanup; avoids invading neighbouring bridge surfaces
- Subtracted the central pool from its plaza to eliminate overlapping coplanar faces seen as a black patch in renders
- Fixed overhead camera roll explicitly so north is at the top, matching the source map

Maximum local road-centreline correction: 2.121 pixels. Corrected paths are visible in map_debug_overlay.png.
Road component areas: [87105.79886679977] m².

## Remaining limitations

- XY scale is a conditional fit to unverified standard-facility dimensions; not surveyed
- Building height is a modeling default, not measured real-world height.
- Stylized planning map may differ from current built campus
- Widths and boundaries are approximate manual traces
- Grass represents generalized parcel landscaping
- Ground is a rectangular supporting slab; external city streets are not modeled
- No guessed walls; parcel boundaries are not confirmed physical walls
- Delivery entrances are unconfirmed facade-access candidates; bays and pedestrian connectors are modeled assumptions.
- Scenario vehicle permission and bidirectionality are explicitly assumed; base map permissions remain unchanged.
- Swept-disk validation checks complete body clearance, not actual steering, dynamics or traffic safety.
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
| ROADS | PASS |
| NAVIGATION | PASS |
| FBX | PASS |
| RENDER | PASS |
| BUILDINGS | PASS |
| ROBOT | PASS |
| DELIVERY | PASS |
| IDEMPOTENCY | PASS |

Overall result reasons:
- INSUFFICIENT SCALE EVIDENCE

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
Bridge objects: 4; bridge properties surface_type/driveable/collidable checked again after import.

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
| ROUTE_018 | UNCHANGED | 2.50 | 0.000 | 0.000 |
| ROUTE_019 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_020 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_021 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_022 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_023 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_024 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_025 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_026 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_027 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_028 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_029 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_030 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_031 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_032 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_033 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_035 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_036 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_037 | UNCHANGED | 2.50 | 0.000 | 0.000 |
| ROUTE_038 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_039 | UNCHANGED | 2.50 | 0.000 | 0.000 |
| ROUTE_040 | UNCHANGED | 3.00 | 0.000 | 0.000 |
| ROUTE_041 | UNCHANGED | 3.00 | 0.000 | 0.000 |

## Navigation graph

Nodes: 88; edges: 109; connected components: 1.
Verified driveable nodes/edges/components: 4 / 2 / 2.
Validation: PASS; detailed errors are in navigation_validation.json and navigation_graph.json.
Dijkstra checks executed: 0. Zero means no approved driveable connected pair is available; it is not a connectivity PASS.
Component counts are undirected structural connectivity. Dijkstra uses only explicit access and permitted directions; unknown direction is excluded. Nearby nodes and short edges are diagnostics, not automatically merged across semantic boundaries.
Nodes are created at endpoints, centreline intersections and bridge boundaries. Curvature vertices remain edge polyline geometry.
Unknown vehicle permissions/directions remain null. Invalid trace edges are marked validation_pass=false.

## Complexity and reproducibility

{"v01_vertices": 57158, "v02_vertices": 10327, "v01_faces": 85585, "v02_faces": 13988, "vertex_ratio": 0.18067462122537528, "face_ratio": 0.16343985511479817}
{"git_commit": "095c3260eb2b5cfb90783ffd9d37795d34f1050e", "python": "3.14.4", "shapely": "2.2.0", "pillow": "12.3.0", "blender": "5.2.2 LTS"}
Regression tests: {'pass_': True, 'log': '/home/michael/.codex/worktrees/0878/unity_car/tools/campus_builder/output/logs/test_v02.log', 'command': 'python3 -m unittest discover -s tools/campus_builder/tests -v'}; tests cover outliers/conflicting evidence, evidence gate, XY/Z independence, bounded repair, shared junctions and Dijkstra on known valid routes.
JSON data hashes and source Mesh summaries are identical across two independent clean builds.

## Additional evidence needed

Provide the measured north-to-south length in metres between the outer track boundary at these endpoints, or two independently measured long campus baselines for HIGH confidence.

## V0.3 building reconstruction

Buildings: 69; photo-referenced: 13; measured heights: 0.
Building heights are differentiated using official minimum floor references, visible photo levels, or explicit typology assumptions. No building height is claimed to be surveyed.
Flat, gabled and swept roofs remain closed solids. Small authored facade tiles are packed in blend, embedded in FBX and included in GLB.
Source and FBX checks include finite UV coordinates, loaded image textures and preserved height/roof provenance.
See [building_reconstruction_report.md](building_reconstruction_report.md) for every building and its source.
Additional close-up renders: building_administration.png, building_teaching.png, building_gym.png, building_library.png.

### Other repairs

Source-image manual road edits are recorded separately in config/source_geometry_changes.json; they are not reported as automatic shifts.
Bridge decks use the explicit bridge masks, including the water gap drawn beneath a bridge symbol.
Zero-area polygon self-touches after bridge cuts are repaired only when area stays within a strict tolerance.
V0.2 to current mesh counts: {"before_vertices": 11896, "after_vertices": 10327, "before_faces": 17664, "after_faces": 13988}

## Delivery robot

ROBOT RESULT: PASS

Design dimensions L/W/H: {'length': 1.2, 'width': 0.8, 'height': 1.1} m. Original compact delivery-robot design, not a measured commercial vehicle. Independent modeled metres; never multiplied by campus XY scale.
Placed root XYZ: [-272.80450384948074, 45.09945781148822, 0.045] m; yaw: 1.5590321636451152 rad; forward world: [0.9999308030307441, -0.011763891800384358, 0].
Road/graph placement: {"route_id": "ROUTE_012", "edge_id": "EDGE_0011", "distance_to_graph_edge_m": 2.767109516749634e-15, "route_width_m": 11.418437445623802, "road_edge_clearance_m": 5.309055883586771, "obstacle_clearance_m": 14.243427155195693, "width_to_road_ratio": 0.07006212573390291, "access_permission": null, "scope": "Pose geometry verified; unknown vehicle access is not promoted to permission."}
Root: DeliveryRobot_ROOT, at footprint center on the wheel contact plane. Local forward -Y, right +X, up +Z.
WheelPivot_FL/FR/RL/RR retain individual local +X spin axes, radius and independent tire/hub children.
BaseLink, ForwardAxis, LidarMount and CameraMount are reference empties; sensors and dynamics are not implemented.
Source metric/hierarchy check: True; placed FBX: True; standalone FBX: True; standalone blend: True.
Measured local dimensions XYZ after FBX: [0.800000011920929, 1.2000000476837158, 1.1000000261470717] m.
Wheel contacts after placed FBX: [0.04500088095664978, 0.04500088095664978, 0.044999122619628906, 0.044999122619628906] m; expected road top: 0.045 m.
Standalone FBX round trip: {"pass_": true, "errors": [], "max_bbox_delta_m": 1.7881393432617188e-07, "max_vertex_delta_m": 2.1490760104825313e-07, "dimension_ratios": [1.0, 1.0, 1.0000001625581363], "direction_check": "Named object world-space bounds and bidirectional vertices match; Z remains height"}
Closeup source/reimport appearance: {"mean_absolute_rgb_error": [0.00922986111111111, 0.007749305555555555, 0.006346527777777778], "pass_": true}
Full clean-build idempotency: True; runs: 2.

## Integration limits

Campus blend/FBX/GLB include one placed robot. Standalone delivery_robot.blend/fbx/glb contain the same vehicle at the origin. Do not instantiate both copies when using the standalone asset in an engine.
Campus scale remains conditional; robot design dimensions are independently fixed metres. Navigation and vehicle access outside this checked starting pose remain unverified.
Collider hints are data only. Rigidbody, wheel physics, mass/inertia, control, sensors and navigation execution belong to the next stage. No Unity/Tuanjie runtime was used.


## V0.4 buildings and road review

Exhibition facade: bottom inset 8 percent inside the original convex envelope. Top XY envelope and height remain fixed; taper is a modeling approximation.
Gym/library/exhibition use photo-informed full-height facade patterns. Gym roof seams are exportable image texture details; no mesh strip proliferation.
Facade UV distance follows the perimeter continuously across curved walls. XY envelope, taper properties, height, manifold geometry and texture decoding are checked again after FBX import.
Flagged road routes: 15 -> 0. Structural graph components: 2 -> 1.
Manual source retraces may differ substantially from the erroneous previous annotation; all before/after coordinates and Hausdorff distances are recorded separately in config/source_geometry_changes.json. They are NOT automatic corrections.
Two false large footprints were replaced by plaza surfaces; two small northeast structures and two training-courtyard wings were traced from the original image. Function/heights of small structures remain approximations.
The branch canal boundary was retraced from the visible blue-water edge instead of moving its bank road into buildings.
Unknown-direction driveable edges: 2; explicitly directed routable edges: 0. Dijkstra uses directed arcs, not undirected components.
NAVIGATION PASS covers geometric/topological data validation. Unknown vehicle access or direction still requires confirmation before vehicle routing; zero campus Dijkstra pairs is not a driving connectivity proof.
New previews: building_exhibition.png, roads_south.png, roads_northeast.png, source_retrace_overlay.png.
Full V0.3/current mesh comparison: {"object_count": 192, "total_vertices": 10327, "total_faces": 13988, "category_counts": {"ACCESS": 4, "BLDG": 69, "BRIDGE": 4, "DOCK": 4, "ENTRANCE": 4, "GRASS": 34, "Ground": 1, "LANDMARK": 4, "PLAZA": 7, "ROAD": 7, "ROBOT": 45, "WATER": 9}}
Manual-review assumptions:
- All revised footprints, widths and centerlines remain approximate plan-map interpretations, not surveys.
- New small plaza structures use a low-building height profile; their function is unidentified.
- Vehicle access and travel direction remain unknown unless already explicitly recorded.

# V0.5 candidate entrances and delivery access

DELIVERY GEOMETRY: PASS

FACTS: building IDs and relative layout are taken from the source map; base-road geometry and permissions are preserved.
ASSUMPTIONS: all four entrances are facade-access candidates, not confirmed physical doors. Roadside handoff bays and pedestrian connectors are authored simulation geometry.
The separate scenario policy assumes bidirectional access on eight explicitly listed routes; it does not establish real-campus traffic permission. A confirmed source prohibition wins.
config/delivery_sites.json and config/simulation_access.json are source inputs. Generated data is not hand edited.
Straight bay width/length: 1.40 / 1.80 m; orientation-independent swept radius: 1.021110 m.
The swept disk encloses the complete 1.20 x 0.80 m body plus 0.30 m margin. Whole polylines are buffered, not just sampled at vertices. This verifies geometric clearance, not wheel kinematics or steering feasibility.
Access slabs and bay markers align with the 0.045 m road top; the cyan marking is 0.002 m thick and noncollidable. Candidate portal markers are noncollidable and do not cut a real doorway into a wall.
Gold access surfaces are pedestrian-only; the vehicle route ends at the roadside bay. The final 1.1 m facade standoff supports handoff, not vehicle entry into buildings.
Scenario graph: 40 nodes, 41 edges. Four Dijkstra paths start at the actual placed robot and end at bay nodes.

| Site | Building trace | Base route | Vehicle path m | Pedestrian connector m | Actual door confirmed |
|---|---|---|---|---|---|
| LIBRARY | BLDG_019 | ROUTE_002 | 371.103 | 3.944 | NO |
| TEACHING_3 | BLDG_003 | ROUTE_008 | 752.953 | 42.680 | NO |
| CANTEEN_20 | BLDG_023 | ROUTE_018 | 400.100 | 5.969 | NO |
| DORM_11 | BLDG_012 | ROUTE_014 | 464.894 | 17.668 | NO |

Source and fresh FBX marker/bay validation: True; graph and connector data hashes match across two clean builds: True.
XY remains conditional on unverified scale anchors. Bay size, pedestrian width, facade standoff and robot dimensions are independent modeled metres.
New views: delivery_site_LIBRARY.png, delivery_site_TEACHING_3.png, delivery_site_CANTEEN_20.png, delivery_site_DORM_11.png and delivery_sites_overlay.png.
Full per-site vectors, evidence hashes and assumptions: data/delivery_sites.json. Waypoint-ready polyline geometry: data/simulation_navigation_graph.json.
Before/current mesh counts: {"before_vertices": 9641, "after_vertices": 10327, "before_faces": 13317, "after_faces": 13988}

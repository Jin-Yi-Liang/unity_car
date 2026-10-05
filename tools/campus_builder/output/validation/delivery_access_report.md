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
Before/current mesh counts: {"before_vertices": 9641, "after_vertices": 9943, "before_faces": 13317, "after_faces": 13666}

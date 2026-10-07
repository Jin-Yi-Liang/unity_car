# Delivery robot validation

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

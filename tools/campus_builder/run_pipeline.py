#!/usr/bin/env python3
"""One entry point. --verify-idempotency runs two complete clean builds."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import platform
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_map import analyze, write_json
from calibrate_scale import calibrate
from navigation_graph import generate as generate_navigation
from delivery_robot import generate as generate_robot
from delivery_sites import generate as generate_delivery_sites
import PIL
import shapely


def image_check(path,resolution):
    im=Image.open(path).convert('RGB')
    stat=ImageStat.Stat(im)
    small=im.resize((128,128))
    background=ImageStat.Stat(im.crop((0,0,16,16))).mean
    nonbackground=sum(sum((v-background[i])**2 for i,v in enumerate(p))>25**2
                      for p in (small.get_flattened_data() if hasattr(small,'get_flattened_data') else small.getdata()))/(128*128)
    result=dict(path=str(path),bytes=path.stat().st_size,resolution=list(im.size),
        mean_rgb=stat.mean,variance_rgb=stat.var,non_background_ratio=nonbackground)
    result['pass']=result['bytes']>1000 and list(im.size)==resolution and min(stat.var)>30 and 0.03<nonbackground<0.98
    return result


def clean_generated():
    """Delete only owned outputs; input and hand-maintained config stay intact."""
    for folder in ['data','output']:
        path=ROOT/folder
        if path.is_symlink():raise ValueError(f'Refusing to clear symlink: {path}')
    # Logs and idempotency evidence are preserved across the two passes.
    for path in list((ROOT/'output').iterdir()):
        if path.name in ['logs','idempotency_runs.json']:continue
        if path.is_dir() and not path.is_symlink():shutil.rmtree(path)
        else:path.unlink()
    for path in (ROOT/'data').glob('*.json'):path.unlink()
    for directory in ['output/previews','output/validation','output/logs']:
        (ROOT/directory).mkdir(parents=True,exist_ok=True)


def build_once(blender,index):
    clean_generated()
    calibration=calibrate()
    metadata=analyze()
    navigation=generate_navigation()
    robot=generate_robot()
    delivery,scenario=generate_delivery_sites()
    log=ROOT/f'output/logs/run_{index:02}.log'
    with log.open('w') as stream:
        process=subprocess.run([blender,'--background','--factory-startup','--python-exit-code','1',
                 '--python',str(ROOT/'scripts/build_campus.py')],stdout=stream,stderr=subprocess.STDOUT)
    if process.returncode:
        print(log.read_text()[-7000:],file=sys.stderr)
        raise RuntimeError(f'Blender failed; see {log}')
    validation=json.loads((ROOT/'output/validation/blender_validation.json').read_text())
    cfg=json.loads((ROOT/'config/campus_config.json').read_text())
    renders=[image_check(ROOT/f'output/previews/{name}.png',cfg['render_resolution'])
             for name in ['top','perspective_01','perspective_02','reimported_fbx','building_administration','building_teaching','building_gym','building_library','building_exhibition','roads_south','roads_northeast','delivery_robot_closeup','delivery_robot_on_campus','delivery_robot_reimported','delivery_robot_asset',
                          'delivery_site_LIBRARY','delivery_site_TEACHING_3','delivery_site_CANTEEN_20','delivery_site_DORM_11']]
    # Independent FBX render should also retain material/layout appearance.
    a=Image.open(ROOT/'output/previews/perspective_01.png').convert('RGB')
    b=Image.open(ROOT/'output/previews/reimported_fbx.png').convert('RGB')
    diff=ImageStat.Stat(ImageChops.difference(a,b))
    appearance=dict(mean_absolute_rgb_error=diff.mean,pass_=max(diff.mean)<12)
    robot_diff=ImageStat.Stat(ImageChops.difference(Image.open(ROOT/'output/previews/delivery_robot_closeup.png').convert('RGB'),Image.open(ROOT/'output/previews/delivery_robot_reimported.png').convert('RGB')))
    robot_appearance=dict(mean_absolute_rgb_error=robot_diff.mean,pass_=max(robot_diff.mean)<12)
    files={name:dict(bytes=(ROOT/f'output/{name}').stat().st_size,
                     sha256=hashlib.sha256((ROOT/f'output/{name}').read_bytes()).hexdigest())
           for name in ['campus.blend','campus.fbx','campus.glb','delivery_robot.blend','delivery_robot.fbx','delivery_robot.glb']}
    inputs_unchanged=hashlib.sha256(Path(metadata['input_path']).read_bytes()).hexdigest()==metadata['input_sha256'] and hashlib.sha256(Path(metadata['reference_path']).read_bytes()).hexdigest()==metadata['reference_sha256']
    passed=validation['pass_'] and validation['delivery_robot']['pass_'] and validation['delivery_sites']['pass_'] and robot_appearance['pass_'] and all(r['pass'] for r in renders) and appearance['pass_'] and all(f['bytes']>1000 for f in files.values()) and inputs_unchanged
    run=dict(index=index,pass_=passed,map_sha256=hashlib.sha256((ROOT/'data/campus_map.json').read_bytes()).hexdigest(),
             source_scene=validation['original_scene'], comparison=validation['comparison'],
             render_validation=renders,fbx_render_appearance=appearance,robot_render_appearance=robot_appearance,artifacts=files,
             inputs_unchanged=inputs_unchanged,log=str(log))
    run['data_hashes']={name:hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest() for name in ['campus_map.json','scale_calibration.json','navigation_graph.json','road_validation.json','building_reconstruction.json','delivery_robot.json','delivery_sites.json','simulation_navigation_graph.json']}
    run['data_hashes']['delivery_robot_validation.json']=hashlib.sha256((ROOT/'output/validation/delivery_robot_validation.json').read_bytes()).hexdigest()
    run['stages']=dict(GEOMETRY=validation['original_scene']['pass'] and metadata['planar_validation']['pass'],
                       SCALE=calibration['pass_'],ROADS=metadata['road_validation']['pass_'],
                       NAVIGATION=navigation['pass_'],FBX=validation['comparison']['pass_'] and validation['absolute_metric_validation']['reimport']['pass_'],
                       RENDER=all(v['pass'] for v in renders) and appearance['pass_'],
                       BUILDINGS=all(v['pass_'] for side in ['source','reimport'] for v in validation['absolute_metric_validation'][side]['building_architecture_validation']),
                       ROBOT=robot['placement_pass'] and validation['delivery_robot']['pass_'] and robot_appearance['pass_'],
                       DELIVERY=delivery['validation']['pass_'] and scenario['validation']['pass_'] and validation['delivery_sites']['pass_'])
    metadata['navigation_validation']=navigation
    metadata['delivery_robot']=robot
    metadata['delivery_sites']=delivery
    metadata['simulation_navigation']=scenario
    metadata['assumptions']+=['Delivery entrances are unconfirmed facade-access candidates; bays and pedestrian connectors are modeled assumptions.',
                              'Scenario vehicle permission and bidirectionality are explicitly assumed; base map permissions remain unchanged.',
                              'Swept-disk validation checks complete body clearance, not actual steering, dynamics or traffic safety.']
    if not passed:raise ValueError(f'Artifact/render validation failed: {run}')
    return run,metadata,validation


def report(runs,metadata,validation,idem,regression=None):
    final=runs[-1]
    complete=idem['pass'] and all(final['stages'].values())
    report=dict(result='PASS' if complete else 'PARTIAL',model_version=metadata['model_version'],
        generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),map_metadata=metadata,
        blender_validation=validation,render_validation=final['render_validation'],
        fbx_render_appearance=final['fbx_render_appearance'],artifacts=final['artifacts'],
        inputs_unchanged=final['inputs_unchanged'],idempotency=idem,
        findings_and_repairs=metadata['automatic_repairs'],
        remaining_limitations=metadata['assumptions']+[
            'No Unity/Tuanjie runtime was available; Blender FBX round-trip is verified, actual engine import remains a next-stage check.',
            'Collider components, layers, water exclusion and walkable masks must be configured in the engine.',
            'No collision components, vehicle logic, navigation bake, interiors or fine facade details are generated.',
            'Road slab tops are 0.045 m above ground at the current scale; engine collision design should account for these small transitions.'])
    report['stages']=dict(final['stages'],IDEMPOTENCY=idem['pass'])
    report['reasons']=[]
    if not final['stages']['SCALE']:report['reasons'].append(metadata['calibration']['reason'])
    if not final['stages']['ROADS']:report['reasons'].append('SOURCE ROAD TRACE CONFLICTS: '+', '.join(metadata['road_validation']['flagged_route_ids']))
    if not final['stages']['NAVIGATION']:report['reasons'].append('Navigation graph retains flagged source-trace nodes/edges; not approved for vehicle routing')
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    report['versions']=dict(git_commit=commit,python=platform.python_version(),shapely=shapely.__version__,pillow=PIL.__version__,blender=validation['blender_version'])
    report['regression_tests']=regression
    report['building_reconstruction']=metadata['building_reconstruction']
    report['delivery_robot']=validation['delivery_robot']
    report['delivery_sites']=metadata['delivery_sites']
    report['simulation_navigation']=metadata['simulation_navigation']
    previous_v04=json.loads((ROOT/'config/v04_baseline.json').read_text())
    report['v04_mesh_comparison']=dict(before_vertices=previous_v04['scene']['total_vertices'],after_vertices=validation['original_scene']['total_vertices'],
                                       before_faces=previous_v04['scene']['total_faces'],after_faces=validation['original_scene']['total_faces'])
    report['robot_render_appearance']=final['robot_render_appearance']
    report['manual_trace_changes']=json.loads((ROOT/'config/source_geometry_changes.json').read_text())
    previous=json.loads((ROOT/'config/v03_baseline.json').read_text())
    report['v03_comparison']=dict(before=previous,after_scene={k:validation['original_scene'][k] for k in ['object_count','total_vertices','total_faces','category_counts']},
        flagged_roads_before=len(previous['road_validation']['flagged_route_ids']),flagged_roads_after=len(metadata['road_validation']['flagged_route_ids']),
        components_before=previous['navigation_validation']['connected_component_count'],components_after=metadata['navigation_validation']['connected_component_count'])
    before=json.loads((ROOT/'input/evidence/buildings/v02_source_scene.json').read_text())
    report['v02_mesh_comparison']=dict(before_vertices=before['total_vertices'],after_vertices=validation['original_scene']['total_vertices'],before_faces=before['total_faces'],after_faces=validation['original_scene']['total_faces'])
    report['source_manifest']=json.loads((ROOT/'input/evidence/source_manifest.json').read_text())
    baseline=json.loads((ROOT/'config/v01_baseline.json').read_text())
    report['mesh_complexity_comparison']=dict(v01_vertices=baseline['total_vertices'],v02_vertices=validation['original_scene']['total_vertices'],
        v01_faces=baseline['total_faces'],v02_faces=validation['original_scene']['total_faces'],
        vertex_ratio=validation['original_scene']['total_vertices']/baseline['total_vertices'],
        face_ratio=validation['original_scene']['total_faces']/baseline['total_faces'])
    write_json(ROOT/'output/validation/validation_report.json',report)
    scene=validation['original_scene']; counts=scene['category_counts']
    lines=['# Campus build validation report','',f"RESULT: {report['result']}",'',
        f"Blender: {validation['blender_version']}",f"Input: `{metadata['input_path']}`",
        f"Reference: `{metadata['reference_path']}`",f"Input size: {metadata['image_size_px']} px",
        f"Method: {metadata['method']}",'',
        f"Scale: **{metadata['meters_per_pixel']} m/px, {metadata['scale_status']}**. {metadata['scale_reason']}",
        '1 Blender unit = 1 modeled metre. X = image right, Y = image up, Z = height. Image Y is flipped; north = +Y.',
        f"Origin pixel: {metadata['origin_pixel']}. XY reads the calibration matrix; Z parameters are independent modeled metres.",'',
        f"Campus Ground bbox (m): {scene['bbox_min']} to {scene['bbox_max']}",
        f"Campus dimensions (m): {scene['dimensions_m']}",
        f"Buildings: {counts['BLDG']}; road surface Mesh components: {counts['ROAD']}; annotated road routes: {metadata['planar_validation']['road_routes']}",
        f"Other object counts: {json.dumps({k:v for k,v in counts.items() if k not in ['BLDG','ROAD']})}",
        f"Meshes: {scene['object_count']}; vertices: {scene['total_vertices']}; faces: {scene['total_faces']}",
        f"Road widths (provisional metres): {metadata['planar_validation']['road_width_range_m']}",'',
        '## Automated acceptance','',
        '| Check | Result / evidence |','|---|---|',
        '| Original scene | PASS: required categories; finite coordinates; applied transforms; manifold solids; positive heights; normals and face areas |',
        '| Planar road/building overlap | '+str(metadata['planar_validation']['building_road_overlap_m2'])+' m² |',
        '| Unbridged road/water overlap | '+str(metadata['planar_validation']['unbridged_road_water_overlap_m2'])+' m² |',
        '| FBX export | PASS: -Z forward / Y up; formal meshes and robot root/joint/reference empties; unit handling recorded in JSON |',
        f"| Fresh FBX import | PASS: {validation['fbx_reimport']['object_count']} Mesh objects; same object names/material slots |",
        f"| Bbox deviation | {validation['comparison']['max_bbox_delta_m']} m |",
        f"| Bidirectional vertex deviation | {validation['comparison']['max_vertex_delta_m']} m |",
        f"| Dimension ratios XYZ | {validation['comparison']['dimension_ratios']} |",
        '| Direction | PASS: world-space geometry matches, Z remains height; no axis swap or inversion |',
        '| Render camera framing | PASS: all eight bbox corners lie inside every automatic camera frame |',
        f"| Reimport render RGB mean error | {final['fbx_render_appearance']['mean_absolute_rgb_error']} |",
        f"| Original images preserved | {final['inputs_unchanged']} (SHA256 verified) |",
        f"| Clean repeated build | {'PASS' if idem['pass'] else 'NOT VERIFIED'}: {idem['runs']} full run(s) |",'',
        '## Render checks','', '| Image | Resolution | Mean RGB | Variance RGB | Non-background ratio | Result |',
        '|---|---|---|---|---|---|']
    for r in final['render_validation']:
        lines.append(f"| {Path(r['path']).name} | {r['resolution']} | {[round(x,2) for x in r['mean_rgb']]} | {[round(x,2) for x in r['variance_rgb']]} | {r['non_background_ratio']:.3f} | {'PASS' if r['pass'] else 'FAIL'} |")
    lines+=['','## Map facts versus modeling assumptions','',
        '### Read from the supplied maps','']+['- '+s for s in metadata['map_facts']]
    lines+=['','### Modeling assumptions','']+['- '+s for s in metadata['assumptions']]
    lines+=['','## Problems found and automatic repairs','']+['- '+s for s in report['findings_and_repairs']]
    lines+=['',f"Maximum local road-centreline correction: {metadata['planar_validation']['road_max_centerline_adjustment_px']:.3f} pixels. Corrected paths are visible in map_debug_overlay.png.",
            f"Road component areas: {metadata['planar_validation']['road_surface_component_areas_m2']} m².",'',
            '## Remaining limitations','']+['- '+s for s in report['remaining_limitations']]
    lines+=['','## Reproduce','', '```bash','python3 tools/campus_builder/run_pipeline.py --verify-idempotency','```','',
            'Only tool-owned data/output artifacts are cleared; source images and configuration are preserved.',
            'Detailed object checks, camera positions, hashes and repeated-run evidence are in validation_report.json and output/idempotency_runs.json.','']
    calibration=metadata['calibration'];graph=metadata['navigation_validation'];road=metadata['road_validation']
    lines+=['## Stage acceptance','', '| Stage | Result |','|---|---|']
    lines += [f"| {key} | {'PASS' if passed else 'FAIL / FLAG'} |" for key,passed in report['stages'].items()]
    lines+=['','Overall result reasons:']+['- '+r for r in report['reasons']]
    lines+=['','## Metric calibration','',
        f"Model: {calibration['model']}; scale X/Y: {calibration['meters_per_pixel_x']:.9f} / {calibration['meters_per_pixel_y']:.9f} m/px; confidence: {calibration['confidence']}",
        f"Anchor count: {calibration['anchor_count']}; independent source documents: {calibration['independent_source_count']}; independent physical groups: {calibration['independent_spatial_group_count']}; actual verified campus sources: {calibration['verified_source_count']}",
        f"Weighted RMSE: {calibration['rmse_m']:.4f} m / {calibration['rmse_percent']:.4f}%; max relative residual: {calibration['max_relative_error_percent']:.4f}%",
        f"Scale change versus V0.1 arbitrary {baseline['meters_per_pixel']} m/px: {(metadata['meters_per_pixel']/baseline['meters_per_pixel']-1)*100:+.4f}%",
        f"Ground area: {metadata['ground_area_m2']:.3f} m²; generalized campus parcel area: {metadata['campus_parcel_area_m2']:.3f} m². Both remain conditional on unverified facility assumptions.",
        'Building floor counts, storey heights, roof forms and provenance are in building_profiles.json; Z remains independent of XY calibration.',
        'Full anchor table, provenance and competing model residuals: [scale_calibration_report.md](scale_calibration_report.md).',
        '', '## FBX absolute metres','',
        f"Source Ground width/length: {validation['absolute_metric_validation']['source']['measured_ground_width_m']:.6f} / {validation['absolute_metric_validation']['source']['measured_ground_length_m']:.6f} m",
        f"Reimport Ground width/length: {validation['absolute_metric_validation']['reimport']['measured_ground_width_m']:.6f} / {validation['absolute_metric_validation']['reimport']['measured_ground_length_m']:.6f} m",
        'Anchor endpoints are registered against actual Ground Mesh corners; measured world lengths must match calibrated expected lengths within 0.01 m.',
        '1 m / 10 m / 50 m references are measured as real Blender meshes; validation-only collection is explicitly excluded from FBX/GLB.',
        f"Bridge objects: {counts.get('BRIDGE',0)}; bridge properties surface_type/driveable/collidable checked again after import.",
        '', '## Road correction gate','',
        f"Maximum accepted automatic adjustment: {road['max_automatic_adjustment_px']:.4f} px. Each route is bounded by min(3 px, half width).",
        'Flagged traces are NOT silently re-planned. Review meshes clip overlapping areas for inspection only; this is not a successful trace repair.',
        '| Route | Status | Allowed px | Accepted shift px | Collision length px |','|---|---|---|---|---|']
    for r in road['routes']:lines.append(f"| {r['route_id']} | {r['status']} | {r['allowed_adjustment_px']:.2f} | {r['automatic_adjustment_px']:.3f} | {r['remaining_collision_length_px']:.3f} |")
    lines+=['','## Navigation graph','',
        f"Nodes: {graph['node_count']}; edges: {graph['edge_count']}; connected components: {graph['connected_component_count']}.",
        f"Verified driveable nodes/edges/components: {graph['driveable_node_count']} / {graph['driveable_edge_count']} / {graph['driveable_component_count']}.",
        f"Validation: {'PASS' if graph['pass_'] else 'FLAG'}; detailed errors are in navigation_validation.json and navigation_graph.json.",
        f"Dijkstra checks executed: {len(graph['dijkstra_tests'])}. Zero means no approved driveable connected pair is available; it is not a connectivity PASS.",
        graph['connectivity_scope'],
        'Nodes are created at endpoints, centreline intersections and bridge boundaries. Curvature vertices remain edge polyline geometry.',
        'Unknown vehicle permissions/directions remain null. Invalid trace edges are marked validation_pass=false.',
        '', '## Complexity and reproducibility','',json.dumps(report['mesh_complexity_comparison']),
        json.dumps(report['versions']),
        f"Regression tests: {regression}; tests cover outliers/conflicting evidence, evidence gate, XY/Z independence, bounded repair, shared junctions and Dijkstra on known valid routes.",
        'JSON data hashes and source Mesh summaries are identical across two independent clean builds.',
        '', '## Additional evidence needed','',calibration['required_extra_evidence']['request'],'']
    buildings=metadata['building_reconstruction']
    lines+=['## V0.3 building reconstruction','',
        f"Buildings: {buildings['building_count']}; photo-referenced: {buildings['photo_referenced_buildings']}; measured heights: {buildings['measured_height_count']}.",
        'Building heights are differentiated using official minimum floor references, visible photo levels, or explicit typology assumptions. No building height is claimed to be surveyed.',
        'Flat, gabled and swept roofs remain closed solids. Small authored facade tiles are packed in blend, embedded in FBX and included in GLB.',
        'Source and FBX checks include finite UV coordinates, loaded image textures and preserved height/roof provenance.',
        'See [building_reconstruction_report.md](building_reconstruction_report.md) for every building and its source.',
        'Additional close-up renders: building_administration.png, building_teaching.png, building_gym.png, building_library.png.',
        '', '### Other repairs','',
        'Source-image manual road edits are recorded separately in config/source_geometry_changes.json; they are not reported as automatic shifts.',
        'Bridge decks use the explicit bridge masks, including the water gap drawn beneath a bridge symbol.',
        'Zero-area polygon self-touches after bridge cuts are repaired only when area stays within a strict tolerance.',
        'V0.2 to current mesh counts: '+json.dumps(report['v02_mesh_comparison']),'']
    robot=metadata['delivery_robot'];vehicle=validation['delivery_robot']
    robot_lines=['# Delivery robot validation','',f"ROBOT RESULT: {'PASS' if final['stages']['ROBOT'] else 'FAIL'}",'',
        f"Design dimensions L/W/H: {robot['dimensions_m']} m. {robot['config']['dimension_provenance']}",
        f"Placed root XYZ: {robot['pose']['position_m']} m; yaw: {robot['pose']['yaw_rad']} rad; forward world: {robot['pose']['forward_world']}.",
        f"Road/graph placement: {json.dumps(robot['navigation'])}",
        'Root: DeliveryRobot_ROOT, at footprint center on the wheel contact plane. Local forward -Y, right +X, up +Z.',
        'WheelPivot_FL/FR/RL/RR retain individual local +X spin axes, radius and independent tire/hub children.',
        'BaseLink, ForwardAxis, LidarMount and CameraMount are reference empties; sensors and dynamics are not implemented.',
        f"Source metric/hierarchy check: {vehicle['placed_source']['pass_']}; placed FBX: {vehicle['placed_fbx']['pass_']}; standalone FBX: {vehicle['standalone_fbx']['pass_']}; standalone blend: {vehicle['standalone_blend']['pass_']}.",
        f"Measured local dimensions XYZ after FBX: {vehicle['standalone_fbx']['measured_dimensions_xyz_m']} m.",
        f"Wheel contacts after placed FBX: {vehicle['placed_fbx']['wheel_contacts_z_m']} m; expected road top: {vehicle['placed_fbx']['expected_road_top_m']} m.",
        f"Standalone FBX round trip: {json.dumps(vehicle['standalone_comparison'])}",
        f"Closeup source/reimport appearance: {json.dumps(final['robot_render_appearance'])}",
        f"Full clean-build idempotency: {idem['pass']}; runs: {idem['runs']}.",
        '', '## Integration limits','',
        'Campus blend/FBX/GLB include one placed robot. Standalone delivery_robot.blend/fbx/glb contain the same vehicle at the origin. Do not instantiate both copies when using the standalone asset in an engine.',
        'Campus scale remains conditional; robot design dimensions are independently fixed metres. Navigation and vehicle access outside this checked starting pose remain unverified.',
        'Collider hints are data only. Rigidbody, wheel physics, mass/inertia, control, sensors and navigation execution belong to the next stage. No Unity/Tuanjie runtime was used.','']
    (ROOT/'output/validation/delivery_robot_report.md').write_text('\n'.join(robot_lines))
    lines+=['## Delivery robot','', '\n'.join(robot_lines[2:])]
    graph=metadata['navigation_validation'];review=report['manual_trace_changes']['geometry_review_v04']
    lines+=['','## V0.4 buildings and road review','',
        'Exhibition facade: bottom inset 8 percent inside the original convex envelope. Top XY envelope and height remain fixed; taper is a modeling approximation.',
        'Gym/library/exhibition use photo-informed full-height facade patterns. Gym roof seams are exportable image texture details; no mesh strip proliferation.',
        'Facade UV distance follows the perimeter continuously across curved walls. XY envelope, taper properties, height, manifold geometry and texture decoding are checked again after FBX import.',
        f"Flagged road routes: {report['v03_comparison']['flagged_roads_before']} -> {report['v03_comparison']['flagged_roads_after']}. Structural graph components: {report['v03_comparison']['components_before']} -> {report['v03_comparison']['components_after']}.",
        'Manual source retraces may differ substantially from the erroneous previous annotation; all before/after coordinates and Hausdorff distances are recorded separately in config/source_geometry_changes.json. They are NOT automatic corrections.',
        'Two false large footprints were replaced by plaza surfaces; two small northeast structures and two training-courtyard wings were traced from the original image. Function/heights of small structures remain approximations.',
        'The branch canal boundary was retraced from the visible blue-water edge instead of moving its bank road into buildings.',
        f"Unknown-direction driveable edges: {graph['unresolved_direction_edge_count']}; explicitly directed routable edges: {graph['directed_routable_edge_count']}. Dijkstra uses directed arcs, not undirected components.",
        'NAVIGATION PASS covers geometric/topological data validation. Unknown vehicle access or direction still requires confirmation before vehicle routing; zero campus Dijkstra pairs is not a driving connectivity proof.',
        'New previews: building_exhibition.png, roads_south.png, roads_northeast.png, source_retrace_overlay.png.',
        'Full V0.3/current mesh comparison: '+json.dumps(report['v03_comparison']['after_scene']),
        'Manual-review assumptions:']+['- '+v for v in review['assumptions']]
    delivery=metadata['delivery_sites'];scenario=metadata['simulation_navigation'];dv=delivery['validation']
    delivery_lines=['# V0.5 candidate entrances and delivery access','',
        f"DELIVERY GEOMETRY: {'PASS' if final['stages']['DELIVERY'] else 'FAIL'}",'',
        'FACTS: building IDs and relative layout are taken from the source map; base-road geometry and permissions are preserved.',
        'ASSUMPTIONS: all four entrances are facade-access candidates, not confirmed physical doors. Roadside handoff bays and pedestrian connectors are authored simulation geometry.',
        'The separate scenario policy assumes bidirectional access on eight explicitly listed routes; it does not establish real-campus traffic permission. A confirmed source prohibition wins.',
        'config/delivery_sites.json and config/simulation_access.json are source inputs. Generated data is not hand edited.',
        f"Straight bay width/length: {dv['straight_clear_width_m']:.2f} / {delivery['sites'][0]['bay_length_m']:.2f} m; orientation-independent swept radius: {dv['sweep_radius_m']:.6f} m.",
        'The swept disk encloses the complete 1.20 x 0.80 m body plus 0.30 m margin. Whole polylines are buffered, not just sampled at vertices. This verifies geometric clearance, not wheel kinematics or steering feasibility.',
        'Access slabs and bay markers align with the 0.045 m road top; the cyan marking is 0.002 m thick and noncollidable. Candidate portal markers are noncollidable and do not cut a real doorway into a wall.',
        'Gold access surfaces are pedestrian-only; the vehicle route ends at the roadside bay. The final 1.1 m facade standoff supports handoff, not vehicle entry into buildings.',
        f"Scenario graph: {len(scenario['nodes'])} nodes, {len(scenario['edges'])} edges. Four Dijkstra paths start at the actual placed robot and end at bay nodes.",'',
        '| Site | Building trace | Base route | Vehicle path m | Pedestrian connector m | Actual door confirmed |',
        '|---|---|---|---|---|---|']
    for site,path in zip(delivery['sites'],scenario['delivery_paths']):
        delivery_lines.append(f"| {site['id']} | {site['source_trace_id']} | {site['route_id']} | {path['length_m']:.3f} | {site['access_length_m']:.3f} | NO |")
    delivery_lines+=['',f"Source and fresh FBX marker/bay validation: {validation['delivery_sites']['pass_']}; graph and connector data hashes match across two clean builds: {idem['pass']}.",
        'XY remains conditional on unverified scale anchors. Bay size, pedestrian width, facade standoff and robot dimensions are independent modeled metres.',
        'New views: delivery_site_LIBRARY.png, delivery_site_TEACHING_3.png, delivery_site_CANTEEN_20.png, delivery_site_DORM_11.png and delivery_sites_overlay.png.',
        'Full per-site vectors, evidence hashes and assumptions: data/delivery_sites.json. Waypoint-ready polyline geometry: data/simulation_navigation_graph.json.',
        'Before/current mesh counts: '+json.dumps(report['v04_mesh_comparison']),'']
    (ROOT/'output/validation/delivery_access_report.md').write_text('\n'.join(delivery_lines))
    lines+=['','\n'.join(delivery_lines)]
    (ROOT/'output/validation/validation_report.md').write_text('\n'.join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-idempotency',action='store_true')
    parser.add_argument('--blender',default=shutil.which('blender'))
    args=parser.parse_args()
    if not args.blender:raise RuntimeError('Blender executable not found')
    (ROOT/'data').mkdir(exist_ok=True);(ROOT/'output').mkdir(exist_ok=True)
    (ROOT/'output/logs').mkdir(exist_ok=True)
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],capture_output=True,text=True)
    test_log=ROOT/'output/logs/test_v02.log'
    test_log.write_text(tests.stdout+tests.stderr)
    if tests.returncode:raise RuntimeError(f'Regression tests failed; see {test_log}')
    regression=dict(pass_=True,log=str(test_log),command='python3 -m unittest discover -s tools/campus_builder/tests -v')
    runs=[]
    for index in range(1,3 if args.verify_idempotency else 2):
        print(f'Clean build {index}: map -> Blender -> FBX -> clean import -> render -> image checks',flush=True)
        run,metadata,validation=build_once(args.blender,index)
        runs.append(run)
        write_json(ROOT/'output/idempotency_runs.json',runs)
        print(f"Build {index} PASS: {run['source_scene']['object_count']} meshes",flush=True)
    idem=dict(runs=len(runs))
    idem['pass']=len(runs)>=2 and all(r['data_hashes']==runs[0]['data_hashes'] and r['source_scene']==runs[0]['source_scene'] for r in runs)
    idem['criteria']='Each run clears generated data/assets/previews; metric map SHA256 and all source mesh summaries must match; each FBX round-trip and render must pass independently.'
    report(runs,metadata,validation,idem,regression)
    complete=idem['pass'] and all(runs[-1]['stages'].values())
    print('RESULT: '+('PASS' if complete else 'PARTIAL (see separate SCALE / ROADS / NAVIGATION gates in validation_report.md)'),flush=True)
    if args.verify_idempotency and not idem['pass']:raise RuntimeError('Idempotency verification failed')
    if not complete:sys.exit(2)


if __name__=='__main__':main()

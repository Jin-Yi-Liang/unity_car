"""Metric robot specification and conservative placement on an approved trace."""
import json
import math
from pathlib import Path
from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]


def shape(feature):
    return Polygon(feature['polygon'], feature.get('holes', []))


def plan(config, campus, graph):
    for key in ['length_m', 'width_m', 'height_m', 'wheel_radius_m', 'wheel_width_m', 'wheelbase_m', 'chassis_clearance_m', 'safety_margin_m', 'hub_protrusion_m']:
        if not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f'Invalid robot dimension: {key}')
    if config['wheelbase_m'] + 2*config['wheel_radius_m'] > config['length_m']:
        raise ValueError('Wheels extend beyond configured length')
    if config['wheel_width_m']*2+2*config['hub_protrusion_m'] >= config['width_m'] or config['chassis_clearance_m'] >= 2*config['wheel_radius_m']:
        raise ValueError('Incompatible wheel/chassis dimensions')
    fraction=config['placement_fraction']
    if not 0 < fraction < 1:raise ValueError('Placement fraction must be inside the route')
    route=next(r for r in campus['road_routes'] if r['id']==config['placement_route_id'])
    if not route['correction_pass']:raise ValueError('Refusing to place robot on a flagged route')
    line=LineString(route['centerline']);distance=line.length*fraction
    center=line.interpolate(distance)
    a=line.interpolate(max(0,distance-.05));b=line.interpolate(min(line.length,distance+.05))
    yaw=math.atan2(b.x-a.x, -(b.y-a.y))  # local -Y forward
    footprint=translate(rotate(box(-config['width_m']/2,-config['length_m']/2,config['width_m']/2,config['length_m']/2),math.degrees(yaw),origin=(0,0)),center.x,center.y)
    road=unary_union([shape(r) for r in campus['roads']])
    obstacles=unary_union([shape(r) for r in campus['buildings']+campus['water']])
    buffered=footprint.buffer(config['safety_margin_m'])
    if not road.covers(buffered) or buffered.intersects(obstacles):
        raise ValueError('Configured robot pose lacks full road coverage or obstacle clearance; choose another explicit placement fraction')
    surface=next(r for r in campus['roads'] if shape(r).covers(footprint))
    edges=[e for e in graph['edges'] if route['id'] in e.get('route_ids',[e['route_id']]) and e['validation_pass']]
    edge=min(edges,key=lambda e:LineString(e['polyline_m']).distance(center)) if edges else None
    if edge is None:raise ValueError('Robot pose has no geometrically valid graph edge')
    result=dict(schema_version=1,asset_version=config['asset_version'],config=config,
        dimensions_m=dict(length=config['length_m'],width=config['width_m'],height=config['height_m']),
        pose=dict(position_m=[center.x,center.y,surface['top_m']],yaw_rad=yaw,forward_world=[math.sin(yaw),-math.cos(yaw),0]),
        footprint_world_xy_m=list(footprint.exterior.coords)[:-1],
        navigation=dict(route_id=route['id'],edge_id=edge['id'],distance_to_graph_edge_m=LineString(edge['polyline_m']).distance(center),
            route_width_m=route['width_m'],road_edge_clearance_m=footprint.distance(road.boundary),
            obstacle_clearance_m=None if obstacles.is_empty else footprint.distance(obstacles),width_to_road_ratio=config['width_m']/route['width_m'],
            access_permission=route['driveable'],scope='Pose geometry verified; unknown vehicle access is not promoted to permission.'),
        ground_surface_id=surface['id'],placement_pass=True,
        collision_hint=dict(type='compound primitive colliders',body_box_size_xyz_m=[config['width_m']*.875,config['length_m']*.8833333333,config['height_m']*.5727272727],
            body_box_center_xyz_m=[0,0,config['height_m']*.5772727273],wheel_radius_m=config['wheel_radius_m'],
            note='Collider dimensions are metadata only; no engine physics components or mass are configured.'))
    return result


def generate():
    read=lambda path:json.loads((ROOT/path).read_text())
    result=plan(read('config/delivery_robot.json'),read('data/campus_map.json'),read('data/navigation_graph.json'))
    (ROOT/'data/delivery_robot.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


if __name__=='__main__':generate()

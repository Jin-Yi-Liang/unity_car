"""Assign every stable building a distinct, connected roadside simulation dock.

Run with tools/campus_builder/.venv/bin/python. Original surveyed/candidate entrance
data remains separate: these are modeled roadside handover points, not entrances.
"""
import copy
import heapq
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, substring, unary_union

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'tools/campus_builder/data'
REGISTRY = ROOT / 'TuanjieProject/Assets/Resources/building_registry.json'
MIN_DOCK_SEPARATION = 3.0


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def polygon(feature):
    return Polygon(feature['polygon'], feature.get('holes', []))


def distances(nodes, edges, start):
    adjacency = {n['id']: [] for n in nodes}
    for edge in edges:
        adjacency[edge['from']].append((edge['to'], edge['length_m']))
        adjacency[edge['to']].append((edge['from'], edge['length_m']))
    result, pending = {start: 0.0}, [(0.0, start)]
    while pending:
        length, node = heapq.heappop(pending)
        if length != result[node]:
            continue
        for other, step in adjacency[node]:
            candidate = length + step
            if candidate < result.get(other, math.inf):
                result[other] = candidate
                heapq.heappush(pending, (candidate, other))
    return result


def generate():
    campus, base = read(DATA / 'campus_map.json'), read(DATA / 'navigation_graph.json')
    previous = read(DATA / 'simulation_navigation_graph.json')
    registry = read(REGISTRY)
    buildings = sorted(registry['buildings'], key=lambda r: r['stableId'])
    geometry = {b['id']: polygon(b) for b in campus['buildings']}
    robot = read(DATA / 'delivery_robot.json')['config']
    radius = math.hypot(robot['width_m'], robot['length_m']) / 2 + robot['safety_margin_m']
    road = unary_union([polygon(f) for f in campus['roads'] + campus['bridges']])
    bridges = unary_union([polygon(f) for f in campus['bridges']])
    water = unary_union([polygon(f) for f in campus['water']]).difference(bridges)
    obstacles = unary_union(list(geometry.values()))
    free = road.buffer(-radius).difference(obstacles.buffer(2.5)).difference(water.buffer(radius))
    start = next(n for n in previous['nodes'] if n['id'] == previous['robot_start_node_id'])
    start_point = Point(start['x_m'], start['y_m'])
    parts = [free] if free.geom_type == 'Polygon' else list(free.geoms)
    component = next(p for p in parts if p.covers(start_point))
    eligible = [e for e in base['edges'] if e['validation_pass'] and e['driveable'] is not False
                and component.buffer(.002).covers(LineString(e['polyline_m']))]
    if not eligible:
        raise ValueError('No connected road edges have full vehicle clearance')
    lines = {e['id']: LineString(e['polyline_m']) for e in eligible}
    # Preserve the four original docks and original SIMNODE IDs (including spawns).
    original_meshes = {s['building_id'] for s in read(DATA / 'delivery_sites.json')['sites']}
    occupied = [Point(b['dockX'], b['dockY']) for b in buildings if b['meshId'] in original_meshes]
    legacy_points = [Point(n['x_m'], n['y_m']) for n in previous['nodes'] if n['id'].startswith('SIMNODE_')]
    stations, dock_records = {}, []
    for building in buildings:
        body = geometry[building['meshId']]
        other_buildings = unary_union([v for k, v in geometry.items() if k != building['meshId']])
        def clear_handover(point):
            facade = nearest_points(point, body)[1]
            connection = LineString([point, facade])
            return connection.intersection(other_buildings).length < .001 and connection.intersection(water).length < .001
        if building['meshId'] in original_meshes:
            point = Point(building['dockX'], building['dockY'])
            kind = 'preserved_candidate_bay'
        else:
            center = Point(building['centerX'], building['centerY'])
            candidates = []
            for edge in eligible:
                line = lines[edge['id']]
                projection = line.project(center)
                for offset in (0, -3.1, 3.1, -6.2, 6.2, -9.3, 9.3):
                    station = min(line.length, max(0, projection + offset))
                    candidate = line.interpolate(station)
                    if any(candidate.distance(p) < .02 for p in legacy_points):
                        continue
                    if any(candidate.distance(p) < MIN_DOCK_SEPARATION for p in occupied):
                        continue
                    if not clear_handover(candidate):
                        continue
                    score = body.distance(candidate) + .05 * center.distance(candidate)
                    candidates.append((score, edge['id'], station, candidate))
            if not candidates:
                raise ValueError(f'No distinct dock for {building["stableId"]}')
            _, edge_id, station, point = min(candidates, key=lambda c: (c[0], c[1], c[2]))
            building.update(navigationStatus='simulation_dock', dockNodeId='DOCK_' + building['stableId'],
                            dockX=round(point.x, 7), dockY=round(point.y, 7))
            stations.setdefault(edge_id, []).append((station, building['dockNodeId']))
            occupied.append(point)
            kind = 'roadside_handover'
        if not component.buffer(.002).covers(point):
            raise ValueError(f'Dock outside safe connected road: {building["stableId"]}')
        if not clear_handover(point):
            raise ValueError(f'Handover crosses another building or water: {building["stableId"]}')
        dock_records.append(dict(stable_id=building['stableId'], mesh_id=building['meshId'],
                                 node_id=building['dockNodeId'], x_m=building['dockX'], y_m=building['dockY'],
                                 kind=kind, distance_to_facade_m=body.distance(point),
                                 handover_line_clear=True,
                                 actual_entrance_confirmed=False))
    nodes = [copy.deepcopy(n) for n in previous['nodes'] if n['id'].startswith('SIMNODE_')]
    legacy_nodes = list(nodes)
    by_xy = {(round(n['x_m'], 5), round(n['y_m'], 5)): n['id'] for n in nodes}
    def node(point, preferred=None):
        key = tuple(round(float(v), 5) for v in point)
        if key not in by_xy:
            identifier = preferred or f'ROAD_NODE_{len(nodes) + 1:04d}'
            by_xy[key] = identifier
            nodes.append(dict(id=identifier, x_m=float(point[0]), y_m=float(point[1])))
        elif preferred and by_xy[key] != preferred:
            raise ValueError(f'Dock node collision: {preferred}')
        return by_xy[key]
    edges = []
    for parent in eligible:
        line = lines[parent['id']]
        cuts = [0.0, line.length]
        for station, identifier in stations.get(parent['id'], []):
            point = line.interpolate(station)
            node(point.coords[0], identifier)
            cuts.append(station)
        for old in legacy_nodes:
            p = Point(old['x_m'], old['y_m'])
            if line.distance(p) < .00001:
                cuts.append(line.project(p))
        cuts = sorted(set(round(c, 8) for c in cuts))
        for index, (low, high) in enumerate(zip(cuts, cuts[1:])):
            if high - low < .00001:
                continue
            piece = substring(line, low, high)
            edges.append(dict(id=f'ROAD_{parent["id"]}_{index:02d}',
                              **{'from': node(piece.coords[0]), 'to': node(piece.coords[-1])},
                              length_m=piece.length, polyline_m=[list(p) for p in piece.coords],
                              base_edge_id=parent['id'], route_ids=parent['route_ids'], edge_type='road',
                              allowed_directions=['backward', 'forward'], clearance_pass=True,
                              sweep_radius_m=radius, real_world_access_confirmed=False,
                              access_basis='campus-wide simulation policy assumption'))
    edges += [copy.deepcopy(e) for e in previous['edges'] if e['edge_type'] == 'docking_maneuver']
    used = {e[k] for e in edges for k in ('from', 'to')}
    nodes = [n for n in nodes if n['id'] in used]
    reachable = distances(nodes, edges, start['id'])
    if len(reachable) != len(nodes):
        raise ValueError('Expanded graph has disconnected nodes')
    matrix = []
    for building in buildings:
        d = distances(nodes, edges, building['dockNodeId'])
        for other in buildings:
            if building is other:
                continue
            length = d[other['dockNodeId']]
            if not math.isfinite(length) or length <= 0:
                raise ValueError('Invalid building route')
            matrix.append(length)
    policy = copy.deepcopy(previous['policy'])
    policy.update(allowed_route_ids=sorted({r for e in edges for r in e['route_ids']}),
                  id='CAMPUS_ALL_BUILDINGS_DEMO',
                  scope='Campus-wide roadside handover simulation; actual entrances and traffic access are unconfirmed.')
    validation = dict(pass_=True, geometry_only=True, real_world_access_confirmed=False,
                      node_count=len(nodes), edge_count=len(edges), building_count=len(buildings),
                      ordered_pair_count=len(matrix), unique_dock_count=len({b['dockNodeId'] for b in buildings}),
                      min_route_m=min(matrix), max_route_m=max(matrix),
                      max_facade_distance_m=max(r['distance_to_facade_m'] for r in dock_records),
                      sweep_radius_m=radius, building_clearance_m=2.5)
    graph = dict(schema_version=1, model_version='0.6', policy=policy, nodes=nodes, edges=edges,
                 robot_start_node_id=start['id'], building_docks=dock_records, validation=validation)
    save(DATA / 'simulation_navigation_graph.json', graph)
    save(REGISTRY, registry)
    save(ROOT / 'data/building-docks.json', dict(schema_version=1, docks=dock_records, validation=validation))
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    generate()

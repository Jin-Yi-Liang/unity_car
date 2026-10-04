"""Build a noded trace graph. Ambiguous access stays null, never guessed true."""
import heapq
import json
import math
import random
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, substring

ROOT=Path(__file__).resolve().parents[1]


def shape(feature):
    return Polygon(feature['polygon'],feature.get('holes',[]))


def line_parts(g):
    if g.geom_type=='LineString':return [g]
    return [p for v in getattr(g,'geoms',[]) for p in line_parts(v)]


def point_parts(g):
    if g.is_empty:return []
    if g.geom_type=='Point':return [g]
    if g.geom_type=='LineString':return [Point(g.coords[0]),Point(g.coords[-1])]
    return [p for v in getattr(g,'geoms',[]) for p in point_parts(v)]


def components(nodes,edges):
    adjacency={n:set() for n in nodes}
    for e in edges:
        adjacency[e['from']].add(e['to']);adjacency[e['to']].add(e['from'])
    result=[];seen=set()
    for node in sorted(nodes):
        if node in seen:continue
        todo=[node];part=[];seen.add(node)
        while todo:
            current=todo.pop();part.append(current)
            for nxt in sorted(adjacency[current]):
                if nxt not in seen:seen.add(nxt);todo.append(nxt)
        result.append(sorted(part))
    return result


def generate():
    data=json.loads((ROOT/'data/campus_map.json').read_text())
    cfg=json.loads((ROOT/'config/campus_config.json').read_text())
    tolerance=cfg['navigation_junction_tolerance_m']
    routes=data['road_routes'];lines={r['id']:LineString(r['centerline']) for r in routes}
    bridge_union=unary_union([shape(b) for b in data['bridges']])
    roads=unary_union([shape(b) for b in data['roads']+data['bridges']])
    buildings=unary_union([shape(b) for b in data['buildings']])
    water=unary_union([shape(b) for b in data['water']])
    noded=unary_union(list(lines.values()))
    pieces=[]
    for part in line_parts(noded):
        cuts=[0.0,part.length]
        if not bridge_union.is_empty:
            cuts += [part.project(p) for p in point_parts(part.intersection(bridge_union.boundary))]
        cuts=sorted(set(round(d,8) for d in cuts))
        for a,b in zip(cuts,cuts[1:]):
            if b-a>1e-6:pieces.append(substring(part,a,b))
    pieces.sort(key=lambda p:(tuple(p.coords[0]),tuple(p.coords[-1]),p.length))
    nodes=[];node_lookup={};edges=[]
    def node(p):
        key=tuple(round(v,7) for v in p[:2])
        if key not in node_lookup:
            identifier=f'NODE_{len(nodes)+1:04}';node_lookup[key]=identifier
            nodes.append(dict(id=identifier,x_m=key[0],y_m=key[1]))
        return node_lookup[key]
    for piece in pieces:
        midpoint=piece.interpolate(0.5,normalized=True)
        owners=[r for r in routes if lines[r['id']].distance(midpoint)<1e-6]
        if not owners:raise ValueError('Noded edge has no source route')
        route=owners[0];polyline=[list(p) for p in piece.coords]
        is_bridge=not bridge_union.is_empty and bridge_union.buffer(tolerance).covers(piece)
        edges.append(dict(id=f'EDGE_{len(edges)+1:04}',**{'from':node(polyline[0]),'to':node(polyline[-1])},
            length_m=piece.length,width_m=route['width_m'],route_id=route['id'],
            route_ids=[r['id'] for r in owners],road_type='bridge' if is_bridge else ('unknown' if route['road_type']=='bridge' else route['road_type']),
            driveable=True if is_bridge else (None if route['road_type']=='bridge' else route['driveable']),bidirectional=route['bidirectional'],
            polyline_m=polyline,bridge_ids=[b['id'] for b in data['bridges'] if shape(b).buffer(tolerance).covers(piece)] if is_bridge else [],
            source_trace_valid=all(r['correction_pass'] for r in owners)))
    errors=[];by_id={n['id']:n for n in nodes}
    for n in nodes:
        if not all(math.isfinite(n[k]) for k in ['x_m','y_m']):errors.append(dict(node_id=n['id'],reason='Non-finite coordinate'))
        if not roads.buffer(tolerance).covers(Point(n['x_m'],n['y_m'])):
            errors.append(dict(node_id=n['id'],reason='Source trace node outside the corresponding rendered road/bridge surface'))
    keys=[(n['x_m'],n['y_m']) for n in nodes]
    if len(set(keys))!=len(keys):errors.append(dict(reason='Duplicate graph nodes'))
    for edge in edges:
        p=LineString(edge['polyline_m']);a,b=by_id[edge['from']],by_id[edge['to']]
        edge_errors=[]
        if not math.isfinite(edge['length_m']) or edge['length_m']<=0 or abs(p.length-edge['length_m'])>1e-6:edge_errors.append('Invalid edge length')
        if math.dist(p.coords[0],(a['x_m'],a['y_m']))>1e-6 or math.dist(p.coords[-1],(b['x_m'],b['y_m']))>1e-6:edge_errors.append('Edge endpoint does not meet graph junction')
        if edge['driveable'] is True:
            if p.intersection(buildings).length>1e-6:edge_errors.append('Driveable edge crosses a building')
            if p.intersection(water).length>tolerance:edge_errors.append('Driveable edge crosses unbridged water')
            if not roads.buffer(tolerance).covers(p):edge_errors.append('Driveable edge outside rendered road surface')
        if edge['road_type']=='bridge' and not edge['bridge_ids']:edge_errors.append('Bridge edge has no bridge surface')
        edge['validation_pass']=not edge_errors and edge['source_trace_valid']
        for reason in edge_errors:errors.append(dict(edge_id=edge['id'],route_id=edge['route_id'],reason=reason))
    # Check every actual centreline crossing has a shared node, not merely crossing edges.
    missing=[]
    node_points=unary_union([Point(p) for p in keys])
    for i,r in enumerate(routes):
        for other in routes[i+1:]:
            for p in point_parts(lines[r['id']].intersection(lines[other['id']])):
                if node_points.distance(p)>tolerance:missing.append([r['id'],other['id'],[p.x,p.y]])
    if missing:errors.append(dict(reason='Missing junction nodes',details=missing))
    all_components=components(by_id,edges)
    drive_edges=[e for e in edges if e['driveable'] is True and e['validation_pass']]
    drive_nodes={n for e in drive_edges for n in [e['from'],e['to']]}
    drive_components=components(drive_nodes,drive_edges)
    adjacency={n:[] for n in drive_nodes}
    for e in drive_edges:
        adjacency[e['from']].append((e['to'],e['length_m']));adjacency[e['to']].append((e['from'],e['length_m']))
    rng=random.Random(20261004);tests=[]
    for component in drive_components:
        if len(component)<2:continue
        a,b=rng.sample(component,2);queue=[(0,a)];distance={a:0}
        while queue:
            d,n=heapq.heappop(queue)
            if n==b:break
            for nxt,length in adjacency[n]:
                value=d+length
                if value<distance.get(nxt,float('inf')):distance[nxt]=value;heapq.heappush(queue,(value,nxt))
        tests.append(dict(start=a,end=b,path_length_m=distance.get(b),pass_=b in distance))
        if len(tests)>=8:break
    validation=dict(pass_=not errors and not missing and all(r['correction_pass'] for r in routes) and all(t['pass_'] for t in tests),errors=errors,
        missing_junctions=missing,node_count=len(nodes),edge_count=len(edges),
        connected_component_count=len(all_components),component_sizes=[len(p) for p in all_components],
        driveable_node_count=len(drive_nodes),driveable_edge_count=len(drive_edges),
        driveable_component_count=len(drive_components),dijkstra_tests=tests,
        connectivity_scope='Undirected structural checks only. Unknown road access/direction is not promoted to a legal driving route.',
        flagged_source_routes=[r['id'] for r in routes if not r['correction_pass']])
    result=dict(schema_version=2,model_version='0.2',coordinate_system='local_metric',nodes=nodes,edges=edges,validation=validation)
    (ROOT/'data/navigation_graph.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (ROOT/'output/validation/navigation_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    return validation


if __name__=='__main__':print(json.dumps(generate(),indent=2))

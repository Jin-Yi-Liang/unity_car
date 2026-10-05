"""Candidate entrances, roadside bays and a separate assumed simulation graph."""
import copy
import hashlib
import heapq
import json
import math
from pathlib import Path

from PIL import Image,ImageDraw
from shapely.affinity import rotate,translate
from shapely.geometry import LineString,Point,Polygon,box
from shapely.ops import unary_union,substring

from analyze_map import encode_mesh
from metric_mapping import MetricMapping

ROOT=Path(__file__).resolve().parents[1]


def polygon(feature):
    return Polygon(feature['polygon'],feature.get('holes',[]))


def footprint(center,yaw,width,length):
    return translate(rotate(box(-width/2,-length/2,width/2,length/2),math.degrees(yaw),origin=(0,0)),center[0],center[1])


def shortest_path(nodes,edges,start,goal):
    adjacency={n['id']:[] for n in nodes}
    for edge in edges:
        for direction in edge['allowed_directions']:
            a,b=(edge['from'],edge['to']) if direction=='forward' else (edge['to'],edge['from'])
            adjacency[a].append((b,edge['length_m'],edge,direction))
    queue=[(0,start)];distance={start:0};previous={}
    while queue:
        d,node=heapq.heappop(queue)
        if d!=distance[node]:continue
        if node==goal:break
        for other,length,edge,direction in adjacency[node]:
            candidate=d+length
            if candidate<distance.get(other,float('inf')):
                distance[other]=candidate;previous[other]=(node,edge,direction);heapq.heappush(queue,(candidate,other))
    if goal not in distance:raise ValueError(f'No scenario path from {start} to {goal}')
    parts=[];identifiers=[goal];node=goal
    while node!=start:
        parent,edge,direction=previous[node]
        parts.append((edge,direction));identifiers.append(parent);node=parent
    coordinates=[]
    for edge,direction in reversed(parts):
        line=edge['polyline_m'] if direction=='forward' else edge['polyline_m'][::-1]
        coordinates.extend(line if not coordinates else line[1:])
    return dict(length_m=distance[goal],node_ids=identifiers[::-1],edge_ids=[e['id'] for e,d in reversed(parts)],polyline_m=coordinates)


def plan(config,campus,base_graph,robot,policy):
    """No source road access is changed; generated paths are candidate geometry."""
    for key in ['entry_standoff_m','access_width_m','dock_lateral_offset_m','portal_width_m','portal_height_m','portal_depth_m','portal_offset_m','bay_thickness_m']:
        if not math.isfinite(config[key]) or config[key]<=0:raise ValueError(f'Invalid delivery parameter {key}')
    if policy.get('real_world_access_confirmed') is not False or policy.get('assumed_bidirectional') is not True:
        raise ValueError('Demo policy must explicitly declare unconfirmed access and assumed bidirectionality')
    routes={r['id']:r for r in campus['road_routes']}
    if not set(policy['allowed_route_ids'])<=routes.keys():raise ValueError('Scenario references unknown road route')
    allowed=[e for e in base_graph['edges'] if e['validation_pass'] and e['driveable'] is not False
             and any(r in policy['allowed_route_ids'] for r in e.get('route_ids',[e['route_id']]))]
    if not allowed:raise ValueError('Scenario has no geometrically valid eligible edges')
    road=unary_union([polygon(f)for f in campus['roads']+campus['bridges']])
    buildings=unary_union([polygon(f)for f in campus['buildings']]);water=unary_union([polygon(f)for f in campus['water']])
    obstacles=unary_union([buildings,water]);mapping=MetricMapping({'pixel_to_metric_matrix':campus['metadata']['pixel_to_metric_matrix']})
    specification=robot['config'];width=specification['width_m'];length=specification['length_m'];margin=specification['safety_margin_m']
    radius=math.hypot(width,length)/2+margin
    sites=[];access=[];bays=[];attachments=[]
    identifiers=[s['id']for s in config['sites']]
    if len(set(identifiers))!=len(identifiers):raise ValueError('Duplicate delivery site ID')
    def attach(point,route_id):
        choices=[e for e in allowed if route_id in e.get('route_ids',[e['route_id']])]
        if not choices:raise ValueError(f'Road {route_id} has no scenario-permitted source edge')
        edge=min(choices,key=lambda e:LineString(e['polyline_m']).distance(point))
        line=LineString(edge['polyline_m']);distance=line.project(point);projected=line.interpolate(distance)
        return edge,distance,projected,line
    start_point=Point(robot['pose']['position_m'][:2]);edge,d,start,_=attach(start_point,robot['navigation']['route_id'])
    if start_point.distance(start)>1e-4:raise ValueError('Robot start is off its source graph edge')
    attachments.append(dict(id='ROBOT_START',edge_id=edge['id'],distance=d,point=[start.x,start.y]))
    for record in config['sites']:
        if any(len(record[key])!=2 or not all(math.isfinite(v)for v in record[key]) for key in ['entry_pixel','outward_pixel']):
            raise ValueError('Entrance coordinates and normal must be finite 2D vectors')
        building=next((b for b in campus['buildings']if record['source_trace_id'] in b['architecture']['source_trace_ids']),None)
        if building is None or building['map_label']!=record['map_label']:raise ValueError(f'Unresolved building reference {record["id"]}')
        entry=mapping.point(record['entry_pixel']);body=polygon(building)
        boundary_error=body.boundary.distance(Point(entry))
        if boundary_error>config['entry_anchor_tolerance_px']*mapping.nominal_scale:
            raise ValueError(f'Entrance anchor is not on the traced facade: {record["id"]}')
        outward_end=mapping.point([record['entry_pixel'][i]+record['outward_pixel'][i] for i in [0,1]])
        vector=[outward_end[i]-entry[i]for i in [0,1]];norm=math.hypot(*vector)
        if norm<1e-9:raise ValueError('Zero entrance normal')
        normal=[v/norm for v in vector]
        approach=[entry[i]+normal[i]*config['entry_standoff_m']for i in [0,1]]
        if body.covers(Point(approach)):raise ValueError('Entrance normal points into its building')
        edge,d,projection,line=attach(Point(approach),record['route_id'])
        toward=[approach[0]-projection.x,approach[1]-projection.y];norm=math.hypot(*toward)
        if norm<config['dock_lateral_offset_m']+radius:raise ValueError('Facade too close to docking lane')
        dock=[projection.x+toward[0]/norm*config['dock_lateral_offset_m'],projection.y+toward[1]/norm*config['dock_lateral_offset_m']]
        a=line.interpolate(max(0,d-.05));b=line.interpolate(min(line.length,d+.05))
        yaw=math.atan2(b.x-a.x,-(b.y-a.y))
        bay=footprint(dock,yaw,width+margin*2,length+margin*2)
        rotation_disk=Point(dock).buffer(radius,quad_segs=16)
        if not road.buffer(1e-5).covers(rotation_disk) or rotation_disk.intersects(obstacles):raise ValueError(f'Dock has insufficient full-body clearance: {record["id"]}')
        connection=LineString([dock,approach]);strip=connection.buffer(config['access_width_m']/2,quad_segs=4)
        if strip.intersection(obstacles).area>1e-5:raise ValueError(f'Candidate pedestrian approach crosses an obstacle: {record["id"]}')
        path=strip.difference(road)
        if path.geom_type!='Polygon' or path.is_empty:raise ValueError('Candidate access must form one nonempty path')
        feature=dict(id='ACCESS_'+record['id'],surface_type='pedestrian_access',driveable=False,collidable=True,
                     top_m=campus['roads'][0]['top_m'],bottom_m=0.0,site_id=record['id'],**encode_mesh(path))
        access.append(feature)
        bay_feature=dict(id='DOCK_'+record['id'],surface_type='delivery_bay_marker',driveable=False,collidable=False,
                         top_m=feature['top_m']+config['bay_thickness_m'],bottom_m=feature['top_m'],site_id=record['id'],**encode_mesh(bay))
        bays.append(bay_feature)
        attachments.append(dict(id=record['id'],edge_id=edge['id'],distance=d,point=[projection.x,projection.y]))
        sites.append(dict(record,building_id=building['id'],entry_world_m=[*entry,0],outward_world_xy=normal,
                          approach_world_m=[*approach,feature['top_m']],dock_world_m=[*dock,feature['top_m']],dock_yaw_rad=yaw,
                          road_attachment_world_m=[projection.x,projection.y,feature['top_m']],base_edge_id=edge['id'],
                          facade_anchor_error_m=boundary_error,access_length_m=connection.length,
                          bay_width_m=width+margin*2,bay_length_m=length+margin*2,
                          road_edge_clearance_m=rotation_disk.distance(road.boundary),obstacle_clearance_m=rotation_disk.distance(obstacles),
                          source_access_permission=routes[record['route_id']]['driveable'],actual_entrance_confirmed=False,
                          geometry_pass=True))
    # Add only actual attachment stations, retaining curvature points on edges.
    nodes=[];lookup={};edges=[];attachment_nodes={}
    def node(point):
        key=tuple(round(float(v),7)for v in point)
        if key not in lookup:
            identifier=f'SIMNODE_{len(nodes)+1:04}';lookup[key]=identifier;nodes.append(dict(id=identifier,x_m=key[0],y_m=key[1]))
        return lookup[key]
    def add_edge(piece,parent,kind='road'):
        if piece.length<1e-7:return
        sweep=piece.buffer(radius,quad_segs=16,cap_style=1,join_style=1)
        if not road.buffer(.002).covers(sweep) or sweep.intersection(obstacles).area>1e-6:
            raise ValueError(f'Scenario full-body swept clearance fails: {parent["id"]}')
        edges.append(dict(id=f'SIMEDGE_{len(edges)+1:04}',**{'from':node(piece.coords[0]),'to':node(piece.coords[-1])},
                          length_m=piece.length,polyline_m=[list(p)for p in piece.coords],base_edge_id=parent['id'],
                          route_ids=parent.get('route_ids',[parent['route_id']]),allowed_directions=['backward','forward'],
                          edge_type=kind,access_basis='explicit simulation policy assumption',real_world_access_confirmed=False,
                          clearance_pass=True,sweep_radius_m=radius))
    for parent in allowed:
        line=LineString(parent['polyline_m']);on_edge=[a for a in attachments if a['edge_id']==parent['id']]
        cuts=sorted(set([0,line.length]+[a['distance']for a in on_edge]))
        for low,high in zip(cuts,cuts[1:]):
            if high-low>1e-7:add_edge(substring(line,low,high),parent)
        for attachment in on_edge:attachment_nodes[attachment['id']]=node(attachment['point'])
    for site in sites:
        connector=LineString([site['road_attachment_world_m'][:2],site['dock_world_m'][:2]])
        add_edge(connector,next(e for e in allowed if e['id']==site['base_edge_id']),'docking_maneuver')
        site['dock_node_id']=node(site['dock_world_m'][:2]);site['attachment_node_id']=attachment_nodes[site['id']]
    paths=[]
    for site in sites:
        path=shortest_path(nodes,edges,attachment_nodes['ROBOT_START'],site['dock_node_id'])
        geometry=LineString(path['polyline_m'])
        if abs(geometry.length-path['length_m'])>1e-5:raise ValueError('Scenario path length disagrees with geometry')
        paths.append(dict(site_id=site['id'],start_node_id=attachment_nodes['ROBOT_START'],goal_node_id=site['dock_node_id'],pass_=True,**path))
    overlaps=[dict(site_id=f['site_id'],area_m2=polygon(f).intersection(road).area)for f in access]
    if any(v['area_m2']>.01 for v in overlaps):raise ValueError('Coplanar access/road surface overlap exceeds precision tolerance')
    result=dict(schema_version=1,model_version='0.5',config=config,sites=sites,access_paths=access,delivery_bays=bays,
                validation=dict(pass_=True,site_count=len(sites),actual_confirmed_entrances=0,
                                straight_clear_width_m=width+2*margin,sweep_radius_m=radius,
                                vehicle_dynamics_validated=False,real_world_access_confirmed=False,
                                access_scope=policy['scope'],path_tests=paths,coplanar_overlap_tolerance_m2=.01,access_road_overlaps=overlaps))
    scenario=dict(schema_version=1,model_version='0.5',policy=copy.deepcopy(policy),nodes=nodes,edges=edges,
                  robot_start_node_id=attachment_nodes['ROBOT_START'],delivery_paths=paths,
                  validation=dict(pass_=True,geometry_only=True,real_world_access_confirmed=False,node_count=len(nodes),edge_count=len(edges),path_count=len(paths)))
    return result,scenario


def generate():
    read=lambda name:json.loads((ROOT/name).read_text())
    campus=read('data/campus_map.json');config=read('config/delivery_sites.json')
    source=ROOT/config['sites'][0]['source']
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if any(s['source_sha256']!=digest for s in config['sites']):raise ValueError('Delivery map evidence hash mismatch')
    result,scenario=plan(config,campus,read('data/navigation_graph.json'),read('data/delivery_robot.json'),read('config/simulation_access.json'))
    campus['access_paths']=result['access_paths'];campus['delivery_bays']=result['delivery_bays']
    reserved=unary_union([polygon(f)for f in result['access_paths']])
    # Remove same-ground landscaping beneath new formal connector slabs.
    for category in ['grass','plazas']:
        modified=[]
        for feature in campus[category]:
            trimmed=polygon(feature).difference(reserved)
            parts=[] if trimmed.is_empty else [trimmed] if trimmed.geom_type=='Polygon' else list(trimmed.geoms)
            for index,part in enumerate(parts):
                if part.area<.01:continue
                value={k:v for k,v in feature.items()if k not in ['polygon','holes','vertices_xy_m','triangles','boundary_rings','area_m2']}
                if len(parts)>1:value['id']+=f'_{index+1}'
                modified.append(dict(value,**encode_mesh(part)))
        campus[category]=modified
    for name,value in [('data/delivery_sites.json',result),('data/simulation_navigation_graph.json',scenario),('data/campus_map.json',campus),('output/validation/delivery_sites_validation.json',result['validation'])]:
        (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    overlay(ROOT,config,result,campus)
    return result,scenario


def overlay(root,config,result,campus):
    from shapely.affinity import affine_transform
    matrix=campus['metadata']['pixel_to_metric_matrix'];a,b,t=matrix[0];c,d,u=matrix[1];det=a*d-b*c
    inverse=[d/det,-b/det,-c/det,a/det,(b*u-d*t)/det,(c*t-a*u)/det]
    im=Image.open(root/config['sites'][0]['source']).convert('RGB').resize((1800,2074));draw=ImageDraw.Draw(im)
    for site,access,bay in zip(result['sites'],result['access_paths'],result['delivery_bays']):
        for feature,color in [(access,(240,160,0)),(bay,(0,180,220))]:
            p=affine_transform(polygon(feature),inverse);draw.polygon([(x*2,y*2)for x,y in p.exterior.coords],fill=color)
        x,y=site['entry_pixel'];draw.ellipse((x*2-5,y*2-5,x*2+5,y*2+5),fill='red');draw.text((x*2+8,y*2-20),site['id'],fill='black',stroke_width=2,stroke_fill='white')
    draw.rectangle((0,0,1800,60),fill='white');draw.text((12,12),'CANDIDATE ENTRANCES (red), PEDESTRIAN ACCESS (gold), DELIVERY BAYS (cyan). All locations/access are modeled assumptions.',fill='black')
    im.save(root/'output/previews/delivery_sites_overlay.png')


if __name__=='__main__':
    result,scenario=generate();print(json.dumps(result['validation'],indent=2))

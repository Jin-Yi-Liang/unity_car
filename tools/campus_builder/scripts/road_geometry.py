"""Bounded annotation cleanup: never re-plan a campus route around obstacles."""
import math
from shapely.geometry import LineString


def repair_routes(routes, obstacles, bounds, max_adjustment_px=3.0, width_fraction=0.5):
    # Preserve explicitly shared trace vertices during small annotation cleanup.
    shared={}
    for route in routes:
        for p in set(tuple(p) for p in route['centerline_px']):
            shared[p]=shared.get(p,0)+1
    repaired=[];diagnostics=[]
    for route in routes:
        line=LineString(route['centerline_px'])
        limit=min(max_adjustment_px,width_fraction*route['width_px'])
        obstacle=obstacles(route['width_px'])
        original_collision=line.intersection(obstacle).length
        candidate=line;status='UNCHANGED';offset=[0.0,0.0]
        if original_collision>1e-7:
            # Shared junction vertices stay fixed. All other vertices receive
            # the same bounded offset; no obstacle-detour search is permitted.
            options=sorted((math.hypot(dx/2,dy/2),dx/2,dy/2)
                for dx in range(-int(limit*2),int(limit*2)+1)
                for dy in range(-int(limit*2),int(limit*2)+1)
                if math.hypot(dx/2,dy/2)<=limit+1e-8)
            for _,dx,dy in options:
                trial=LineString([(x,y) if shared.get((x,y),0)>1 else (x+dx,y+dy) for x,y in line.coords])
                if trial.intersection(obstacle).length<=1e-7 and all(bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3] for x,y in trial.coords):
                    candidate=trial;offset=[dx,dy];status='BOUNDED_FIX';break
            else:status='FLAG_RETRACE_REQUIRED'
        # Hausdorff compares both directions, including lost endpoints/segments.
        drift=line.hausdorff_distance(candidate)
        accepted=status!='FLAG_RETRACE_REQUIRED' and drift<=limit+1e-8
        repaired.append(dict(route,centerline_px=list(candidate.coords),max_adjustment_px=drift,
                             correction_pass=accepted))
        diagnostics.append(dict(route_id=route['id'],name=route['name'],pass_=accepted,
            allowed_adjustment_px=limit,automatic_adjustment_px=drift,translation_px=offset,
            status=status,original_collision_length_px=original_collision,
            remaining_collision_length_px=candidate.intersection(obstacle).length,
            original_centerline_px=route['centerline_px'],accepted_centerline_px=list(candidate.coords),
            reason='Trace intersects building clearance or unbridged water; no valid correction exists within the configured limit.' if not accepted else None))
    return repaired,dict(pass_=all(d['pass_'] for d in diagnostics),
                        max_automatic_adjustment_px=max(d['automatic_adjustment_px'] for d in diagnostics),
                        flagged_route_ids=[d['route_id'] for d in diagnostics if not d['pass_']],routes=diagnostics)

"""Small deterministic clearance repair for visually traced road centre lines."""
import heapq
import math

from shapely.geometry import LineString, Point
from shapely.prepared import prep


def repair_routes(routes, obstacles, bounds, grid=1, margin=40):
    """Keep roads near their annotations, while fitting a full-width corridor.

    This is an offline geometry repair, not the vehicle/server path planner.
    Shared annotated junctions use the same snapped node on a 1-pixel grid.
    """
    obstacle = None
    cached = {}
    snapped = {}
    xmin, ymin, xmax, ymax = bounds

    def free(node):
        if node not in cached:
            x, y = node[0]*grid, node[1]*grid
            cached[node] = xmin <= x <= xmax and ymin <= y <= ymax and not obstacle.covers(Point(x,y))
        return cached[node]

    def snap(p):
        key = (current_width, *p)
        if key not in snapped:
            node = tuple(round(v/grid) for v in p)
            candidates = [(dx*dx+dy*dy, node[0]+dx, node[1]+dy)
                          for dx in range(-28,29) for dy in range(-28,29)]
            for _, x,y in sorted(candidates):
                if free((x,y)):
                    snapped[key]=(x,y)
                    break
            else:
                raise ValueError(f'Cannot fit road junction near {p}')
        return snapped[key]

    def segment(a,b):
        if a==b:
            return [a]
        start,end=snap(a),snap(b)
        direct=LineString([a,b])
        bx1,by1,bx2,by2=direct.bounds
        queue=[(0.0,0,start)]
        cost={start:0.0}
        parent={}
        while queue:
            _, distance, current=heapq.heappop(queue)
            if distance>cost[current]+1e-9:
                continue
            if current==end:
                result=[end]
                while result[-1]!=start:
                    result.append(parent[result[-1]])
                return [(n[0]*grid,n[1]*grid) for n in result[::-1]]
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                n=(current[0]+dx,current[1]+dy)
                x,y=n[0]*grid,n[1]*grid
                if not (bx1-margin<=x<=bx2+margin and by1-margin<=y<=by2+margin) or not free(n):
                    continue
                # Prevent corner cutting through an obstacle on diagonal steps.
                if dx and dy and (not free((current[0]+dx,current[1])) or not free((current[0],current[1]+dy))):
                    continue
                drift=direct.distance(Point(x,y))
                value=distance+math.hypot(dx,dy)*(1+drift*0.025)
                if value<cost.get(n,float('inf')):
                    cost[n]=value
                    parent[n]=current
                    heuristic=math.hypot(n[0]-end[0],n[1]-end[1])
                    heapq.heappush(queue,(value+heuristic,value,n))
        raise ValueError(f'No clearance corridor near segment {a} -> {b}')

    repaired=[]
    max_drift=0
    for route in routes:
        current_width=route['width_px']
        obstacle=prep(obstacles(current_width))
        cached={}
        points=[]
        for a,b in zip(route['centerline_px'],route['centerline_px'][1:]):
            path=segment(a,b)
            points+=path if not points else path[1:]
        line=LineString(points).simplify(0.55,preserve_topology=True)
        original=LineString(route['centerline_px'])
        drift=max(original.distance(Point(p)) for p in line.coords)
        max_drift=max(max_drift,drift)
        repaired.append(dict(route, centerline_px=list(line.coords), max_adjustment_px=drift))
    return repaired,max_drift

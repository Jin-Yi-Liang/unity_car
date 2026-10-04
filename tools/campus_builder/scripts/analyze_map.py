"""Convert auditable image annotations into engine-independent metric geometry."""
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely import constrained_delaunay_triangles, set_precision
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from road_geometry import repair_routes

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    return [p for g in geometry.geoms for p in parts(g)]


def encode_mesh(poly):
    """Constrained triangles preserve concave boundaries and courtyard holes."""
    # Boolean subtraction can leave almost coincident vertices around icon traces.
    # Blender stores float32 vertices: microscopic features far from the origin
    # can collapse even when GEOS double-precision geometry is valid.
    poly = set_precision(poly, 0.001).simplify(0.002, preserve_topology=True)
    ring_coords=[tuple(p[:2]) for ring in [poly.exterior,*poly.interiors] for p in list(ring.coords)[:-1]]
    if len(set(ring_coords))!=len(ring_coords):
        # Valid 2D polygons can have point-touching rings. Extruding a shared
        # point makes a four-face vertical edge. Close only that microscopic pinch.
        poly=set_precision(poly.buffer(0.02,quad_segs=1),0.001).simplify(0.002,preserve_topology=True)
    if poly.geom_type != 'Polygon' or not poly.is_valid:
        raise ValueError('Precision normalization changed polygon topology')
    vertices, triangles, rings, index = [], [], [], {}

    def vertex(xy):
        key = tuple(round(float(v), 8) for v in xy[:2])
        if key not in index:
            index[key] = len(vertices)
            vertices.append(list(key))
        return index[key]

    for ring in [poly.exterior, *poly.interiors]:
        rings.append([vertex(xy) for xy in list(ring.coords)[:-1]])
    covered = 0.0
    for triangle in constrained_delaunay_triangles(poly).geoms:
        triangles.append([vertex(xy) for xy in list(triangle.exterior.coords)[:-1]])
        covered += triangle.area
    if abs(covered - poly.area) > max(1e-6, poly.area * 1e-8):
        raise ValueError('Triangulation does not cover polygon')
    return dict(vertices_xy_m=vertices, triangles=triangles, boundary_rings=rings,
                area_m2=poly.area, polygon=list(poly.exterior.coords)[:-1],
                holes=[list(r.coords)[:-1] for r in poly.interiors])


def analyze():
    cfg = json.loads((ROOT / 'config/campus_config.json').read_text())
    source = json.loads((ROOT / 'config/source_geometry.json').read_text())
    primary = REPO / cfg['primary_map']
    reference = REPO / cfg['reference_map']
    image = Image.open(primary).convert('RGB')
    if list(image.size) != source['source_image_size']:
        raise ValueError('Annotation canvas differs from input image dimensions')
    s = float(cfg['meters_per_pixel'])
    if not math.isfinite(s) or s <= 0:
        raise ValueError('meters_per_pixel must be finite and positive')
    height_factor = s / cfg['height_reference_meters_per_pixel']
    xmin, ymin, xmax, ymax = source['ground_bounds_px']
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2

    def metric(poly):
        return affine_transform(poly, [s, 0, 0, -s, -cx * s, cy * s])

    def xy(point):
        return [(point[0] - cx) * s, (cy - point[1]) * s]

    data = dict(schema_version=1, metadata=dict(coordinate_system='local_metric',
                axes='X=image right, Y=image up, Z=height; north arrow points +Y',
                meters_per_pixel=s, origin_pixel=[cx, cy], scale_status=cfg['scale_status']),
                buildings=[], roads=[], plazas=[], grass=[], water=[], walls=[], landmarks=[])
    data['ground'] = dict(id='Ground', **encode_mesh(metric(box(xmin, ymin, xmax, ymax))),
                          bottom_m=-cfg['ground_thickness_m'] * height_factor, top_m=0.0)
    bpolys = []
    # Adjoining wings of the same numbered building form one solid footprint.
    traced_buildings = source['buildings']
    groups = {}
    for building in traced_buildings:
        groups.setdefault(building['map_label'], []).append(building)
    normalized = []
    for members in groups.values():
        for piece in parts(unary_union([Polygon(b['polygon_px']) for b in members])):
            normalized.append(dict(members[0], id=f'BLDG_{len(normalized)+1:03}',
                                   polygon_px=list(piece.exterior.coords)[:-1]))
    source['buildings'] = normalized
    for building in source['buildings']:
        poly = Polygon(building['polygon_px'])
        if not poly.is_valid or poly.area <= 0:
            raise ValueError(f"Invalid traced footprint: {building['id']}")
        for previous, previous_poly in zip(data['buildings'], bpolys):
            if poly.intersection(previous_poly).area > 0.05:
                raise ValueError(f"Overlapping footprints: {building['id']} / {previous['id']}")
        bpolys.append(poly)
        height = cfg['low_building_height_m'] if building['height_class'] == 'low' else cfg['default_building_height_m']
        data['buildings'].append(dict(id=building['id'], name=building['name'],
            map_label=building['map_label'], confidence=building['confidence'],
            height_m=height * height_factor, height_provenance='modeling default, not measured',
            **encode_mesh(metric(poly))))

    wpolys = [Polygon(p['polygon_px']) for p in source['water']]
    bridges = unary_union([Polygon(p) for p in source['bridge_masks_px']])
    all_buildings = unary_union(bpolys)
    all_water = unary_union(wpolys)
    # Full-width paths avoid severing a road when an approximate annotation hits a building.
    def obstacles(width):
        road_clearance = width / 2 + cfg['minimum_building_clearance_px']
        return unary_union([all_buildings.buffer(road_clearance),
                            all_water.difference(bridges).buffer(road_clearance)])
    source['roads'], max_adjustment = repair_routes(source['roads'], obstacles,
                                                    source['ground_bounds_px'])
    corridors = [LineString(r['centerline_px']).buffer(r['width_px'] / 2, cap_style=1, join_style=1)
                 for r in source['roads']]
    raw_roads = unary_union(corridors)
    road_poly = raw_roads.difference(all_buildings.buffer(cfg['minimum_building_clearance_px']))
    removed_for_buildings = raw_roads.area - road_poly.area
    road_poly = road_poly.difference(all_water.difference(bridges))
    for i, poly in enumerate(parts(road_poly)):
        data['roads'].append(dict(id=f'ROAD_{i+1:03}', name='Merged connected road surface',
            top_m=cfg['road_top_m'] * height_factor,
            bottom_m=(cfg['road_top_m'] - cfg['road_thickness_m']) * height_factor,
            **encode_mesh(metric(poly))))
    data['road_routes'] = [dict(id=r['id'], name=r['name'],
                              centerline=[xy(p) for p in r['centerline_px']],
                              width_m=r['width_px'] * s) for r in source['roads']]
    data['bridges'] = [encode_mesh(metric(p)) for p in parts(road_poly.intersection(bridges).intersection(all_water))]
    remaining_water = all_water.difference(road_poly)
    for i, poly in enumerate(parts(remaining_water)):
        data['water'].append(dict(id=f'WATER_{i+1:03}', top_m=cfg['water_top_m'] * height_factor,
                                 bottom_m=0, **encode_mesh(metric(poly))))
    ppolys = []
    landmark_water=unary_union([Polygon(p['polygon_px']) for p in source['landmarks'] if p['kind']=='water'])
    for p in source['plazas']:
        poly = Polygon(p['polygon_px']).difference(all_buildings).difference(road_poly).difference(all_water).difference(landmark_water)
        ppolys += parts(poly)
        for i, piece in enumerate(parts(poly)):
            data['plazas'].append(dict(id=f"{p['id']}_{i}", name=p['name'],
                top_m=cfg['plaza_top_m'] * height_factor, bottom_m=0, **encode_mesh(metric(piece))))
    lpolys = []
    for p in source['landmarks']:
        poly = Polygon(p['polygon_px'])
        lpolys.append(poly)
        data['landmarks'].append(dict(id=p['id'], name=p['name'], kind=p['kind'],
            top_m=(cfg['water_top_m'] if p['kind']=='water' else 0.035 if p['kind'] == 'field' else 0.025) * height_factor,
            bottom_m=0.0, **encode_mesh(metric(poly))))
    grass = unary_union([Polygon(p) for p in source['grass_parcels_px']]).difference(
        unary_union([all_buildings, road_poly, all_water, *ppolys, *lpolys]))
    for i, poly in enumerate(parts(grass)):
        if poly.area > 1:
            data['grass'].append(dict(id=f'GRASS_{i+1:03}', top_m=cfg['grass_top_m'] * height_factor,
                                     bottom_m=0, **encode_mesh(metric(poly))))

    road_components = sorted([p.area * s*s for p in parts(road_poly)], reverse=True)
    building_overlap = sum(road_poly.intersection(p).area for p in bpolys) * s*s
    forbidden_water_overlap = road_poly.intersection(all_water.difference(bridges)).area * s*s
    checks = dict(valid_polygons=all(metric(p).is_valid for p in [*bpolys, *parts(road_poly), *wpolys]),
                  building_road_overlap_m2=building_overlap,
                  unbridged_road_water_overlap_m2=forbidden_water_overlap,
                  road_surface_component_areas_m2=road_components,
                  road_routes=len(source['roads']), road_width_range_m=[min(r['width_px']*s for r in source['roads']),max(r['width_px']*s for r in source['roads'])],
                  trimmed_road_building_clearance_area_m2=removed_for_buildings*s*s,
                  triangulation_area_coverage=True)
    checks['road_max_centerline_adjustment_px'] = max_adjustment
    top_surfaces=[]
    for category in ['roads','grass','water','plazas','landmarks']:
        for feature in data[category]:
            top_surfaces.append((feature['id'],feature['top_m'],Polygon(feature['polygon'],feature['holes'])))
    coplanar=[]
    for i,(name,height,poly) in enumerate(top_surfaces):
        for other,other_height,other_poly in top_surfaces[i+1:]:
            if abs(height-other_height)<1e-6:
                area=poly.intersection(other_poly).area
                if area>0.01:
                    coplanar.append(dict(objects=[name,other],area_m2=area))
    checks['coplanar_surface_overlaps'] = coplanar
    checks['pass'] = checks['valid_polygons'] and building_overlap < 1e-6 and forbidden_water_overlap < 1e-6 and not coplanar
    if not checks['pass']:
        raise ValueError(f'Planar validation failed: {checks}')
    metadata = dict(input_path=str(primary), reference_path=str(reference),
        input_sha256=hashlib.sha256(primary.read_bytes()).hexdigest(),
        reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
        image_size_px=list(image.size), map_type='Stylized color campus planning diagram',
        method='Visual polygon/centreline digitization + Shapely union/difference + constrained triangulation',
        meters_per_pixel=s, scale_status=cfg['scale_status'], scale_reason=cfg['scale_reason'],
        origin_pixel=[cx,cy], y_flip=True,
        map_facts=['Relative layout and visible footprints', 'Canals, bridges, athletics field, plazas', 'Numbered building labels cross-checked against campus_2'],
        assumptions=['Scale is provisional, not surveyed', 'Building height is a modeling default, not measured real-world height.',
                     'Stylized planning map may differ from current built campus', 'Widths and boundaries are approximate manual traces',
                     'Grass represents generalized parcel landscaping', 'Ground is a rectangular supporting slab; external city streets are not modeled',
                     'No guessed walls; parcel boundaries are not confirmed physical walls'],
        planar_validation=checks,
        automatic_repairs=[f'Merged overlapping same-label wings: {len(traced_buildings)} traces -> {len(normalized)} disjoint building solids',
                           'Unioned road intersections; trimmed approximate road corridors against building clearance and unbridged water'])
    metadata['automatic_repairs'].append('Re-routed annotated corridors locally around full-width clearance obstacles')
    metadata['automatic_repairs'].append('Normalized vertices on a 0.001 m grid with 0.002 m boundary simplification for stable Blender float32 meshes')
    metadata['automatic_repairs'].append('Closed point-touching road rings by a 0.02 m expansion to prevent four-face non-manifold extrusion edges')
    metadata['automatic_repairs'].append('Subtracted the central pool from its plaza to eliminate overlapping coplanar faces seen as a black patch in renders')
    metadata['automatic_repairs'].append('Fixed overhead camera roll explicitly so north is at the top, matching the source map')
    write_json(ROOT/'data/campus_map.json', data)
    write_json(ROOT/'data/map_metadata.json', metadata)
    # Draw translucent regions, with solid contours and stable IDs, on a copy only.
    overlay = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(overlay)
    for poly in parts(road_poly):
        draw.polygon(list(poly.exterior.coords), fill=(255,0,230,100), outline=(255,0,230,255), width=2)
        for ring in poly.interiors:
            draw.polygon(list(ring.coords), fill=(0,0,0,0), outline=(255,0,230,180))
    for p in source['water']:
        draw.polygon(p['polygon_px'], fill=(0,130,255,90), outline=(0,60,255,255), width=2)
    for p in source['buildings']:
        points = [tuple(v) for v in p['polygon_px']]
        draw.polygon(points, fill=(255,120,0,100), outline=(255,45,0,255), width=2)
        c=Polygon(points).centroid
        draw.text((c.x,c.y),p['id'].split('_')[1],fill=(120,0,0,255),anchor='mm')
    for p in source['plazas']+source['landmarks']:
        draw.line([tuple(v) for v in p['polygon_px']]+[tuple(p['polygon_px'][0])], fill=(255,210,0,255), width=3)
    result=Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
    draw=ImageDraw.Draw(result)
    draw.rectangle((5,5,440,52),fill='white')
    draw.text((12,9),'ORANGE: footprints | MAGENTA: roads | BLUE: water',fill='black')
    draw.text((12,28),'YELLOW: plazas/sports | IDs match campus_map.json',fill='black')
    result.save(ROOT/'output/previews/map_debug_overlay.png')
    return metadata


if __name__ == '__main__':
    print(json.dumps(analyze()['planar_validation'], indent=2))

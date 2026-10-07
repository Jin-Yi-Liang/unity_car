"""One-time stable-ID bootstrap. Refuses to overwrite an existing registry."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = json.loads((ROOT / 'tools/campus_builder/data/campus_map.json').read_text())
sites = json.loads((ROOT / 'tools/campus_builder/data/delivery_sites.json').read_text())
by_building = {site['building_id']: site for site in sites['sites']}
output = ROOT / 'TuanjieProject/Assets/Resources/building_registry.json'
if output.exists():
    raise SystemExit(f'Registry already exists; refusing to renumber: {output}')
records = []
for number, building in enumerate(source['buildings'], 1):
    site = by_building.get(building['id'])
    points = building['vertices_xy_m']
    center_x = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    center_y = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
    records.append({
        'stableId': f'B{number:04d}',
        'meshId': building['id'],
        'displayName': building['name'],
        'mapLabel': building['map_label'],
        'sourceTraceIds': building['architecture']['source_trace_ids'],
        'centerX': round(center_x, 6),
        'centerY': round(center_y, 6),
        'navigationStatus': 'simulation_dock' if site else 'unassigned',
        'dockNodeId': site['dock_node_id'] if site else '',
        'dockX': round(site['dock_world_m'][0], 6) if site else 0,
        'dockY': round(site['dock_world_m'][1], 6) if site else 0,
    })
assert len(records) == len({r['stableId'] for r in records}) == len({r['meshId'] for r in records})
output.write_text(json.dumps({'schemaVersion': 1, 'buildings': records}, ensure_ascii=False, indent=2) + '\n')
print(f'Initialized {len(records)} stable building IDs in {output}')

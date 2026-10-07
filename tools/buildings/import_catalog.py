"""Validate a Tuanjie scene export and write the backend's UTF-8 TSV catalog."""
import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / 'data/buildings-unity.json'
DEFAULT_REGISTRY = ROOT / 'TuanjieProject/Assets/Resources/building_registry.json'
DEFAULT_OUTPUT = ROOT / 'data/buildings.tsv'
DEFAULT_GRAPH = ROOT / 'tools/campus_builder/data/simulation_navigation_graph.json'
FIELDS = ('stable_id', 'mesh_id', 'display_name', 'map_label', 'center_x', 'center_y',
          'navigation_status', 'dock_node_id', 'dock_x', 'dock_y')


def load_records(path):
    data = json.loads(path.read_text())
    if data.get('schemaVersion') != 1 or not isinstance(data.get('buildings'), list):
        raise ValueError(f'Invalid catalog schema in {path}')
    return data['buildings']


def validate(exported, registry, graph_nodes):
    known = {item['stableId']: item for item in registry}
    if len(known) != len(registry) or len(exported) != len(registry):
        raise ValueError('Building count or stable ID uniqueness changed')
    seen = set()
    result = []
    for item in exported:
        stable_id = item.get('stableId', '')
        if not re.fullmatch(r'B\d{4}', stable_id) or stable_id not in known or stable_id in seen:
            raise ValueError(f'Unknown or duplicate stable ID: {stable_id}')
        seen.add(stable_id)
        source = known[stable_id]
        for field in ('meshId', 'mapLabel', 'sourceTraceIds', 'navigationStatus', 'dockNodeId'):
            if item.get(field) != source.get(field):
                raise ValueError(f'{stable_id}: protected field {field} changed')
        for field in ('centerX', 'centerY', 'dockX', 'dockY'):
            value = item.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value - source[field]) > .001:
                raise ValueError(f'{stable_id}: protected coordinate {field} changed')
        if item['navigationStatus'] == 'simulation_dock':
            node = graph_nodes.get(item['dockNodeId'])
            if node is None or abs(node['x_m'] - item['dockX']) > .01 or abs(node['y_m'] - item['dockY']) > .01:
                raise ValueError(f'{stable_id}: dock node missing or coordinate mismatch')
        name = item.get('displayName')
        if not isinstance(name, str) or not name.strip() or any(char in name for char in '\t\r\n'):
            raise ValueError(f'{stable_id}: display name is empty or contains a tab/newline')
        result.append(dict(item, displayName=name.strip()))
    if seen != set(known):
        raise ValueError('Building IDs are missing')
    return sorted(result, key=lambda item: item['stableId'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--registry', type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--graph', type=Path, default=DEFAULT_GRAPH)
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text())
    graph_nodes = {node['id']: node for node in graph['nodes']}
    records = validate(load_records(args.input), load_records(args.registry), graph_nodes)
    lines = ['\t'.join(FIELDS)]
    for item in records:
        lines.append('\t'.join([
            item['stableId'], item['meshId'], item['displayName'], item['mapLabel'],
            format(item['centerX'], '.6f'), format(item['centerY'], '.6f'),
            item['navigationStatus'], item['dockNodeId'] or '-',
            format(item['dockX'], '.6f'), format(item['dockY'], '.6f')
        ]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + '.tmp')
    temporary.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    dock_count = sum(item['navigationStatus'] == 'simulation_dock' for item in records)
    print(f'Imported {len(records)} buildings ({dock_count} simulation docks) to {args.output}')


if __name__ == '__main__':
    main()

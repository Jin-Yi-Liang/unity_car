"""Export the checked simulation graph as a compact Unity TextAsset."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
source = root / 'tools/campus_builder/data/simulation_navigation_graph.json'
out = root / 'TuanjieProject/Assets/Resources/simulation_graph.txt'
graph = json.loads(source.read_text())
assert graph['validation']['pass_'] and len(graph['nodes']) and len(graph['edges'])
lines = ['# Generated from simulation_navigation_graph.json; XY coordinates are modeled metres.']
for node in graph['nodes']:
    lines.append('N|{}|{:.8f}|{:.8f}'.format(node['id'], node['x_m'], node['y_m']))
for edge in graph['edges']:
    points = ';'.join('{:.8f}:{:.8f}'.format(*point) for point in edge['polyline_m'])
    lines.append('E|{}|{}|{}|{}'.format(edge['id'], edge['from'], edge['to'], points))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text('\n'.join(lines) + '\n')
print(out, len(graph['nodes']), len(graph['edges']))

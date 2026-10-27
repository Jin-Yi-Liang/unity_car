"""Independent graph/catalog checks for all building pairs; standard library."""
import csv
import heapq
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DockCatalog(unittest.TestCase):
    def test_all_pairs_and_exports(self):
        graph = json.loads((ROOT / 'tools/campus_builder/data/simulation_navigation_graph.json').read_text())
        registry = json.loads((ROOT / 'TuanjieProject/Assets/Resources/building_registry.json').read_text())['buildings']
        exported = json.loads((ROOT / 'data/buildings-unity.json').read_text())['buildings']
        with (ROOT / 'data/buildings.tsv').open() as stream:
            catalog = list(csv.DictReader(stream, delimiter='\t'))
        self.assertEqual(len(registry), 69)
        self.assertEqual({r['stableId'] for r in registry}, {r['stable_id'] for r in catalog})
        self.assertEqual(len({r['dockNodeId'] for r in registry}), 69)
        nodes = {n['id']: (n['x_m'], n['y_m']) for n in graph['nodes']}
        text_nodes = {}
        text_edges = []
        for line in (ROOT / 'TuanjieProject/Assets/Resources/simulation_graph.txt').read_text().splitlines():
            fields = line.split('|')
            if fields[0] == 'N':
                text_nodes[fields[1]] = (float(fields[2]), float(fields[3]))
            elif fields[0] == 'E':
                text_edges.append(fields[1])
        self.assertEqual(set(nodes), set(text_nodes))
        self.assertEqual(set(text_edges), {e['id'] for e in graph['edges']})
        adjacency = {n: [] for n in nodes}
        for edge in graph['edges']:
            self.assertEqual(set(edge['allowed_directions']), {'forward', 'backward'})
            self.assertTrue(edge['clearance_pass'])
            points = edge['polyline_m']
            self.assertLess(math.dist(points[0], nodes[edge['from']]), .001)
            self.assertLess(math.dist(points[-1], nodes[edge['to']]), .001)
            length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
            self.assertAlmostEqual(length, edge['length_m'], places=5)
            adjacency[edge['from']].append((edge['to'], length))
            adjacency[edge['to']].append((edge['from'], length))
        export_by_id = {r['stableId']: r for r in exported}
        catalog_by_id = {r['stable_id']: r for r in catalog}
        pair_count = 0
        for record in registry:
            key, node = record['stableId'], record['dockNodeId']
            self.assertEqual(record['navigationStatus'], 'simulation_dock')
            self.assertEqual(export_by_id[key]['dockNodeId'], node)
            self.assertEqual(catalog_by_id[key]['dock_node_id'], node)
            self.assertLess(math.dist(nodes[node], text_nodes[node]), .00001)
            for x, y in [(record['dockX'], record['dockY']),
                         (export_by_id[key]['dockX'], export_by_id[key]['dockY']),
                         (float(catalog_by_id[key]['dock_x']), float(catalog_by_id[key]['dock_y']))]:
                self.assertLess(math.dist(nodes[node], (x, y)), .001)
            distances, pending = {node: 0}, [(0, node)]
            while pending:
                cost, current = heapq.heappop(pending)
                if cost != distances[current]:
                    continue
                for other, step in adjacency[current]:
                    candidate = cost + step
                    if candidate < distances.get(other, math.inf):
                        distances[other] = candidate
                        heapq.heappush(pending, (candidate, other))
            self.assertEqual(len(distances), len(nodes))
            for target in registry:
                if target['stableId'] == key:
                    continue
                self.assertGreater(distances[target['dockNodeId']], 0)
                pair_count += 1
        self.assertEqual(pair_count, 4692)


if __name__ == '__main__':
    unittest.main()

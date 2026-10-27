"""Verify physical road clearance and handover access; use campus_builder venv."""
import json
import math
import unittest
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

ROOT = Path(__file__).resolve().parents[1]


class DockGeometry(unittest.TestCase):
    def test_swept_roads_and_handover_lines(self):
        data = ROOT / 'tools/campus_builder/data'
        campus = json.loads((data / 'campus_map.json').read_text())
        graph = json.loads((data / 'simulation_navigation_graph.json').read_text())
        docks = json.loads((ROOT / 'data/building-docks.json').read_text())['docks']
        shape = lambda f: Polygon(f['polygon'], f.get('holes', []))
        buildings = {b['id']: shape(b) for b in campus['buildings']}
        road = unary_union([shape(f) for f in campus['roads'] + campus['bridges']])
        water = unary_union([shape(f) for f in campus['water']]).difference(unary_union([shape(f) for f in campus['bridges']]))
        obstacles = unary_union(list(buildings.values()) + [water])
        radius = graph['validation']['sweep_radius_m']
        for edge in graph['edges']:
            sweep = LineString(edge['polyline_m']).buffer(radius, quad_segs=16)
            self.assertTrue(road.buffer(.002).covers(sweep), edge['id'])
            self.assertLess(sweep.intersection(obstacles).area, .0001, edge['id'])
        for i, dock in enumerate(docks):
            point = Point(dock['x_m'], dock['y_m'])
            body = buildings[dock['mesh_id']]
            facade = nearest_points(point, body)[1]
            connection = LineString([point, facade])
            self.assertAlmostEqual(connection.length, dock['distance_to_facade_m'], places=4)
            self.assertLess(connection.intersection(water).length, .001, dock['stable_id'])
            for mesh, obstacle in buildings.items():
                if mesh != dock['mesh_id']:
                    self.assertLess(connection.intersection(obstacle).length, .001, (dock['stable_id'], mesh))
            for other in docks[i+1:]:
                self.assertGreaterEqual(math.dist((dock['x_m'], dock['y_m']), (other['x_m'], other['y_m'])), 2.9999)


if __name__ == '__main__':
    unittest.main()

"""Permissions, directed edges and surface coverage must survive graph noding."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import navigation_graph


class NavigationTopologyTests(unittest.TestCase):
    def run_graph(self,routes,roads=None,bridges=None):
        data=dict(road_routes=routes,roads=roads or [dict(polygon=[[-11,-2],[11,-2],[11,2],[-11,2]])],
                  bridges=bridges or [],buildings=[],water=[])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for path in ['config','data','output/validation']:(root/path).mkdir(parents=True)
            (root/'config/campus_config.json').write_text(json.dumps(dict(navigation_junction_tolerance_m=.02)))
            (root/'data/campus_map.json').write_text(json.dumps(data))
            with patch.object(navigation_graph,'ROOT',root):validation=navigation_graph.generate()
            graph=json.loads((root/'data/navigation_graph.json').read_text())
        return graph,validation

    def route(self,identifier='R1',points=None,**kwargs):
        return dict(id=identifier,centerline=points or [[-10,0],[10,0]],width_m=2,
                    road_type=kwargs.get('road_type','unknown'),driveable=kwargs.get('driveable'),
                    bidirectional=kwargs.get('bidirectional'),correction_pass=True)

    def test_bridge_surface_does_not_grant_unknown_vehicle_access(self):
        graph,validation=self.run_graph([self.route()],bridges=[dict(id='BRIDGE_001',polygon=[[-2,-1],[2,-1],[2,1],[-2,1]])])
        self.assertTrue(validation['pass_'])
        bridge=[e for e in graph['edges']if e['road_type']=='bridge']
        self.assertEqual(len(bridge),1)
        self.assertIsNone(bridge[0]['driveable'])
        self.assertEqual(validation['dijkstra_tests'],[])

    def test_unknown_edge_must_fit_surface_for_its_entire_length(self):
        _,validation=self.run_graph([self.route(points=[[-10,0],[0,4],[10,0]])])
        self.assertFalse(validation['pass_'])
        self.assertTrue(any('outside rendered' in e['reason'] for e in validation['errors']))

    def test_one_way_permission_is_used_by_dijkstra(self):
        graph,validation=self.run_graph([self.route(road_type='vehicle',driveable=True,bidirectional=False)])
        edge=graph['edges'][0]
        self.assertEqual(edge['allowed_directions'],['forward'])
        self.assertFalse(edge['bidirectional'])
        self.assertEqual(validation['dijkstra_tests'][0]['start'],edge['from'])
        self.assertEqual(validation['dijkstra_tests'][0]['end'],edge['to'])
        adjacency={edge['from']:[(edge['to'],edge['length_m'])],edge['to']:[]}
        self.assertNotIn(edge['from'],navigation_graph.shortest_distances(adjacency,edge['to']))

    def test_overlapping_prohibition_wins_over_permitted_route(self):
        graph,_=self.run_graph([self.route('R1',driveable=True,bidirectional=True),
                               self.route('R2',driveable=False,bidirectional=True)])
        self.assertTrue(all(e['driveable'] is False for e in graph['edges']))


if __name__=='__main__':unittest.main()

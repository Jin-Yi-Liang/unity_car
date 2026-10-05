"""Reject unsafe placements and keep vehicle dimensions independent of map scale."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from delivery_robot import plan


class RobotPlacementTests(unittest.TestCase):
    def fixture(self,scale=1,width=4,valid=True):
        cfg=json.loads((ROOT/'config/delivery_robot.json').read_text())
        road=dict(id='ROAD_001',polygon=[[-10*scale,-width/2],[10*scale,-width/2],[10*scale,width/2],[-10*scale,width/2]],top_m=.045)
        route=dict(id=cfg['placement_route_id'],centerline=[[-9*scale,0],[9*scale,0]],width_m=width,driveable=None,correction_pass=valid)
        campus=dict(roads=[road],road_routes=[route],buildings=[],water=[])
        edge=dict(id='EDGE_1',route_id=route['id'],validation_pass=valid,polyline_m=route['centerline'])
        return cfg,campus,dict(edges=[edge])

    def test_scale_changes_pose_but_not_vehicle_dimensions(self):
        a=plan(*self.fixture());b=plan(*self.fixture(scale=2))
        self.assertEqual(a['dimensions_m'],b['dimensions_m'])
        self.assertAlmostEqual(b['pose']['position_m'][0],a['pose']['position_m'][0]*2)
        self.assertAlmostEqual(a['pose']['forward_world'][0],1)
        self.assertIsNone(a['navigation']['access_permission'])

    def test_narrow_road_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'coverage'):plan(*self.fixture(width=.9))

    def test_flagged_source_route_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'flagged'):plan(*self.fixture(valid=False))

    def test_obstacle_in_footprint_is_rejected(self):
        cfg,campus,graph=self.fixture()
        campus['buildings']=[dict(polygon=[[-4,-.3],[-2,-.3],[-2,.3],[-4,.3]])]
        with self.assertRaisesRegex(ValueError,'clearance'):plan(cfg,campus,graph)

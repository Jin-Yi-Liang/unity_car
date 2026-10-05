"""Delivery access must preserve evidence and reject unsafe candidate geometry."""
import copy
import sys
import unittest
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import delivery_sites


class DeliverySiteTests(unittest.TestCase):
    def fixture(self):
        config=dict(entry_standoff_m=1.1,access_width_m=1.8,dock_lateral_offset_m=1.3,entry_anchor_tolerance_px=.1,
                    portal_width_m=1.6,portal_height_m=2.3,portal_depth_m=.15,portal_offset_m=.3,bay_thickness_m=.002,
                    sites=[dict(id='S1',name='Candidate',source_trace_id='RAW1',map_label='1',entry_pixel=[4,0],
                                outward_pixel=[0,-1],route_id='R1',confidence='low',entrance_status='candidate')])
        campus=dict(metadata=dict(pixel_to_metric_matrix=[[1,0,0],[0,1,0],[0,0,1]]),
                    road_routes=[dict(id='R1',width_m=8,driveable=None)],
                    roads=[dict(id='ROAD_001',top_m=.045,polygon=[[-12,-14],[12,-14],[12,-6],[-12,-6]])],bridges=[],
                    buildings=[dict(id='BLDG_001',map_label='1',architecture=dict(source_trace_ids=['RAW1']),polygon=[[0,0],[8,0],[8,5],[0,5]])],water=[])
        graph=dict(nodes=[],edges=[dict(id='E1',**{'from':'N1','to':'N2'},route_id='R1',route_ids=['R1'],
                                       polyline_m=[[-10,-10],[10,-10]],driveable=None,validation_pass=True)])
        robot=dict(config=dict(width_m=.8,length_m=1.2,safety_margin_m=.3),pose=dict(position_m=[-5,-10,.045]),navigation=dict(route_id='R1'))
        policy=dict(real_world_access_confirmed=False,assumed_bidirectional=True,allowed_route_ids=['R1'],scope='simulation only')
        return config,campus,graph,robot,policy

    def test_candidate_and_scenario_do_not_upgrade_source_evidence(self):
        args=self.fixture();before=copy.deepcopy(args[1:3]);sites,scenario=delivery_sites.plan(*args)
        self.assertEqual(args[1:3],before)
        self.assertFalse(sites['sites'][0]['actual_entrance_confirmed'])
        self.assertIsNone(sites['sites'][0]['source_access_permission'])
        self.assertTrue(scenario['delivery_paths'][0]['pass_'])
        path=scenario['delivery_paths'][0]
        self.assertAlmostEqual(path['length_m'],10.3)

    def test_confirmed_prohibition_overrides_assumed_permission(self):
        args=self.fixture();args[2]['edges'][0]['driveable']=False
        with self.assertRaisesRegex(ValueError,'no geometrically valid'):delivery_sites.plan(*args)

    def test_rotation_disk_rejects_a_lane_that_fits_straight_body(self):
        args=self.fixture();args[0]['dock_lateral_offset_m']=.2
        args[1]['roads'][0]['polygon']=[[-12,-11],[12,-11],[12,-9],[-12,-9]]
        self.assertLess(.8+2*.3+2*.2,2)
        with self.assertRaisesRegex(ValueError,'full-body clearance'):delivery_sites.plan(*args)

    def test_pedestrian_connector_cannot_cross_water(self):
        args=self.fixture();args[1]['water']=[dict(polygon=[[3,-5],[5,-5],[5,-3],[3,-3]])]
        with self.assertRaisesRegex(ValueError,'approach crosses an obstacle'):delivery_sites.plan(*args)

    def test_entrance_must_be_on_the_requested_building_boundary(self):
        args=self.fixture();args[0]['sites'][0]['entry_pixel']=[4,2]
        with self.assertRaisesRegex(ValueError,'not on the traced facade'):delivery_sites.plan(*args)

    def test_xy_calibration_does_not_scale_bay_or_robot(self):
        args=self.fixture();first,_=delivery_sites.plan(*args)
        args=self.fixture();args[1]['metadata']['pixel_to_metric_matrix']=[[2,0,0],[0,2,0],[0,0,1]]
        for category in ['roads','buildings']:
            for feature in args[1][category]:feature['polygon']=[[2*x,2*y]for x,y in feature['polygon']]
        args[2]['edges'][0]['polyline_m']=[[-20,-20],[20,-20]];args[3]['pose']['position_m']=[-10,-20,.045]
        second,_=delivery_sites.plan(*args)
        self.assertEqual(second['sites'][0]['entry_world_m'],[8,0,0])
        for result in [first,second]:
            self.assertAlmostEqual(Polygon(result['delivery_bays'][0]['polygon']).area,1.4*1.8,places=5)


if __name__=='__main__':unittest.main()

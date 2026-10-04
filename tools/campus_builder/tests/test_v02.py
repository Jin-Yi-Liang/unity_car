"""Regressions for evidence gates, bounded trace repair and metric mapping."""
import contextlib
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import calibrate_scale
import analyze_map
import navigation_graph
from metric_mapping import MetricMapping
from road_geometry import repair_routes
from shapely.geometry import box


class CalibrationTests(unittest.TestCase):
    def records(self, scales):
        return [dict(pixel_distance=100, real_distance_m=s*100) for s in scales]

    def test_outlier_does_not_choose_the_scale(self):
        fit, _, outliers, _, _ = calibrate_scale.uniform_fit(self.records([1, 1, 1, 3]), [1]*4)
        self.assertTrue(outliers[-1])
        self.assertLess(abs(fit['meters_per_pixel']-1), .02)
        self.assertGreater(fit['rmse_percent'], 10)  # conflict still visible

    def test_collinear_controls_cannot_register_a_plane(self):
        self.assertIsNone(calibrate_scale.similarity_fit([
            dict(pixel=[i, 0], metric=[i*2, 0]) for i in range(3)]))

    def test_similarity_handles_rotation_and_image_y_flip(self):
        points=[dict(pixel=[x,y], metric=[y*2+5,x*2+7]) for x,y in [(0,0),(10,0),(0,10),(10,10)]]
        fit=calibrate_scale.similarity_fit(points)
        mapping=MetricMapping({'pixel_to_metric_matrix':fit['matrix']})
        self.assertLess(fit['control_point_rmse_m'], 1e-9)
        self.assertEqual(mapping.point([3,4]), [13,13])

    def run_calibration(self, mutate):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'config').mkdir()
            for name in ['campus_config.json','source_geometry.json','scale_anchors.json']:
                value=json.loads((ROOT/'config'/name).read_text())
                if name=='scale_anchors.json':
                    for r in value['anchors']:r['evidence_file']=str(ROOT/r['evidence_file'])
                    mutate(value)
                (root/'config'/name).write_text(json.dumps(value))
            with patch.object(calibrate_scale,'ROOT',root):return calibrate_scale.calibrate()

    def test_standards_fit_cannot_become_real_world_pass(self):
        result=self.run_calibration(lambda _:None)
        self.assertTrue(result['residual_pass'])
        self.assertFalse(result['pass_'])
        self.assertEqual(result['confidence'],'LOW')
        self.assertEqual(result['reason'],'INSUFFICIENT SCALE EVIDENCE')

    def test_high_confidence_conflict_is_not_hidden_as_outlier(self):
        def mutate(config):
            for anchor in config['anchors']:
                anchor.update(source_type='measured',confidence='high')
            config['anchors'][0]['real_distance_m']*=2
        result=self.run_calibration(mutate)
        self.assertFalse(result['pass_'])
        self.assertIn('TRACK_OUTER_LONG',result['robust_statistics']['high_confidence_conflicts'])


class RoadTests(unittest.TestCase):
    def route(self, identifier, points, width=6):
        return dict(id=identifier,name=identifier,centerline_px=points,width_px=width)

    def test_large_required_detour_keeps_original_and_flags(self):
        route=self.route('R1',[(0,0),(20,0)])
        fixed, report=repair_routes([route],lambda _:box(5,-20,15,20),[-30,-30,30,30])
        self.assertFalse(report['pass_'])
        self.assertEqual(fixed[0]['centerline_px'],[(0.,0.),(20.,0.)])
        self.assertEqual(report['max_automatic_adjustment_px'],0)

    def test_width_fraction_caps_small_correction(self):
        route=self.route('R1',[(0,0),(10,0)],width=2)
        _, report=repair_routes([route],lambda _:box(4,-.2,6,.2),[-20,-20,20,20])
        self.assertTrue(report['pass_'])
        self.assertLessEqual(report['max_automatic_adjustment_px'],1)

    def test_small_fix_keeps_explicit_shared_junction(self):
        a=self.route('R1',[(0,0),(5,0),(10,0)])
        b=self.route('R2',[(0,0),(0,10)])
        fixed, report=repair_routes([a,b],lambda _:box(4,-.2,6,.2),[-20,-20,20,20])
        self.assertTrue(report['pass_'])
        self.assertEqual(fixed[0]['centerline_px'][0],fixed[1]['centerline_px'][0])


class PipelineDataTests(unittest.TestCase):
    def test_xy_recalibration_does_not_scale_z(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ['config','data','output/previews']: (root/name).mkdir(parents=True)
            (root/'input').symlink_to(ROOT/'input',target_is_directory=True)
            (root/'config/building_profiles.json').write_bytes((ROOT/'config/building_profiles.json').read_bytes())
            for name in ['campus_config.json','source_geometry.json','scale_anchors.json']:
                value=json.loads((ROOT/'config'/name).read_text())
                if name=='scale_anchors.json':
                    for r in value['anchors']:r['evidence_file']=str(ROOT/r['evidence_file'])
                (root/'config'/name).write_text(json.dumps(value))
            with patch.object(calibrate_scale,'ROOT',root):calibration=calibrate_scale.calibrate()
            samples=[]
            for factor in [1,1.2]:
                current=copy.deepcopy(calibration)
                current['pixel_to_metric_matrix']=[[v*factor for v in row] if i<2 else row for i,row in enumerate(calibration['pixel_to_metric_matrix'])]
                for key in ['meters_per_pixel','meters_per_pixel_x','meters_per_pixel_y']: current[key]*=factor
                (root/'data/scale_calibration.json').write_text(json.dumps(current))
                with patch.object(analyze_map,'ROOT',root): analyze_map.analyze()
                samples.append(json.loads((root/'data/campus_map.json').read_text()))
            self.assertEqual([b['height_m'] for b in samples[0]['buildings']],[b['height_m'] for b in samples[1]['buildings']])
            self.assertEqual(samples[0]['ground']['bottom_m'],samples[1]['ground']['bottom_m'])
            self.assertEqual([b['top_m'] for b in samples[0]['roads']],[b['top_m'] for b in samples[1]['roads']])
            self.assertAlmostEqual(samples[1]['ground']['area_m2']/samples[0]['ground']['area_m2'],1.2**2,places=5)

    def test_crossing_routes_are_noded_and_driveable_dijkstra_runs(self):
        routes=[dict(id='R1',centerline=[[-10,0],[0,0],[10,0]],width_m=2,road_type='vehicle',driveable=True,bidirectional=True,correction_pass=True),
                dict(id='R2',centerline=[[0,-10],[0,10]],width_m=2,road_type='vehicle',driveable=True,bidirectional=True,correction_pass=True)]
        data=dict(road_routes=routes,roads=[dict(polygon=[[-11,-11],[11,-11],[11,11],[-11,11]])],bridges=[],buildings=[],water=[])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ['config','data','output/validation']:(root/name).mkdir(parents=True)
            (root/'config/campus_config.json').write_text(json.dumps(dict(navigation_junction_tolerance_m=.02)))
            (root/'data/campus_map.json').write_text(json.dumps(data))
            with patch.object(navigation_graph,'ROOT',root):result=navigation_graph.generate()
            self.assertTrue(result['pass_'])
            self.assertEqual((result['node_count'],result['edge_count'],result['connected_component_count']),(5,4,1))
            self.assertTrue(result['dijkstra_tests'][0]['pass_'])


if __name__=='__main__':unittest.main()

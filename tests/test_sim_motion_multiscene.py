"""SW-04A input boundaries, independent geometry and genuine generated wire."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sim_motion_fixture import ROOT
from sim_motion_multiscene_fixture import expected, expected_wire, layout, source_cases, wire_cases
from sim_motion_multiscene_oracle import box_hits, nearest_hit, ray_direction, verify_literals
from ufm_simulation.motion_suite import case_spec, geometry_template, load_suite, validate_geometry, validate_suite


class MultisceneTests(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(ROOT / 'configs/sim_motion_multiscene_fixture.json')
        self.literals = expected()

    def test_nine_bound_cases_geometry_map_and_epoch_contract(self):
        for wanted, row in zip(self.literals['cases'], self.suite['cases']):
            spec = case_spec(self.suite, wanted['case_id'])
            self.assertEqual(row['ic_degrees'], wanted['ic_degrees'])
            self.assertEqual(spec['geometry'], self.literals['geometry'][wanted['geometry_id']])
            if row['case_id'] != 'S01':self.assertEqual(spec['map_settings'], self.literals['wide_map'])
            else:self.assertIsNone(spec['map_settings'])
        self.assertEqual([e['after_step'] for e in self.suite['cases'][6]['epochs']], [100,225])
        self.assertEqual(self.suite['cases'][7]['fault'], dict(sensor_kind=1, step_index=125))

    def test_bad_versions_identities_and_base_paths_are_not_fallback(self):
        for key, value in (('schema_version','v2'),('suite_id','foreign'),
                ('base_motion_profile','../4D-Radar-Diffusion/config.json'),
                ('base_motion_profile','/tmp/profile.json'),('base_motion_profile','configs/../configs/sim_scene_motion_fixture.json')):
            suite = copy.deepcopy(self.suite); suite[key] = value
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):validate_suite(suite)
        with self.assertRaises(ValueError):case_spec(self.suite, 'S10')

    def test_case_count_duplicates_and_order_preserve_recovery_sequence(self):
        for rows in (self.suite['cases'][:-1], self.suite['cases']*2,
                self.suite['cases'][:-1]+[self.suite['cases'][7]], list(reversed(self.suite['cases']))):
            suite = copy.deepcopy(self.suite); suite['cases'] = rows
            with self.assertRaises(ValueError):validate_suite(suite)

    def test_ic_geometry_expected_binding_and_native_are_fixed(self):
        for key, value in (('ic_degrees',[0,0,91]),('ic_degrees',[True,0,90]),
                ('geometry_id','empty'),('expected_id','multiscene:S06'),('native',1),('native',True)):
            suite = copy.deepcopy(self.suite); suite['cases'][0][key] = value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_suite(suite)

    def test_epochs_are_exact_paused_boundaries_and_named_obstacle(self):
        for key, value in (('after_step',True),('after_step',100.),('after_step',101),
                ('obstacle_name','sensor_aircraft'),('position',[101,0,8]),('position',[float('nan'),0,8])):
            suite = copy.deepcopy(self.suite); suite['cases'][6]['epochs'][0][key] = value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_suite(suite)
        for epochs in ([],self.suite['cases'][6]['epochs']*2,list(reversed(self.suite['cases'][6]['epochs']))):
            suite = copy.deepcopy(self.suite); suite['cases'][6]['epochs'] = epochs
            with self.assertRaises(ValueError):validate_suite(suite)

    def test_fault_cannot_be_moved_retyped_or_hidden_in_normal_case(self):
        for key, value in (('sensor_kind',True),('sensor_kind',2),('step_index',125.),('step_index',250)):
            suite = copy.deepcopy(self.suite); suite['cases'][7]['fault'][key] = value
            with self.assertRaises(ValueError):validate_suite(suite)
        suite = copy.deepcopy(self.suite); suite['cases'][0]['fault'] = suite['cases'][7]['fault']
        with self.assertRaises(ValueError):validate_suite(suite)

    def test_training_or_control_fields_rejected_at_every_declared_level(self):
        for path in ((),('cases',0),('cases',6,'epochs',0),('cases',7,'fault'),('resource_limits',)):
            for key in ('lidar','target','observed_mask','training_supervision','control','duration_steps'):
                suite = copy.deepcopy(self.suite); node = suite
                for part in path:node = node[part]
                node[key] = []
                with self.subTest(path=path,key=key),self.assertRaises(ValueError):validate_suite(suite)

    def test_resource_contract_rejects_relaxed_zero_boolean_and_missing_limits(self):
        for key in self.suite['resource_limits']:
            for value in (0,True,self.suite['resource_limits'][key]*2):
                suite = copy.deepcopy(self.suite); suite['resource_limits'][key] = value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_suite(suite)
        suite = copy.deepcopy(self.suite); del suite['resource_limits']['receipt_bytes']
        with self.assertRaises(ValueError):validate_suite(suite)

    def test_loader_rejects_duplicate_nonfinite_encoding_and_byte_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'suite.json'
            for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}',b'\xff',
                    b' '*262145, b'['*1100+b'0'+b']'*1100):
                path.write_bytes(raw)
                with self.subTest(raw=raw[:40]),self.assertRaises(ValueError):load_suite(path)
            raw = json.dumps(self.suite).encode('utf-8')
            path.write_bytes(raw+b' '*(262144-len(raw)))
            self.assertEqual(load_suite(path),self.suite)

    def test_structure_and_utf8_limits_before_schema_validation(self):
        for value in ({'x':'a'*129},{'x':'\u4e2d'*43},{'x':'\ud800'},{'x':'a\0b'},
                {'x':[[[[[[[[[0]]]]]]]]]}, {'x':[0]*513}, {'x':{str(i):0 for i in range(65)}},
                {'x':[[0]*512 for _ in range(17)]}):
            with self.subTest(value=str(value)[:50]),self.assertRaises(ValueError):validate_suite(value)

    def test_loader_also_checks_fixed_base_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'profile.json'
            profile = json.loads((ROOT/'configs/sim_scene_motion_fixture.json').read_text())
            profile['duration_steps'] = 500
            path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError,'scene_profile_differs'):
                load_suite(ROOT/'configs/sim_motion_multiscene_fixture.json',base_profile_path=path)

    def test_geometry_is_explicit_no_ground_and_validates_box_boundaries(self):
        self.assertFalse(geometry_template('empty')['include_ground'])
        self.assertEqual(geometry_template('empty')['objects'],[])
        for value in (0,-1,float('inf'),float('nan'),True):
            geometry = geometry_template('east_wall'); geometry['objects'][0]['size'][0] = value
            with self.assertRaises(ValueError):validate_geometry('east_wall',geometry)
        for kind in ('ground','cylinder','../wall'):
            with self.assertRaises(ValueError):geometry_template(kind)
        geometry = geometry_template('east_wall'); geometry['objects'] *= 9
        with self.assertRaises(ValueError):validate_geometry('east_wall',geometry)
        for key in ('lidar','target','observed_mask'):
            geometry = geometry_template('east_wall'); geometry['objects'][0][key] = []
            with self.assertRaises(ValueError):validate_geometry('east_wall',geometry)

    def test_geometry_and_case_results_are_isolated_from_input_and_other_calls(self):
        spec = case_spec(self.suite,'S07')
        spec['epochs'][0]['position'][0] = 0
        spec['geometry']['objects'][0]['size'][0] = 99
        spec['map_settings']['shape'][0] = 1
        again = case_spec(self.suite,'S07')
        self.assertEqual(again['epochs'][0]['position'],[100,0,8])
        self.assertEqual(again['geometry']['objects'][0]['size'],[1,12,12])
        self.assertEqual(again['map_settings']['shape'],[160,160,64])

    def test_frozen_analytic_rotations_lever_arms_time_and_budget(self):
        verify_literals(self.literals)
        self.assertEqual(len(self.literals['cases']),9)
        self.assertEqual(self.literals['budget']['core_committed_ns'],8496000000)

    def test_nearest_box_occludes_farther_surface_on_actual_even_ray_grid(self):
        boxes = self.literals['geometry']['occlusion_boxes']['objects']
        d = ray_direction(48,12)
        hits = box_hits([.8,0,8],d,boxes)
        self.assertEqual([h['name'] for h in hits],['obstacle_near','obstacle_far'])
        self.assertAlmostEqual(hits[0]['distance'],7.201029212956173,places=12)
        self.assertEqual(nearest_hit([.8,0,8],d,boxes),hits[0])
        self.assertGreater(abs(d[1]),0)
        self.assertGreater(abs(d[2]),0)
        self.assertAlmostEqual(sum(x*x for x in d),1.)
        for h,v in ((-1,0),(96,0),(0,24),(True,0)):
            with self.assertRaises(ValueError):ray_direction(h,v)

    def test_slab_parallel_behind_inside_and_exact_range_endpoints(self):
        def box(center):return [dict(name='box',position=center,size=[1,2,2])]
        self.assertIsNone(nearest_hit([0,0,0],[0,1,0],box([4,0,0])))
        self.assertIsNone(nearest_hit([0,0,0],[1,0,0],box([-4,0,0])))
        self.assertEqual(box_hits([0,0,0],[1,0,0],box([0,0,0]))[0]['distance'],.5)
        self.assertIsNone(nearest_hit([0,0,0],[1,0,0],box([1,0,0])))
        self.assertIsNone(nearest_hit([0,0,0],[1,0,0],box([30.5,0,0])))
        self.assertAlmostEqual(nearest_hit([0,0,0],[1,0,0],box([1.001,0,0]))['distance'],.501)

    def test_empty_and_far_obstacle_have_no_in_range_analytic_rays(self):
        boxes = copy.deepcopy(self.literals['geometry']['moving_box']['objects'])
        boxes[0]['position'] = [100,0,8]
        for v in range(24):
            for h in range(96):
                d = ray_direction(h,v)
                self.assertIsNone(nearest_hit([.8,0,8],d,[]))
                self.assertIsNone(nearest_hit([5.8,0,4],d,boxes))

    def test_synthetic_raw_fdm_conversion_matches_independent_frozen_geometry(self):
        from sim_motion_multiscene_checks import verify_sources
        profile = json.loads((ROOT/'configs/sim_scene_motion_fixture.json').read_text())
        self.assertEqual(len(verify_sources(source_cases(self.literals),self.literals,profile)),18)

    def test_actual_generated_scene_wire_matches_saved_independent_layout(self):
        from ufm_scene_contract.codec import to_ros, deserialize
        rows = wire_cases(self.literals)
        self.assertEqual(len(rows),77)
        for row in rows:
            stream = io.BytesIO(); to_ros(row['kind'],row['value']).serialize(stream)
            self.assertEqual(stream.getvalue(),expected_wire(row,layout()),row['id'])
            self.assertEqual(deserialize(row['kind'],stream.getvalue()),row['value'])

    def test_empty_public_wire_and_history_ttl_match_independent_query_oracle(self):
        from sim_motion_multiscene_checks import verify_empty_semantics
        result = verify_empty_semantics(self.literals)
        self.assertEqual(len(result['wire']),36)
        self.assertEqual(result['historical_cell_ns'],400000000)
        self.assertEqual(result['queries']['ten_empty']['status'],'unknown')

    def test_contract_import_does_not_start_ros_or_import_business_layers(self):
        result = subprocess.run([sys.executable,'-B','-c',
            'import sys; import ufm_simulation.motion_suite; '
            'assert not any(k in sys.modules for k in ("rospy","numpy","ufm_perception.engine","uav_fusionmap_sim_scene_msgs.msg"))'],
            text=True,capture_output=True,timeout=10.)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_verify_refuses_partial_evidence_before_any_new_write(self):
        from sim_motion_multiscene_run import verify
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); old = path/'actual-000.bin'; old.write_bytes(b'old')
            with self.assertRaisesRegex(ValueError,'already exists'):verify(path)
            self.assertEqual(list(path.iterdir()),[old])
            self.assertEqual(old.read_bytes(),b'old')

    def test_verifier_rejects_dropped_or_reordered_frozen_inputs(self):
        from sim_motion_multiscene_run import verify
        for name, rows in (('wire-inputs.json',wire_cases(self.literals)[:-1]),
                           ('wire-inputs.json',list(reversed(wire_cases(self.literals)))),
                           ('source-inputs.json',source_cases(self.literals)[:-1])):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                data = {'independent-expectations.json':self.literals,'suite.json':self.suite,
                    'base-profile.json':json.loads((ROOT/'configs/sim_scene_motion_fixture.json').read_text()),
                    'wire-inputs.json':wire_cases(self.literals),'source-inputs.json':source_cases(self.literals)}
                data[name] = rows
                for filename,value in data.items():(path/filename).write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'frozen inputs missing'):verify(path)
                self.assertEqual(list(path.glob('actual-*.bin')),[])


if __name__ == '__main__':unittest.main()

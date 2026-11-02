"""M4-SW-01 behavior: explicit registration, isolated inputs and frozen independent tables."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m4_fixture import CONFIG, P, bound_spec, load_spec, observation, scenarios, step
from m4_oracle import expected_step
from m4_fixture_run import roundtrip
from m3_oracle import expected_sequence
from ufm_mapping.m4_contract import validate_fixture_observation, validate_registration_time, validate_spec
from ufm_mapping.factory import create_map
from ufm_ros_contract.perf01a_codec import to_ros_occupancy, from_ros_occupancy


class M4FixtureContractTest(unittest.TestCase):
    def setUp(self):
        self.spec=bound_spec(load_spec(),'test-m4')
        self.declaration=step(0,10_000_000,['p'],[],1,10_000_000)
        self.row=observation(self.spec,self.declaration)

    def test_complete_explicit_configuration_and_inputs_are_not_modified(self):
        before=copy.deepcopy((self.spec,self.row))
        validate_spec(self.spec)
        validate_fixture_observation(self.row,self.spec)
        self.assertEqual((self.spec,self.row),before)
        self.assertFalse(self.spec['enabled_by_default'])

    def test_missing_registration_and_undeclared_configuration_are_rejected(self):
        for key in self.spec:
            spec=copy.deepcopy(self.spec)
            del spec[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_spec(spec)
        for changes in (dict(fixture_only=False),dict(enabled_by_default=True),
                dict(schema_version='old'),dict(lidar={}),dict(target=[])):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_spec(dict(self.spec,**changes))

    def test_registration_direction_status_source_and_identity_are_explicit(self):
        for key,value in (('source_frame','map'),('target_frame','odom'),('status','unavailable'),
                ('source','measured'),('registration_id',''),('clock_id',''),('run_id','')):
            spec=copy.deepcopy(self.spec)
            spec['registration'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_spec(spec)

    def test_rotation_nonfinite_boolean_and_implicit_identity_are_rejected(self):
        matrix=self.spec['registration']['T_map_odom']
        invalid=[matrix[:-1],dict(enumerate(matrix))]
        for index,value in ((0,0.),(1,.01),(3,float('nan')),(3,True),(15,0.),(3,0.)):
            bad=list(matrix)
            bad[index]=value
            invalid.append(bad)
        for bad in invalid:
            spec=copy.deepcopy(self.spec)
            spec['registration']['T_map_odom']=bad
            with self.subTest(matrix=bad),self.assertRaises(ValueError):
                validate_spec(spec)

    def test_fractional_registration_lattice_and_mismatched_resolution_reject(self):
        for change in ('translation','scene_origin','resolution'):
            spec=copy.deepcopy(self.spec)
            if change=='translation':
                spec['registration']['T_map_odom'][3]=32.25
            elif change=='scene_origin':
                spec['scene']['origin'][0]=.25
            else:
                spec['scene']['resolution'][0]=.25
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_spec(spec)

    def test_scene_geometry_and_resource_limits_reject_bad_types(self):
        for key,value in (('max_sealed_submaps',True),('max_sealed_submaps',0),
                ('max_sealed_submaps',1.5)):
            with self.assertRaises(ValueError):
                validate_spec(dict(self.spec,**{key:value}))
        for key,value in (('shape',[True,64,16]),('shape',[256,0,16]),('shape',[2**31,64,16]),
                ('origin',[float('inf'),0.,0.]),('resolution',[True,.5,.5]),('frame_id','odom'),
                ('map_id','other')):
            spec=copy.deepcopy(self.spec)
            spec['scene'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                validate_spec(spec)

    def test_registration_time_interval_requires_ordered_int64(self):
        for start,end in ((0,0),(1,0),(-1,2),(False,2),(0,2**63),(0,1.5)):
            spec=copy.deepcopy(self.spec)
            spec['registration'].update(valid_from_ns=start,valid_until_ns=end)
            with self.subTest(start=start,end=end),self.assertRaises(ValueError):
                validate_spec(spec)

    def test_half_open_registration_time_is_enforced_on_inputs(self):
        for stamp,accepts in ((0,True),(999_999_999,True),(1_000_000_000,False),(-1,False),(True,False)):
            row=copy.deepcopy(self.row)
            row['header']['timestamp']=row['context']['reference_timestamp']=stamp
            if accepts:
                validate_fixture_observation(row,self.spec)
            else:
                with self.assertRaises(ValueError):
                    validate_fixture_observation(row,self.spec)

    def test_wrong_registration_domain_is_refused(self):
        for run,clock in (('foreign','sim:test-m4'),('test-m4','foreign')):
            with self.assertRaisesRegex(ValueError,'run or clock'):
                validate_registration_time(self.spec,10_000_000,run,clock)
        row=copy.deepcopy(self.row)
        row['header']['run_id']='foreign'
        with self.assertRaisesRegex(ValueError,'run or clock'):
            validate_fixture_observation(row,self.spec)

    def test_full_window_boundaries_are_checked_even_for_empty_valid_frames(self):
        for body,accepts in ((-16.,True),(80.,True),(-16.5,False),(80.5,False)):
            row=observation(self.spec,step(1,20_000_000,[],[],0,None,body=body,kind='empty'))
            if accepts:
                validate_fixture_observation(row,self.spec)
            else:
                with self.assertRaisesRegex(ValueError,'complete active window'):
                    validate_fixture_observation(row,self.spec)

    def test_nonvalid_missing_transform_is_not_read_as_a_window(self):
        row=observation(self.spec,step(1,20_000_000,[],[],0,None,body=200.,kind='unavailable',
                                       mutate='unavailable_transform'))
        validate_fixture_observation(row,self.spec)
        row['header'].update(status='valid',reason='')
        with self.assertRaises(ValueError):
            validate_fixture_observation(row,self.spec)

    def test_half_cell_and_adjacent_float64_window_boundary_follow_declared_tie_rule(self):
        import struct
        # Explicit aligned observation origins are independent of fractional body coordinates.
        for center,origin,outcomes in ((-16.25,-32.,[True,True,False]),
                                       (80.25,64.,[True,False,False])):
            bits=struct.unpack('!Q',struct.pack('!d',center))[0]
            for offset,accepts in zip((-1,0,1),outcomes):
                body=struct.unpack('!d',struct.pack('!Q',bits+offset))[0]
                row=observation(self.spec,step(0,10_000_000,[],[],0,None,body=body,kind='empty'))
                row['origin']=[origin,-8.,-4.]
                if accepts:
                    validate_fixture_observation(row,self.spec)
                else:
                    with self.assertRaisesRegex(ValueError,'complete active window'):
                        validate_fixture_observation(row,self.spec)

    def test_window_preflight_matches_existing_m3_float_arithmetic_on_all_axes(self):
        # M3 performs intermediate float64 additions before half-cell rounding.
        # Near a tie, exact rational evaluation can pick a different window.
        for axis,body,accepts in ((1,8.249999999999998,False),
                                  (2,.24999999999999997,False),
                                  (2,-.25000000000000006,True)):
            row=copy.deepcopy(self.row)
            row['voxels']=[]
            row['context']['T_mapping_body'][4*axis+3]=body
            if accepts:
                validate_fixture_observation(row,self.spec)
            else:
                with self.subTest(axis=axis),self.assertRaisesRegex(ValueError,'complete active window'):
                    validate_fixture_observation(row,self.spec)

    def test_lidar_target_and_observed_mask_reject_at_each_input_boundary(self):
        for key in ('lidar','target','observed_mask'):
            for boundary in ('observation','header','context','voxel'):
                row=copy.deepcopy(self.row)
                target={'observation':row,'header':row['header'],'context':row['context'],
                        'voxel':row['voxels'][0]}[boundary]
                target[key]=[]
                with self.subTest(key=key,boundary=boundary),self.assertRaises(ValueError):
                    validate_fixture_observation(row,self.spec)

    def test_input_geometry_source_and_calibration_cannot_bypass_profile(self):
        for mutate in ('fractional_origin','wrong_source','wrong_calibration','bool_shape','bool_resolution'):
            row=copy.deepcopy(self.row)
            if mutate=='fractional_origin': row['origin'][0]+=.25
            elif mutate=='wrong_source': row['header']['source_type']='model'
            elif mutate=='wrong_calibration': row['context']['calibration_id']='foreign'
            elif mutate=='bool_shape': row['shape'][0]=True
            else: row['resolution'][0]=True
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                validate_fixture_observation(row,self.spec)

    def test_bad_last_quality_is_refused_without_rewriting_input(self):
        for change in (dict(unit='m2'),dict(source='foreign'),dict(value=[.8,.7]),
                dict(value=[.8,.9]),dict(value=[True,.8]),dict(value=[float('inf'),.8])):
            row=copy.deepcopy(self.row)
            row['voxels'].append(copy.deepcopy(row['voxels'][0]))
            row['voxels'][-1]['index']=[40,16,8]
            row['voxels'][-1]['uncertainty'].update(change)
            before=copy.deepcopy(row)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_fixture_observation(row,self.spec)
            self.assertEqual(row,before)

    def test_all_declared_input_cases_retain_fields_through_real_serialization(self):
        for case in scenarios(self.spec):
            for declaration in case['steps']:
                row=observation(case['spec'],declaration)
                decoded=roundtrip(row,to_ros_occupancy,from_ros_occupancy)
                self.assertEqual(row,decoded)
                for value in (row,decoded):
                    if declaration['contract_accepts']:
                        validate_fixture_observation(value,case['spec'])
                    else:
                        with self.assertRaises(ValueError):
                            validate_fixture_observation(value,case['spec'])

    def test_independent_coordinate_and_fifo_table_have_concrete_expected_values(self):
        case=next(c for c in scenarios(self.spec) if c['name']=='fifo_eviction_and_fresh_return')
        first=expected_step(case['spec'],case['versions'],case['steps'][0])
        self.assertEqual(first['snapshot']['cells'][0]['index'],[80,32,8])
        middle=expected_step(case['spec'],case['versions'],case['steps'][2])
        self.assertEqual([c['index'] for c in middle['snapshot']['cells']],[[160,32,8],[240,32,8]])
        self.assertEqual(middle['queries'][0]['result']['status'],'unknown')
        last=expected_step(case['spec'],case['versions'],case['steps'][-1])
        p=next(c for c in last['snapshot']['cells'] if c['index']==[80,32,8])
        self.assertEqual(p['probability'],.25)
        self.assertEqual(p['uncertainty']['value'],[.2,.3])

    def test_quality_takeover_and_empty_seal_tables_do_not_borrow_or_refresh(self):
        cases={case['name']:case for case in scenarios(self.spec)}
        case=cases['missing_takeover_ttl']
        expected=expected_step(case['spec'],case['versions'],case['steps'][4])
        cell=next(c for c in expected['snapshot']['cells'] if c['index']==[80,32,8])
        self.assertEqual(cell['uncertainty']['status'],'unavailable')
        self.assertEqual(cell['last_observed_timestamp'],40_000_000)
        self.assertEqual([q['result']['status'] for q in expected['queries']],['occupied','stale'])
        case=cases['empty_seals_do_not_evict']
        for declaration in case['steps'][1:4]:
            state=expected_step(case['spec'],case['versions'],declaration)
            self.assertEqual(state['ownership'],dict(active=[],sealed=[['p']]))
            self.assertEqual(state['snapshot']['header']['timestamp'],10_000_000)

    def test_oracle_tables_reject_duplicate_ownership_and_capacity_errors(self):
        case=scenarios(self.spec)[0]
        for active,sealed in ((['p'],[['p']]),([], [[],['p']]),([], [['p'],['p'],['p']])):
            declaration=dict(case['steps'][0],active=active,sealed=sealed)
            with self.assertRaises(ValueError):
                expected_step(case['spec'],case['versions'],declaration)

    def test_declared_probability_fractions_match_existing_independent_m3_arithmetic(self):
        arithmetic=self.spec['local_map']['arithmetic']
        traces=[(('occupied','occupied'),('9/10',['49/58','9/10'])),
                (('occupied','free'),('1/2',['7/19','12/19'])),
                (('occupied','free','free'),('1/4',['7/55','36/85']))]
        for kinds,(p,bounds) in traces:
            events=[dict(kind=kind,probability='3/4' if kind=='occupied' else '1/4',
                bounds=['7/10','4/5'] if kind=='occupied' else ['1/5','3/10'],timestamp=(i+1)*10_000_000)
                for i,kind in enumerate(kinds)]
            last=expected_sequence(events,arithmetic)[-1]
            self.assertEqual((last['probability_fraction'],last['interval_fractions']),(p,bounds))

    def test_custom_contract_cannot_silently_reuse_incompatible_expected_tables(self):
        spec=copy.deepcopy(self.spec)
        spec['local_map']['arithmetic']['occupied_probability']=.78125
        validate_spec(spec)  # Valid contract, but a different arithmetic problem.
        with self.assertRaisesRegex(ValueError,'scenario tables'):
            scenarios(spec)

    def test_default_does_not_import_m4_and_scene_requires_explicit_config(self):
        with self.assertRaisesRegex(ValueError,'requires explicit fixture configuration'):
            create_map('m4_fixture')
        subprocess.run([sys.executable,'-B','-c',
            "from ufm_mapping.factory import create_map; import sys; create_map(); "
            "assert 'ufm_mapping.m4_contract' not in sys.modules; "
            "assert not any(k.endswith('probability_map') for k in sys.modules)"],check=True,timeout=10)

    def test_freezing_runner_reports_expectations_without_executing_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            process=subprocess.run([sys.executable,'-B',str(CONFIG.parent.parent/'tests/m4_fixture_run.py'),
                '--output-root',folder],text=True,capture_output=True,timeout=10)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            receipt=json.loads(process.stdout)
            report=json.loads((Path(receipt['run'])/'report.json').read_text())
            self.assertTrue(report['passed'])
            self.assertFalse(report['scene_map_executed'])
            self.assertFalse(report['map_accumulation_executed'])
            self.assertEqual(report['scenario_count'],8)
            self.assertEqual(report['expected_states'],['free','occupied','stale','unavailable','unknown'])
            self.assertEqual(report['contract_refused'],3)
            self.assertTrue((Path(receipt['run'])/'fixtures.json').is_file())

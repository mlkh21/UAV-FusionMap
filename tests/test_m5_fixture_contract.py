"""M5 private inputs: bounded bytes, datums, masks, quality and explicit domains."""
import copy
from fractions import Fraction as F
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from m5_fixture import input_cases, load_spec, query_request, set_path, unavailable_quality
from m5_oracle import load_expected
from ufm_mapping.m5_contract import LIMITS, load_fixture, validate_request, validate_spec


class M5FixtureContractTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()

    def test_declared_input_matrix_matches_independent_acceptance(self):
        for case in input_cases(self.spec):
            before = copy.deepcopy(case['spec'])
            with self.subTest(case=case['name']):
                if case['accepts']:
                    validate_spec(case['spec'])
                else:
                    with self.assertRaises(ValueError):validate_spec(case['spec'])
                self.assertEqual(case['spec'], before)

    def test_exact_json_roundtrip_preserves_every_input_and_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tile.json'
            for case in input_cases(self.spec):
                path.write_text(json.dumps(case['spec'], allow_nan=False))
                with self.subTest(case=case['name']):
                    if case['accepts']:
                        self.assertEqual(load_fixture(path), case['spec'])
                    else:
                        with self.assertRaises(ValueError):load_fixture(path)

    def test_frozen_pixel_height_and_interval_examples_are_rational(self):
        grid, matrix = self.spec['grid'], self.spec['registration']['T_map_terrain']
        gt = [F(str(v)) for v in grid['affine']]
        for sample in load_expected()['samples']:
            row, col = sample['row'], sample['column']
            x, y = gt[0]+(col+F(1,2))*gt[1], gt[3]+(row+F(1,2))*gt[5]
            self.assertEqual([float(x),float(y)], sample['source_xy'])
            self.assertEqual([float(x+matrix[3]),float(y+matrix[7])], sample['map_xy'])
            index = row*grid['columns']+col
            self.assertEqual(grid['heights'][index], sample['source_height'])
            if not grid['no_data_mask'][index]:
                self.assertEqual(float(F(str(grid['heights'][index]))+matrix[11]), sample['map_height'])
                source_bounds = grid['height_quality'][index]['value']
                reg_bounds = self.spec['registration']['height_quality']['value']
                self.assertEqual([float(F(str(a))+F(str(b))) for a,b in zip(source_bounds,reg_bounds)],
                                 sample['map_height_interval'])

    def test_geoid_arithmetic_is_expected_only_no_conversion_backend(self):
        groups = {g['id']:g for g in load_expected()['groups']}
        for name in ('T5','T6'):
            row = groups[name]
            self.assertEqual(row['H']+row['N']-row['h0'], row['expected_z'])
            self.assertIn('unsupported', row['sw01'])
        row = groups['T6']
        h,n,z = row['H_bounds'],row['N_bounds'],row['h0_bounds']
        self.assertEqual([h[0]+n[0]-z[1],h[1]+n[1]-z[0]],row['expected_bounds'])

    def test_all_sixteen_groups_and_future_events_are_frozen_not_executed(self):
        expected = load_expected()
        self.assertEqual([r['id'] for r in expected['groups']], ['T'+str(i) for i in range(1,17)])
        self.assertEqual([r['expected_revision'] for r in expected['future_events'][:4]], [1,1,1,1])
        self.assertIn('candidate_pending', expected['groups'][7]['sw01'])

    def test_unavailable_quality_is_admitted_without_inventing_bounds(self):
        before = copy.deepcopy(self.spec)
        self.spec['grid']['height_quality'][0] = unavailable_quality()
        self.spec['registration']['height_quality'] = unavailable_quality()
        validate_spec(self.spec)
        self.assertIsNone(self.spec['grid']['height_quality'][0]['value'])
        self.assertEqual(self.spec['grid']['heights'], before['grid']['heights'])

    def test_no_data_and_valid_zero_negative_are_distinct(self):
        validate_spec(self.spec)
        self.assertIsNone(self.spec['grid']['heights'][2])
        self.assertTrue(self.spec['grid']['no_data_mask'][2])
        self.assertEqual(self.spec['grid']['heights'][3], -2.)
        self.spec['grid']['heights'][0] = 0.
        self.spec['grid']['height_quality'][0]['value'] = [-.1,.1]
        validate_spec(self.spec)
        self.spec['grid']['no_data_mask'][0] = True
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_nonfinite_boolean_numeric_and_malformed_arrays_rejected(self):
        for path in (('grid','heights',0),('grid','affine',0),('registration','T_map_terrain',11),
                     ('grid','height_quality',0,'value',0),('map_grid','origin_xy',0)):
            for replacement in (True, '1', float('nan'), float('inf'), -float('inf')):
                candidate = copy.deepcopy(self.spec)
                set_path(candidate,path,replacement)
                with self.subTest(path=path,value=replacement),self.assertRaises(ValueError):validate_spec(candidate)
        for path in (('grid','heights'),('grid','affine'),('grid','no_data_mask'),
                     ('grid','height_quality'),('registration','T_map_terrain')):
            for replacement in (None, {}, '123', [1]):
                candidate = copy.deepcopy(self.spec)
                set_path(candidate,path,replacement)
                with self.subTest(path=path),self.assertRaises(ValueError):validate_spec(candidate)

    def test_bounds_reject_empty_reversed_excluding_nominal_and_wrong_units(self):
        for value in ([11.,10.], [0.,1.], [], [10.]):
            self.spec['grid']['height_quality'][0]['value'] = value
            with self.subTest(value=value),self.assertRaises(ValueError):validate_spec(self.spec)
        self.spec = load_spec()
        self.spec['grid']['height_quality'][0]['unit'] = 'm2'
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_fixed_transform_does_not_accept_identity_rotation_or_reversed_direction(self):
        for slot, value in ((0,0.),(15,0.),(1,.1)):
            spec = copy.deepcopy(self.spec)
            spec['registration']['T_map_terrain'][slot] = value
            with self.subTest(slot=slot),self.assertRaises(ValueError):validate_spec(spec)
        identity = copy.deepcopy(self.spec)
        for index in (3,7,11):identity['registration']['T_map_terrain'][index] = 0.
        identity['registration']['height_quality']['value'] = [-.1,.1]
        with self.assertRaisesRegex(ValueError,'nonzero'):validate_spec(identity)
        self.spec['registration']['source_frame'], self.spec['registration']['target_frame'] = 'map','terrain_fixture'
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_int64_time_intervals_precision_and_boolean_times(self):
        for path in (('source_time','acquisition_ns'),('source_time','publication_ns'),
                     ('source_time','precision_ns'),('eligibility','valid_interval_ns',0),
                     ('registration','valid_interval_ns',1)):
            for replacement in (-1,True,1.5,2**63):
                spec = copy.deepcopy(self.spec)
                set_path(spec,path,replacement)
                with self.subTest(path=path,value=replacement),self.assertRaises(ValueError):validate_spec(spec)

    def test_query_timestamps_outside_validity_are_syntax_valid_future_results_pending(self):
        for stamp in (99,100,199,200,300):
            self.assertIsNone(validate_request(self.spec,query_request(self.spec,stamp)))
        # SW-01 validates syntax only; these statuses belong to the future candidate.
        t8 = load_expected()['groups'][7]
        self.assertEqual(t8['expected_status'],['unavailable','valid','valid','stale','unavailable'])

    def test_request_domains_units_and_non_center_samples_rejected(self):
        for key,value in (('run_id','foreign'),('clock_id','dataset:m5-fixture'),('frame_id','odom'),
                          ('query_timestamp',True),('query_timestamp',-1),('point_xy',[111.1,179.]),
                          ('point_xy',[111.,True]),('point_xy',[111.,179.,13.])):
            request = query_request(self.spec,100)
            request[key] = value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_request(self.spec,request)
        validate_request(self.spec,query_request(self.spec,100,point=(121.,179.)))

    def test_schema_missing_extra_and_training_supervision_rejected_at_boundaries(self):
        for path in ((),('identity',),('source_time',),('horizontal',),('vertical',),('grid',),
                     ('registration',),('eligibility',),('map_grid',),('limits',),
                     ('grid','height_quality',0)):
            for field in ('lidar','target','observed_mask'):
                spec = copy.deepcopy(self.spec)
                target = spec
                for key in path:target = target[key]
                target[field] = []
                with self.subTest(path=path,field=field),self.assertRaises(ValueError):validate_spec(spec)
        del self.spec['vertical']
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_frozen_limits_checked_before_array_traversal(self):
        self.spec['grid']['rows'] = 10**12
        self.spec['grid']['heights'] = None
        with self.assertRaisesRegex(ValueError,'sample limits'):validate_spec(self.spec)
        for key in LIMITS:
            spec = load_spec()
            spec['limits'][key] += 1
            with self.subTest(limit=key),self.assertRaises(ValueError):validate_spec(spec)

    def test_maximum_small_tile_and_no_data_capacity(self):
        grid = self.spec['grid']
        grid.update(rows=4,columns=4,heights=[None]*16,no_data_mask=[True]*16,
                    height_quality=[unavailable_quality() for _ in range(16)])
        validate_spec(self.spec)
        grid['rows'] = 5
        with self.assertRaises(ValueError):validate_spec(self.spec)

    def test_bounded_reader_rejects_before_json_decode_and_accepts_exact_byte_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'tile.json'
            encoded = json.dumps(self.spec).encode()
            path.write_bytes(encoded+b' '*(LIMITS['max_input_bytes']-len(encoded)))
            self.assertEqual(load_fixture(path), self.spec)
            path.write_bytes(b' '*(LIMITS['max_input_bytes']+1))
            with patch('ufm_mapping.m5_contract.json.loads',side_effect=AssertionError('decoder must not run')):
                with self.assertRaisesRegex(ValueError,'byte limit'):load_fixture(path)

    def test_json_rejects_duplicate_keys_nan_utf8_and_deep_input(self):
        payloads = [b'{"grid":1,"grid":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff',
                    b'['*1100+b'0'+b']'*1100, b'{"x":1e999}', b'null', b'{}']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'tile.json'
            for payload in payloads:
                path.write_bytes(payload)
                with self.subTest(payload=payload[:30]),self.assertRaises(ValueError):load_fixture(path)

    def test_default_latest_m2_m3_m4_stay_independent_of_terrain(self):
        command = '''import sys
sys.path.insert(0, 'tests')
from ufm_mapping.factory import create_map
from m4_fixture import bound_spec, load_spec
spec = bound_spec(load_spec(), 'isolated')
create_map()
create_map('m2_fixture', fixture_spec=spec['local_map']['arithmetic'], run_id='isolated', clock_id='sim:isolated')
create_map('m3_fixture', fixture_spec=spec['local_map'], run_id='isolated', clock_id='sim:isolated')
create_map('m4_fixture', {'rolling_enabled':True}, fixture_spec=spec, run_id='isolated', clock_id='sim:isolated')
assert not any(k in sys.modules for k in ('ufm_mapping.m5_contract','osgeo','pyproj','torch'))
try: create_map('m5_fixture')
except ValueError: pass
else: raise AssertionError('M5 runtime unexpectedly enabled')
'''
        subprocess.run([sys.executable,'-B','-c',command],cwd=Path(__file__).resolve().parents[1],check=True,timeout=10)

    def test_future_conflict_is_valid_input_but_bad_tile_rejects_without_mutation(self):
        from m5_fixture import future_events
        events = future_events(self.spec, load_expected())
        for event in events:
            if 'input' not in event:continue
            before = copy.deepcopy(event['input'])
            if event['operation'] == 'install_bad_tile':
                with self.assertRaises(ValueError):validate_spec(event['input'])
            else:
                validate_spec(event['input'])
            self.assertEqual(event['input'], before)
        self.assertEqual(events[0]['input'],events[1]['input'])
        self.assertNotEqual(events[1]['input'],events[2]['input'])
        self.assertEqual(events[1]['input']['identity'],events[2]['input']['identity'])

    def test_input_checks_do_not_touch_existing_occupancy_snapshot_or_revision(self):
        from ufm_mapping.factory import create_map
        from test_local_map_query import observation
        local = create_map()
        local.update(observation())
        before = local.snapshot()
        for case in input_cases(self.spec):
            try:validate_spec(case['spec'])
            except ValueError:pass
        validate_request(self.spec,query_request(self.spec,300))
        self.assertEqual(local.snapshot(),before)


if __name__ == '__main__':
    unittest.main()

"""Private M5 candidate behavior against frozen expectations, without ROS/GIS."""
import copy
from fractions import Fraction as F
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from m5_fixture import future_events, input_cases, load_spec, query_request, unavailable_quality
from m5_oracle import load_expected
from ufm_mapping.terrain_fixture import TerrainFixture
from ufm_mapping.terrain_replay import replay_terrain


class TerrainFixtureTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.layer = self.make_layer()

    def make_layer(self,spec=None):
        return TerrainFixture(spec or self.spec,'m5-fixture','sim:m5-fixture')

    def install(self,layer=None,spec=None,stamp=100):
        layer = layer or self.layer
        layer.observe_clock(stamp)
        return layer.install(spec or self.spec,stamp)

    def query(self,stamp=100,point=(111.,179.),layer=None):
        return (layer or self.layer).query(query_request(self.spec,stamp,point))

    def test_explicit_constructor_domain_and_clock_are_required(self):
        for run,clock in ((None,None),('other','sim:other'),('m5-fixture','other')):
            with self.assertRaises(ValueError):TerrainFixture(self.spec,run,clock)
        self.assertEqual(self.query()['reason'],'clock_unavailable')
        with self.assertRaises(ValueError):self.layer.install(self.spec,100)
        self.layer.observe_clock(100)
        self.assertEqual(self.query()['reason'],'terrain_unavailable')

    def test_frozen_samples_match_center_height_and_outward_quality_bounds(self):
        self.install()
        for sample in load_expected()['samples']:
            result = self.query(point=sample['map_xy'])
            self.assertEqual(result['source_index'],[sample['row'],sample['column']])
            self.assertEqual(result['source_xy'],sample['source_xy'])
            self.assertEqual(result['height'],sample['map_height'])
            if sample['map_height'] is None:
                self.assertEqual((result['status'],result['reason']),('unknown','no_data'))
                self.assertEqual(result['height_quality']['status'],'unavailable')
            else:
                self.assertEqual(result['status'],'valid')
                bounds = result['height_quality']['value']
                for actual,expected in zip(bounds,sample['map_height_interval']):
                    self.assertAlmostEqual(actual,expected,places=12)
                self.assertLessEqual(F.from_float(bounds[0]), F(str(sample['map_height_interval'][0])))
                self.assertGreaterEqual(F.from_float(bounds[1]), F(str(sample['map_height_interval'][1])))

    def test_frozen_half_open_times_and_original_metadata_preserved(self):
        self.install()
        t8 = load_expected()['groups'][7]
        before = self.layer.snapshot()
        for stamp,status in zip(t8['times_ns'],t8['expected_status']):
            result = self.query(stamp)
            self.assertEqual(result['status'],status)
            if status in ('valid','stale'):
                self.assertEqual(result['source_time'],self.spec['source_time'])
                self.assertEqual(result['eligibility'],self.spec['eligibility'])
                self.assertEqual(result['installed_timestamp'],100)
                self.assertEqual(result['height'],13.)
            else:
                self.assertIsNone(result['height'])
                self.assertIsNone(result['source_time'])
        self.assertEqual(before,self.layer.snapshot())

    def test_saved_future_events_replay_without_using_expected_fields(self):
        expected = load_expected()
        events = future_events(self.spec,expected)
        first = replay_terrain(self.spec,events)
        outcomes = ['installed','idempotent','rejected','rejected','stale','unavailable','unavailable']
        self.assertEqual([row['outcome'] for row in first['receipts']],outcomes)
        self.assertEqual([row['terrain_revision'] for row in first['receipts']],[1]*7)
        self.assertTrue(first['final_snapshot']['locked'])
        self.assertEqual(first['receipts'][-1]['result']['reason'],'clock_reset_new_run_required')
        for row in events:
            row.pop('expected',None)
            row.pop('expected_revision',None)
        second = replay_terrain(self.spec,events)
        self.assertEqual(first,second)

    def test_identical_install_does_not_refresh_expiry_revision_or_activation(self):
        self.install()
        before = self.layer.snapshot()
        self.assertFalse(self.install(stamp=110))
        self.assertFalse(self.install(stamp=200))
        after = self.layer.snapshot()
        for key in ('terrain_revision','installed_timestamp','spec','samples','version_ids'):
            self.assertEqual(after[key],before[key])
        self.assertEqual(self.query(200)['status'],'stale')
        self.assertEqual(self.query(99)['reason'],'query_before_terrain_activation')

    def test_bad_and_conflicting_versions_reject_keep_committed_state(self):
        self.install()
        for case in input_cases(self.spec):
            if case['accepts']:continue
            self.layer.observe_clock(110)
            before = self.layer.snapshot()
            with self.subTest(case=case['name']),self.assertRaises(ValueError):self.layer.install(case['spec'],110)
            self.assertEqual(self.layer.snapshot(),before)
        changed = copy.deepcopy(self.spec)
        changed['grid']['height_quality'][0] = unavailable_quality()
        with self.assertRaisesRegex(ValueError,'conflicting'):self.layer.install(changed,110)
        self.assertEqual(self.query(110)['height'],13.)

    def test_successful_whole_version_replace_then_retired_version_never_revives(self):
        self.install()
        replacement = copy.deepcopy(self.spec)
        replacement['identity']['dataset_version'] = 'v2'
        replacement['grid']['heights'][0] = 20.
        replacement['grid']['height_quality'][0]['value'] = [19.75,20.25]
        self.assertTrue(self.install(spec=replacement,stamp=120))
        result = self.query(120)
        self.assertEqual((result['dataset_version'],result['terrain_revision'],result['height']),('v2',2,23.))
        self.assertEqual(self.query(119)['status'],'unavailable')
        self.assertEqual(self.query(120,point=(113.,179.))['height'],14.)
        before = self.layer.snapshot()
        with self.assertRaisesRegex(ValueError,'retired'):self.layer.install(self.spec,120)
        self.assertEqual(self.layer.snapshot(),before)

    def test_source_time_reversal_and_invalid_install_times_do_not_replace(self):
        self.install()
        replacement = copy.deepcopy(self.spec)
        replacement['identity']['dataset_version'] = 'v2'
        replacement['source_time']['acquisition_ns'] = 9
        self.layer.observe_clock(120)
        with self.assertRaisesRegex(ValueError,'backwards'):self.layer.install(replacement,120)
        with self.assertRaisesRegex(ValueError,'current run clock'):self.layer.install(self.spec,119)
        replacement['source_time']['acquisition_ns'] = 10
        for stamp in (99,200,300):
            layer = self.make_layer()
            layer.observe_clock(stamp)
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):layer.install(replacement,stamp)
            self.assertEqual(layer.snapshot()['terrain_revision'],0)

    def test_registration_and_geometry_cannot_be_hot_swapped(self):
        self.install()
        for key in ('registration_id','height_quality'):
            replacement = copy.deepcopy(self.spec)
            replacement['identity']['dataset_version'] = 'v2'
            replacement['registration'][key] = 'other' if key == 'registration_id' else unavailable_quality()
            with self.subTest(key=key),self.assertRaises(ValueError):self.layer.install(replacement,100)
        replacement = copy.deepcopy(self.spec)
        replacement['grid']['rows'] = 1
        for name in ('heights','no_data_mask','height_quality'):replacement['grid'][name] = replacement['grid'][name][:2]
        with self.assertRaisesRegex(ValueError,'new instance'):self.layer.install(replacement,100)

    def test_each_missing_quality_stays_unavailable_without_fabricated_error(self):
        for case in input_cases(self.spec):
            if 'missing_' not in case['name'] or not case['accepts']:continue
            layer = self.make_layer(case['spec'])
            self.install(layer,case['spec'])
            result = self.query(layer=layer)
            self.assertEqual(result['height'],13.)
            self.assertEqual(result['height_quality']['status'],'unavailable')
            self.assertIsNone(result['height_quality']['value'])
            self.assertEqual(result['quality_contributors']['sample'],case['spec']['grid']['height_quality'][0])

    def test_zero_and_negative_heights_and_no_data_never_become_free(self):
        spec = copy.deepcopy(self.spec)
        spec['grid']['heights'][0] = 0.
        spec['grid']['height_quality'][0]['value'] = [-.1,.1]
        layer = self.make_layer(spec)
        self.install(layer,spec)
        self.assertEqual(self.query(layer=layer)['height'],3.)
        self.assertEqual(self.query(point=(113.,177.),layer=layer)['height'],1.)
        for point in ((111.,177.),(121.,179.)):
            result = self.query(point=point,layer=layer)
            self.assertEqual(result['status'],'unknown')
            self.assertIsNone(result['height'])
            self.assertNotIn('probability',result)
            self.assertNotIn('observed',result)

    def test_request_domain_is_unavailable_but_bad_syntax_and_interpolation_error(self):
        self.install()
        for key,value in (('run_id','foreign'),('clock_id','other'),('frame_id','odom')):
            request = query_request(self.spec,100)
            request[key] = value
            result = self.layer.query(request)
            self.assertEqual(result['status'],'unavailable')
            self.assertIsNone(result['height'])
            self.assertIsNone(result['dataset_version'])
        for key,value in (('point_xy',[111.1,179.]),('query_timestamp',True),('frame_id','')):
            request = query_request(self.spec,100)
            request[key] = value
            with self.subTest(key=key),self.assertRaises(ValueError):self.layer.query(request)

    def test_clock_reset_is_explicit_terminal_and_queries_do_not_reset_clock(self):
        self.install()
        self.layer.observe_clock(150)
        self.query(100)
        self.assertFalse(self.layer.snapshot()['locked'])
        self.layer.observe_clock(149)
        self.layer.observe_clock(160)
        self.assertEqual(self.query(160)['reason'],'clock_reset_new_run_required')
        with self.assertRaises(ValueError):self.layer.install(self.spec,160)
        self.assertEqual(self.layer.snapshot()['terrain_revision'],1)

    def test_disable_never_returns_prior_payload_and_does_not_affect_new_instance(self):
        self.install()
        self.layer.disable()
        result = self.query()
        self.assertEqual(result['reason'],'terrain_disabled')
        self.assertIsNone(result['height'])
        with self.assertRaises(ValueError):self.layer.install(self.spec,100)
        fresh = self.make_layer()
        self.install(layer=fresh)
        self.assertEqual(self.query(layer=fresh)['status'],'valid')

    def test_caller_cannot_mutate_committed_spec_results_or_snapshot(self):
        self.install()
        self.spec['grid']['heights'][0] = 1000
        self.assertEqual(self.query()['height'],13.)
        snapshot = self.layer.snapshot()
        snapshot['spec']['grid']['heights'][0] = 2000
        result = self.query()
        result['quality_contributors']['sample']['value'][0] = -1000
        self.assertEqual(self.query()['height'],13.)
        self.assertEqual(self.query()['quality_contributors']['sample']['value'],[9.75,10.25])

    def test_prepare_failure_is_atomic_and_same_identity_retry_works(self):
        self.install()
        spec = copy.deepcopy(self.spec)
        spec['identity']['dataset_version'] = 'v2'
        self.layer.observe_clock(120)
        before = self.layer.snapshot()
        with patch.object(self.layer,'_prepare_samples',side_effect=ValueError('fixture fault')):
            with self.assertRaises(ValueError):self.layer.install(spec,120)
        self.assertEqual(self.layer.snapshot(),before)
        self.assertTrue(self.layer.install(spec,120))
        self.assertEqual(self.query(120)['terrain_revision'],2)

    def test_finite_inputs_with_output_overflow_reject_before_commit(self):
        spec = copy.deepcopy(self.spec)
        spec['registration']['T_map_terrain'][11] = 1e308
        spec['registration']['height_quality'] = unavailable_quality()
        spec['grid']['heights'][0] = 1e308
        spec['grid']['height_quality'][0] = unavailable_quality()
        layer = self.make_layer(spec)
        with self.assertRaisesRegex(ValueError,'float64'):self.install(layer,spec)
        self.assertEqual(layer.snapshot()['terrain_revision'],0)

    def test_replay_is_bounded_and_rejects_unsupported_operations(self):
        with self.assertRaises(ValueError):replay_terrain(self.spec,[{}]*65)
        with self.assertRaises(ValueError):replay_terrain(self.spec,[dict(sequence=1,operation='query')])
        with self.assertRaises(ValueError):replay_terrain(self.spec,[dict(sequence=0,operation='fallback')])
        with self.assertRaises(ValueError):replay_terrain(self.spec,[None])
        with self.assertRaises(ValueError):replay_terrain(self.spec,[dict(sequence=False,operation='disable',timestamp_ns=100)])
        with self.assertRaises(ValueError):replay_terrain(self.spec,[dict(sequence=0,operation='query',timestamp_ns=100,
                                                                       request=query_request(self.spec,101))])

    def test_full_lifecycle_does_not_modify_an_existing_occupancy_map(self):
        from ufm_mapping.factory import create_map
        from test_local_map_query import observation
        local = create_map()
        local.update(observation())
        before = local.snapshot()
        replay_terrain(self.spec,future_events(self.spec,load_expected()))
        self.install()
        self.layer.disable()
        self.query()
        self.assertEqual(local.snapshot(),before)

    def test_registered_source_does_not_read_source_ref_or_gis_assets(self):
        self.spec['identity']['source_ref'] = '/does/not/exist/terrain.tif'
        layer = self.make_layer()
        with patch('builtins.open',side_effect=AssertionError('no source file access')):
            self.install(layer)
            self.assertEqual(self.query(layer=layer)['height'],13.)

    def test_version_id_budget_fails_without_evicting_previous_identity(self):
        for index in range(64):
            spec = copy.deepcopy(self.spec)
            spec['identity']['dataset_version'] = 'v'+str(index)
            self.install(spec=spec)
        before = self.layer.snapshot()
        spec['identity']['dataset_version'] = 'v64'
        with self.assertRaisesRegex(ValueError,'identity limit'):self.layer.install(spec,100)
        self.assertEqual(self.layer.snapshot(),before)
        self.assertEqual(len(before['version_ids']),64)
        spec['identity']['dataset_version'] = 'v0'
        with self.assertRaisesRegex(ValueError,'retired'):self.layer.install(spec,100)

    def test_candidate_byte_limit_applies_to_direct_objects_and_no_state_changes(self):
        self.install()
        replacement = copy.deepcopy(self.spec)
        replacement['identity']['dataset_version'] = 'x'*16384
        before = self.layer.snapshot()
        with self.assertRaisesRegex(ValueError,'byte limit'):self.layer.install(replacement,100)
        self.assertEqual(self.layer.snapshot(),before)

    def test_replacement_replaces_no_data_and_quality_without_inheriting_old_samples(self):
        self.install()
        spec = copy.deepcopy(self.spec)
        spec['identity']['dataset_version'] = 'replace-all'
        spec['grid']['heights'][0] = None
        spec['grid']['no_data_mask'][0] = True
        spec['grid']['height_quality'][0] = unavailable_quality()
        spec['grid']['heights'][2] = 30.
        spec['grid']['no_data_mask'][2] = False
        spec['grid']['height_quality'][2] = unavailable_quality()
        self.install(spec=spec,stamp=110)
        self.assertEqual(self.query(110)['reason'],'no_data')
        self.assertIsNone(self.query(110)['height'])
        replacement = self.query(110,point=(111.,177.))
        self.assertEqual(replacement['height'],33.)
        self.assertEqual(replacement['height_quality']['status'],'unavailable')

    def test_commit_preparation_failure_preserves_version_identity_for_retry(self):
        self.install()
        spec = copy.deepcopy(self.spec)
        spec['identity']['dataset_version'] = 'v2'
        self.layer.observe_clock(120)
        before = self.layer.snapshot()
        with patch('ufm_mapping.terrain_fixture._Committed',side_effect=ValueError('precommit failure')):
            with self.assertRaises(ValueError):self.layer.install(spec,120)
        self.assertEqual(self.layer.snapshot(),before)
        self.assertTrue(self.layer.install(spec,120))


if __name__ == '__main__':
    unittest.main()

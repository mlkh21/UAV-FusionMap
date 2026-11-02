"""Public live gates and atomic versions against frozen terrain expectations."""
import copy
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from m5_fixture import load_spec
from m5_iface_fixture import expected, request
from ufm_mapping.terrain_dataset import from_private_fixture
from ufm_mapping.terrain_provider import TerrainProvider
from ufm_terrain_contract.codec import deserialize, serialize


class TerrainProviderTest(unittest.TestCase):
    def setUp(self):
        self.dataset = from_private_fixture(load_spec())
        self.wall = 0
        self.provider = self.make()

    def make(self, dataset=None, enabled=True):
        return TerrainProvider(dataset or self.dataset, 'm5-fixture', 'sim:m5-fixture',
                               enabled=enabled, monotonic_ns=lambda: self.wall)

    def clock(self, stamp=100, provider=None):
        p = provider or self.provider
        p.set_clock_source(True)
        p.observe_clock(stamp)

    def query(self, provider=None, **changes):
        p = provider or self.provider
        req = dict(request(), expected_provider_instance_id=p.provider_instance_id)
        req.update(changes)
        return p.query(req)

    def install(self, dataset=None):
        self.clock()
        return self.provider.install(dataset or self.dataset)

    def test_explicit_domain_enable_and_clock_are_required(self):
        self.assertEqual(self.provider.status()['state'], 'waiting_clock')
        self.assertEqual(self.query()['reason'], 'clock_unavailable')
        self.assertFalse(self.provider.observe_clock(100))
        disabled = self.make(enabled=False)
        self.clock(provider=disabled)
        self.assertEqual(disabled.status()['state'], 'disabled')
        self.assertEqual(self.query(provider=disabled)['reason'], 'terrain_disabled')
        with self.assertRaises(ValueError): TerrainProvider(self.dataset, 'other', 'sim:other')

    def test_frozen_live_boundary_expectations_and_startup_once(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/m5_provider_expectations.json').read_text())['cases']
        for case in cases:
            self.clock(case['clock'])
            self.provider.startup_install()
            row = self.query(query_timestamp=case['query'], pin_version=False,
                             expected_terrain_revision=0, expected_provider_instance_id='')
            self.assertEqual((row['status'], row['reason']), (case['status'], case['reason']))
            self.assertEqual(row['height'], case.get('height'))
            self.assertEqual(deserialize('TerrainQueryResult', serialize('TerrainQueryResult', row)), row)
        self.assertEqual(self.provider.status()['last_attempt_id'], 1)

    def test_samples_no_data_outside_and_outward_quality_match_saved_table(self):
        self.install()
        for sample in expected()['samples']:
            value = self.query(point_xy=sample['point_xy'])
            self.assertEqual(value['height'], sample['height'])
            self.assertEqual(value['source_index'], sample['source_index'])
            if sample['map_interval'] is not None:
                self.assertEqual(value['height_quality']['value'], sample['map_interval'])
        outside = self.query(point_xy=[115., 179.])
        self.assertEqual((outside['status'], outside['reason'], outside['source_index']), ('unknown', 'outside_coverage', None))

    def test_zero_negative_height_and_missing_contributions_remain_distinct(self):
        for height in (-3., -4.):
            dataset = copy.deepcopy(self.dataset)
            dataset['grid']['heights'][0] = height
            dataset['grid']['height_quality'][0] = dict(status='unavailable', kind='', value=None, unit='', source='missing')
            p = self.make(dataset)
            self.clock(provider=p)
            p.install(dataset)
            row = self.query(provider=p)
            self.assertEqual((row['status'], row['height'], row['height_quality']['status']), ('valid', height + 3., 'unavailable'))

    def test_request_domain_and_pin_mismatches_clear_payload(self):
        self.install()
        for key, value, reason in (('run_id', 'other', 'request_domain_mismatch'),
                ('clock_id', 'sim:other', 'request_domain_mismatch'), ('terrain_id', 'other', 'request_domain_mismatch'),
                ('frame_id', 'odom', 'request_domain_mismatch'),
                ('expected_provider_instance_id', 'old', 'provider_instance_mismatch'),
                ('expected_terrain_revision', 2, 'revision_mismatch')):
            row = self.query(**{key: value})
            self.assertEqual((row['reason'], row['height'], row['context']), (reason, None, None))
            if reason == 'request_domain_mismatch': self.assertEqual(row['terrain_revision'], 0)
        with self.assertRaises(ValueError): self.query(point_xy=[111.1, 179.])
        with self.assertRaises(ValueError): self.query(query_timestamp=100.)

    def test_query_never_advances_clock_or_reactivates_history(self):
        self.clock(110)
        self.provider.install(self.dataset)
        self.assertEqual(self.query(query_timestamp=100)['reason'], 'query_before_terrain_activation')
        self.assertEqual(self.query(query_timestamp=111)['reason'], 'query_ahead_of_clock')
        self.assertEqual(self.provider.status()['evaluation_timestamp'], 110)
        self.clock(200)
        value = self.query(query_timestamp=110)
        self.assertEqual((value['status'], value['height'], value['context']['installed_timestamp']), ('stale', 13., 110))
        self.clock(300)
        self.assertEqual(self.query(query_timestamp=110)['reason'], 'registration_unavailable')

    def test_transport_timeout_pause_and_source_recovery_do_not_refresh_evidence(self):
        self.install()
        self.wall = 1_000_000_000
        self.assertEqual(self.query()['reason'], 'clock_transport_unavailable')
        self.clock(100)
        row = self.query()
        self.assertEqual((row['status'], row['context']['installed_timestamp'], row['context']['acquisition_ns']), ('valid', 100, 10))
        self.provider.set_clock_source(False, 'clock_source_mismatch')
        self.assertEqual(self.query()['reason'], 'clock_source_mismatch')
        self.provider.set_clock_source(True)
        self.assertEqual(self.query()['reason'], 'clock_transport_unavailable')
        self.clock(101)
        self.assertEqual(self.query()['status'], 'valid')

    def test_reset_locks_until_new_instance_and_new_run(self):
        self.install()
        self.clock(99)
        self.clock(120)
        self.assertEqual(self.query()['reason'], 'clock_reset_new_run_required')
        self.assertEqual(self.provider.status()['state'], 'locked')
        dataset = copy.deepcopy(self.dataset)
        dataset['registration'].update(run_id='new', clock_id='sim:new')
        dataset['eligibility'].update(run_id='new', clock_id='sim:new')
        p = TerrainProvider(dataset, 'new', 'sim:new', enabled=True, monotonic_ns=lambda: self.wall)
        p.set_clock_source(True)
        p.observe_clock(100)
        p.install(dataset)
        self.assertNotEqual(p.provider_instance_id, self.provider.provider_instance_id)
        self.assertEqual(p.status()['state'], 'current')

    def test_same_run_restart_uses_new_instance_and_rejects_old_pin(self):
        self.install()
        new = self.make()
        self.clock(provider=new)
        new.install(self.dataset)
        self.assertEqual(new.status()['terrain_revision'], 1)
        self.assertEqual(new.query(dict(request(), expected_provider_instance_id=self.provider.provider_instance_id))['reason'],
                         'provider_instance_mismatch')

    def test_failed_new_version_preserves_old_revision_and_exposes_last_attempt(self):
        self.install()
        bad = copy.deepcopy(self.dataset)
        bad['grid']['observed_mask'] = []
        receipt = self.provider.install(bad)
        self.assertEqual((receipt['outcome'], receipt['terrain_revision']), ('rejected', 1))
        state = self.provider.status()
        self.assertEqual((state['state'], state['last_attempt_id'], state['last_install_outcome']), ('current', 2, 'rejected'))
        self.assertEqual(self.query()['height'], 13.)
        self.clock(200)
        self.assertEqual(self.provider.status()['state'], 'expired')
        self.assertEqual(self.provider.install(self.dataset)['outcome'], 'idempotent')
        self.assertEqual(self.provider.status()['context']['installed_timestamp'], 100)

    def test_duplicate_conflict_replacement_and_retired_versions(self):
        self.install()
        self.assertEqual(self.provider.install(self.dataset)['outcome'], 'idempotent')
        conflict = copy.deepcopy(self.dataset)
        conflict['grid']['heights'][0] = 10.1
        self.assertEqual(self.provider.install(conflict)['outcome'], 'rejected')
        new = copy.deepcopy(self.dataset)
        new['identity']['dataset_version'] = 'v2'
        new['grid']['heights'][0] = 10.1
        self.assertEqual(self.provider.install(new)['terrain_revision'], 2)
        self.assertEqual(self.query()['reason'], 'revision_mismatch')
        self.assertEqual(self.query(expected_terrain_revision=2)['height'], 13.1)
        self.assertEqual(self.provider.install(self.dataset)['outcome'], 'rejected')

    def test_metadata_preparation_and_private_precommit_failure_allow_same_identity_retry(self):
        self.install()
        new = copy.deepcopy(self.dataset)
        new['identity']['dataset_version'] = 'retry-v2'
        with patch('ufm_mapping.terrain_provider.dataset_context', side_effect=ValueError('prepare failure')):
            self.assertEqual(self.provider.install(new)['outcome'], 'rejected')
        with patch.object(self.provider._layer, '_prepare_samples', side_effect=ValueError('sample failure')):
            self.assertEqual(self.provider.install(new)['outcome'], 'rejected')
        self.assertEqual(self.query()['height'], 13.)
        self.assertEqual(self.provider.install(new)['terrain_revision'], 2)

    def test_geometry_change_and_capacity_exhaustion_lock_instead_of_evicting(self):
        self.install()
        changed = copy.deepcopy(self.dataset)
        changed['registration']['registration_id'] = 'new-registration'
        self.assertEqual(self.provider.install(changed)['reason'], 'registration_changed_new_run_required')
        self.assertEqual(self.provider.status()['state'], 'locked')
        p = self.make()
        self.clock(provider=p)
        for index in range(64):
            row = copy.deepcopy(self.dataset)
            row['identity']['dataset_version'] = 'v%d' % index
            self.assertEqual(p.install(row)['outcome'], 'installed')
        row['identity']['dataset_version'] = 'v64'
        self.assertEqual(p.install(row)['reason'], 'version_capacity_new_run_required')
        self.assertEqual(p.status()['terrain_revision'], 64)
        self.assertEqual(self.query(provider=p)['height'], None)

    def test_one_query_slot_and_serialized_clock_install_status(self):
        self.install()
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()
        original = self.provider._layer.query
        rows = []
        def blocked(req):
            entered.set()
            if not release.wait(3): raise RuntimeError('test release deadline')
            return original(req)
        with patch.object(self.provider._layer, 'query', side_effect=blocked):
            thread = threading.Thread(target=lambda: rows.append(self.query()))
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                busy = self.query()
                self.assertEqual((busy['reason'], busy['terrain_revision'], busy['evaluation_timestamp']), ('terrain_busy', 0, None))
                clock = threading.Thread(target=lambda: (self.clock(200), completed.set()))
                clock.start()
                self.assertFalse(completed.wait(.05))
            finally:
                release.set()
                thread.join(3)
                if 'clock' in locals(): clock.join(3)
        self.assertEqual((rows[0]['status'], rows[0]['evaluation_timestamp']), ('valid', 100))
        self.assertEqual(self.query()['status'], 'stale')

    def test_status_heartbeat_and_returned_copies_do_not_change_committed_evidence(self):
        self.install()
        first, second = self.provider.status(), self.provider.status()
        self.assertEqual(first['status_sequence'] + 1, second['status_sequence'])
        self.assertEqual(first['context'], second['context'])
        first['context']['registration_quality']['value'][0] = -999.
        value = self.query()
        value['context']['dataset_version'] = 'tampered'
        self.assertEqual(self.query()['context']['dataset_version'], self.dataset['identity']['dataset_version'])
        self.provider.disable()
        self.assertEqual(self.query()['reason'], 'terrain_disabled')


if __name__ == '__main__':
    unittest.main()

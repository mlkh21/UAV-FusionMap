"""Execute saved public operations, including failures; expectations never drive terrain."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from m5_fixture import load_spec
from m5_iface_fixture import request
from ufm_mapping.terrain_dataset import from_private_fixture
from ufm_mapping.terrain_recording import RecordedTerrainProvider, replay_recording
from ufm_mapping.terrain_recording_contract import load_recording


class TerrainRecordingTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'recording'
        self.wall=0
        self.dataset=from_private_fixture(load_spec())
        self.session=RecordedTerrainProvider(self.dataset,'m5-fixture','sim:m5-fixture',self.path,
                                             monotonic_ns=lambda:self.wall)

    def query(self,stamp=100):
        req=dict(request(),pin_version=False,expected_provider_instance_id='',expected_terrain_revision=0,query_timestamp=stamp)
        return self.session.query(req)

    def install(self):
        self.session.set_clock_source(True)
        self.session.observe_clock(100)
        return self.session.startup_install()

    def test_create_only_manifest_starts_incomplete_then_exact_replay(self):
        with self.assertRaises(ValueError):load_recording(self.path)
        self.install()
        expected=self.query()
        self.session.status()
        self.assertTrue(self.session.close_recording())
        replay=replay_recording(self.path)
        self.assertEqual(replay['results'],[expected])
        self.assertEqual(replay['mode'],'recorded')
        self.assertNotEqual(replay['playback_session_id'],replay['provider_instance_id'])
        with self.assertRaises(FileExistsError):
            RecordedTerrainProvider(self.dataset,'m5-fixture','sim:m5-fixture',self.path)

    def test_conflicts_bad_attempts_idempotency_and_new_version_execute(self):
        self.install()
        self.session.install(self.dataset)
        bad=copy.deepcopy(self.dataset);bad['grid']['observed_mask']=[]
        self.assertEqual(self.session.install(bad)['outcome'],'rejected')
        new=copy.deepcopy(self.dataset);new['identity']['dataset_version']='v2'
        self.session.install(new)
        self.session.status()
        expected=self.query()
        self.session.close_recording()
        self.assertEqual(replay_recording(self.path)['results'],[expected])
        _,datasets,events=load_recording(self.path)
        self.assertEqual(len(datasets),2)
        self.assertIsNotNone(next(e for e in events if e.get('outcome')=='rejected')['attempt'])

    def test_recorded_elapsed_time_reconstructs_timeout_expiry_and_reset(self):
        self.install()
        outputs=[self.query()]
        self.wall=1_000_000_000
        outputs.append(self.query())
        self.session.observe_clock(200)
        outputs.append(self.query())
        self.session.observe_clock(99)
        self.session.observe_clock(120)
        outputs.append(self.query())
        self.session.status()
        self.session.disable()
        self.session.close_recording()
        self.assertEqual(replay_recording(self.path)['results'],outputs)
        self.assertEqual([r['status'] for r in outputs],['valid','unavailable','stale','unavailable'])

    def test_expected_result_tampering_fails_execution_even_when_schema_valid(self):
        self.install();self.query();self.session.close_recording()
        path=self.path/'events.jsonl'
        events=[json.loads(line) for line in path.read_text().splitlines()]
        event=next(e for e in events if e['operation']=='query')
        event['result']['height']=13.1
        path.write_text(''.join(json.dumps(e)+'\n' for e in events))
        with self.assertRaisesRegex(ValueError,'query_differs'):replay_recording(self.path)

    def test_overflow_marks_incomplete_without_changing_committed_terrain(self):
        self.install()
        for i in range(65):self.session.observe_clock(100)
        self.assertTrue(self.session.recorder.failed)
        self.assertEqual(self.query()['height'],13)
        self.assertFalse(self.session.close_recording())
        with self.assertRaises(ValueError):replay_recording(self.path)

    def test_unrecordable_input_is_not_truncated_or_claimed_complete(self):
        self.install()
        bad=copy.deepcopy(self.dataset);bad['identity']['source_ref']='x'*20000
        self.assertEqual(self.session.install(bad)['outcome'],'rejected')
        self.assertFalse(self.session.close_recording())
        with self.assertRaises(ValueError):replay_recording(self.path)

    def test_write_failure_leaves_recording_incomplete_and_service_usable(self):
        self.install()
        with patch.object(self.session.recorder,'_persist',side_effect=OSError('disk failure')):
            self.assertEqual(self.query()['height'],13)
        self.assertTrue(self.session.recorder.failed)
        self.assertEqual(self.query()['height'],13)
        self.assertFalse(self.session.close_recording())
        with self.assertRaises(ValueError):replay_recording(self.path)

    def test_status_heartbeat_gaps_are_reconstructed_and_disable_is_terminal(self):
        self.install()
        for i in range(5):self.session.status()
        self.session.disable()
        self.session.close_recording()
        replay=replay_recording(self.path)
        self.assertEqual([s['status_sequence'] for s in replay['statuses']],[1,6])
        self.assertEqual(replay['statuses'][-1]['state'],'disabled')

    def test_full_sixteen_center_public_record_and_replay_remain_bounded(self):
        dataset=copy.deepcopy(self.dataset)
        grid=dataset['grid']
        grid.update(rows=4,columns=4,heights=[10.]*16,no_data_mask=[False]*16,
                    height_quality=[copy.deepcopy(grid['height_quality'][0]) for _ in range(16)])
        path=Path(self.tmp.name)/'sixteen'
        session=RecordedTerrainProvider(dataset,'m5-fixture','sim:m5-fixture',path,monotonic_ns=lambda:self.wall)
        session.set_clock_source(True);session.observe_clock(100);session.startup_install()
        results=[]
        for r in range(4):
            for c in range(4):
                req=dict(request(),point_xy=[111.+2*c,179.-2*r],pin_version=False,
                         expected_provider_instance_id='',expected_terrain_revision=0)
                results.append(session.query(req))
        self.assertTrue(session.close_recording())
        self.assertEqual(replay_recording(path)['results'],results)
        self.assertLessEqual(sum(p.stat().st_size for p in path.iterdir()),4*1024*1024)

    def test_unrepresentable_source_and_query_failures_never_claim_complete(self):
        self.install()
        self.session.set_clock_source(False,'clock_source_mismatch')
        self.assertFalse(self.session.close_recording())
        with self.assertRaises(ValueError):replay_recording(self.path)
        path=Path(self.tmp.name)/'invalid-query'
        session=RecordedTerrainProvider(self.dataset,'m5-fixture','sim:m5-fixture',path,monotonic_ns=lambda:self.wall)
        session.set_clock_source(True);session.observe_clock(100);session.startup_install()
        with self.assertRaises(ValueError):
            session.query(dict(request(),pin_version=False,expected_provider_instance_id='',expected_terrain_revision=0,point_xy=[111.1,179.]))
        self.assertFalse(session.close_recording())


if __name__ == '__main__': unittest.main()

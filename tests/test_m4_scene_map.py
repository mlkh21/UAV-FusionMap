"""M4 public behavior and atomic ownership handoff; no ROS Master or research backend."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from m4_fixture import P, Q, R, bound_spec, load_spec, observation, scenarios, step
from m4_oracle import expected_step
from m4_scene_run import run_cases
from ufm_mapping.scene_map import SceneMap
from ufm_mapping.factory import create_map


ROOT = Path(__file__).resolve().parents[1]


class SceneMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Unit tests can build their fixtures; the acceptance CLI separately reads
        # the historical frozen input without importing either builder or oracle.
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.saved = Path(cls.folder.name) / 'fixtures.json'
        cases = []
        for case in scenarios(bound_spec(load_spec(), 'unit-scene')):
            case['steps'] = [dict(declaration=declaration,
                observation=observation(case['spec'], declaration),
                expected=expected_step(case['spec'], case['versions'], declaration))
                for declaration in case['steps']]
            cases.append(case)
        cls.saved.write_text(json.dumps(cases))

    def setUp(self):
        self.spec = bound_spec(load_spec(), 'scene-test')
        self.scene = SceneMap(self.spec, 'scene-test', 'sim:scene-test')

    def send(self, sequence, *, body=0., kind='occupied', points=(P,), bounds='default', stamp=None):
        declaration = step(sequence, (sequence+1)*10_000_000 if stamp is None else stamp,
                           [], [], 0, None, body=body, kind=kind, points=points, bounds=bounds)
        return self.scene.update(observation(self.spec, declaration))

    def query(self, timestamp, point=(40.25,.25,.25), **changes):
        request = dict(map_id='m4-scene-fixture', frame_id='map', run_id='scene-test',
            clock_id='sim:scene-test', query_timestamp=timestamp, max_age_ns=100_000_000,
            point=list(point))
        request.update(changes)
        return self.scene.query(**request)

    def test_explicit_domain_and_configuration_are_required(self):
        for run,clock in (('foreign','sim:scene-test'),('scene-test','other'),(None,None)):
            with self.assertRaises(ValueError):
                SceneMap(self.spec,run,clock)
        bad=copy.deepcopy(self.spec)
        bad['registration']['status']='unavailable'
        with self.assertRaises(ValueError):
            SceneMap(bad,'scene-test','sim:scene-test')

    def test_nonzero_registered_scene_index_is_independent_of_local_index(self):
        self.send(0)
        snapshot=self.scene.snapshot()
        self.assertEqual(snapshot['header']['frame_id'],'map')
        self.assertEqual(snapshot['cells'][0]['index'],[80,32,8])
        self.assertEqual(self.query(10_000_000)['index'],[80,32,8])
        self.assertEqual(self.query(10_000_000,frame_id='odom')['status'],'unavailable')
        self.assertEqual(self.query(10_000_000,point=P)['status'],'unknown')

    def test_overlap_empty_move_does_not_accumulate_or_refresh(self):
        self.send(0)
        first=self.query(10_000_000)
        self.send(1,body=.5,kind='empty')
        second=self.query(20_000_000)
        for key in ('probability','uncertainty','last_observed_timestamp'):
            self.assertEqual(second[key],first[key])
        self.assertEqual(len(self.scene._state.sealed),0)
        self.assertEqual(self.query(10_000_000)['status'],'unavailable')

    def test_sealed_history_is_queryable_and_fifo_eviction_never_creates_free(self):
        self.spec['max_sealed_submaps']=1
        self.scene=SceneMap(self.spec,'scene-test','sim:scene-test')
        self.send(0)
        self.send(1,body=40.,points=(Q,))
        self.assertEqual(self.query(20_000_000)['status'],'occupied')
        self.send(2,body=80.,points=(R,))
        result=self.query(30_000_000)
        self.assertEqual(result['status'],'unknown')
        self.assertFalse(result['observed'])
        self.assertIsNone(result['probability'])
        self.assertEqual(self.query(30_000_000,point=(80.25,.25,.25))['status'],'occupied')

    def test_return_new_free_starts_from_local_prior_and_removes_old_owner(self):
        self.send(0)
        self.send(1,body=40.,kind='empty')
        self.send(2,kind='free')
        result=self.query(30_000_000)
        self.assertEqual(result['status'],'free')
        self.assertAlmostEqual(result['probability'],.25)
        self.assertEqual(len(self.scene.snapshot()['cells']),1)
        self.assertEqual(len(self.scene._state.sealed),0)

    def test_missing_quality_takeover_cannot_borrow_sealed_range(self):
        self.send(0)
        self.send(1,body=40.,kind='empty')
        self.send(2,bounds=None)
        self.send(3)
        result=self.query(40_000_000)
        self.assertAlmostEqual(result['probability'],.9)
        self.assertEqual(result['uncertainty']['status'],'unavailable')
        self.assertIsNone(result['uncertainty']['value'])
        self.send(4,stamp=150_000_000)
        self.assertEqual(self.query(150_000_000)['uncertainty']['status'],'available')

    def test_stale_history_keeps_quality_and_original_time_without_query_mutation(self):
        self.send(0)
        self.send(1,body=40.,kind='empty')
        before=self.scene.snapshot()
        self.assertEqual(self.query(110_000_000)['status'],'occupied')
        result=self.query(110_000_001)
        self.assertEqual(result['status'],'stale')
        self.assertEqual(result['last_observed_timestamp'],10_000_000)
        self.assertEqual(result['uncertainty'],before['cells'][0]['uncertainty'])
        self.assertEqual(before,self.scene.snapshot())

    def test_snapshot_query_and_constructor_config_are_copy_isolated(self):
        self.spec['registration']['T_map_odom'][3]=64.
        self.send(0)
        snapshot=self.scene.snapshot()
        snapshot['cells'][0]['uncertainty']['value'][0]=0.
        result=self.query(10_000_000)
        result['uncertainty']['value'][0]=0.
        self.assertAlmostEqual(self.query(10_000_000)['uncertainty']['value'][0],.7)
        self.assertEqual(self.scene.snapshot()['cells'][0]['index'],[80,32,8])

    def test_scene_construction_failure_does_not_commit_local_watermark_or_scene(self):
        self.send(0)
        before=self.scene.snapshot()
        with patch.object(self.scene,'_validate_scene',side_effect=ValueError('injected after local update')):
            with self.assertRaisesRegex(ValueError,'injected'):
                self.send(1,body=40.,points=(Q,))
        self.assertEqual(self.scene.snapshot(),before)
        # Same identity/time succeeds once the staging failure is removed.
        self.assertTrue(self.send(1,body=40.,points=(Q,)))
        self.assertEqual(self.scene.snapshot()['revision'],2)
        self.assertEqual(self.query(20_000_000)['status'],'occupied')

    def test_same_time_conflicting_sealed_estimate_is_atomic(self):
        self.send(0)
        self.send(1,body=40.,kind='empty')
        before=self.scene.snapshot()
        original=self.scene._scene_cells
        def conflicting(local):
            cells=original(local)
            cell=cells[(80,32,8)]
            cell['last_observed_timestamp']=10_000_000
            cell['probability']=.7
            return cells
        with patch.object(self.scene,'_scene_cells',side_effect=conflicting):
            with self.assertRaisesRegex(ValueError,'conflicting'):
                self.send(2)
        self.assertEqual(self.scene.snapshot(),before)
        self.assertTrue(self.send(2))

    def test_future_outside_window_rejection_allows_earlier_valid_recovery(self):
        self.send(0)
        before=self.scene.snapshot()
        with self.assertRaisesRegex(ValueError,'outside Scene'):
            self.send(8,body=200.,kind='empty',stamp=900_000_000)
        self.assertEqual(before,self.scene.snapshot())
        self.send(1,kind='free')
        self.assertEqual(self.query(20_000_000)['status'],'unknown')

    def test_new_run_does_not_inherit_and_query_identity_time_are_fail_closed(self):
        self.send(0)
        for change in (dict(run_id='foreign'),dict(clock_id='foreign'),dict(map_id='other'),
                       dict(frame_id='odom'),dict(query_timestamp=1_000_000_000)):
            result=self.query(10_000_000,**change)
            self.assertEqual(result['status'],'unavailable')
            self.assertIsNone(result['probability'])
        fresh=bound_spec(self.spec,'fresh')
        self.assertEqual(SceneMap(fresh,'fresh','sim:fresh').snapshot()['cells'],[])
        for change in (dict(query_timestamp=True),dict(max_age_ns=-1),dict(point=[True,0.,0.]),
                       dict(point=[float('nan'),0.,0.])):
            with self.assertRaises(ValueError):
                self.query(10_000_000,**change)

    def test_default_factory_remains_isolated_from_scene(self):
        with self.assertRaises(ValueError):
            create_map('m4_fixture')
        subprocess.run([sys.executable,'-B','-c',
            "from ufm_mapping.factory import create_map; import sys; create_map(); "
            "assert 'ufm_mapping.scene_map' not in sys.modules"],check=True,timeout=10)

    def test_saved_independent_answers_match_and_altered_quality_is_detected(self):
        cases=json.loads(self.saved.read_text())
        self.assertEqual(len(run_cases(cases)),8)
        cases[0]['steps'][0]['expected']['snapshot']['cells'][0]['uncertainty']['source']='altered'
        with self.assertRaisesRegex(ValueError,'snapshot differs'):
            run_cases(cases)

    def test_saved_replay_cli_does_not_import_oracle_and_rejects_altered_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tests/m4_scene_run.py'),
                '--input',str(self.saved),'--output-root',directory],text=True,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            receipt=json.loads(result.stdout)
            report=json.loads((Path(receipt['run'])/'report.json').read_text())
            self.assertEqual((report['observation_count'],report['query_count']),(41,52))
            cases=json.loads(self.saved.read_text())
            cases[0]['steps'][0]['expected']['ownership']['active']=[]
            changed=Path(directory)/'changed.json'
            changed.write_text(json.dumps(cases))
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tests/m4_scene_run.py'),
                '--input',str(changed),'--output-root',directory],text=True,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,1)
            self.assertIn('ownership/FIFO differs',result.stdout)

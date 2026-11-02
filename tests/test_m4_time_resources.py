"""M4-SW-03 time, rollback and logical resource contracts, independent of hardware."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m4_fixture import P,Q,R,load_spec
from m4_resource_audit import assert_retained,retained_counts
from m4_scene_run import run_cases
from m4_time_run import resources
from m4_time_scenarios import frozen_cases,periodic_fixture
from m4_time_validation import atomic_probes,census_probes,domain_probes,fingerprint,make_scene,row


class SceneTimeResourceTest(unittest.TestCase):
    def setUp(self):
        self.spec=load_spec()
        self.scene,self.config=make_scene(self.spec)

    def query(self,stamp,point=(40.25,.25,.25),**changes):
        request=dict(map_id='m4-scene-fixture',frame_id='map',run_id=self.config['registration']['run_id'],
            clock_id=self.config['registration']['clock_id'],query_timestamp=stamp,
            max_age_ns=100_000_000,point=list(point))
        request.update(changes)
        return self.scene.query(**request)

    def test_explicit_time_tables_match_candidates_and_all_five_states(self):
        results=run_cases(frozen_cases(self.spec))
        self.assertEqual([len(c['steps']) for c in results],[7,7,6])
        statuses={q['result']['status'] for c in results for s in c['steps'] for q in s['queries']}
        self.assertEqual(statuses,{'occupied','free','unknown','stale','unavailable'})

    def test_periodic_120_step_schedule_matches_closed_form_ownership(self):
        case=periodic_fixture(self.spec)
        result=run_cases([case])[0]
        self.assertEqual(len(result['steps']),120)
        counts=resources(case)
        self.assertEqual(counts['retained_maxima']['sealed_submaps'],1)
        self.assertEqual(counts['retained_maxima']['ownership_index'],4)
        self.assertEqual(counts['retained_maxima']['identity_records'],3)
        self.assertEqual(counts['retained_maxima']['identity_voxels'],5)

    def test_all_four_failure_points_rollback_private_state_and_retry_once(self):
        results=atomic_probes(self.spec)
        self.assertEqual(len(results),4)
        self.assertTrue(all(r['rollback_equal'] and r['same_identity_retry'] and
                            not r['duplicate_fused'] for r in results))

    def test_new_run_clock_and_expired_registration_do_not_mix_old_state(self):
        result=domain_probes(self.spec)
        self.assertEqual(result['rejected'],['run_id','clock_id','registration_expired'])
        self.assertTrue(result['old_state_equal'])
        self.assertAlmostEqual(result['new_run_probability'],.25)

    def test_payload_census_includes_committed_staged_and_returned_copies(self):
        report=census_probes(self.spec)
        self.assertEqual(report['peaks']['scene_states'],2)
        self.assertEqual(report['peaks']['local_maps'],2)
        self.assertGreater(report['peaks']['cell_payloads'],6) # committed max: (K+2)*N
        self.assertGreater(report['samples'],0)
        self.assertTrue(all(report['peaks'][k]<=report['bounds'][k] for k in report['peaks']))
        self.assertEqual(max(r['snapshot_cells'] for r in report['output_counts']),4)

    def test_ownership_index_alias_and_nominal_range_ledger_corruption_are_detected(self):
        self.scene.update(row(self.config,0))
        original=self.scene._state.cells
        self.scene._state.cells=copy.deepcopy(original)
        with self.assertRaisesRegex(AssertionError,'index copied'):
            retained_counts(self.scene)
        self.scene._state.cells=original
        self.scene._state.local._log_odds.clear()
        with self.assertRaisesRegex(AssertionError,'ledger differs'):
            retained_counts(self.scene)

    def test_identity_memory_is_bounded_by_frame_voxels_not_only_active_cell_count(self):
        points=(P,(9.25,.25,.25),(10.25,.25,.25))
        for seq in range(5):
            self.scene.update(row(self.config,seq,points=points))
            counts=assert_retained(self.scene,3)
        self.assertEqual(counts['local_cells'],2)
        self.assertEqual(counts['identity_records'],3)
        self.assertEqual(counts['identity_voxels'],9)
        with self.assertRaises(AssertionError):
            assert_retained(self.scene,2)

    def test_dedup_history_eviction_does_not_allow_old_timestamp_reentry(self):
        first=row(self.config,0)
        self.scene.update(first)
        for seq in range(1,5):self.scene.update(row(self.config,seq))
        self.assertNotIn(first['header']['sample_id'],self.scene._state.local._seen)
        before=fingerprint(self.scene)
        with self.assertRaisesRegex(ValueError,'timestamp must increase'):
            self.scene.update(first)
        self.assertEqual(before,fingerprint(self.scene))

    def test_multiple_cell_ages_use_original_times_and_request_max_age(self):
        self.scene.update(row(self.config,0,points=(P,(9.25,.25,.25))))
        self.scene.update(row(self.config,1,points=(P,)))
        before=fingerprint(self.scene)
        self.assertEqual(self.query(110_000_001)['status'],'occupied')
        self.assertEqual(self.query(110_000_001,point=(41.25,.25,.25))['status'],'stale')
        self.assertEqual(self.query(110_000_001,max_age_ns=1)['status'],'stale')
        self.assertEqual(self.query(120_000_000,max_age_ns=999_000_000)['status'],'occupied')
        self.assertEqual(self.query(120_000_001,max_age_ns=999_000_000)['status'],'stale')
        self.assertEqual(before,fingerprint(self.scene))

    def test_planar_turn_and_overlap_move_preserve_world_index_and_quality(self):
        self.scene.update(row(self.config,0))
        value=row(self.config,1,body=.5)
        angle=math.pi/2
        value['context']['T_mapping_body']=[math.cos(angle),-math.sin(angle),0.,.5,
            math.sin(angle),math.cos(angle),0.,.5,0.,0.,1.,0.,0.,0.,0.,1.]
        self.scene.update(value)
        result=self.query(20_000_000)
        self.assertEqual(result['index'],[80,32,8])
        self.assertAlmostEqual(result['probability'],.9)
        self.assertAlmostEqual(result['uncertainty']['value'][0],49/58)
        self.assertEqual(len(self.scene._state.sealed),0)

    def test_no_return_or_unavailable_never_moves_or_refreshes_stale_scene(self):
        self.scene.update(row(self.config,0))
        for seq,kind in ((1,'no_return'),(2,'unavailable'),(3,'degraded')):
            value=row(self.config,seq,kind=kind)
            value['context']['T_mapping_body_status']='unavailable' if kind!='no_return' else 'available'
            self.scene.update(value)
        snapshot=self.scene.snapshot()
        self.assertEqual(snapshot['header']['timestamp'],10_000_000)
        self.assertEqual(snapshot['cells'][0]['last_observed_timestamp'],10_000_000)
        self.assertEqual(self.query(110_000_001)['status'],'stale')

    def test_empty_move_with_newer_active_capacity_eviction_cannot_revive_old_owner(self):
        cases=frozen_cases(self.spec)
        case=next(c for c in cases if c['name']=='no_stale_owner_resurrection')
        result=run_cases([case])[0]
        # Once P's first owner is FIFO-evicted, empty return leaves P unknown.
        self.assertEqual(result['steps'][3]['queries'][0]['result']['status'],'unknown')
        self.assertEqual(result['steps'][4]['queries'][0]['result']['status'],'free')

    def test_saved_replay_reuses_answers_and_detects_changed_structure_time(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.json'
            frozen=dict(spec=self.spec,cases=frozen_cases(self.spec))
            source.write_text(json.dumps(frozen))
            command=[sys.executable,'-B',str(Path(__file__).resolve().parent/'m4_time_run.py'),
                     '--input',str(source),'--output-root',directory]
            result=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            receipt=json.loads(result.stdout)
            report=json.loads((Path(receipt['run'])/'report.json').read_text())
            self.assertFalse(report['saved_expectations_recomputed'])
            frozen['cases'][0]['steps'][0]['expected']['structure_timestamp']=11_000_000
            source.write_text(json.dumps(frozen))
            result=subprocess.run(command,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,1)
            self.assertIn('structure time differs',result.stdout)

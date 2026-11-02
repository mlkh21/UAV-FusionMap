import copy
import unittest

import test_sensor_scene as scene_fixture
from ufm_sensors.scene_stream import SceneStream
from ufm_perception.placeholder import placeholder_infer
from ufm_mapping.factory import create_map

MS=1000000


class MotionDeliveryTests(unittest.TestCase):
    def setUp(self):
        helper=scene_fixture.SensorSceneTest()
        helper.setUp()
        self.profile,self.inputs=helper.profile,helper.inputs

    def test_exact_motion_policy_waits_for_same_tick_without_changing_default(self):
        for exact in (False,True):
            with self.subTest(exact=exact):
                stream=SceneStream('r',self.profile,require_exact_pose=exact)
                state,radar,ir=self.inputs(100*MS)
                prior=copy.deepcopy(state)
                prior['header']['timestamp']=96*MS
                prior['header']['sample_id']+=':prior'
                stream.set_clock(100*MS)
                for kind,value in (('state',prior),('radar',radar),('infrared',ir)):stream.add(kind,value)
                bundles=stream.ready()
                self.assertEqual(len(bundles),0 if exact else 1)
                if exact:
                    stream.add('state',state)
                    bundle,=stream.ready()
                    self.assertEqual(bundle['pose_age_ns'],0)
                else:self.assertEqual(bundles[0]['pose_age_ns'],4*MS)

    def test_exact_motion_missing_pose_times_out_without_old_pose_fallback(self):
        stream=SceneStream('r',self.profile,require_exact_pose=True)
        stream.set_clock(100*MS)
        state,radar,ir=self.inputs(100*MS)
        state['header']['timestamp']-=1
        for kind,value in (('state',state),('radar',radar),('infrared',ir)):stream.add(kind,value)
        self.assertEqual(stream.ready(),[])
        stream.set_clock(140*MS+1)
        self.assertEqual(stream.ready(),[])
        self.assertEqual(stream.rejected['pair_timeout'],1)

    def test_ir_five_ms_boundary_and_one_ns_rejection(self):
        for delta,wanted in ((5*MS,1),(5*MS+1,0)):
            stream=SceneStream('r',self.profile)
            stream.set_clock(100*MS)
            state,radar,ir=self.inputs(100*MS)
            ir['header']['timestamp']+=delta
            for kind,value in (('state',state),('radar',radar),('infrared',ir)):stream.add(kind,value)
            self.assertEqual(len(stream.ready()),wanted)

    def test_pose_ten_ms_boundary_and_one_ns_rejection(self):
        for age,wanted in ((10*MS,1),(10*MS+1,0)):
            stream=SceneStream('r',self.profile)
            stream.set_clock(100*MS)
            state,radar,ir=self.inputs(100*MS)
            state['header']['timestamp']-=age
            for kind,value in (('state',state),('radar',radar),('infrared',ir)):stream.add(kind,value)
            self.assertEqual(len(stream.ready()),wanted)

    def test_pairing_forty_ms_boundary_and_one_ns_rejection(self):
        for age,wanted in ((40*MS,1),(40*MS+1,0)):
            stream=SceneStream('r',self.profile)
            stream.set_clock(100*MS+age)
            for kind,value in zip(('state','radar','infrared'),self.inputs(100*MS)):stream.add(kind,value)
            self.assertEqual(len(stream.ready()),wanted)

    def test_no_echo_keeps_old_evidence_time_and_new_run_starts_empty(self):
        stream=SceneStream('r',self.profile,require_exact_pose=True)
        local=create_map('latest',dict(self.profile['map'],free_threshold=.3,occupied_threshold=.7))
        for stamp,empty in ((100*MS,False),(200*MS,True)):
            stream.set_clock(stamp)
            state,radar,ir=self.inputs(stamp)
            if empty:radar['points']=[]
            for kind,value in (('state',state),('radar',radar),('infrared',ir)):stream.add(kind,value)
            bundle,=stream.ready()
            observation=placeholder_infer(bundle,**{k:self.profile['map'][k] for k in ('resolution','shape','origin')})
            if empty:self.assertEqual(observation['voxels'],[])
            local.update(observation)
        snapshot=local.snapshot()
        self.assertTrue(snapshot['cells'])
        self.assertTrue(all(c['last_observed_timestamp']==100*MS and c['probability']==.9 for c in snapshot['cells']))
        fresh=create_map('latest',dict(self.profile['map'],free_threshold=.3,occupied_threshold=.7))
        self.assertEqual(fresh.snapshot()['cells'],[])
        self.assertEqual(fresh.snapshot()['revision'],0)


if __name__=='__main__':unittest.main()

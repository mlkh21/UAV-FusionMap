import copy
import collections
import json
import math
from pathlib import Path
import unittest
import tempfile
import threading

import numpy as np
from scipy.spatial.transform import Rotation

from sim_motion_fixture import expected, frame, response, source_sample
from ufm_simulation.scene_motion import SceneRegistration, SceneTransactions
from ufm_sensors.state_adapter import adapt_scene_ground_truth
from ufm_sensors.scene_stream import SceneStream
import yaml

ROOT = Path(__file__).resolve().parents[1]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'configs/sim_scene_motion_fixture.json').read_text())

    def registration(self, latitude=0., longitude=0.):
        return SceneRegistration(source_sample(0), latitude, longitude, self.profile)

    def test_nonzero_ecef_matches_frozen_answer(self):
        case = expected()['coordinate_cases'][0]
        initial = source_sample(0)
        initial['ecef_ft'] = case['input']['ecef_origin_ft']
        reg = SceneRegistration(initial, 0., 0., self.profile)
        sample = source_sample(1)
        sample['ecef_ft'] = case['input']['ecef_ft']
        original = copy.deepcopy(sample)
        actual = reg.convert(sample, 'motion-fixture')
        # Frozen oracle used anchor [10,20,8]; fixed runtime profile uses [0,0,8].
        oracle = np.array(case['expected']['scene_position_m']) - [10, 20, 0]
        np.testing.assert_allclose(actual['state']['position'], oracle, atol=1e-12)
        self.assertEqual(sample, original)

    def test_geodetic_not_geocentric(self):
        reg = self.registration(math.pi/4)
        sample = source_sample(1)
        sample['ecef_ft'] = [v+d for v, d in zip(sample['ecef_ft'], [1, 0, 1])]
        delta = np.array(reg.convert(sample, 'motion-fixture')['state']['position']) - [0, 0, 8]
        np.testing.assert_allclose(delta, expected()['coordinate_cases'][-1]['expected']['scene_delta_m'], atol=1e-14)
        wrong = self.registration(math.radians(44.8)).convert(sample, 'motion-fixture')
        self.assertGreater(abs(wrong['state']['position'][1]), 1e-4)

    def test_rotation_mount_and_body_units(self):
        reg = self.registration()
        sample = source_sample(25)
        rotation = Rotation.from_euler('z', 90, degrees=True).as_matrix()
        sample['R_ecef_frd'] = (reg.Q.T @ rotation @ np.diag([1., -1., -1.])).reshape(-1).tolist()
        sample['uvw_ftps'] = [4/.3048, 5/.3048, 6/.3048]
        sample['pqr_radps'] = [1., 2., 3.]
        f = reg.convert(sample, 'motion-fixture')
        np.testing.assert_allclose(f['state']['orientation_xyzw'],
            expected()['coordinate_cases'][2]['expected']['quaternion_xyzw'], atol=1e-15)
        np.testing.assert_allclose(f['state']['linear_velocity'], [4., -5., -6.], atol=1e-14)
        self.assertEqual(f['angular_velocity_flu'], [1., -2., -3.])
        mount = Rotation.from_quat(f['state']['orientation_xyzw']).apply([.8, 0, 0])
        np.testing.assert_allclose(mount, [0., .8, 0.], atol=1e-15)

    def test_bad_time_distance_ground_and_registration(self):
        with self.assertRaises(ValueError):
            SceneRegistration(source_sample(1), 0., 0., self.profile)
        with self.assertRaises(ValueError):
            self.registration(float('nan'))
        for changes in (dict(sim_time_s=.004000002), dict(ecef_ft=[20_000_000., 1000., 0.]),
                        dict(ecef_ft=[19_999_970., 0., 0.]), dict(pqr_radps=[0., 0., float('inf')])):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.registration().convert(dict(source_sample(1), **changes), 'motion-fixture')

    def test_sequence_duplicate_ownership_and_one_pending(self):
        t = SceneTransactions('motion-fixture')
        with self.assertRaisesRegex(ValueError, 'sequence'):
            t.begin(frame(1))
        self.assertIsNone(t.begin(frame(0)))
        with self.assertRaisesRegex(ValueError, 'pending'):
            t.begin(frame(0))
        t.finish(response(0))
        answer = t.begin(frame(0))
        self.assertEqual(answer, response(0))
        answer['applied_frame']['state']['position'][0] = 999.
        self.assertEqual(t.begin(frame(0)), response(0))
        t.begin(frame(1)); t.finish(response(1))
        with self.assertRaisesRegex(ValueError, 'sequence'):
            t.begin(frame(0))
        self.assertEqual(t.completed, frame(1))

    def test_conflict_locks_and_new_run_is_empty(self):
        t = SceneTransactions('motion-fixture')
        t.begin(frame(0)); t.finish(response(0))
        with self.assertRaisesRegex(ValueError, 'conflict'):
            t.begin(frame(0, height=9.))
        with self.assertRaisesRegex(ValueError, 'locked'):
            t.begin(frame(1))
        fresh = SceneTransactions('another-run')
        self.assertIsNone(fresh.completed)
        self.assertIsNone(fresh.begin(frame(0, run_id='another-run')))

    def test_failed_ack_and_late_reply_cannot_advance(self):
        t = SceneTransactions('motion-fixture')
        for index in range(25):
            t.begin(frame(index)); t.finish(response(index))
        t.begin(frame(25))
        with self.assertRaisesRegex(ValueError, 'scene_ir_timeout'):
            t.finish(response(25, accepted=False))
        with self.assertRaisesRegex(ValueError, 'no_pending'):
            t.finish(response(25))
        self.assertEqual(t.completed['step_index'], 24)
        self.assertEqual(t.terminal('another_error')['header']['reason'], 'terminal:scene_ir_timeout')

    def test_readback_bad_geometry_locks_before_completion(self):
        t = SceneTransactions('motion-fixture')
        t.begin(frame(0))
        bad = response(0)
        bad['applied_frame']['state']['position'][0] += 1e-6
        with self.assertRaises(ValueError):
            t.finish(bad)
        self.assertIsNone(t.completed)

    def test_identity_change_requires_new_run(self):
        t = SceneTransactions('motion-fixture')
        with self.assertRaisesRegex(ValueError, 'identity_changed'):
            t.begin(frame(0, run_id='another-run'))
        self.assertEqual(t.failed, 'scene_identity_changed')

    def test_truth_terminal_is_not_geometry_and_stream_stays_locked(self):
        t = SceneTransactions('motion-fixture')
        t.begin(frame(0)); t.finish(response(0))
        terminal = t.terminal('scene_ir_timeout')
        self.assertEqual(terminal['orientation_xyzw'], [0., 0., 0., 0.])
        converted = adapt_scene_ground_truth(terminal, 'gazebo_scene_world_enu_identity_v1')
        self.assertEqual(converted['header']['frame_id'], 'odom')
        stream = SceneStream('motion-fixture', yaml.safe_load((ROOT / 'configs/sensor_scene.yaml').read_text()))
        stream.set_clock(100000000)
        stream.add('state', converted)
        stream.add('state', adapt_scene_ground_truth(frame()['state'], 'gazebo_scene_world_enu_identity_v1'))
        self.assertTrue(stream.failed)
        self.assertEqual(list(stream.states), [])
        self.assertEqual(stream.ready(), [])
        converted['state_source'] = 'estimated'
        with self.assertRaises(ValueError):
            stream2 = copy.deepcopy(terminal)
            stream2['state_source'] = 'estimated'
            adapt_scene_ground_truth(stream2, 'gazebo_scene_world_enu_identity_v1')

    def test_malformed_actual_wire_receipt_cannot_be_overwritten(self):
        from check_sim_motion_live import LiveReceipts
        from sensor_msgs.msg import PointCloud2
        with tempfile.TemporaryDirectory() as directory:
            recorder = LiveReceipts.__new__(LiveReceipts)
            recorder.run = Path(directory)
            recorder.lock = threading.RLock()
            recorder.rows = collections.defaultdict(list)
            recorder.errors, recorder.total = [], 0
            message = PointCloud2(data=b'bad')
            message._connection_header = dict(callerid='/gazebo')
            recorder.receive('radar', message)
            self.assertTrue(recorder.errors)
            saved = (Path(directory) / 'radar-000.bin').read_bytes()
            message.data = b'changed'
            recorder.receive('radar', message)
            self.assertEqual((Path(directory) / 'radar-000.bin').read_bytes(), saved)
            self.assertEqual(len(recorder.errors), 1)
            self.assertEqual(list(recorder.rows['radar']), [])


if __name__ == '__main__':
    unittest.main()

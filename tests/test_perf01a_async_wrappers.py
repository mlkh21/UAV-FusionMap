"""Independent async wrapper regressions; no ROS master, threads or disk output."""
from contextlib import ExitStack
import copy
import importlib.util
import itertools
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import weakref


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'ros_ws/src/uav_fusionmap_sensors/scripts'
MS = 1_000_000


def module(name, **values):
    result = types.ModuleType(name)
    result.__dict__.update(values)
    return result


def encode(frame):
    return types.SimpleNamespace(header=types.SimpleNamespace(**frame['header']), payload=frame)


class ClockMessage:
    def __init__(self, stamp):
        self.clock = types.SimpleNamespace(to_nsec=lambda: stamp)


class ManualWall:
    def __init__(self):
        self.ns = 0

    def monotonic(self):
        return self.ns / 1_000_000_000

    def monotonic_ns(self):
        return self.ns

    def thread_time_ns(self):
        return self.ns


class ControlledStop:
    """Allow a finite number of worker iterations without sleeping or stopping callbacks."""
    def __init__(self, iterations=1):
        self.remaining = iterations
        self.stopped = False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, timeout):
        if self.stopped or self.remaining == 0:
            return True
        self.remaining -= 1
        return False


class Publisher:
    def __init__(self, topic):
        self.topic = topic
        self.rows = []

    def get_num_connections(self):
        return 1

    def publish(self, msg):
        # Emulate transport consuming the payload; audit only scalar identities.
        if hasattr(msg, 'payload'):
            self.rows.append(copy.deepcopy(msg.payload['header']))
        else:
            self.rows.append(copy.deepcopy(vars(msg)))


class WrapperHarness:
    def __enter__(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(sys, 'path', [str(ROOT / 'sensors')] + sys.path))
        self.wall = ManualWall()
        self.params = {'~run_id': 'r', '~kind': 'infrared',
                       '/perf01a_async_duration_ns': '2000000000',
                       '/perf01a_async_run_directory': str(ROOT)}
        self.publishers = {}
        self.subscribers = {}
        self.audits = {}
        self.shutdown_callbacks = []

        def publisher(topic, *args, **kwargs):
            result = Publisher(topic)
            self.publishers[topic] = result
            return result

        def subscriber(topic, *args, **kwargs):
            self.subscribers[topic] = kwargs
            return types.SimpleNamespace(get_num_connections=lambda: 1)

        rospy = module('rospy', get_param=lambda key, default=None: self.params.get(key, default),
                       set_param=lambda key, value: self.params.__setitem__(key, value),
                       Publisher=publisher,
                       Subscriber=subscriber,
                       on_shutdown=self.shutdown_callbacks.append,
                       is_shutdown=lambda: False, logerr=lambda *args: None)
        messages = module('uav_fusionmap_msgs.msg', **{name: type(name, (), {}) for name in (
            'AircraftState', 'InfraredFrame', 'PerfEvent', 'RadarFrame', 'SensorBundle')})
        contract = module('ufm_ros_contract', from_ros_state=lambda msg: msg.payload,
                          to_ros_state=encode)
        contract.__path__ = [str(ROOT / 'ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract')]
        codec = module('ufm_ros_contract.perf01a_codec',
                       from_ros_infrared=lambda msg, borrow_image=False: dict(
                           msg.payload, image=(msg.payload['image'] if borrow_image else
                                               list(msg.payload['image']))),
                       from_ros_radar=lambda msg: msg.payload,
                       to_ros_bundle=encode, to_ros_infrared=encode, to_ros_radar=encode)
        self.codec = codec
        replacements = {'rospy': rospy, 'rosgraph_msgs': module('rosgraph_msgs'),
                        'rosgraph_msgs.msg': module('rosgraph_msgs.msg', Clock=ClockMessage),
                        'uav_fusionmap_msgs': module('uav_fusionmap_msgs'),
                        'uav_fusionmap_msgs.msg': messages, 'ufm_ros_contract': contract,
                        'ufm_ros_contract.perf01a_codec': codec}
        self.stack.enter_context(patch.dict(sys.modules, replacements))
        from ufm_sensors import perf01a_async, perf01a_fixture
        self.business = perf01a_async
        self.fixture = perf01a_fixture
        self.profile = perf01a_async.load_profile()
        self.params['/perf01a_async_profile'] = self.profile
        self.load('ufm_ros_contract.perf01a_ros', Path(contract.__path__[0]) / 'perf01a_ros.py')
        self.common = self.load('perf01a_async_common', SCRIPTS / 'perf01a_async_common.py')
        self.stack.enter_context(patch.object(self.common, 'write_audit', self.save_audit))
        self.producer_module = self.load('_review_async_producer', SCRIPTS / 'perf01a_async_producer_node.py')
        self.matcher_module = self.load('_review_async_matcher', SCRIPTS / 'perf01a_async_matcher_node.py')
        return self

    def load(self, name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[name] = loaded
        spec.loader.exec_module(loaded)
        self.stack.enter_context(patch.object(loaded, 'time', self.wall))
        return loaded

    def save_audit(self, directory, filename, payload):
        if filename in self.audits:
            raise FileExistsError(filename)
        self.audits[filename] = copy.deepcopy(payload)

    def tick(self, node, wall_ns):
        self.wall.ns = wall_ns
        node.stop = ControlledStop()
        node.poll()

    def __exit__(self, *args):
        return self.stack.__exit__(*args)


class AsyncWrapperTest(unittest.TestCase):
    def test_infrared_borrow_keeps_matcher_owned_payload(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), WrapperHarness() as h:
                h.params['/perf01a_ir_borrow_image'] = enabled
                node = h.matcher_module.Matcher()
                frame = h.fixture.make_fake_infrared('r', 0, 100 * MS)
                original = frame['image'][0]
                msg = encode(frame)
                node.receive_infrared(msg)
                self.assertEqual(node.errors, [])
                self.assertIs(node.ir_borrow_image, enabled)
                owned = node.matcher._buffers['infrared'][0]['frame']['image']
                self.assertIsNot(owned, frame['image'])
                self.assertEqual(owned, frame['image'])
                frame['image'][0] = original + 1
                self.assertEqual(owned[0], original)

    def test_match_trace_is_opt_in_and_records_worker_decision_and_state_input(self):
        with WrapperHarness() as h:
            h.params['/perf01a_match_trace'] = True
            h.profile['pairing_policy'] = 'exact'
            node = h.matcher_module.Matcher()
            node.receive_clock(ClockMessage(100 * MS))
            node.receive_state(encode(h.fixture.make_fixture_state('r', 0, 100 * MS)))
            node.receive_radar(encode(h.fixture.make_fake_radar('r', 0, 100 * MS)))
            node.receive_infrared(encode(h.fixture.make_fake_infrared('r', 0, 100 * MS)))
            h.tick(node, MS)
            accepted = [row for row in node.decisions if not row['reason']]
            self.assertEqual(len(accepted), 1)
            self.assertEqual(accepted[0]['trigger']['source'], 'advance')
            self.assertEqual(node.lock_records[accepted[0]['trigger']['lock_id']]['role'], 'worker')
            self.assertEqual(len(node.state_inputs), 1)
            self.assertEqual(node.state_inputs[0]['timestamp'], 100 * MS)
            self.assertEqual({row['kind'] for row in node.sensor_inputs}, {'radar', 'infrared'})
            stages = node.stage_records
            self.assertTrue(any(s['name'] == 'state.publish' for s in stages))
            self.assertTrue(any(s['name'] == 'matcher.advance' for s in stages))
            self.assertTrue(any(s['name'] == 'bundle.publish' and
                                s['sample_id'] == accepted[0]['radar_id'] for s in stages))
            self.assertTrue(all(s['start_ns'] <= s['end_ns'] and s['thread_cpu_ns'] >= 0
                                and s['lock_id'] < len(node.lock_records) for s in stages))
            self.assertTrue(all(row['released_ns'] >= row['acquired_ns'] >= row['entered_ns']
                                for row in node.lock_records))
            self.assertEqual(len(node.worker_polls), 1)
            poll = node.worker_polls[0]
            self.assertEqual(poll['lock_id'], accepted[0]['trigger']['lock_id'])
            self.assertLessEqual(poll['sleep_start_ns'], poll['wake_ns'])
            self.assertLessEqual(poll['wake_ns'], node.lock_records[poll['lock_id']]['entered_ns'])
            self.assertTrue(all(row['lock_thread_cpu_ns'] >= 0 for row in node.lock_records))
            self.assertTrue(all(s['thread_cpu_start_ns'] <= s['thread_cpu_end_ns'] for s in stages))
        with WrapperHarness() as h:
            node = h.matcher_module.Matcher()
            self.assertFalse(node.match_trace)
            self.assertEqual(node.lock_records, [])
            self.assertEqual(node.stage_records, [])
            self.assertEqual(node.worker_polls, [])

    def test_match_trace_finish_saves_released_worker_lock(self):
        with WrapperHarness() as h:
            h.params['/perf01a_match_trace'] = True
            node = h.matcher_module.Matcher()
            h.params['/perf01a_async_finish'] = 'r'
            h.params['/perf01a_radar/done'] = 'r'
            h.params['/perf01a_infrared/done'] = 'r'
            h.tick(node, MS)
            audit = h.audits['matcher-audit.json']['match_trace']
            self.assertTrue(audit['locks'])
            self.assertTrue(all('released_ns' in row for row in audit['locks']))
            self.assertEqual(h.params['~done'], 'r')

    def test_ir_tcp_nodelay_is_opt_in_and_scoped_to_ir(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), WrapperHarness() as h:
                h.params['/perf01a_ir_tcp_nodelay'] = enabled
                h.matcher_module.Matcher()
                self.assertEqual(h.subscribers['/uav/sensors/infrared']['tcp_nodelay'], enabled)
                self.assertTrue(all('tcp_nodelay' not in options for topic, options
                                    in h.subscribers.items() if topic != '/uav/sensors/infrared'))

    def test_lagging_producer_bounds_live_images_and_preserves_every_identity(self):
        class Pixels(list):
            pass

        with WrapperHarness() as h:
            h.profile['ir_resolution'] = [32, 32]
            h.profile['producer_capacity'] = 3
            producer = h.producer_module.Producer()
            refs, peak = [], [0]
            original = h.producer_module.make_fake_infrared

            def tracked(*args, **kwargs):
                frame = original(*args, **kwargs)
                frame['image'] = Pixels(frame['image'])
                refs.append(weakref.ref(frame['image']))
                peak[0] = max(peak[0], sum(ref() is not None for ref in refs))
                return frame

            producer.receive_clock(ClockMessage(2_000 * MS))
            with patch.object(h.producer_module, 'make_fake_infrared', tracked):
                producer.produce()
            rows = h.publishers['/uav/sensors/infrared'].rows
            self.assertLessEqual(peak[0], h.profile['producer_capacity'],
                                 'producer retained a run-sized image backlog')
            self.assertEqual([r['timestamp'] for r in rows], list(range(0, 2000 * MS, 20 * MS)))
            self.assertEqual(len({r['sample_id'] for r in rows}), 100)
            self.assertTrue(all(ref() is None for ref in refs))
            self.assertEqual(h.audits['infrared-audit.json']['errors'], [])

    def test_first_clock_absent_wall_timeout_is_observable_at_boundary(self):
        with WrapperHarness() as h:
            node = h.matcher_module.Matcher()
            node.receive_radar(encode(h.fixture.make_fake_radar('r', 0, 0)))
            h.tick(node, 500 * MS - 1)
            self.assertEqual(node.decisions, [])
            h.tick(node, 500 * MS)
            self.assertEqual([d['reason'] for d in node.decisions], ['wall_timeout'])
            self.assertEqual(node.matcher.cache_sizes['radar'], 0)
            self.assertEqual(h.publishers['/uav/sensors/bundle'].rows, [])
            events = h.publishers['/uav/perf/events'].rows
            self.assertEqual([e['reason'] for e in events if e['stage'] == 'sensor_bundle_ready'],
                             ['wall_timeout'])
            self.assertEqual(node.errors, [])

    def test_clock_callback_before_worker_rejects_late_radar_in_either_input_order(self):
        for order in itertools.permutations(('radar', 'infrared')):
            with self.subTest(order=order), WrapperHarness() as h:
                node = h.matcher_module.Matcher()
                node.receive_clock(ClockMessage(100 * MS))
                node.receive_state(encode(h.fixture.make_fixture_state('r', 0, 100 * MS)))
                h.tick(node, MS)
                # The callback records 141ms, but the worker has not run again.
                h.wall.ns = 2 * MS
                node.receive_clock(ClockMessage(141 * MS))
                frames = {'radar': h.fixture.make_fake_radar('r', 0, 100 * MS),
                          'infrared': h.fixture.make_fake_infrared('r', 0, 100 * MS)}
                for kind in order:
                    getattr(node, 'receive_' + kind)(encode(frames[kind]))
                h.tick(node, 3 * MS)
                self.assertEqual([d['reason'] for d in node.decisions], ['arrival_deadline_exceeded'])
                self.assertEqual(h.publishers['/uav/sensors/bundle'].rows, [])
                self.assertEqual(node.errors, [])

    def test_ir_after_deadline_cannot_be_adopted_regardless_of_worker_order(self):
        for poll_first in (False, True):
            with self.subTest(poll_first=poll_first), WrapperHarness() as h:
                node = h.matcher_module.Matcher()
                node.receive_clock(ClockMessage(100 * MS))
                node.receive_state(encode(h.fixture.make_fixture_state('r', 0, 100 * MS)))
                node.receive_radar(encode(h.fixture.make_fake_radar('r', 0, 100 * MS)))
                h.tick(node, MS)
                node.receive_clock(ClockMessage(141 * MS))
                if poll_first:
                    h.tick(node, 2 * MS)
                node.receive_infrared(encode(h.fixture.make_fake_infrared('r', 0, 100 * MS)))
                h.tick(node, 3 * MS)
                self.assertEqual(len(node.decisions), 1)
                self.assertTrue(node.decisions[0]['reason'])
                self.assertEqual(h.publishers['/uav/sensors/bundle'].rows, [])
                self.assertEqual(node.errors, [])

    def test_state_after_deadline_cannot_salvage_pair_regardless_of_worker_order(self):
        for poll_first in (False, True):
            with self.subTest(poll_first=poll_first), WrapperHarness() as h:
                node = h.matcher_module.Matcher()
                node.receive_clock(ClockMessage(100 * MS))
                node.receive_radar(encode(h.fixture.make_fake_radar('r', 0, 100 * MS)))
                node.receive_infrared(encode(h.fixture.make_fake_infrared('r', 0, 100 * MS)))
                h.tick(node, MS)
                node.receive_clock(ClockMessage(140 * MS + 1))
                if poll_first:
                    h.tick(node, 2 * MS)
                node.receive_state(encode(h.fixture.make_fixture_state('r', 0, 100 * MS)))
                h.tick(node, 3 * MS)
                self.assertEqual([d['reason'] for d in node.decisions], ['pose_unavailable'])
                self.assertEqual(h.publishers['/uav/sensors/bundle'].rows, [])
                self.assertEqual(node.errors, [])

    def test_timed_out_identity_cannot_revive_but_new_sample_recovers(self):
        with WrapperHarness() as h:
            node = h.matcher_module.Matcher()
            old = h.fixture.make_fake_radar('r', 0, 0)
            node.receive_clock(ClockMessage(0))
            node.receive_radar(encode(old))
            h.tick(node, 500 * MS)
            self.assertEqual([d['reason'] for d in node.decisions], ['wall_timeout'])
            node.receive_state(encode(h.fixture.make_fixture_state('r', 0, 0)))
            node.receive_infrared(encode(h.fixture.make_fake_infrared('r', 0, 0)))
            node.receive_radar(encode(old))
            node.receive_clock(ClockMessage(100 * MS))
            node.receive_state(encode(h.fixture.make_fixture_state('r', 1, 100 * MS)))
            node.receive_infrared(encode(h.fixture.make_fake_infrared('r', 1, 100 * MS)))
            node.receive_radar(encode(h.fixture.make_fake_radar('r', 1, 100 * MS)))
            node.receive_clock(ClockMessage(140 * MS))
            h.tick(node, 501 * MS)
            self.assertEqual([d['reason'] for d in node.decisions], ['wall_timeout', ''])
            self.assertEqual([r['timestamp'] for r in h.publishers['/uav/sensors/bundle'].rows],
                             [100 * MS])
            self.assertEqual(node.errors, [])

    def test_overflowed_identity_and_older_new_identity_cannot_revive(self):
        with WrapperHarness() as h:
            h.profile['radar_capacity'] = 1
            node = h.matcher_module.Matcher()
            node.receive_clock(ClockMessage(101 * MS))
            node.receive_state(encode(h.fixture.make_fixture_state('r', 0, 100 * MS)))
            node.receive_infrared(encode(h.fixture.make_fake_infrared('r', 0, 100 * MS)))
            old = h.fixture.make_fake_radar('r', 0, 100 * MS)
            node.receive_radar(encode(old))
            node.receive_radar(encode(h.fixture.make_fake_radar('r', 1, 101 * MS)))
            node.receive_radar(encode(old))
            node.receive_radar(encode(h.fixture.make_fake_radar('r', 2, 99 * MS)))
            node.receive_clock(ClockMessage(141 * MS))
            h.tick(node, MS)
            self.assertEqual([d['reason'] for d in node.decisions],
                             ['radar_overflow', 'late_radar', ''])
            self.assertEqual([r['timestamp'] for r in h.publishers['/uav/sensors/bundle'].rows],
                             [101 * MS])
            self.assertEqual(node.errors, [])


if __name__ == '__main__':
    unittest.main()

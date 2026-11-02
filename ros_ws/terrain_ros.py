"""Thin terrain transport: clock source audit, single service slot, wall heartbeat."""
import re
import threading
import time

from sim01b_runtime import rpc_proxy
from ufm_mapping.terrain_dataset import load_dataset
from ufm_mapping.terrain_provider import TerrainProvider
from ufm_terrain_contract.codec import from_ros, to_ros, to_ros_response


def validate_clock_publisher(name):
    if type(name) is not str or not re.fullmatch(r'/[A-Za-z][A-Za-z0-9_]*(/[A-Za-z][A-Za-z0-9_]*)*', name):
        raise ValueError('terrain_expected_clock_publisher')


def clock_graph_ok(system_state, expected):
    """ROS identity consistency, not authentication against a hostile ROS peer."""
    publishers = dict(system_state[0]).get('/clock', [])
    return publishers == [expected]


class TerrainNode:
    def __init__(self, rospy):
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_terrain_msgs.msg import TerrainStatus
        from uav_fusionmap_terrain_msgs.srv import TerrainQuery
        self.ros = rospy
        if rospy.get_param('~enabled', False) is not True or rospy.get_param('/use_sim_time', False) is not True:
            raise ValueError('terrain_requires_explicit_enable_and_sim_clock')
        self.expected = rospy.get_param('~clock_publisher')
        validate_clock_publisher(self.expected)
        dataset = load_dataset(rospy.get_param('~dataset'))
        recording_directory = rospy.get_param('~recording_directory', '')
        if recording_directory:
            from ufm_mapping.terrain_recording import RecordedTerrainProvider
            self.provider = RecordedTerrainProvider(dataset, rospy.get_param('~run_id'),
                rospy.get_param('~clock_id'), recording_directory)
        else:
            self.provider = TerrainProvider(dataset, rospy.get_param('~run_id'),
                rospy.get_param('~clock_id'), enabled=True)
        self.master_uri = rospy.get_master().getUri()[2]
        self._service_slot = threading.Lock()
        self._audit_lock = threading.Lock()
        self._stop = threading.Event()
        self._audit_ok, self._audit_ns = False, 0
        self.publisher = rospy.Publisher('/uav/terrain/v1/status', TerrainStatus, queue_size=1, latch=True)
        self.subscriber = rospy.Subscriber('/clock', Clock, self.receive_clock, queue_size=1)
        self.service = rospy.Service('/uav/terrain/v1/query', TerrainQuery, self.query)
        rospy.on_shutdown(self.close)
        rospy.set_param('~provider_instance_id', self.provider.provider_instance_id)
        rospy.set_param('~ready', rospy.get_param('~run_id'))

    def audit_source(self):
        with self._audit_lock:
            try:
                response = rpc_proxy(self.master_uri).getSystemState(self.ros.get_name())
                if response[0] != 1:
                    raise RuntimeError('clock_graph_unavailable')
                ok = clock_graph_ok(response[2], self.expected)
                code = 'clock_source_mismatch' if not ok else 'clock_source_unavailable'
            except Exception:
                ok, code = False, 'clock_source_unavailable'
            self._audit_ns, self._audit_ok = time.monotonic_ns(), ok
            self.provider.set_clock_source(ok, code)
            return ok

    def receive_clock(self, message):
        received_ns = time.monotonic_ns()
        caller = getattr(message, '_connection_header', {}).get('callerid')
        with self._audit_lock:
            if caller != self.expected:
                self._audit_ok = False
                self.provider.set_clock_source(False, 'clock_source_mismatch')
                return
            if not self._audit_ok or received_ns - self._audit_ns >= 1_000_000_000:
                self.provider.set_clock_source(False, 'clock_source_unavailable')
                return
            try:
                self.provider.observe_clock(message.clock.to_nsec(), received_ns)
            except ValueError:
                self.provider.set_clock_source(False, 'clock_value_invalid')

    def query(self, message):
        try:
            request = from_ros('TerrainQueryRequest', message)
        except ValueError:
            raise self.ros.ServiceException('invalid_request')
        if not self._service_slot.acquire(blocking=False):
            return to_ros_response(self.provider.busy_result(request))
        try:
            self.audit_source()
            return to_ros_response(self.provider.query(request))
        except ValueError:
            raise self.ros.ServiceException('invalid_request')
        finally:
            self._service_slot.release()

    def tick(self):
        self.audit_source()
        self.provider.startup_install()
        self.publisher.publish(to_ros('TerrainStatus', self.provider.status()))

    def run(self):
        # ROS timers follow paused simulation time; use a wall-clock event instead.
        try:
            while not self.ros.is_shutdown() and not self._stop.is_set():
                self.tick()
                self._stop.wait(.5)
        finally:
            self.close()

    def close(self):
        if self._stop.is_set():
            return
        self._stop.set()
        self.provider.disable()
        self.service.shutdown('terrain_shutdown')
        self.subscriber.unregister()
        self.publisher.unregister()
        if hasattr(self.provider, 'close_recording'):
            if not self.provider.close_recording():
                self.ros.logerr('terrain_recording_incomplete')

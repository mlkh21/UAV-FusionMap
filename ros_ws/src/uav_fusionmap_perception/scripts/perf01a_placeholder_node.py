#!/usr/bin/env python
"""PERF-01-A placeholder perception ROS节点；不加载研究模型/GPU/LiDAR。"""
import sys
import time
import threading

import rospy
from uav_fusionmap_msgs.msg import OccupancyObservation, SensorBundle

from ufm_perception.engine import PerceptionEngine, UntrustedInputError
from ufm_ros_contract.perf01a_codec import from_ros_bundle, to_ros_occupancy
from ufm_ros_contract.perf01a_ros import PerfTrace, publish_perf_event, perf_publisher
from ufm_ros_contract.perf01a_wire import WireAudit
from runtime_config import map_settings, ros_map_config


def main(engine_factory=PerceptionEngine):
    if not sys.executable.endswith("/Radar-Diffusion/bin/python"):
        raise RuntimeError("PERF-01-A必须使用Radar-Diffusion Python")
    rospy.init_node("perf01a_placeholder_perception")
    run_id = rospy.get_param("~run_id")
    mode = str(rospy.get_param("~mode", "placeholder")).strip().lower()
    if mode not in ("disabled", "placeholder", "research"):
        raise RuntimeError("unsupported perception mode: " + mode)
    research_report = None
    if mode == "research":
        from ufm_perception.research_preflight import preflight
        research_report = preflight()
        if research_report["ready"]:
            rospy.logerr("research preflight passed, but no research backend adapter is implemented")
        else:
            rospy.logerr("research preflight blocked: %s", ",".join(research_report["blockers"]))
    rolling_grid = rospy.get_param('~rolling_grid', False)
    settings = map_settings(rospy.get_param)
    geometry = {key: settings[key] for key in ('resolution', 'shape', 'origin')}
    max_delta_ns = int(rospy.get_param('~max_radar_ir_delta_ns', 5_000_000))
    max_pose_age_ns = int(rospy.get_param('~max_pose_age_ns', 10_000_000))
    if max_delta_ns < 0 or max_pose_age_ns < 0:
        raise ValueError('bundle age limits must be nonnegative')
    engine = engine_factory(run_id, mode=mode, rolling_grid=rolling_grid,
        max_delta_ns=max_delta_ns, max_pose_age_ns=max_pose_age_ns,
        preflight=research_report, **geometry)
    rospy.set_param('~resolved_map_config', ros_map_config(settings))
    segmented = rospy.get_param('/perf01a_segmented_timing', False)
    receive_type = SensorBundle
    if rospy.get_param('/perf01a_receive_backend', 'standard') == 'numpy':
        from ufm_ros_contract.perf01a_numpy_receive import numpy_list_receive_type
        receive_type = numpy_list_receive_type(SensorBundle)
    audit = WireAudit.for_node('perception')
    audit.install(receive_type, 'deserialize')
    occupancy_pub = rospy.Publisher("/uav/perception/occupancy", OccupancyObservation, queue_size=100)
    event_pub = perf_publisher(rospy)
    worker = None
    lock = threading.RLock()
    stopped = threading.Event()
    active_started = [None]
    if rospy.get_param('~worker_enabled', False):
        from ufm_perception.worker import BoundedPerceptionWorker
        worker = BoundedPerceptionWorker(engine, rospy.get_param('~worker_deadline_s'))

    def publish(occupancy, trace, started):
        ready_ns = time.monotonic_ns()
        sample_id = occupancy['header']['sample_id'][len('perception.occupancy:'):]
        try:
            encoded = trace.call('occupancy_encode', to_ros_occupancy, occupancy)
        except Exception as exc:
            # Business results have already been checked; preserve a wire failure as a diagnostic.
            publish_perf_event(event_pub, run_id, sample_id, 'occupancy_ready',
                occupancy['header']['timestamp'], status='unavailable',
                reason=type(exc).__name__ + ':' + str(exc))
            return
        publish_perf_event(event_pub, run_id, sample_id, 'occupancy_ready',
                           occupancy['header']['timestamp'], ready_ns - started,
                           status=occupancy['header']['status'], reason=occupancy['header']['reason'],
                           monotonic_ns=ready_ns)
        trace.call('occupancy_publish', occupancy_pub.publish, encoded)
        trace.flush(event_pub, run_id, sample_id, occupancy['header']['timestamp'])

    def receive(msg):
        started = time.monotonic_ns()
        audit.record('callback:SensorBundle', msg, callback_ns=started)
        trace = PerfTrace(segmented)
        trace.mark('bundle_callback', started)
        sample_id = msg.header.sample_id
        decoded = None
        try:
            decoded = trace.call('bundle_decode', from_ros_bundle, msg)
            if worker is not None:
                occupancy = worker.submit(decoded)
                if occupancy is None:
                    active_started[0] = started
                    return
            else:
                occupancy = trace.call('perception', engine.process, decoded)
        except Exception as exc:
            reason = type(exc).__name__ + ':' + str(exc)
            if decoded is None or isinstance(exc, UntrustedInputError):
                publish_perf_event(event_pub, run_id, sample_id, 'occupancy_ready',
                                   msg.header.timestamp, status='unavailable', reason=reason)
                trace.flush(event_pub, run_id, sample_id, msg.header.timestamp)
                return
            occupancy = engine.failure(decoded, reason)
        publish(occupancy, trace, started)

    def receive_locked(msg):
        with lock:
            if not stopped.is_set():
                receive(msg)

    def pump():
        while not stopped.wait(.01):
            with lock:
                result = worker.poll()
                if result is not None:
                    publish(result, PerfTrace(segmented), active_started[0])

    if worker is not None:
        thread = threading.Thread(target=pump, name='perception-worker-poll', daemon=True)
        def shutdown():
            stopped.set()
            thread.join(timeout=1.)
            with lock:
                worker.close()
        rospy.on_shutdown(shutdown)
        thread.start()

    rospy.Subscriber("/uav/sensors/bundle", receive_type, receive_locked, queue_size=100,
                     buff_size=int(rospy.get_param('/perf01a_image_buff_size', 65536)))
    deadline = time.monotonic() + 15.0
    require_observers = rospy.get_param('/perf01a_require_observers', True)
    while not (occupancy_pub.get_num_connections() and
            (not require_observers or event_pub is None or event_pub.get_num_connections())):
        if time.monotonic() > deadline or rospy.is_shutdown():
            raise RuntimeError('perception subscribers not ready')
        time.sleep(.02)
    rospy.set_param('~ready', run_id)
    rospy.spin()


if __name__ == "__main__":
    main()

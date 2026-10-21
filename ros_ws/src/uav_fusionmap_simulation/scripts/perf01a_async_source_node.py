#!/usr/bin/env python
"""Profile-driven stationary source; defaults to 1 ms clock and 100 Hz state."""
import json
from pathlib import Path
import sys
import threading
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState

from ufm_ros_contract import to_ros_state
from ufm_simulation.perf01a_fixture import make_fixture_state, make_motion_state


def source(run_id, stop):
    directory = Path(rospy.get_param('/perf01a_async_run_directory'))
    audit = dict(run_id=run_id, clock_count=0, first_ns=None, last_ns=None,
                 state_count=0, python=sys.executable, errors=[])
    try:
        publish_source(run_id, stop, audit)
    except Exception as exc:
        audit['errors'].append(type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        with (directory / 'source-audit.json').open('x', encoding='utf-8') as stream:
            json.dump(audit, stream, indent=2, allow_nan=False)
            stream.write('\n')
    rospy.set_param('~done', run_id)


def publish_source(run_id, stop, audit):
    duration_ns = int(rospy.get_param('/perf01a_async_duration_ns',
        round(float(rospy.get_param('~duration_s', 10.0)) * 1_000_000_000)))
    profile = rospy.get_param('/perf01a_async_profile', {})
    clock_period_ns = profile.get('clock_period_ns', 1_000_000)
    state_frequency_hz = profile.get('state_frequency_hz', 100)
    drain_ns = profile.get('source_drain_ns', 200_000_000)
    if type(clock_period_ns) is not int or clock_period_ns <= 0:
        raise ValueError('clock_period_ns must be a positive integer')
    if (type(state_frequency_hz) is not int or state_frequency_hz <= 0 or
            1_000_000_000 % state_frequency_hz):
        raise ValueError('state_frequency_hz requires an integer nanosecond period')
    state_period_ns = 1_000_000_000 // state_frequency_hz
    if state_period_ns % clock_period_ns:
        raise ValueError('state sampling must align to source clock ticks')
    if duration_ns <= 0 or type(drain_ns) is not int or drain_ns < 200_000_000:
        raise ValueError('positive duration and at least 200 ms drain required')
    audit['config'] = dict(clock_period_ns=clock_period_ns, state_frequency_hz=state_frequency_hz,
                           state_period_ns=state_period_ns, source_drain_ns=drain_ns)
    clock_pub = rospy.Publisher('/clock', Clock, queue_size=1000)
    state_pub = rospy.Publisher('/uav/sim/state', AircraftState, queue_size=100)
    rospy.set_param('~ready', run_id)
    deadline = time.monotonic() + 15.0
    nodes = ('source', 'sensor', 'radar', 'infrared', 'perception', 'mapping')
    while not stop.is_set():
        if (all(rospy.get_param('/perf01a_' + node + '/ready', '') == run_id for node in nodes)
                and state_pub.get_num_connections() >= 1 and clock_pub.get_num_connections() >= 3):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('six-node readiness timed out')
        stop.wait(.02)
    sequence = 0
    next_wall = time.monotonic()
    for stamp in range(0, duration_ns + drain_ns + 1, clock_period_ns):
        if stop.wait(max(0.0, next_wall - time.monotonic())) or rospy.is_shutdown():
            raise RuntimeError('shutdown_before_source_done')
        clock_pub.publish(Clock(clock=rospy.Time(stamp // 1_000_000_000, stamp % 1_000_000_000)))
        audit['clock_count'] += 1
        if audit['first_ns'] is None:
            audit['first_ns'] = stamp
        audit['last_ns'] = stamp
        if stamp % state_period_ns == 0:
            state = (make_motion_state(run_id, sequence, stamp, profile['speed_mps'])
                     if profile.get('speed_mps', 0) else make_fixture_state(run_id, sequence, stamp))
            state_pub.publish(to_ros_state(state))
            sequence += 1
            audit['state_count'] = sequence
        # Do not burst overdue ticks and remove the producers' delivery window.
        next_wall = max(next_wall + clock_period_ns / 1_000_000_000, time.monotonic())


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required: ' + sys.executable)
    rospy.init_node('perf01a_source')
    run_id = rospy.get_param('~run_id')
    stop = threading.Event()
    rospy.on_shutdown(stop.set)
    try:
        source(run_id, stop)
    except Exception as exc:
        message = type(exc).__name__ + ': ' + str(exc)
        rospy.set_param('~error', dict(run_id=run_id, message=message))
        rospy.logerr('PERF-01-A async source: %s', message)
    rospy.spin()


if __name__ == '__main__':
    main()

"""Explicit synthetic obstacles for report figures, through public ROS occupancy only."""
import argparse
import io
import json
from pathlib import Path
import sys
import signal
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import OccupancyObservation, MapSnapshot
from ufm_ros_contract.perf01a_codec import to_ros_occupancy, from_ros_occupancy, from_ros_snapshot
from m4_fixture import load_spec
from m3_motion_fixture import motion_observation


def points():
    occupied = {(8.25, -.25 + y * .5, .25 + z * .5) for y in range(-9, 11) for z in range(8)}
    occupied |= {(16.25, .25 + y * .5, .25 + z * .5) for y in range(-8, 8) for z in range(6)}
    occupied |= {(4.25 + x * .5, -5.75 + y * .5, .25 + z * .5)
                 for x in range(4) for y in range(3) for z in range(4)}
    occupied |= {(12.25 + x * .5, 3.25 + y * .5, .25 + z * .5)
                 for x in range(6) for y in range(4) for z in range(7)}
    free = {(3.25 + x * .5, -6.75 + y * .5, .25) for x in range(34) for y in range(28)} - occupied
    unknown = {(19.25, .25 + y * .5, .25) for y in range(-5, 5)}
    free -= unknown
    return sorted(occupied), sorted(free), sorted(unknown)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('report_scene_fixture', disable_signals=True)
    signal.signal(signal.SIGINT, lambda *_:rospy.signal_shutdown('fixture stopped'))
    spec = load_spec(args.run / 'm4-config.yaml')['local_map']
    clock = rospy.Publisher('/clock', Clock, queue_size=1)
    occupancy = rospy.Publisher('/uav/perception/occupancy', OccupancyObservation, queue_size=1)
    snapshots = []
    subscription = rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
        lambda msg:snapshots.append(from_ros_snapshot(msg)), queue_size=10)
    deadline = time.monotonic() + 25.
    while not (occupancy.get_num_connections() and
               subscription.get_num_connections() and
               rospy.get_param('/uav/report_ui/ready', False) and
               rospy.get_param('/perf01a_mapping/ready', '') == args.run_id):
        if rospy.is_shutdown():return
        if time.monotonic() > deadline:raise RuntimeError('report fixture readiness timeout')
        time.sleep(.05)
    obstacles, floor, neutral = points()
    observations = []
    sequence = [('occupied', obstacles, 'default'), ('free', floor, 'default'),
                ('occupied', neutral, 'default'), ('free', neutral, 'default'),
                ('occupied', [(16.25, .25, .25)], None)]
    stamp = 0
    for index, (kind, coordinates, bounds) in enumerate(sequence):
        stamp = (index + 1) * 10_000_000
        value = motion_observation(spec, args.run_id, index, kind=kind, points=coordinates,
            body=(8., 0., 0.), origin=(-8., -8., -4.), stamp=stamp, bounds=bounds)
        message = to_ros_occupancy(value)
        buffer = io.BytesIO()
        message.serialize(buffer)
        message = type(message)().deserialize(buffer.getvalue())
        observations.append(from_ros_occupancy(message))
        clock.publish(Clock(clock=rospy.Time(0, stamp)))
        occupancy.publish(message)
        limit = time.monotonic() + 5.
        while len(snapshots) < index + 1:
            if rospy.is_shutdown():return
            if time.monotonic() > limit:
                raise RuntimeError('report scene snapshot timeout: input=%d received=%d' % (index, len(snapshots)))
            time.sleep(.01)
        time.sleep(.7)
    (args.run / 'scene-receipts.json').write_text(json.dumps(dict(
        observations=observations, snapshots=snapshots,
        scope='explicit synthetic obstacle fixture; no radar-IR model, LiDAR, terrain or flight evidence'), indent=2))
    rospy.set_param('/uav/report_fixture/complete', True)
    while not rospy.is_shutdown():
        if rospy.get_param('/uav/report_fixture/expire', False):stamp = 200_000_001
        if not rospy.get_param('/uav/report_fixture/stop_clock', False):
            clock.publish(Clock(clock=rospy.Time(0, stamp)))
        time.sleep(.1)
    subscription.unregister()


if __name__ == '__main__':
    main()

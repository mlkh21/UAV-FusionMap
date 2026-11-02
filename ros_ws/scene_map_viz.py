"""Read-only public map to standard RViz markers; sensors have separate displays."""
import argparse
from pathlib import Path
import sys
import threading
import time

import rospy
from rosgraph_msgs.msg import Clock
from visualization_msgs.msg import MarkerArray
from uav_fusionmap_msgs.msg import MapSnapshot
from ufm_ros_contract.perf01a_codec import from_ros_snapshot
from rviz_map_markers import build_map_markers

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from ufm_application.visualization import COLORS, SnapshotView


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clock-id', required=True)
    parser.add_argument('--ttl-ns', type=int, required=True)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('scene_map_visualizer')
    policy = SnapshotView(args.ttl_ns, .3, .7)
    lock = threading.RLock()
    current = dict(snapshot=None, stamp=None, received=0.)
    publisher = rospy.Publisher('/uav/visual/map', MarkerArray, queue_size=1, latch=True)

    def snapshot(message):
        with lock:current['snapshot'] = from_ros_snapshot(message)

    def clock(message):
        with lock:current.update(stamp=message.clock.to_nsec(), received=time.monotonic())

    subscribers = [rospy.Subscriber('/uav/map/snapshot', MapSnapshot, snapshot, queue_size=1),
                   rospy.Subscriber('/clock', Clock, clock, queue_size=1)]
    while not rospy.is_shutdown():
        with lock:
            if current['snapshot'] is not None:
                frame = policy.frame(current['snapshot'], current['stamp'], args.clock_id,
                                     time.monotonic() - current['received'] < 3.)
                publisher.publish(build_map_markers(frame, COLORS))
        time.sleep(.2)


if __name__ == '__main__':
    main()

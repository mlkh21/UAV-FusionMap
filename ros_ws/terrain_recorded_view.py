"""Optional recorded terrain MarkerArray on a separate historical namespace."""
import argparse
from pathlib import Path
import signal
import sys
import threading

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))


def main():
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('wrong Python')
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--group',type=int,default=0)
    args=parser.parse_args()
    from ufm_terrain_contract.bounds import read_json,RECORDING_BYTES
    from ufm_application.terrain_visualization import recorded_groups,marker_rows
    from terrain_rviz_node import build_markers
    import rospy
    from visualization_msgs.msg import MarkerArray
    groups=recorded_groups(read_json(args.receipt,RECORDING_BYTES))
    if not 0<=args.group<len(groups):raise ValueError('terrain_recorded_group_index')
    message=build_markers(marker_rows(groups[args.group]))
    rospy.init_node('terrain_recorded_view',disable_signals=True)
    publisher=rospy.Publisher('/uav/terrain/recorded/markers',MarkerArray,queue_size=1,latch=True)
    stop=threading.Event()
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    while not stop.is_set() and not rospy.is_shutdown():
        publisher.publish(message)
        stop.wait(.5)
    publisher.unregister()
    rospy.signal_shutdown('recorded view stopped')


if __name__=='__main__':main()

"""Standalone application query through the existing ROS MapQuery service."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from ufm_application import MapQueryClient, QueryTransportError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-id', default='perf01a-local')
    parser.add_argument('--frame-id', default='odom')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--clock-id', required=True)
    parser.add_argument('--timestamp-ns', type=int, required=True)
    parser.add_argument('--max-age-ns', type=int, required=True)
    parser.add_argument('--point', type=float, nargs=3, required=True)
    parser.add_argument('--service', default='/uav/map/query')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    import rospy
    from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
    from ufm_ros_contract.query_codec import from_ros_query_result
    rospy.init_node('map_query_application', anonymous=True, disable_signals=True)

    def transport(request):
        try:
            rospy.wait_for_service(args.service, timeout=2.)
            return from_ros_query_result(rospy.ServiceProxy(args.service, MapQuery)(
                MapQueryRequest(**request)).result)
        except (rospy.ROSException, rospy.ServiceException, OSError) as exc:
            raise QueryTransportError(str(exc)) from exc

    result = MapQueryClient(transport).query(map_id=args.map_id, frame_id=args.frame_id,
        run_id=args.run_id, clock_id=args.clock_id, query_timestamp=args.timestamp_ns,
        max_age_ns=args.max_age_ns, point=args.point)
    print(json.dumps(result), flush=True)
    rospy.signal_shutdown('query completed')
    return int(result['status'] == 'unavailable')


if __name__ == '__main__':
    sys.exit(main())

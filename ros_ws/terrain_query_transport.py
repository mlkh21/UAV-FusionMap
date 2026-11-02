"""One bounded in-flight ROS call; timeout discards late results without queuing."""
import threading
import time
import copy


class TerrainQueryTransport:
    def __init__(self, service='/uav/terrain/v1/query', discovery_s=2., call_s=1., call=None):
        if not 0 < discovery_s <= 2. or not 0 < call_s <= 1.:
            raise ValueError('terrain_transport_deadline')
        self.service, self.discovery_s, self.call_s = service, discovery_s, call_s
        self._call = call
        self._lock = threading.Lock()
        self._worker = None
        self._closed = False
        self._generation = 0

    def _ros_call(self, request, discovered):
        import rospy
        from uav_fusionmap_terrain_msgs.srv import TerrainQuery
        from ufm_terrain_contract.codec import from_ros_response, to_ros
        try:
            rospy.wait_for_service(self.service, timeout=self.discovery_s)
            discovered.set()
            response = rospy.ServiceProxy(self.service, TerrainQuery)(to_ros('TerrainQueryRequest', request))
            return from_ros_response(response, request=request)
        except rospy.ROSException as exc:
            raise OSError('terrain_ros_unavailable') from exc
        except rospy.ServiceException as exc:
            raise OSError('terrain_ros_service_error') from exc

    def __call__(self, request):
        from ufm_terrain_contract.contract import validate_request
        validate_request(request)
        request = copy.deepcopy(request)
        done, discovered, answer = threading.Event(), threading.Event(), {}
        with self._lock:
            if self._closed or self._worker is not None and self._worker.is_alive():
                raise OSError('terrain_transport_busy_or_closed')
            generation = self._generation
            def work():
                try:
                    if self._call is None:
                        answer['value'] = self._ros_call(request, discovered)
                    else:
                        discovered.set()
                        answer['value'] = self._call(request)
                except Exception as exc:
                    answer['error'] = exc
                finally:
                    discovered.set()
                    done.set()
            self._worker = threading.Thread(target=work, name='terrain-query', daemon=True)
            self._worker.start()
        # Discovery and call have separate deadlines. The worker's service wait is <=2s.
        found = discovered.wait(self.discovery_s)
        if not found or not done.wait(self.call_s):
            with self._lock: self._generation += 1
            raise TimeoutError('terrain_query_deadline')
        with self._lock:
            if generation != self._generation or self._closed:
                raise OSError('terrain_late_response')
        if 'error' in answer:
            raise OSError('terrain_call_failed') from answer['error']
        return answer['value']

    def close(self):
        with self._lock:
            self._closed = True
            self._generation += 1


def main():
    import argparse
    import json
    import sys
    from pathlib import Path
    import rospy
    parser = argparse.ArgumentParser()
    parser.add_argument('--terrain-id', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--clock-id', required=True)
    parser.add_argument('--timestamp-ns', type=int, required=True)
    parser.add_argument('--point', nargs=2, type=float, required=True)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
    from ufm_application.terrain_client import TerrainClient
    rospy.init_node('terrain_query_client', anonymous=True, disable_signals=True)
    transport = TerrainQueryTransport()
    client = TerrainClient(transport, args.terrain_id, args.run_id, args.clock_id)
    try:
        result = client.query(dict(terrain_id=args.terrain_id, run_id=args.run_id, clock_id=args.clock_id,
            frame_id='map', query_timestamp=args.timestamp_ns, point_xy=args.point,
            pin_version=False, expected_provider_instance_id='', expected_terrain_revision=0))
        print(json.dumps(result, allow_nan=False))
        return int(result['status'] == 'unavailable')
    finally:
        transport.close()


if __name__ == '__main__':
    import sys
    sys.exit(main())

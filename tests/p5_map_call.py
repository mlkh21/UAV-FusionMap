"""A real synchronous application query isolated by the P5 external supervisor."""
import json
from pathlib import Path
import sys
import time

if __name__ == '__main__':
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    import rospy
    from uav_fusionmap_msgs.srv import MapQuery,MapQueryRequest
    from ufm_ros_contract.query_codec import from_ros_query_result
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
    from ufm_application.query_client import MapQueryClient
    directory = Path(sys.argv[1])
    rospy.init_node('p5_isolated_map_client',disable_signals=True)
    (directory/'ready.json').write_text('{"ready":true}\n')
    deadline = time.monotonic()+15.
    while not (directory/'request.json').exists():
        if time.monotonic()>=deadline:
            raise RuntimeError('isolated application query was never dispatched')
        time.sleep(.005)
    request = json.loads((directory/'request.json').read_text())
    def call(value):
        return from_ros_query_result(rospy.ServiceProxy('/uav/map/query',MapQuery)(MapQueryRequest(**value)).result)
    result = MapQueryClient(call).query(**request)
    with (directory/'result.json').open('x') as stream:
        json.dump(result,stream)

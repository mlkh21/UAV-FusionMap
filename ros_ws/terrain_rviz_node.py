"""Optional public terrain MarkerArray consumer; it publishes no TF and no zero-height surface."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))


def build_markers(rows):
    from visualization_msgs.msg import Marker, MarkerArray
    message = MarkerArray()
    clear = Marker()
    clear.action = Marker.DELETEALL
    message.markers.append(clear)
    for index, row in enumerate(rows):
        marker = Marker()
        marker.header.frame_id = row['frame_id']
        marker.ns, marker.id = 'terrain-public', index
        marker.type, marker.action = Marker.CUBE, Marker.ADD
        marker.pose.position.x, marker.pose.position.y, marker.pose.position.z = row['point']
        marker.pose.orientation.w = 1.
        marker.scale.x = marker.scale.y = .8
        marker.scale.z = .2
        marker.color.r, marker.color.g, marker.color.b, marker.color.a = row['color']
        message.markers.append(marker)
    if rows:
        label = Marker()
        label.header.frame_id = rows[0]['frame_id']
        label.ns, label.id = 'terrain-label', 0
        label.type, label.action = Marker.TEXT_VIEW_FACING, Marker.ADD
        label.pose.position.x, label.pose.position.y, label.pose.position.z = rows[0]['point']
        label.pose.position.z += 1.
        label.pose.orientation.w, label.scale.z = 1., .35
        label.color.r = label.color.g = label.color.b = label.color.a = 1.
        label.text = '%s | fixture DTM | rev %d' % (rows[0]['mode'], rows[0]['terrain_revision'])
        message.markers.append(label)
    return message


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    import rospy
    from visualization_msgs.msg import Marker, MarkerArray
    from ufm_application.terrain_client import TerrainClient
    from ufm_application.terrain_visualization import marker_rows
    from terrain_query_transport import TerrainQueryTransport
    from uav_fusionmap_terrain_msgs.msg import TerrainStatus

    rospy.init_node('terrain_rviz_markers')
    terrain_id = rospy.get_param('~terrain_id')
    run_id = rospy.get_param('~run_id')
    clock_id = rospy.get_param('~clock_id')
    transport = TerrainQueryTransport(discovery_s=2., call_s=1.)
    client = TerrainClient(transport, terrain_id, run_id, clock_id)
    publisher = rospy.Publisher('/uav/terrain/v1/markers', MarkerArray, queue_size=1, latch=True)
    closed = threading.Event()

    def status_callback(message):
        try:
            from ufm_terrain_contract.codec import from_ros
            value = from_ros('TerrainStatus', message)
            client.receive_status(value)
        except ValueError:
            client.invalidate()

    def publish(rows):
        publisher.publish(build_markers(rows))

    def loop():
        while not closed.is_set() and not rospy.is_shutdown():
            if client.current_group() is None:
                client.sample_group()
            closed.wait(.5)

    def display_loop():
        while not closed.is_set() and not rospy.is_shutdown():
            publish(marker_rows(client.current_group()))
            closed.wait(.1)

    subscriber = rospy.Subscriber('/uav/terrain/v1/status', TerrainStatus, status_callback, queue_size=1)
    worker = threading.Thread(target=loop, daemon=True)
    worker.start()
    display_worker = threading.Thread(target=display_loop, daemon=True)
    display_worker.start()
    rospy.on_shutdown(lambda: (closed.set(), subscriber.unregister(), transport.close()))
    rospy.spin()


if __name__ == '__main__':
    main()

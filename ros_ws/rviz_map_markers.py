"""Standard MarkerArray view of public map cells; no Qt or private map state."""
from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray


def build_map_markers(frame, colors):
    output = MarkerArray()
    for number, (state, color) in enumerate(colors.items()):
        marker = Marker()
        marker.header.frame_id = frame['header']['frame_id']
        marker.ns, marker.id = 'map_' + state, number
        marker.type, marker.action = Marker.CUBE_LIST, Marker.ADD
        marker.pose.orientation.w = 1.
        marker.scale.x, marker.scale.y, marker.scale.z = [v * .9 for v in frame['resolution']]
        marker.color.r, marker.color.g, marker.color.b, marker.color.a = color
        marker.color.a *= .5
        marker.points = [Point(*cell['center']) for cell in frame['cells'] if cell['state'] == state]
        if not marker.points:marker.action = Marker.DELETE
        output.markers.append(marker)
    return output

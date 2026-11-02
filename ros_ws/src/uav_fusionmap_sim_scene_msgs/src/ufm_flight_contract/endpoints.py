"""Frozen endpoint names/types only. No ROS imports, registration or clients."""
from types import MappingProxyType

ENDPOINTS = MappingProxyType({
    'step': ('/uav/flight/scene/step', 'uav_fusionmap_sim_scene_msgs/SceneStep'),
    'frame_applied': ('/uav/flight/scene/frame_applied', 'uav_fusionmap_sim_scene_msgs/SceneFrame'),
    'capture_ack': ('/uav/flight/scene/capture_ack', 'uav_fusionmap_sim_scene_msgs/SceneCaptureAck'),
})


def validate_endpoints(value):
    if type(value) is not dict or set(value) != set(ENDPOINTS):
        raise ValueError('flight_endpoint_fields')
    for key, wanted in ENDPOINTS.items():
        if type(value[key]) is not list or value[key] != list(wanted):
            raise ValueError('flight_endpoint_name_or_type')

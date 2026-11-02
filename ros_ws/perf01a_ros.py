"""旧导入路径的兼容入口；实现统一由ROS契约包维护。"""
from ufm_ros_contract import to_ros_state as state_message
from ufm_ros_contract.perf01a_ros import publish_perf_event

__all__ = ['publish_perf_event', 'state_message']

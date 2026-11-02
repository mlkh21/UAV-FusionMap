"""Thin ROS wrapper failure handling; wire codecs use real generated types."""
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import rospy
from rosgraph_msgs.msg import Clock
from m5_fixture import load_spec
from m5_iface_fixture import ROOT, request
from terrain_ros import TerrainNode, clock_graph_ok, validate_clock_publisher
from ufm_mapping.terrain_dataset import from_private_fixture
from ufm_mapping.terrain_provider import TerrainProvider
from ufm_terrain_contract.codec import from_ros_response, to_ros


class TerrainNodeTest(unittest.TestCase):
    def node(self):
        node = TerrainNode.__new__(TerrainNode)
        node.ros = SimpleNamespace(ServiceException=rospy.ServiceException, get_name=lambda: '/terrain_provider')
        node.provider = TerrainProvider(from_private_fixture(load_spec()), 'm5-fixture', 'sim:m5-fixture', enabled=True)
        node.expected, node.master_uri = '/expected', 'http://127.0.0.1:1'
        node._service_slot, node._audit_lock = threading.Lock(), threading.Lock()
        node._audit_ns, node._audit_ok = time.monotonic_ns(), True
        node.provider.set_clock_source(True)
        return node

    def test_only_explicit_single_absolute_clock_identity_is_accepted(self):
        validate_clock_publisher('/clock_owner')
        for value in ('clock_owner', '/', '', '/bad name', None):
            with self.assertRaises(ValueError): validate_clock_publisher(value)
        for publishers in ([], ['/other'], ['/expected', '/other']):
            self.assertFalse(clock_graph_ok([[['/clock', publishers]], [], []], '/expected'))
        self.assertTrue(clock_graph_ok([[['/clock', ['/expected']]], [], []], '/expected'))

    def test_wrong_connection_header_and_stale_graph_cannot_observe_clock(self):
        node = self.node()
        msg = Clock(clock=rospy.Time(0, 100))
        msg._connection_header = {'callerid': '/other'}
        node.receive_clock(msg)
        self.assertIsNone(node.provider.status()['evaluation_timestamp'])
        node._audit_ok = True
        node._audit_ns = time.monotonic_ns() - 1_000_000_001
        msg._connection_header = {'callerid': '/expected'}
        node.receive_clock(msg)
        self.assertIsNone(node.provider.status()['evaluation_timestamp'])

    def test_source_graph_failure_clears_availability(self):
        node = self.node()
        node.provider.observe_clock(100)
        node.provider.startup_install()
        with patch('terrain_ros.rpc_proxy', side_effect=OSError('offline')):
            self.assertFalse(node.audit_source())
        self.assertEqual(node.provider.status()['state'], 'unavailable')

    def test_service_busy_has_no_unlocked_cached_payload_and_errors_are_stable(self):
        node = self.node()
        req = request()
        node._service_slot.acquire()
        try:
            row = from_ros_response(node.query(to_ros('TerrainQueryRequest', req)))
        finally:
            node._service_slot.release()
        self.assertEqual((row['reason'], row['terrain_revision'], row['evaluation_timestamp']), ('terrain_busy', 0, None))
        bad = to_ros('TerrainQueryRequest', req)
        bad.point_xy = [float('nan'), 0.]
        with self.assertRaisesRegex(rospy.ServiceException, '^invalid_request$'): node.query(bad)

    def test_launch_defaults_off_and_existing_launches_never_include_terrain(self):
        for name in ('terrain_fixture.launch', 'terrain_rviz_fixture.launch'):
            launch = ET.parse(ROOT / 'ros_ws/launch' / name).getroot()
            self.assertEqual(launch.find("arg[@name='enabled']").get('default'), 'false')
            self.assertEqual(launch.find('group').get('if'), '$(arg enabled)')
        for path in (ROOT / 'ros_ws/launch').glob('*.launch'):
            if path.name in ('terrain_fixture.launch', 'terrain_rviz_fixture.launch'): continue
            self.assertNotIn('uav_fusionmap_terrain', path.read_text())


if __name__ == '__main__':
    unittest.main()

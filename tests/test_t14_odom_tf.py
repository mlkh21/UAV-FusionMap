"""T-14 contract tests for the AircraftState compatibility mirror."""
import copy
import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
for directory in ('simulation', 'sensors', 'ros_ws'):
    sys.path.insert(0, str(ROOT / directory))

from ufm_simulation.perf01a_fixture import make_motion_state
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.odom_mirror import build_odom_mirror


FRAMES = {
    'odom_origin_policy': 'px4_estimator_local_origin',
    'body_origin_policy': 'source_body_virtual_flu',
}


def adapted(stamp=1234567890123):
    return adapt_state(make_motion_state('t14', 3, stamp, .1), FRAMES)


class OdomMirrorContractTest(unittest.TestCase):
    def test_mirror_preserves_aircraft_identity_geometry_and_unknown_quality(self):
        state = adapted()
        mirror = build_odom_mirror(state)
        self.assertEqual(mirror['header'], state['header'])
        self.assertEqual(mirror['frame_id'], 'odom')
        self.assertEqual(mirror['child_frame_id'], 'base_link')
        self.assertEqual(mirror['position'], state['position'])
        self.assertEqual(mirror['orientation_xyzw'], state['orientation_xyzw'])
        self.assertEqual(mirror['linear_velocity'], state['linear_velocity'])
        self.assertEqual(mirror['pose_covariance'][0], -1.0)
        self.assertEqual(mirror['twist_covariance'][0], -1.0)
        self.assertFalse(mirror['covariance_available'])

    def test_terminal_state_cannot_become_odom_or_tf_geometry(self):
        state = adapted()
        state['header'].update(status='unavailable', reason='terminal:source_timeout',
                               sample_id='sensors.state:sim.terminal:t14:0')
        state['position'] = [float('nan')] * 3
        state['orientation_xyzw'] = [0.0] * 4
        with self.assertRaises(ValueError):
            build_odom_mirror(state)

    def test_mirror_does_not_mutate_aircraft_state(self):
        state = adapted()
        original = copy.deepcopy(state)
        build_odom_mirror(state)
        self.assertEqual(state, original)

    def test_launches_make_mirror_and_tf_explicit(self):
        for name in ('sim01_state.launch', 'sim01_sensor_fixture.launch', 'sim01b_sensors.launch'):
            root = ET.parse(str(ROOT / 'ros_ws/launch' / name)).getroot()
            args = {item.attrib['name']: item.attrib for item in root.findall('arg')}
            self.assertEqual(args['publish_odom']['default'], 'false')
            self.assertEqual(args['broadcast_tf']['default'], 'false')
            params = {item.attrib['name']: item.attrib for item in root.findall('.//param')}
            self.assertIn('publish_odom', params)
            self.assertIn('broadcast_tf', params)

    def test_only_state_adapter_owns_dynamic_odom_to_base_link_tf(self):
        owners = []
        for path in ROOT.glob('ros_ws/**/*.py'):
            text = path.read_text(encoding='utf-8')
            if 'TransformBroadcaster(' in text:
                owners.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(owners, ['ros_ws/src/uav_fusionmap_sensors/scripts/state_adapter_node.py'])


if __name__ == '__main__':
    unittest.main()

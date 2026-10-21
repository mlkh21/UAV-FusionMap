"""SENS-TRAIN-01: generated ROS wire types and launch graph, without master."""
import sys
import unittest
import xmlrpc.client
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
for relative in ('simulation', 'sensors'):
    sys.path.insert(0, str(ROOT / relative))
from ufm_sensors.state_adapter import adapt_state
from ufm_simulation.perf01a_fixture import make_motion_state
from ufm_sensors.training_supervision import build_training_sample


class TrainingRosContractTest(unittest.TestCase):
    def test_motion_launch_keeps_int64_configuration_out_of_xmlrpc_parameters(self):
        from roslaunch.config import load_config_default
        path = str(ROOT / 'ros_ws/launch/sens_train_01.launch')
        config_path = str(ROOT / 'configs/sens_train_01_motion_fixture.yaml')
        launch = load_config_default([(path, [
            'run_id:=launch-audit', 'output_path:=/tmp/not-opened-by-launch-audit.jsonl',
            'config_path:=' + config_path])], 11447, verbose=False, assign_machines=False)
        xmlrpc.client.dumps((dict((name, value.value) for name, value in launch.params.items()),))
        config = yaml.safe_load(Path(config_path).read_text())
        self.assertEqual(config['calibration']['valid_until_ns'], 2_200_000_000)

    def test_generated_radar_and_ir_messages_preserve_identity_and_values(self):
        from ufm_ros_contract.perf01a_codec import (to_ros_radar, from_ros_radar,
                                                    to_ros_infrared, from_ros_infrared)
        cfg = yaml.safe_load((ROOT / 'configs/sens_train_01_fixture.yaml').read_text())
        state = adapt_state(make_motion_state('ros-train', 1, 100_000_000, 0), {
            'odom_origin_policy':'px4_estimator_local_origin',
            'body_origin_policy':'source_body_virtual_flu'})
        sample = build_training_sample(state, cfg)
        radar = from_ros_radar(to_ros_radar(sample['radar']))
        infrared = from_ros_infrared(to_ros_infrared(sample['infrared']))
        self.assertEqual(radar['header']['run_id'], 'ros-train')
        self.assertEqual(radar['scan_start'], 100_000_000)
        self.assertEqual(len(radar['points']), 1)
        self.assertFalse(radar['points'][0]['doppler_available'])
        self.assertFalse(radar['points'][0]['power_available'])
        self.assertEqual(infrared['camera_info']['calibration_id'], cfg['calibration']['calibration_id'])
        self.assertAlmostEqual(infrared['image'][7], 0.9, places=6)
        self.assertNotIn('lidar', radar)
        self.assertNotIn('lidar', infrared)

    def test_launch_graph_separates_training_supervision_from_inference(self):
        train = ET.parse(str(ROOT / 'ros_ws/launch/sens_train_01.launch')).getroot()
        online = ET.parse(str(ROOT / 'ros_ws/launch/perf01a_async.launch')).getroot()
        train_types = [node.attrib['type'] for node in train.findall('node')]
        online_types = [node.attrib['type'] for node in online.findall('node')]
        self.assertEqual(len(train_types), 3)
        self.assertIn('sens_train_01_fake_lidar_node.py', train_types)
        self.assertIn('sens_train_01_recorder_node.py', train_types)
        self.assertFalse(any('lidar' in name or 'train' in name for name in online_types))
        self.assertFalse(any('perception' in name or 'map' in name or 'matcher' in name
                             for name in train_types))
        fake = (ROOT / 'ros_ws/src/uav_fusionmap_sensors/scripts/sens_train_01_fake_lidar_node.py').read_text()
        recorder = (ROOT / 'ros_ws/src/uav_fusionmap_sensors/scripts/sens_train_01_recorder_node.py').read_text()
        self.assertNotIn('SensorBundle', fake)
        self.assertNotIn('SensorBundle', recorder)
        self.assertIn('/uav/training/lidar_supervision', fake)
        self.assertIn('/uav/training/lidar_supervision', recorder)


if __name__ == '__main__':
    unittest.main()

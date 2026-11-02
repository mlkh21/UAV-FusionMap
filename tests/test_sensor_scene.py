"""Scene geometry and bounded online pairing, independent of Gazebo/ROS processes."""
import copy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import sys

import yaml
from ufm_simulation.sensor_scene import create_world
from ufm_sensors.scene_stream import SceneStream, scene_context, validate_scene_profile
from ufm_sensors.perf01a_fixture import make_fake_infrared, make_fake_radar
from test_perf01a_async import pose

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'application'))
MS = 1_000_000


class SensorSceneTest(unittest.TestCase):
    def setUp(self):
        self.profile = yaml.safe_load((ROOT / 'configs/sensor_scene.yaml').read_text())
        self.stream = SceneStream('r', self.profile)

    def inputs(self, stamp):
        state = pose(stamp // (10 * MS), stamp)
        state.update(position=[0., 0., 2.], orientation_xyzw=[0., 0., 0., 1.], state_source='ground_truth')
        radar = make_fake_radar('r', stamp // MS, stamp)
        ir = make_fake_infrared('r', stamp // MS, stamp)
        ir['camera_info']['calibration_id'] = self.profile['calibration_id']
        return state, radar, ir

    def add_inputs(self, stamp):
        for kind, value in zip(('state', 'radar', 'infrared'), self.inputs(stamp)):
            self.stream.add(kind, value)

    def test_bundle_preserves_nonzero_mount_and_excludes_supervision(self):
        self.stream.set_clock(100 * MS)
        self.add_inputs(100 * MS)
        bundle, = self.stream.ready()
        self.assertEqual([bundle['context']['T_mapping_source'][i] for i in (3,7,11)], [.8,0.,2.])
        self.assertEqual([bundle['context']['T_mapping_body'][i] for i in (3,7,11)], [0.,0.,2.])
        self.assertEqual(set(bundle), {'header','radar','infrared','state','calibration_id','context',
                                      'radar_ir_delta_ns','pose_age_ns'})
        self.assertEqual(bundle['calibration_id'], self.profile['calibration_id'])

    def test_mount_follows_body_rotation(self):
        state, _, _ = self.inputs(100 * MS)
        state['orientation_xyzw'] = [0.,0.,2**-.5,2**-.5]
        context = scene_context(state, 100 * MS, 'r', self.profile)
        self.assertAlmostEqual(context['T_mapping_source'][3], 0.)
        self.assertAlmostEqual(context['T_mapping_source'][7], .8)

    def test_timeout_never_reuses_late_ir(self):
        self.stream.set_clock(141 * MS)
        self.add_inputs(100 * MS)
        self.assertEqual(self.stream.ready(), [])
        self.assertEqual(self.stream.rejected['pair_timeout'], 1)

    def test_no_pose_or_wrong_ir_time_produces_no_bundle(self):
        self.stream.set_clock(100 * MS)
        state, radar, ir = self.inputs(100 * MS)
        self.stream.add('radar', radar)
        self.stream.add('infrared', ir)
        self.assertEqual(self.stream.ready(), [])
        ir['header']['timestamp'] += 6 * MS
        self.stream.add('state', state)
        self.assertEqual(self.stream.ready(), [])

    def test_reordered_old_radar_cannot_regress_bundle_time(self):
        self.stream.set_clock(120 * MS)
        _, old, _ = self.inputs(100 * MS)
        self.stream.add('radar', old)
        self.add_inputs(120 * MS)
        bundle, = self.stream.ready()
        self.assertEqual(bundle['header']['timestamp'], 120 * MS)
        self.add_inputs(100 * MS)
        self.assertEqual(self.stream.ready(), [])

    def test_clock_reset_locks_stream_and_capacity_is_bounded(self):
        self.stream.set_clock(200 * MS)
        self.stream.set_clock(100 * MS)
        self.add_inputs(100 * MS)
        self.assertEqual(self.stream.ready(), [])
        self.assertTrue(self.stream.failed)
        for index in range(500):self.add_inputs(index * MS)
        self.assertLessEqual(len(self.stream.states), 200)
        self.assertLessEqual(len(self.stream.infrared), 8)
        self.assertLessEqual(len(self.stream.radar), 30)

    def test_foreign_domain_and_bad_calibration_rejected(self):
        for kind, value in zip(('state', 'radar', 'infrared'), self.inputs(100 * MS)):
            value['header']['run_id'] = 'foreign'
            with self.assertRaises(ValueError):self.stream.add(kind, value)
        _, _, ir = self.inputs(100 * MS)
        ir['camera_info']['calibration_id'] = 'unregistered'
        with self.assertRaises(ValueError):self.stream.add('infrared', ir)
        bad = copy.deepcopy(self.profile)
        bad['thermal_optical_xyzw'] = [0,0,0,1]
        with self.assertRaises(ValueError):validate_scene_profile(bad)

    def test_world_has_same_scene_collision_visual_and_explicit_sensor_mounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.world'
            create_world(self.profile, ROOT, path)
            world = ET.parse(path).getroot().find('world')
        hot = world.find("model[@name='hot_crate']/link")
        self.assertEqual(ET.tostring(hot.find('collision/geometry')), ET.tostring(hot.find('visual/geometry')))
        model = world.find("model[@name='sensor_aircraft']")
        radar = model.find("link/sensor[@name='functional_radar']")
        self.assertEqual(radar.findtext('pose'), '0.8 0 0 0 0 0')
        self.assertEqual(radar.find('plugin').get('filename'), 'libufm_scene_radar.so')
        plugins = [p.get('filename') for p in world.iter('plugin')]
        self.assertFalse(any('lidar' in p.lower() for p in plugins))
        self.assertEqual(len(model.findall('link/sensor')), 2)

    def test_empty_return_does_not_invent_free_observation(self):
        from ufm_perception.placeholder import placeholder_infer
        self.stream.set_clock(100 * MS)
        state, radar, ir = self.inputs(100 * MS)
        radar['points'] = []
        for kind, value in (('state',state), ('radar',radar), ('infrared',ir)):self.stream.add(kind,value)
        bundle, = self.stream.ready()
        observation = placeholder_infer(bundle, resolution=self.profile['map']['resolution'],
            shape=self.profile['map']['shape'], origin=self.profile['map']['origin'])
        self.assertEqual(observation['voxels'], [])

    def test_empty_marker_groups_delete_previous_geometry(self):
        from ufm_application.visualization import COLORS
        from rviz_map_markers import build_map_markers
        from visualization_msgs.msg import Marker
        output = build_map_markers(dict(header=dict(frame_id='odom'), resolution=[.5,.5,.5], cells=[]), COLORS)
        self.assertTrue(all(marker.action == Marker.DELETE for marker in output.markers))

    def test_scene_truth_adapter_preserves_source_and_requires_registration(self):
        from ufm_sensors.state_adapter import adapt_scene_ground_truth
        state, _, _ = self.inputs(100 * MS)
        state['header'].update(source_type='simulation', frame_id='scene_world')
        adapted = adapt_scene_ground_truth(state, self.profile['world_to_odom_registration'])
        self.assertEqual(adapted['header']['frame_id'], 'odom')
        self.assertEqual(adapted['state_source'], 'ground_truth')
        self.assertEqual(adapted['position'], state['position'])
        self.assertEqual(state['header']['frame_id'], 'scene_world')
        with self.assertRaises(ValueError):adapt_scene_ground_truth(state, 'assumed_identity')
        state['state_source'] = 'estimated'
        with self.assertRaises(ValueError):adapt_scene_ground_truth(state, self.profile['world_to_odom_registration'])


if __name__ == '__main__':
    unittest.main()

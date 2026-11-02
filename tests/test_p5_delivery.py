"""Fault and evidence guards for the frozen native delivery scenarios."""
import copy
import unittest

from p5_contract import load_pair
from p5_delivery_checks import graph_errors, native_separation, verify_delivery


class DeliveryChecksTest(unittest.TestCase):
    def setUp(self):
        self.graph = [[['/clock', ['/p5_source']]],
            [['/uav/perception/occupancy', ['/p5_map']], ['/clock', ['/p5_terrain']]],
            [['/uav/map/query', ['/p5_map']], ['/uav/terrain/v1/query', ['/p5_terrain']]]]
        self.identities = {'/p5_map': 'run', '/p5_terrain': 'run'}
        self.bus = [[1, '/p5_map', 'o', 'TCPROS', '/uav/perception/occupancy', True]]

    def test_clock_conflict_and_missing_or_wrong_subscriber_fail(self):
        self.assertEqual(graph_errors(self.graph, self.identities, 'run', self.bus), [])
        self.graph[1][1][1].append('/p5_map')
        self.assertEqual(graph_errors(self.graph, self.identities, 'run', self.bus), [])
        self.graph[0][0][1].append('/foreign')
        self.assertIn('clock_source_conflict', graph_errors(self.graph, self.identities, 'run', self.bus))
        self.graph[0][0][1].pop()
        self.bus[0][1] = '/observer'
        self.assertIn('mapping_connection_missing', graph_errors(self.graph, self.identities, 'run', self.bus))
        self.bus[0][1] = '/p5_map'
        self.bus[0][5] = False
        self.assertIn('mapping_connection_missing', graph_errors(self.graph, self.identities, 'run', self.bus))

    def test_wrong_identity_training_and_cross_layer_graph_fail(self):
        self.identities['/p5_map'] = 'previous'
        self.assertIn('run_identity:/p5_map', graph_errors(self.graph, self.identities, 'run', self.bus))
        self.graph[1].append(['/uav/sensors/observed_mask', ['/p5_map']])
        errors = graph_errors(self.graph, self.identities, 'run', self.bus)
        self.assertIn('supervision_in_online_graph', errors)
        self.assertIn('subscription_boundary:/p5_map', errors)

    def test_recovery_requires_actual_old_binding_and_new_instance(self):
        _, expected = load_pair()
        answer = next(c for c in expected['cases'] if c['id'] == 'S09.recover_view')
        rows = [dict(event_id=c['after'], values=copy.deepcopy(c['values'])) for c in answer['checks']]
        rows[0]['values']['terrain.instance'] = 'new-instance'
        for old in (None, '', True):
            with self.assertRaises(ValueError):
                verify_delivery(answer, rows, old)
        self.assertTrue(verify_delivery(answer, rows, 'old-instance')['passed'])
        self.assertFalse(verify_delivery(answer, rows, 'new-instance')['passed'])
        self.assertFalse(verify_delivery(answer, rows[1:], 'old-instance')['passed'])
        with self.assertRaises(ValueError):
            verify_delivery(answer, rows + [rows[0]], 'old-instance')

    def test_cleanup_and_preflight_cannot_be_static_successes(self):
        _, expected = load_pair()
        answer = next(c for c in expected['cases'] if c['id'] == 'S09.clock_conflict')
        rows = [dict(event_id='preflight', values={'graph.accepted': True}),
                dict(event_id='cleanup', values={'cleanup.owned_only': True})]
        self.assertFalse(verify_delivery(answer, rows)['passed'])
        rows[0]['values']['graph.accepted'] = False
        rows[1]['values']['cleanup.owned_only'] = False
        self.assertFalse(verify_delivery(answer, rows)['passed'])

    def native_inputs(self):
        scene = dict(passed=True, commands=[dict(name=n, args=['roscore', '-p', '11733'])
            for n in ('roscore', 'gazebo-server', 'gazebo-window', 'rviz-window')])
        terrain = dict(passed=True, commands=[dict(name=n, args=['roscore', '-p', '11735'])
            for n in ('roscore', 'rviz')])
        def config(displays):
            return {'Visualization Manager': {'Displays': displays}}
        return scene, terrain, config([{'Topic': '/uav/sensors/radar/raw'},
            {'Image Topic': '/uav/sensors/infrared/raw'}]), config([{'Marker Topic': '/uav/terrain/v1/markers'}])

    def test_native_views_require_actual_successful_window_processes(self):
        values = self.native_inputs()
        self.assertEqual(native_separation(*values),
                         {'view.native': True, 'view.unregistered_overlay': False})
        values[0]['passed'] = False
        self.assertFalse(native_separation(*values)['view.native'])
        values[0]['passed'] = True
        values[0]['commands'].pop()
        self.assertFalse(native_separation(*values)['view.native'])

    def test_unregistered_overlay_detects_marker_image_and_master_mix(self):
        for key, topic in [('Marker Topic', '/uav/terrain/v1/markers'),
                           ('Image Topic', '/uav/terrain/recorded/markers')]:
            values = self.native_inputs()
            values[2]['Visualization Manager']['Displays'].append({key: topic})
            self.assertTrue(native_separation(*values)['view.unregistered_overlay'])
        values = self.native_inputs()
        values[1]['commands'][0]['args'][-1] = '11733'
        self.assertTrue(native_separation(*values)['view.unregistered_overlay'])


if __name__ == '__main__':
    unittest.main()

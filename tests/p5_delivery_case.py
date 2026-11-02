"""Actual S09 assembly failures and fresh run probes through public ROS contracts."""
import time

from p5_contract import ROOT
from p5_delivery_checks import graph_errors
from p5_payloads import terrain_dataset
from p5_ros_case import Case
from sim01b_runtime import write_json


class DeliveryCase(Case):
    def start_generation(self, run_id, missing=False, bad_identity=False):
        import sys
        from ufm_application.terrain_client import TerrainClient
        self.run_id = run_id
        self.client = TerrainClient(self.transport, 'm5-terrain-fixture', run_id, 'sim:' + run_id)
        self.ros.set_param('/perf01a_require_observers', False)
        self.ros.set_param('/ufm_diagnostics_enabled', True)
        write_json(self.directory / 'dataset.json', terrain_dataset(self.inputs, run_id))
        configured = 'foreign-' + run_id if bad_identity else run_id
        self.map_name = 'mapping-' + str(self.terrain_generation + 1)
        self.ros.delete_param('/p5_map/ready') if self.ros.has_param('/p5_map/ready') else None
        command = [sys.executable, '-B', str(ROOT /
            'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
            '__name:=p5_map', '_run_id:=' + configured, '_enable_query:=true',
            '_free_threshold:=0.3', '_occupied_threshold:=0.7']
        if missing:
            from uav_fusionmap_msgs.msg import OccupancyObservation
            # Keep the wrongly remapped node idle but normally stoppable after graph rejection.
            self.missing_publisher = self.ros.Publisher('/p5/missing/occupancy', OccupancyObservation, queue_size=1)
            command.append('/uav/perception/occupancy:=/p5/missing/occupancy')
        self.processes.spawn(self.map_name, command)
        self.start_terrain()
        self.ros.wait_for_service('/uav/map/query', timeout=10.)
        self.wait(lambda: self.ros.get_param('/p5_map/ready', '') == configured, 'map readiness', 15.)
        self.wait(lambda: self.node_outputs_ready('/p5_map', {'/uav/map/snapshot': 1,
                  '/uav/perf/events': 1}), 'map output barriers')

    def audit(self, label):
        graph = self.ros.get_master().getSystemState()[2]
        identities = {node: self.ros.get_param(node + '/ready', None)
                      for node in ('/p5_map', '/p5_terrain')}
        bus = self.ros.get_master().lookupNode('/p5_source')[2]
        from sim01b_runtime import rpc_proxy
        connections = rpc_proxy(bus).getBusInfo('/p5_delivery')[2]
        errors = graph_errors(graph, identities, self.run_id, connections)
        write_json(self.directory / ('graph-' + label + '.json'),
                   dict(system=graph, identities=identities, connections=connections, errors=errors))
        return errors

    def map_query(self, run_id):
        from ufm_application.query_client import MapQueryClient
        from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
        from ufm_ros_contract.query_codec import from_ros_query_result
        request = dict(map_id='perf01a-local', frame_id='odom', run_id=run_id,
                       clock_id='sim:' + run_id, query_timestamp=100_000_000,
                       point=[8.25, .25, .25], max_age_ns=50_000_000)
        def call(value):
            response = self.ros.ServiceProxy('/uav/map/query', MapQuery)(MapQueryRequest(**value))
            return from_ros_query_result(response.result)
        result = MapQueryClient(call).query(**request)
        self.append('/p5/delivery/map-query', dict(request=request, result=result))
        return result

    def recover(self, identity, previous_run):
        from check_local_map_query_ros import fixture
        from ufm_ros_contract.perf01a_codec import to_ros_occupancy
        self.start_generation(previous_run)
        if self.audit('previous'):
            raise ValueError('previous assembly rejected')
        self.advance(100_000_000)
        self.occupancy.publish(to_ros_occupancy(fixture(previous_run, 0, 100_000_000)))
        self.wait(lambda: self.latest('/uav/map/snapshot') is not None, 'previous map evidence')
        old_map = self.map_query(previous_run)
        if old_map['status'] != 'occupied' or old_map['revision'] != 1:
            raise ValueError('actual previous map not established')
        self.query_terrain(100_000_000, {'cell': 0})
        group = self.client.sample_group()
        if group is None or self.terrain_result['status'] != 'valid':
            raise ValueError('actual previous pinned terrain not established')
        old_client = self.client
        write_json(self.directory / 'previous-run.json', dict(run_id=previous_run, map=old_map,
                   group=group, query=self.terrain_result))
        self.stop_terrain()
        self.processes.stop(self.map_name)
        self.ros.delete_param('/p5_terrain/ready')
        self.start_generation(identity)
        if self.audit('new'):
            raise ValueError('new assembly rejected')
        # Query before any occupancy seed in the new process; stale observer history is never used.
        fresh = self.map_query(identity)
        previous_on_new = self.map_query(previous_run)
        self.advance(100_000_000)
        self.query_terrain(100_000_000, {'cell': 0})
        new = self.terrain_result
        self.previous_group = group
        self.query_terrain(100_000_000, {'cell': 0, 'pin': 'previous_group'})
        pin = self.terrain_result
        status = self.latest('/uav/terrain/v1/status')
        accepted = old_client.receive_status(status)
        isolated = (identity != previous_run and fresh['revision'] == 0 and
                    fresh['status'] == previous_on_new['status'] == 'unavailable' and
                    fresh['probability'] is None and fresh['last_observed_timestamp'] is None and
                    new['status'] == 'valid' and new['provider_instance_id'] != group['provider_instance_id'] and
                    pin['status'] == 'unavailable' and pin['reason'] == 'provider_instance_mismatch' and
                    not accepted and old_client.current_group() is None)
        write_json(self.directory / 'new-run.json', dict(run_id=identity, map=fresh,
            previous_query_on_new=previous_on_new, terrain=new, old_pin_on_new=pin,
            old_client_accepted_status=accepted, old_client_group=old_client.current_group(), isolated=isolated))
        if not isolated:
            raise ValueError('new run inherits previous evidence or pin')
        return {'run.inherits': not isolated, 'map.revision': fresh['revision'],
                'terrain.instance': new['provider_instance_id']}

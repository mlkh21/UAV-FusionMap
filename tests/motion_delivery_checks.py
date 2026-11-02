"""Independent motion-time geometry oracle and public receipt checks (no live producer)."""
import numpy as np
from scipy.spatial.transform import Rotation
from uav_fusionmap_msgs.msg import SensorBundle
from ufm_ros_contract.perf01a_codec import from_ros_bundle


def bundle_summary(msg):
    return dict(timestamp=msg.header.timestamp, sample_id=msg.header.sample_id,
                radar_points=len(msg.radar.points))


def check_graph(graph):
    publishers=dict(graph[0])
    for topic,node in (('/clock','/sim_motion_host'),('/uav/sim/state','/sim_motion_host'),
            ('/uav/sensors/state','/state_adapter'),('/tf','/state_adapter'),
            ('/uav/sensors/radar/raw','/gazebo'),('/uav/sensors/infrared/raw','/gazebo'),
            ('/uav/sensors/bundle','/scene_sensor_adapter'),('/uav/perception/occupancy','/perf01a_placeholder_perception'),
            ('/uav/map/snapshot','/perf01a_mapping')):
        if publishers.get(topic)!=[node]:raise ValueError('motion_graph_authority:'+topic)
    for topic,nodes in graph[1]:
        if '/perf01a_mapping' in nodes and topic not in ('/clock','/uav/perception/occupancy'):
            raise ValueError('motion_mapping_cross_layer_subscription')
    for section in graph[:2]:
        for topic,nodes in section:
            if any(token in name.lower() for name in [topic,*nodes] for token in ('lidar','observed_mask','target','training')):
                raise ValueError('motion_training_graph')


def verify_chain(run, rows, expected_count, profile):
    bundles = [from_ros_bundle(SensorBundle().deserialize((run/r['wire']).read_bytes()))
               for r in rows.get('bundle', [])]
    observations = [r['value'] for r in rows.get('occupancy', [])]
    snapshots = [r['value'] for r in rows.get('snapshot', [])]
    if not all(len(values) == expected_count for values in (bundles, observations, snapshots)):
        raise ValueError('motion_chain_count')
    sources = {r['value']['state']['header']['timestamp']:r['value']['state'] for r in rows['applied']}
    point_count = 0
    for number, (bundle, observation, snapshot) in enumerate(zip(bundles, observations, snapshots), 1):
        stamp = number*100000000
        if any(v['header']['timestamp'] != stamp for v in (bundle, observation, snapshot)):
            raise ValueError('motion_chain_timestamp')
        if bundle['radar_ir_delta_ns'] != 0 or bundle['pose_age_ns'] != 0:
            raise ValueError('motion_chain_not_same_tick')
        source = sources[stamp]
        body = np.eye(4)
        body[:3,:3] = Rotation.from_quat(source['orientation_xyzw']).as_matrix()
        body[:3,3] = source['position']
        radar = body.copy()
        radar[:3,3] += body[:3,:3] @ np.array([.8,0.,0.])
        context = bundle['context']
        for name, wanted in (('T_mapping_source',radar),('T_mapping_body',body)):
            if not np.allclose(np.array(context[name]).reshape(4,4), wanted, rtol=0, atol=1e-9):
                raise ValueError('motion_observation_context')
        if (context['reference_timestamp'] != stamp or context['mapping_frame_id'] != 'odom' or
                context['source_frame_id'] != 'radar' or bundle['state']['state_source'] != 'ground_truth'):
            raise ValueError('motion_context_identity')
        points = np.array([[p[k] for k in ('x','y','z')] for p in bundle['radar']['points']])
        transformed = points @ radar[:3,:3].T + radar[:3,3] if len(points) else np.empty((0,3))
        geometry = profile['map']
        indices = np.floor((transformed-geometry['origin'])/geometry['resolution']).astype(int)
        wanted = {tuple(i) for i in indices if all(0 <= i[a] < geometry['shape'][a] for a in range(3))}
        actual = {tuple(v['index']) for v in observation['voxels']}
        if actual != wanted or observation['observed_domain_source'] != 'fixture_radar_point':
            raise ValueError('motion_placeholder_independent_voxels')
        if (observation['context']['T_mapping_body'] != context['T_mapping_body'] or
                observation['context']['reference_timestamp'] != stamp):
            raise ValueError('motion_occupancy_context_lost')
        for voxel in observation['voxels']:
            if (not voxel['observed'] or abs(voxel['probability']-.9)>1e-6 or
                    voxel['confidence'] is not None or voxel['uncertainty']['status'] != 'unavailable'):
                raise ValueError('motion_invented_quality_or_free')
        if snapshot['revision'] != number or any(c['probability'] < .7 or not c['observed'] for c in snapshot['cells']):
            raise ValueError('motion_snapshot_evidence')
        point_count += len(points)
    for kind, caller in (('bundle','/scene_sensor_adapter'),('occupancy','/perf01a_placeholder_perception'),
                          ('snapshot','/perf01a_mapping')):
        if any(r['caller'] != caller for r in rows.get(kind, [])):
            raise ValueError('motion_business_source')
    return dict(passed=True, bundles=len(bundles), observations=len(observations), snapshots=len(snapshots),
        transformed_radar_points=point_count, exact_tick_context=True, occupied_only=True), observations, snapshots


def verify_public_replay(observations, snapshots, run_id, settings, queries):
    from ufm_mapping.replay import equivalent,replay_observations
    rebuilt=replay_observations(observations,run_id,settings,queries)
    if not equivalent(rebuilt['snapshots'],snapshots) or not equivalent(rebuilt['queries'],queries):
        raise ValueError('motion_public_replay_differs')
    return rebuilt

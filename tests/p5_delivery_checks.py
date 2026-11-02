"""Independent S09 graph, recovery binding and native separation checks."""
from p5_checkpoints import compare


def graph_errors(system, identities, run_id, bus):
    published, subscribed, services = map(dict, system)
    errors = []
    if set(published.get('/clock', [])) != {'/p5_source'}:
        errors.append('clock_source_conflict')
    for node, topics in {'/p5_map': {'/uav/perception/occupancy'},
                         '/p5_terrain': {'/clock'}}.items():
        actual = {topic for topic, nodes in subscribed.items() if node in nodes}
        if node == '/p5_map':
            actual.discard('/clock')  # rospy adds its infrastructure clock subscription.
        if actual != topics:
            errors.append('subscription_boundary:' + node)
        if identities.get(node) != run_id:
            errors.append('run_identity:' + node)
    if not any(len(row) >= 6 and row[1] == '/p5_map' and row[2] == 'o' and
               row[4] == '/uav/perception/occupancy' and row[5] is True for row in bus):
        errors.append('mapping_connection_missing')
    for name in ('/uav/map/query', '/uav/terrain/v1/query'):
        if name not in services:
            errors.append('service_missing:' + name)
    if any(any(token in topic.lower() for token in ('lidar', 'training', 'observed_mask', 'target'))
           for topic in set(published) | set(subscribed)):
        errors.append('supervision_in_online_graph')
    return errors


def verify_delivery(expected, receipts, previous_instance=None):
    by_event = {row['event_id']: row for row in receipts}
    if len(by_event) != len(receipts):
        raise ValueError('duplicate actual event receipt')
    bindings = {}
    if expected['id'] == 'S09.recover_view':
        if type(previous_instance) is not str or not previous_instance.strip():
            raise ValueError('actual previous provider instance required')
        bindings['terrain.instance'] = previous_instance
    checks = []
    for check in expected['checks']:
        row = by_event.get(check['after'])
        errors = ['event missing'] if row is None else compare(row['values'], check['values'], bindings)
        checks.append(dict(event_id=check['after'], passed=not errors, errors=errors,
                           expected=check['values'], actual=None if row is None else row['values']))
    return dict(passed=all(row['passed'] for row in checks), checks=checks,
                checked_values=sum(len(row['expected']) for row in checks), bindings=bindings)


def native_separation(scene_manifest, terrain_manifest, scene_config, terrain_config):
    scene = {row['name'] for row in scene_manifest['commands']}
    terrain = {row['name'] for row in terrain_manifest['commands']}
    native = (scene_manifest['passed'] and terrain_manifest['passed'] and
              {'gazebo-server', 'gazebo-window', 'rviz-window'} <= scene and 'rviz' in terrain)
    scene_displays = scene_config['Visualization Manager']['Displays']
    terrain_displays = terrain_config['Visualization Manager']['Displays']
    scene_topics = {value for row in scene_displays for key, value in row.items() if key.endswith('Topic')}
    terrain_topics = {value for row in terrain_displays for key, value in row.items() if key.endswith('Topic')}
    scene_master = next(row['args'][-1] for row in scene_manifest['commands'] if row['name'] == 'roscore')
    terrain_master = next(row['args'][-1] for row in terrain_manifest['commands'] if row['name'] == 'roscore')
    # Independent Masters and view configurations provide no scene/terrain registration.
    overlay = (any('/terrain' in topic for topic in scene_topics) or
               any('/radar' in topic or '/infrared' in topic for topic in terrain_topics) or
               scene_master == terrain_master)
    return {'view.native': bool(native), 'view.unregistered_overlay': bool(overlay)}

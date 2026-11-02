"""Bounded public-output acceptance with an isolated fixture pose perturbation."""
import argparse
import collections
import json
import math
from pathlib import Path
import struct
import sys
import threading
import time

import rospy
from sensor_msgs.msg import Image, PointCloud2
from sensor_msgs.point_cloud2 import read_points
from uav_fusionmap_msgs.msg import MapSnapshot, SensorBundle
from ufm_ros_contract.perf01a_codec import from_ros_bundle, from_ros_snapshot
import yaml
from PIL import Image as PILImage


def box_distance(point, center, size):
    delta = [abs(point[a] - center[a]) - size[a] / 2 for a in range(3)]
    return math.sqrt(sum(max(v, 0.) ** 2 for v in delta)) if max(delta) > 0 else -max(delta)


def surface_distance(point, objects):
    distances = [abs(point[2])]
    for obj in objects:
        if obj['kind'] == 'box':
            distances.append(box_distance(point, obj['position'], obj['size']))
        else:
            x, y, z = [point[a] - obj['position'][a] for a in range(3)]
            delta = [math.hypot(x, y) - obj['radius'], abs(z) - obj['length'] / 2]
            distances.append(math.hypot(*[max(v, 0) for v in delta]) if max(delta) > 0 else -max(delta))
    return min(distances)


def reject_supervision(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('lidar', 'target', 'observed_mask'):raise ValueError('training input: ' + key)
            reject_supervision(item)
    elif isinstance(value, (list, tuple)):
        for item in value:reject_supervision(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('sensor_scene_acceptance')
    profile = yaml.safe_load((args.run / 'profile.yaml').read_text())
    latest, counts, errors = {}, collections.Counter(), []
    lock = threading.Lock()

    def receive(message, key):
        with lock:
            latest[key] = message
            counts[key] += 1

    subscriptions = [rospy.Subscriber(topic, cls, receive, key, queue_size=1, buff_size=4 * 1024 * 1024)
        for topic, cls, key in (('/uav/sensors/radar/raw', PointCloud2, 'radar'),
            ('/uav/sensors/infrared/raw', Image, 'infrared'), ('/uav/sensors/bundle', SensorBundle, 'bundle'),
            ('/uav/map/snapshot', MapSnapshot, 'map'))]
    deadline = time.monotonic() + 65.
    result = dict(passed=False, python=sys.executable, errors=errors)
    try:
        while time.monotonic() < deadline and not rospy.is_shutdown():
            with lock:
                if len(latest) == 4 and min(counts.values()) >= 5:
                    samples = dict(latest)
                    break
            time.sleep(.1)
        else:raise RuntimeError('missing scene streams: ' + str(dict(counts)))
        radar = samples['radar']
        points = list(read_points(radar, field_names=('x', 'y', 'z', 'doppler', 'power'), skip_nans=False))
        if radar.header.frame_id != 'radar' or len(points) < 100:raise ValueError('Radar cloud missing/frame mismatch')
        if not all(math.isfinite(v) for point in points for v in point):raise ValueError('nonfinite Radar')
        world = [[point[a] + profile['radar_mount_xyz'][a] + profile['body_pose'][a] for a in range(3)]
                 for point in points]
        distances = sorted(surface_distance(point, profile['objects']) for point in world)
        if distances[int(len(distances) * .99)] > .05:raise ValueError('Radar does not match scene surfaces')
        if max(abs(point[3]) for point in points) > .001:raise ValueError('static fixture Doppler not zero')
        image = samples['infrared']
        if image.encoding != '32FC1' or image.header.frame_id != 'thermal_optical':
            raise ValueError('IR layout/frame mismatch')
        values = struct.unpack(('<' if not image.is_bigendian else '>') + str(image.width * image.height) + 'f', image.data)
        if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):raise ValueError('invalid IR intensity')
        focal = image.width / (2 * math.tan(profile['infrared']['horizontal_fov_rad'] / 2))
        roi = {}
        for name in ('hot_crate', 'cold_pillar', 'warm_column'):
            obj = next(o for o in profile['objects'] if o['name'] == name)
            x = obj['position'][0] - profile['body_pose'][0] - profile['thermal_mount_xyz'][0]
            y = obj['position'][1] - profile['body_pose'][1]
            z = obj['position'][2] - profile['body_pose'][2]
            u, v = round(image.width / 2 - focal * y / x), round(image.height / 2 - focal * z / x)
            patch = [values[row * image.width + col] for row in range(v - 2, v + 3) for col in range(u - 2, u + 3)]
            roi[name] = dict(pixel=[u, v], mean=sum(patch) / len(patch))
        if not roi['hot_crate']['mean'] > roi['warm_column']['mean'] > roi['cold_pillar']['mean'] + .1:
            raise ValueError('thermal material contrast incorrect: ' + str(roi))
        PILImage.frombytes('L', (image.width, image.height), bytes(round(v * 255) for v in values)).resize(
            (960, 720)).save(args.run / 'figures/infrared-fixture.png')
        bundle = from_ros_bundle(samples['bundle'])
        reject_supervision(bundle)
        if bundle['header']['run_id'] != args.run_id or bundle['calibration_id'] != profile['calibration_id']:
            raise ValueError('bundle identity mismatch')
        transform = bundle['context']['T_mapping_source']
        if any(abs(transform[a * 4 + 3] - profile['body_pose'][a] - profile['radar_mount_xyz'][a]) > .001 for a in range(3)):
            raise ValueError('Radar mount transform lost')
        snapshot = from_ros_snapshot(samples['map'])
        cells = snapshot['cells']
        if not cells or any(c['probability'] < .7 or not c['observed'] for c in cells):
            raise ValueError('placeholder map missing occupied observations or invented free cells')
        # Move only our named fixture via Gazebo's standard API, then restore it.
        from gazebo_msgs.msg import ModelState
        from gazebo_msgs.srv import GetModelState, SetModelState
        rospy.wait_for_service('/gazebo/get_model_state', timeout=5.)
        original = rospy.ServiceProxy('/gazebo/get_model_state', GetModelState)('hot_crate', 'world')
        if not original.success:raise RuntimeError('fixture model unavailable')
        setter = rospy.ServiceProxy('/gazebo/set_model_state', SetModelState)
        moved = ModelState(model_name='hot_crate', reference_frame='world', pose=original.pose)
        moved.pose.position.y += 1.5
        with lock:before_move = dict(counts)
        try:
            if not setter(moved).success:raise RuntimeError('fixture pose perturbation failed')
            until = time.monotonic() + 10.
            while time.monotonic() < until:
                with lock:
                    if all(counts[k] >= before_move[k] + 5 for k in ('radar', 'infrared')):
                        changed = dict(latest)
                        break
                time.sleep(.05)
            else:raise RuntimeError('sensors stopped after fixture pose perturbation')
            moved_image = changed['infrared']
            moved_values = struct.unpack('<' + str(moved_image.width * moved_image.height) + 'f', moved_image.data)
            image_delta = sum(abs(a - b) > .05 for a, b in zip(values, moved_values))
            moved_points = list(read_points(changed['radar'], field_names=('x','y','z','doppler','power')))
            radar_delta = abs(len(points) - len(moved_points)) + sum(
                any(abs(a - b) > .01 for a, b in zip(p[:3], q[:3])) for p, q in zip(points, moved_points))
            if image_delta < 500 or radar_delta < 50:raise ValueError('scene perturbation not visible in both sensors')
            PILImage.frombytes('L', (moved_image.width, moved_image.height), bytes(round(v * 255) for v in moved_values)).resize(
                (960,720)).save(args.run / 'figures/infrared-fixture-moved.png')
        finally:
            moved.pose.position.y -= 1.5
            if not setter(moved).success:raise RuntimeError('fixture pose restoration failed')
        result.update(passed=True, counts=dict(counts), radar_points=len(points),
            surface_distance_p99_m=distances[int(len(distances) * .99)], infrared_range=[min(values), max(values)],
            thermal_regions=roi, bundle_calibration=bundle['calibration_id'],
            radar_to_odom_translation=[transform[a * 4 + 3] for a in range(3)],
            map_cells=len(cells), map_sources=snapshot['source_types'],
            pose_perturbation=dict(model='hot_crate', translation_y_m=1.5,
                changed_ir_pixels=image_delta, changed_radar_points=radar_delta, restored=True),
            checks=['scene surface geometry', 'separate thermal material contrast', 'Radar nonzero mount',
                    'Radar/IR bundle without training supervision', 'occupied-only placeholder map',
                    'scene pose perturbation changes both sensors and is restored'])
    except Exception as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
        result['counts'] = dict(counts)
        result['latest_stamps'] = {key:value.header.stamp.to_nsec() for key,value in latest.items()
                                   if key in ('radar', 'infrared')}
    (args.run / 'scene-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    sys.exit(main())

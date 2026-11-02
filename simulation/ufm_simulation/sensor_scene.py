"""One explicit scene description generates Gazebo geometry and sensor placement."""
from pathlib import Path
import xml.etree.ElementTree as ET


def element(parent, tag, text=None, **attributes):
    child = ET.SubElement(parent, tag, attributes)
    if text is not None:
        child.text = ' '.join(str(v) for v in text) if isinstance(text, (list, tuple)) else str(text)
    return child


def create_world(profile, root, destination):
    if profile['schema_version'] != 'sensor_scene_fixture.v1':
        raise ValueError('explicit sensor scene profile required')
    root = Path(root)
    sdf = ET.Element('sdf', version='1.6')
    world = element(sdf, 'world', name='sensor_scene_fixture')
    physics = element(world, 'physics', name='ode', type='ode')
    element(physics, 'max_step_size', .001)
    element(physics, 'real_time_update_rate', 1000)
    scene = element(world, 'scene')
    element(scene, 'ambient', [.55, .55, .55, 1])
    element(scene, 'background', [.08, .08, .08, 1])
    light = element(world, 'light', name='sun', type='directional')
    element(light, 'pose', [0, 0, 20, 0, 0, 0])
    element(light, 'diffuse', [.8, .8, .8, 1])
    element(light, 'direction', [-.4, .2, -1])
    gui = element(world, 'gui')
    element(gui, 'plugin', name='scene_screenshot', filename='libufm_scene_gui.so')
    camera = element(gui, 'camera', name='overview')
    element(camera, 'pose', profile.get('overview_camera_pose', [-16, -28, 20, 0, .45, .83]))
    element(camera, 'view_controller', 'orbit')

    def geometry(parent, obj):
        geo = element(parent, 'geometry')
        shape = element(geo, obj['kind'])
        if obj['kind'] == 'box':element(shape, 'size', obj['size'])
        elif obj['kind'] == 'cylinder':
            element(shape, 'radius', obj['radius'])
            element(shape, 'length', obj['length'])
        else:raise ValueError('scene supports explicit boxes/cylinders only')

    objects = [profile.get('ground', dict(name='ground', kind='box', position=[10, 0, -.15],
                    size=[60, 40, .3], material='FusionAmbient'))] + profile['objects']
    for obj in objects:
        model = element(world, 'model', name=obj['name'])
        element(model, 'static', 'true')
        element(model, 'pose', obj['position'] + [0, 0, 0])
        link = element(model, 'link', name='body')
        geometry(element(link, 'collision', name='collision'), obj)
        visual = element(link, 'visual', name='visual')
        geometry(visual, obj)
        script = element(element(visual, 'material'), 'script')
        element(script, 'uri', (root / 'simulation/sensor_scene_media/materials/scripts').as_uri())
        element(script, 'name', obj['material'])

    model = element(world, 'model', name='sensor_aircraft')
    element(model, 'static', 'true')
    element(model, 'pose', profile['body_pose'])
    link = element(model, 'link', name='base_link')
    mesh_path = root / '.runtime/src/px4-v1.13.3/Tools/sitl_gazebo/models/plane/meshes/body.dae'
    if not mesh_path.is_file():raise ValueError('existing plane visual mesh missing')
    visual = element(link, 'visual', name='airframe')
    mesh = element(element(visual, 'geometry'), 'mesh')
    element(mesh, 'uri', mesh_path.as_uri())
    element(mesh, 'scale', profile.get('aircraft_visual_scale', [1, 1, 1]))
    pose = element(model, 'plugin', name='scene_pose', filename='libufm_scene_pose.so')
    element(pose, 'topic', '/uav/scene/body_odometry')

    radar = element(link, 'sensor', name='functional_radar', type='ray')
    element(radar, 'pose', profile['radar_mount_xyz'] + [0, 0, 0])
    element(radar, 'always_on', 'true')
    element(radar, 'update_rate', profile['frequency_hz'])
    ray = element(radar, 'ray')
    scan = element(ray, 'scan')
    for axis in ('horizontal', 'vertical'):
        target = element(scan, axis)
        element(target, 'samples', profile['radar'][axis + '_samples'])
        element(target, 'resolution', 1)
        element(target, 'min_angle', -profile['radar'][axis + '_fov_rad'] / 2)
        element(target, 'max_angle', profile['radar'][axis + '_fov_rad'] / 2)
    distance = element(ray, 'range')
    element(distance, 'min', profile['radar']['min_range_m'])
    element(distance, 'max', profile['radar']['max_range_m'])
    element(distance, 'resolution', .01)
    plugin = element(radar, 'plugin', name='functional_radar', filename='libufm_scene_radar.so')
    if 'measurement_model' in profile['radar']:
        for key in ('measurement_model', 'detection_probability', 'detection_distance_m', 'range_std_m',
                    'angle_std_rad', 'doppler_std_mps', 'noise_seed', 'max_points'):
            element(plugin, key, profile['radar'][key])

    thermal = element(link, 'sensor', name='functional_infrared', type='camera')
    element(thermal, 'pose', profile['thermal_mount_xyz'] + [0, 0, 0])
    element(thermal, 'always_on', 'true')
    element(thermal, 'update_rate', profile['frequency_hz'])
    camera = element(thermal, 'camera')
    element(camera, 'horizontal_fov', profile['infrared']['horizontal_fov_rad'])
    image = element(camera, 'image')
    element(image, 'width', profile['infrared']['width'])
    element(image, 'height', profile['infrared']['height'])
    element(image, 'format', 'R8G8B8')
    clip = element(camera, 'clip')
    element(clip, 'near', .1)
    element(clip, 'far', profile['infrared'].get('far_clip_m', 60))
    element(thermal, 'plugin', name='functional_ir', filename='libufm_scene_ir.so')
    ET.ElementTree(sdf).write(destination, encoding='utf-8', xml_declaration=True)

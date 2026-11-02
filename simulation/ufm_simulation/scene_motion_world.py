"""Explicit controlled variant; the existing static generator and entry stay unchanged."""
import xml.etree.ElementTree as ET
from .sensor_scene import create_world, element


def create_motion_world(scene, root, destination):
    create_world(scene, root, destination)
    tree = ET.parse(destination)
    world = tree.getroot().find('world')
    model = world.find("model[@name='sensor_aircraft']")
    model.remove(model.find("plugin[@name='scene_pose']"))
    element(model, 'plugin', name='scene_step', filename='libufm_scene_step.so')
    for sensor in model.findall('link/sensor'):
        # Render/ray substeps prepare actual buffers. Only exact 100 ms ticks publish raw/ACK.
        sensor.find('update_rate').text = '1000'
        element(sensor.find('plugin'), 'controlled_motion', 'true')
    tree.write(destination, encoding='utf-8', xml_declaration=True)

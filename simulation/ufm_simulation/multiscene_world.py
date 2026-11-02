"""Explicit suite assembly; the legacy scene generator retains its default ground."""
import copy
import xml.etree.ElementTree as ET

from .motion_suite import validate_geometry
from .scene_motion_world import create_motion_world


def assemble_scene(scene, spec):
    validate_geometry(spec['geometry_id'], spec['geometry'])
    result = copy.deepcopy(scene)
    result['body_pose'] = [0., 0., 8., 0., 0., 0.]
    if not spec['geometry']['inherit_legacy']:
        result['objects'] = copy.deepcopy(spec['geometry']['objects'])
        result['map'].update(copy.deepcopy(spec['map_settings']))
        result['map']['map_id'] = 'sensor-scene-' + spec['case_id']
    return result


def create_suite_world(scene, spec, root, destination):
    validate_geometry(spec['geometry_id'], spec['geometry'])
    if not spec['geometry']['inherit_legacy'] and scene['objects'] != spec['geometry']['objects']:
        raise ValueError('suite scene differs from named geometry')
    create_motion_world(scene, root, destination)
    if not spec['geometry']['include_ground']:
        tree = ET.parse(destination)
        world = tree.getroot().find('world')
        ground = world.find("model[@name='ground']")
        if ground is None:
            raise ValueError('legacy generator did not create expected ground')
        world.remove(ground)
        tree.write(destination, encoding='utf-8', xml_declaration=True)


def create_suite_ic(source, destination, ic_degrees, speed_mps):
    tree = ET.parse(source)
    # JSBSim v1 applies gamma after theta and would reset the requested pitch.
    if ic_degrees[1] != 0:
        gamma=tree.getroot().find('gamma')
        if gamma is not None:tree.getroot().remove(gamma)
    tree.getroot().find('altitude').text = '8'
    tree.getroot().find('vt').text = str(speed_mps/.3048)
    for name, value in zip(('phi','theta','psi'), ic_degrees):
        field = tree.getroot().find(name)
        if field is None or field.attrib.get('unit') != 'DEG':
            raise ValueError('suite IC angle units missing')
        field.text = str(value)
    tree.write(destination, encoding='utf-8', xml_declaration=True)

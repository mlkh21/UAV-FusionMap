"""Synthetic world-point occupancy packets; independent of candidate window calculations."""
import copy
import math

from m2_fixture import observation


def motion_observation(spec, run_id, sequence, kind='occupied', body=(0., 0., 0.),
                       points=((8.25, .25, .25),), yaw=0., origin=None, stamp=None):
    row = observation(spec, run_id, sequence, kind)
    if stamp is not None:
        row['header']['timestamp'] = stamp
        row['context']['reference_timestamp'] = stamp
    if origin is not None:
        row['origin'] = list(origin)
    cosine, sine = math.cos(yaw), math.sin(yaw)
    row['context']['T_mapping_body'] = [cosine, -sine, 0., body[0],
        sine, cosine, 0., body[1], 0., 0., 1., body[2], 0., 0., 0., 1.]
    if row['voxels']:
        template = row['voxels'][0]
        row['voxels'] = []
        for point in points:
            index = [math.floor((point[axis] - row['origin'][axis]) / spec['resolution'][axis])
                     for axis in range(3)]
            if any(not 0 <= index[axis] < spec['shape'][axis] for axis in range(3)):
                raise ValueError('motion fixture world point outside its explicit observation grid')
            voxel = copy.deepcopy(template)
            voxel['index'] = index
            row['voxels'].append(voxel)
    return row

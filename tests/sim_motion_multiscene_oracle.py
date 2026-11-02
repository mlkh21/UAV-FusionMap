"""Independent analytic test oracles; never imported by online production modules."""
import math


def matmul(a, b):
    return [[sum(x*y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


def rotation_from_ic(ic_degrees):
    phi, theta, psi = map(math.radians, ic_degrees)
    C, S = math.cos, math.sin
    frd_ned = matmul(matmul([[C(psi), -S(psi), 0], [S(psi), C(psi), 0], [0, 0, 1]],
        [[C(theta), 0, S(theta)], [0, 1, 0], [-S(theta), 0, C(theta)]]),
        [[1, 0, 0], [0, C(phi), -S(phi)], [0, S(phi), C(phi)]])
    return matmul(matmul([[0, 1, 0], [1, 0, 0], [0, 0, -1]], frd_ned),
        [[1, 0, 0], [0, -1, 0], [0, 0, -1]])


def fdm_pose(sample, origin_ft, latitude_rad, longitude_rad):
    sl, cl = math.sin(longitude_rad), math.cos(longitude_rad)
    sp, cp = math.sin(latitude_rad), math.cos(latitude_rad)
    basis = [[-sl, cl, 0], [-sp*cl, -sp*sl, cp], [cp*cl, cp*sl, sp]]
    delta = [(a-b)*.3048 for a, b in zip(sample['ecef_ft'], origin_ft)]
    position = [sum(a*b for a, b in zip(axis, delta)) + anchor
                for axis, anchor in zip(basis, (0, 0, 8))]
    raw = sample['R_ecef_frd']
    rotation = matmul(basis, [raw[i:i+3] for i in (0, 3, 6)])
    rotation = [[x*sign for x, sign in zip(row, (1, -1, -1))] for row in rotation]
    return position, rotation


def radar_origin(position, rotation):
    return [p + .8*row[0] for p, row in zip(position, rotation)]


def rotation_estimate(matrix):
    """Independent scalar Markley estimate for the declared matrix-to-quaternion rule."""
    trace=sum(matrix[i][i] for i in range(3))
    choice=max(range(4),key=lambda i:matrix[i][i] if i<3 else trace)
    q=[0.,0.,0.,0.]
    if choice==3:
        q=[matrix[2][1]-matrix[1][2],matrix[0][2]-matrix[2][0],
           matrix[1][0]-matrix[0][1],1+trace]
    else:
        i=choice;j=(i+1)%3;k=(j+1)%3
        q[i]=1-trace+2*matrix[i][i]
        q[j]=matrix[j][i]+matrix[i][j]
        q[k]=matrix[k][i]+matrix[i][k]
        q[3]=matrix[k][j]-matrix[j][k]
    norm=math.sqrt(sum(v*v for v in q))
    x,y,z,w=[v/norm for v in q]
    return [[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
            [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
            [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]


def ray_direction(h, v):
    if type(h) is not int or type(v) is not int or not (0 <= h < 96 and 0 <= v < 24):
        raise ValueError('oracle_ray_index')
    azimuth, elevation = -.7+h*1.4/95, -.35+v*.7/23
    return [math.cos(elevation)*math.cos(azimuth),
            math.cos(elevation)*math.sin(azimuth), math.sin(elevation)]


def box_hits(origin, direction, boxes):
    """Positive surface distances, including beyond the sensor range, in nearest order."""
    hits = []
    for box in boxes:
        enter, leave = -math.inf, math.inf
        for p, d, center, size in zip(origin, direction, box['position'], box['size']):
            low, high = center-size/2, center+size/2
            if d == 0:
                if p < low or p > high:
                    break
                continue
            a, b = (low-p)/d, (high-p)/d
            enter, leave = max(enter, min(a, b)), min(leave, max(a, b))
            if enter > leave:
                break
        else:
            distance = enter if enter > 0 else leave
            if distance > 0 and math.isfinite(distance):
                hits.append(dict(name=box['name'], distance=distance))
    return sorted(hits, key=lambda h: (h['distance'], h['name']))


def nearest_hit(origin, direction, boxes):
    hits = box_hits(origin, direction, boxes)
    if not hits or not .5 < hits[0]['distance'] < 30:
        return None
    return hits[0]


def verify_literals(literals):
    assert len(literals['cases']) == 9
    for row in literals['cases']:
        rotation = rotation_from_ic(row['ic_degrees'])
        x, y, z, w = row['quaternion_xyzw']
        qmatrix = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                   [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                   [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
        assert max(abs(a-b) for a, b in zip(sum(rotation, []), sum(qmatrix, []))) < 1e-12
        assert row['clock_ns'] == row['committed_step']*4_000_000
        assert row['captures'] == row['committed_step']//25
    for sample in literals['rotation_samples']:
        case = next(c for c in literals['cases'] if c['case_id'] == sample['case_id'])
        r = rotation_from_ic(case['ic_degrees'])
        assert max(abs(a-b) for a, b in zip(sum(r, []), sample['matrix'])) < 1e-12
        assert max(abs(a-b) for a, b in zip(radar_origin([0, 0, 8], r), sample['radar_origin'])) < 1e-12
    boxes = literals['geometry']['occlusion_boxes']['objects']
    for row in literals['ray_samples']:
        direction = row['direction'] if row['h'] is None else ray_direction(row['h'], row['v'])
        hits = box_hits(row['origin'], direction, boxes)
        assert len(hits) == len(row['distances'])
        assert hits[0]['name'] == row['first']
        assert max(abs(hit['distance']-wanted) for hit, wanted in zip(hits, row['distances'])) < 1e-12
    assert sum(c['clock_ns'] for c in literals['cases']) == literals['budget']['core_committed_ns']

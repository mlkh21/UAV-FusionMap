"""Independent checks of actual FDM, installed geometry and captured Ray/Camera wire."""
import copy
import json
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import Image,PointCloud2

from sim_motion_multiscene_oracle import box_hits,fdm_pose,radar_origin,ray_direction,rotation_from_ic,rotation_estimate


def proper_rotation(raw):
    matrix=np.asarray(raw,dtype=float)
    if (not np.isfinite(matrix).all() or np.max(np.abs(matrix.T@matrix-np.eye(3)))>1e-9 or
            abs(np.linalg.det(matrix)-1.)>1e-9):
        raise ValueError('suite_original_rotation_contract')
    # Compare unit-quaternion geometry to an independent polar projection, preserving raw input.
    u,_,vt=np.linalg.svd(matrix)
    return u@vt


def scan_oracle(position,rotation,boxes):
    origin=radar_origin(position,rotation)
    result={};boundary=[]
    for v in range(24):
        for h in range(96):
            local=ray_direction(h,v)
            direction=[sum(a*b for a,b in zip(row,local)) for row in rotation]
            hits=box_hits(origin,direction,boxes)
            if not hits or not .5<hits[0]['distance']<30:continue
            hit=hits[0]
            result[v*96+h]=hit['distance']
            box=next(b for b in boxes if b['name']==hit['name'])
            point=[p+hit['distance']*d for p,d in zip(origin,direction)]
            clearances=sorted(size/2-abs(p-center) for p,center,size in zip(point,box['position'],box['size']))
            if clearances[1]<=.02 or min(abs(hit['distance']-.5),abs(hit['distance']-30))<=.011:
                boundary.append(v*96+h)
    return result,boundary


def compare_scan(points,wanted):
    points=np.asarray(points,dtype=float).reshape(-1,5)
    if not np.isfinite(points).all():raise ValueError('suite_nonfinite_ray')
    distance=np.linalg.norm(points[:,:3],axis=1)
    if np.any(distance<=.5) or np.any(distance>=30):raise ValueError('suite_ray_range')
    azimuth=np.arctan2(points[:,1],points[:,0])
    elevation=np.arcsin(np.clip(points[:,2]/distance,-1,1))
    h=np.rint((azimuth+.7)*95/1.4).astype(int)
    v=np.rint((elevation+.35)*23/.7).astype(int)
    if np.any(h<0) or np.any(h>=96) or np.any(v<0) or np.any(v>=24):raise ValueError('suite_ray_grid_bounds')
    if (np.any(np.abs(azimuth-(-.7+h*1.4/95))>5e-6) or
            np.any(np.abs(elevation-(-.35+v*.7/23))>5e-6)):
        raise ValueError('suite_ray_grid_angle')
    ids=(v*96+h).tolist()
    if ids!=sorted(set(ids)) or set(ids)!=set(wanted):raise ValueError('suite_analytic_ray_hit_set')
    error=max((abs(float(d)-wanted[i]) for i,d in zip(ids,distance)),default=0.)
    if error>.011:raise ValueError('suite_analytic_ray_range')
    return dict(points=len(ids),maximum_range_error_m=error)


def verify_live(run,rows,spec,completed):
    policy=json.loads((run/'sim_motion_strict_geometry_expectations.json').read_text())
    if (policy['policy']!='strict_all_rays_no_exemptions_v1' or type(policy['maximum_exemptions']) is not int or
            policy['maximum_exemptions']!=0 or policy['hit_set_must_equal'] is not True or
            policy['angle_error_rad']!=.000005 or policy['range_error_m']!=.011):
        raise ValueError('suite_strict_geometry_policy')
    literals=json.loads((run/'sim_motion_multiscene_expectations.json').read_text())
    case=next(c for c in literals['cases'] if c['case_id']==spec['case_id'])
    if completed!=case['committed_step']:raise ValueError('suite_committed_steps')
    raw=[json.loads(line) for line in (run/'fdm.jsonl').read_text().splitlines()]
    frames=[r['value'] for r in rows['applied']]
    if len(raw)!=len(frames):raise ValueError('suite_raw_fdm_count')
    geography=json.loads((run/'initial-geography.json').read_text())
    poses={}
    for sample,frame in zip(raw,frames):
        if sample['step_index']!=frame['step_index'] or abs(sample['sim_time_s']*1e9-frame['step_index']*4000000)>1:
            raise ValueError('suite_original_fdm_time')
        p,r=fdm_pose(sample,raw[0]['ecef_ft'],geography['geodetic_latitude_rad'],geography['longitude_rad'])
        proper_rotation(r)  # Validate the original 1e-9 input bound, without changing the source.
        r=rotation_estimate(r)
        state=frame['state']
        np.testing.assert_allclose(state['position'],p,rtol=0,atol=1e-9)
        np.testing.assert_allclose(Rotation.from_quat(state['orientation_xyzw']).as_matrix(),r,rtol=0,atol=1e-12)
        np.testing.assert_allclose(state['linear_velocity'],np.array(sample['uvw_ftps'])*[.3048,-.3048,-.3048],rtol=0,atol=1e-12)
        np.testing.assert_allclose(frame['angular_velocity_flu'],np.array(sample['pqr_radps'])*[1,-1,-1],rtol=0,atol=1e-12)
        poses[frame['state']['header']['timestamp']]=(p,r)
    np.testing.assert_allclose(poses[0][1],rotation_from_ic(case['ic_degrees']),rtol=0,atol=1e-12)
    ic=ET.parse(run/'initial.xml').getroot()
    if [float(ic.find(k).text) for k in ('phi','theta','psi')]!=case['ic_degrees']:
        raise ValueError('suite_actual_ic')
    if case['ic_degrees'][1]!=0 and ic.find('gamma') is not None:
        raise ValueError('suite_conflicting_pitch_and_flightpath_ic')
    installed=json.loads((run/'installed-geometry.json').read_text())
    geometry=literals['geometry'][case['geometry_id']]
    world=ET.parse(run/'scene.world').getroot().find('world')
    if not geometry['inherit_legacy']:
        expected_names={'sensor_aircraft',*(b['name'] for b in geometry['objects'])}
        if {r['name'] for r in installed['models']}!=expected_names or {m.attrib['name'] for m in world.findall('model')}!=expected_names:
            raise ValueError('suite_independent_no_hidden_ground')
        for box in geometry['objects']:
            actual=next(m for m in installed['models'] if m['name']==box['name'])
            if actual['position']!=box['position']:raise ValueError('suite_installed_box_position')
            np.testing.assert_allclose(actual['orientation_xyzw'],[0,0,0,1],rtol=0,atol=1e-12)
            model=world.find("model[@name='%s']"%box['name'])
            for kind in ('collision','visual'):
                if [float(v) for v in model.find('link/'+kind+'/geometry/box/size').text.split()]!=box['size']:
                    raise ValueError('suite_installed_box_geometry')
        if world.findall("model[@name='sensor_aircraft']/link/collision"):
            raise ValueError('suite_aircraft_hidden_collision')
    scans=[]
    for row in rows['radar']:
        stamp=row['timestamp']
        if geometry['inherit_legacy']:continue
        boxes=copy.deepcopy(geometry['objects'])
        if case['case_id']=='S07' and 400000000<stamp<=900000000:boxes[0]['position']=[100,0,8]
        wanted,boundary=scan_oracle(*poses[stamp],boxes)
        message=PointCloud2().deserialize((run/row['wire']).read_bytes())
        checked=compare_scan(np.frombuffer(message.data,dtype='<f4').reshape(-1,5),wanted)
        checked.update(timestamp=stamp,boundary_rays=len(boundary))
        scans.append(checked)
        if case['case_id']=='S05' and stamp==100000000:
            p,r=poses[stamp];direction=np.array(r)@ray_direction(48,12)
            hits=box_hits(radar_origin(p,r),direction.tolist(),boxes)
            if (len(hits)!=2 or hits[0]['name']!='obstacle_near' or 12*96+48 in boundary or
                    12*96+48 not in wanted):raise ValueError('suite_first_capture_not_occluded')
    images={}
    for row in rows['infrared']:
        image=Image().deserialize((run/row['wire']).read_bytes())
        images[row['timestamp']]=np.frombuffer(image.data,dtype='<f4')
    if case['case_id']=='S06':
        if any(np.ptp(i)!=0 for i in images.values()):raise ValueError('suite_empty_ir_geometry')
    events=[]
    if case['case_id']=='S07':
        events=json.loads((run/'geometry-events.json').read_text())
        if [e['step_index'] for e in events]!=case['switch_after_steps']:raise ValueError('suite_epoch_count_or_order')
        for index,event in enumerate(events):
            if event['epoch_index']!=index or event['world_before_ns']!=event['world_after_ns']:
                raise ValueError('suite_epoch_advanced_time')
        empty=[images[t] for t in images if 400000000<t<=900000000]
        if len(empty)!=5 or any(np.ptp(i)!=0 or not np.array_equal(i,empty[0]) for i in empty):
            raise ValueError('suite_empty_epoch_camera_not_updated')
        if np.array_equal(images[400000000],empty[0]) or np.array_equal(images[1000000000],empty[0]):
            raise ValueError('suite_camera_geometry_not_returned')
    return dict(passed=True,case_id=case['case_id'],raw_fdm_frames_checked=len(raw),
        actual_scan_checks=scans,geometry_epochs=events,independent_initial_ic=True,
        no_hidden_ground=not geometry['include_ground'],new_trajectory_executed=True,
        nominal_boundary_rays_checked_strictly=True,boundary_exemptions=0,
        geometry_policy=policy['policy'],full_matrix_or_native_accepted=False)

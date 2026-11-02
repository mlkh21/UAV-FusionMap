"""Independent checks of actual parameterized Radar wire and same-tick motion."""
import numpy as np
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import PointCloud2, Image
from tf2_msgs.msg import TFMessage
from check_sensor_scene_ros import surface_distance


def verify_report_payloads(run, rows, profile):
    frames={r['value']['state']['header']['timestamp']:r['value'] for r in rows['applied']}
    counts=[]; residuals=[]; doppler_errors=[]; clouds=[]
    for row in rows['radar']:
        message=PointCloud2().deserialize((run/row['wire']).read_bytes())
        if message.point_step!=20 or message.height!=1 or message.is_bigendian:
            raise ValueError('report_radar_wire_layout')
        if [(f.name,f.offset,f.datatype,f.count) for f in message.fields] != [
                (name,offset,7,1) for name,offset in zip(('x','y','z','doppler','power'),range(0,20,4))]:
            raise ValueError('report_radar_fields')
        points=np.frombuffer(message.data,dtype='<f4').reshape(-1,5).astype(float)
        if not 1 <= len(points) <= profile['radar']['max_points'] or not np.isfinite(points).all():
            raise ValueError('report_radar_count_or_nonfinite')
        counts.append(len(points));clouds.append(points)
        frame=frames[message.header.stamp.to_nsec()]
        state=frame['state']; rotation=Rotation.from_quat(state['orientation_xyzw']).as_matrix()
        origin=np.array(state['position'])+rotation@np.array(profile['radar_mount_xyz'])
        world=points[:,:3]@rotation.T+origin
        residuals.extend(surface_distance(p,profile['objects']) for p in world)
        ranges=np.linalg.norm(points[:,:3],axis=1)
        if not np.all((ranges>profile['radar']['min_range_m'])&(ranges<profile['radar']['max_range_m'])):
            raise ValueError('report_radar_range')
        v=np.array(state['linear_velocity'])+np.cross(frame['angular_velocity_flu'],profile['radar_mount_xyz'])
        doppler_errors.extend((points[:,3]+points[:,:3]@v/ranges).tolist())
        if not np.allclose(points[:,4],1/(1+ranges**2),rtol=1e-6,atol=1e-9):
            raise ValueError('report_power_semantics')
    residuals=np.array(residuals);doppler_errors=np.array(doppler_errors)
    # 0.08 m range and 0.003 rad angle errors permit displacement from exact surfaces.
    if np.quantile(residuals,.99)>1. or np.quantile(np.abs(doppler_errors),.99)>.4:
        raise ValueError('report_measurement_errors_exceed_declared_check')
    if np.std(doppler_errors)<.01:
        raise ValueError('report_doppler_noise_absent')
    images=[]
    for row in rows['infrared']:
        message=Image().deserialize((run/row['wire']).read_bytes())
        if (message.width,message.height,message.encoding)!=(320,240,'32FC1'):
            raise ValueError('report_ir_layout')
        image=np.frombuffer(message.data,dtype='<f4')
        if not np.isfinite(image).all() or image.min()<0 or image.max()>1:
            raise ValueError('report_ir_values')
        images.append(image)
    changed=int(np.count_nonzero(images[0]!=images[-1]))
    if changed<100:raise ValueError('report_ir_motion_absent')
    for row in rows['tf']:
        message=TFMessage().deserialize((run/row['wire']).read_bytes())
        for transform in message.transforms:
            state=frames[transform.header.stamp.to_nsec()]['state']
            p=transform.transform.translation;q=transform.transform.rotation
            if not np.allclose([p.x,p.y,p.z],state['position'],atol=1e-9,rtol=0):
                raise ValueError('report_tf_position')
            if abs(np.dot([q.x,q.y,q.z,q.w],state['orientation_xyzw']))<1-1e-12:
                raise ValueError('report_tf_orientation')
    first=frames[min(frames)]['state'];last=frames[max(frames)]['state']
    return dict(passed=True,radar_counts=counts,points_checked=sum(counts),point_budget=profile['radar']['max_points'],
        surface_error_99_m=float(np.quantile(residuals,.99)),doppler_error_std_mps=float(np.std(doppler_errors)),
        changed_ir_pixels=changed,initial_scene_position=first['position'],final_scene_position=last['position'],
        displacement_m=float(np.linalg.norm(np.array(last['position'])-first['position'])),
        tf_geometry_matches=True,measurement_model='parameterized_v1',calibrated=False)

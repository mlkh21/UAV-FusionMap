"""Bounded actual ROS/wire receipts for the SW-02 engine gate, without business logic."""
import collections
import io
import json
import threading
import time

import numpy as np
import rospy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import PointCloud2, Image
from tf2_msgs.msg import TFMessage
from uav_fusionmap_msgs.msg import AircraftState
from uav_fusionmap_sim_scene_msgs.msg import SceneCaptureAck, SceneFrame
from ufm_ros_contract import from_ros_state
from ufm_scene_contract.codec import from_ros


class LiveReceipts:
    max_count=512
    max_wire_bytes=16*1024*1024
    scene_codec=staticmethod(from_ros)

    def __init__(self, run, extra_streams=(), *, max_count=512, max_wire_bytes=16*1024*1024,
                 scene_codec=from_ros, scene_namespace='/uav/scene',wire_directory=None):
        self.run = run
        self.lock = threading.RLock()
        self.rows = collections.defaultdict(list)
        self.errors = []
        self.total = 0
        self.max_count,self.max_wire_bytes,self.scene_codec=max_count,max_wire_bytes,scene_codec
        self.wire_directory=wire_directory
        if wire_directory is not None:(run/wire_directory).mkdir(exist_ok=False)
        self.subscribers = []
        self.decoders = {kind:decoder for _, kind, _, decoder in extra_streams}
        for topic, kind, message in (
                ('/clock', 'clock', Clock), ('/uav/sim/state', 'source', AircraftState),
                ('/uav/sensors/state', 'state', AircraftState), ('/tf', 'tf', TFMessage),
                ('/uav/sensors/radar/raw', 'radar', PointCloud2),
                ('/uav/sensors/infrared/raw', 'infrared', Image),
                (scene_namespace+'/capture_ack', 'ack', SceneCaptureAck),
                (scene_namespace+'/frame_applied', 'applied', SceneFrame)):
            self.subscribers.append(rospy.Subscriber(topic, message,
                lambda msg, k=kind:self.receive(k, msg), queue_size=512, buff_size=4*1024*1024))
        for topic, kind, message, _ in extra_streams:
            self.subscribers.append(rospy.Subscriber(topic, message,
                lambda msg, k=kind:self.receive(k, msg), queue_size=100, buff_size=4*1024*1024))

    def receive(self, kind, message):
        with self.lock:
            if self.errors:
                return
            try:
                if len(self.rows[kind]) >= self.max_count:
                    raise ValueError('receipt_count_limit')
                stream = io.BytesIO()
                message.serialize(stream)
                raw = stream.getvalue()
                if self.total + len(raw) > self.max_wire_bytes:
                    raise ValueError('receipt_byte_limit')
                self.total += len(raw)
                path = '%s-%03d.bin' % (kind, len(self.rows[kind]))
                if getattr(self,'wire_directory',None):path=self.wire_directory+'/'+path
                with (self.run / path).open('xb') as stream:
                    stream.write(raw)
                row = dict(wall=time.monotonic(), caller=message._connection_header.get('callerid'), wire=path)
                if kind in getattr(self, 'decoders', {}):
                    row['value'] = self.decoders[kind](message)
                elif kind in ('source', 'state'):
                    row['value'] = from_ros_state(message)
                elif kind == 'ack':
                    row['value'] = self.scene_codec('SceneCaptureAck', message)
                elif kind == 'applied':
                    row['value'] = self.scene_codec('SceneFrame', message)
                elif kind == 'clock':
                    row['timestamp'] = message.clock.to_nsec()
                elif kind == 'tf':
                    row['transforms'] = [dict(parent=t.header.frame_id, child=t.child_frame_id,
                        timestamp=t.header.stamp.to_nsec()) for t in message.transforms]
                else:
                    row.update(timestamp=message.header.stamp.to_nsec(), frame_id=message.header.frame_id)
                    if kind == 'radar':
                        points = np.frombuffer(message.data, dtype='<f4').reshape(-1, 5)
                        row.update(points=len(points), finite=bool(np.isfinite(points).all()),
                            doppler_min=float(points[:,3].min()) if len(points) else None,
                            doppler_max=float(points[:,3].max()) if len(points) else None)
                    else:
                        pixels = np.frombuffer(message.data, dtype='<f4')
                        row.update(width=message.width, height=message.height, encoding=message.encoding,
                            finite=bool(np.isfinite(pixels).all()), minimum=float(pixels.min()), maximum=float(pixels.max()))
                self.rows[kind].append(row)
            except Exception as exc:
                self.errors.append(type(exc).__name__ + ': ' + str(exc))

    def snapshot(self):
        with self.lock:
            if self.errors:
                raise ValueError(';'.join(self.errors))
            return {key:list(value) for key, value in self.rows.items()}

    def save(self):
        with self.lock:
            (self.run / 'receipts.json').write_text(json.dumps(dict(rows=dict(self.rows),
                errors=self.errors, wire_bytes=self.total), indent=2, allow_nan=False) + '\n')

    def close(self):
        for sub in self.subscribers:
            sub.unregister()
        self.save()


def validate(rows, completed, fault=False, *, allow_empty=False):
    clocks = [r['timestamp'] for r in rows.get('clock', [])]
    wanted = [i*4000000 for i in range(completed+1)]
    if clocks != wanted:
        raise ValueError('public_clock_sequence')
    for key in ('source', 'state'):
        states = rows.get(key, [])
        valid = [r['value']['header']['timestamp'] for r in states if r['value']['header']['status'] == 'valid']
        if valid != wanted:
            raise ValueError(key + '_valid_sequence')
        if not states or not states[-1]['value']['header']['reason'].startswith('terminal:'):
            raise ValueError(key + '_missing_terminal')
    captures = [i*100000000 for i in range(1, completed//25+1)]
    if fault:
        captures.append((completed//25+1)*100000000)
    for key in ('radar', 'infrared'):
        values = rows.get(key, [])
        if [r['timestamp'] for r in values] != captures or not all(r['finite'] for r in values):
            raise ValueError(key + '_actual_capture_sequence')
        if any(r['caller'] != '/gazebo' for r in values):
            raise ValueError(key + '_caller')
    if len(rows.get('ack', [])) != 2*len(captures):
        raise ValueError('ack_count')
    seen = set()
    for r in rows['ack']:
        a = r['value']
        key = (a['measurement_timestamp'], a['sensor_kind'])
        if not a['published'] or r['caller'] != '/gazebo' or key in seen:
            raise ValueError('ack_not_actual_plugin_publish')
        seen.add(key)
    if seen != {(stamp, kind) for stamp in captures for kind in (1, 2)}:
        raise ValueError('ack_capture_binding')
    applied = rows.get('applied', [])
    if ([r['value']['step_index'] for r in applied] != list(range(completed+1+int(fault))) or
            any(r['caller'] != '/gazebo' for r in applied)):
        raise ValueError('applied_frame_sequence')
    if not fault and not allow_empty and not any(r['points'] for r in rows['radar']):
        raise ValueError('scene_payload_empty')
    transforms = [t for r in rows.get('tf', []) for t in r['transforms']]
    if ([t['timestamp'] for t in transforms] != wanted or
            any(t['parent'] != 'odom' or t['child'] != 'base_link' for t in transforms)):
        raise ValueError('single_tf_sequence')
    return dict(passed=True, completed_steps=completed, public_clocks=len(clocks),
        captures_per_sensor=len(captures), acks=len(rows.get('ack', [])),
        truth_terminal=True, fault_expected=fault)


def verify_payloads(run, rows, fault=False, *, require_ir_change=True):
    """Read actual wire, compare analytic body-frame kinematics and TF, no engine substitute."""
    frames = {r['value']['state']['header']['timestamp']:r['value'] for r in rows['applied']}
    maximum_error, point_count = 0., 0
    for row in rows['radar']:
        msg = PointCloud2().deserialize((run / row['wire']).read_bytes())
        if (msg.point_step != 20 or msg.height != 1 or msg.is_bigendian or
                [(f.name,f.offset,f.datatype,f.count) for f in msg.fields] !=
                [(name, offset, 7, 1) for name, offset in zip(('x','y','z','doppler','power'), range(0,20,4))]):
            raise ValueError('actual_radar_wire_fields')
        points = np.frombuffer(msg.data, dtype='<f4').reshape(-1, 5).astype(float)
        f = frames[msg.header.stamp.to_nsec()]
        velocity = np.array(f['state']['linear_velocity']) + np.cross(f['angular_velocity_flu'], [.8, 0., 0.])
        distance = np.linalg.norm(points[:,:3], axis=1)
        if len(points):
            predicted = -(points[:,:3] @ velocity)/distance
            error = float(np.max(np.abs(predicted-points[:,3])))
            tolerance = 8*np.finfo(np.float32).eps*max(1., float(np.linalg.norm(velocity)))
            if error > tolerance or not np.allclose(points[:,4], 1/(1+distance**2), rtol=1e-6, atol=1e-9):
                raise ValueError('actual_doppler_or_power')
            maximum_error = max(maximum_error, error)
        point_count += len(points)
    images = []
    for row in rows['infrared']:
        msg = Image().deserialize((run / row['wire']).read_bytes())
        if (msg.width,msg.height,msg.encoding,msg.step,len(msg.data)) != (320,240,'32FC1',1280,307200):
            raise ValueError('actual_infrared_wire')
        images.append(np.frombuffer(msg.data, dtype='<f4'))
    changed = int(np.count_nonzero(images[0] != images[-1])) if len(images) > 1 else 0
    if not fault and require_ir_change and changed == 0:
        raise ValueError('actual_infrared_not_changed')
    for row in rows['tf']:
        msg = TFMessage().deserialize((run / row['wire']).read_bytes())
        for t in msg.transforms:
            f = frames[t.header.stamp.to_nsec()]['state']
            p, q = t.transform.translation, t.transform.rotation
            if not np.allclose([p.x,p.y,p.z], f['position'], rtol=0, atol=1e-9):
                raise ValueError('actual_tf_position')
            actual = np.array([q.x,q.y,q.z,q.w]); wanted = np.array(f['orientation_xyzw'])
            if min(np.max(np.abs(actual-wanted)), np.max(np.abs(actual+wanted))) > 1e-12:
                raise ValueError('actual_tf_orientation')
    first, last = frames[min(frames)]['state']['position'], frames[max(frames)]['state']['position']
    return dict(points_checked=point_count, maximum_doppler_error_mps=maximum_error,
        changed_ir_pixels=changed, initial_scene_position=first, final_applied_scene_position=last,
        displacement_m=float(np.linalg.norm(np.array(last)-first)), tf_geometry_matches=True)

"""实际ROS线格式调用的进程内探针与轻量收发记录；不修改生成文件。"""
import json
import os
from pathlib import Path
import threading
import time


def message_identity(msg):
    header = msg.header
    row = dict(sample_id=header.sample_id, run_id=header.run_id, clock_id=header.clock_id,
               timestamp=header.timestamp, status=header.status)
    infrared = getattr(msg, 'infrared', msg)
    row.update(image_shape=[infrared.width, infrared.height], pixel_count=len(infrared.image))
    if hasattr(msg, 'radar'):
        row.update(radar_id=msg.radar.header.sample_id, infrared_id=infrared.header.sample_id,
                   radar_ir_delta_ns=msg.radar_ir_delta_ns, pose_age_ns=msg.pose_age_ns)
    return row


class WireAudit:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.rows = []
        self.lock = threading.Lock()
        self.originals = []

    def record(self, operation, msg, **fields):
        if self.path is None:
            return
        row = dict(message_identity(msg), operation=operation, **fields)
        with self.lock:
            self.rows.append(row)

    def install(self, message_type, method):
        if self.path is None:
            return
        original = getattr(message_type, method)
        self.originals.append((message_type, method, original))
        audit = self

        def measured(msg, data):
            offset = data.tell() if method == 'serialize' else 0
            cpu_start = time.thread_time_ns()
            start = time.monotonic_ns()
            result = original(msg, data)
            end = time.monotonic_ns()
            cpu_end = time.thread_time_ns()
            audit.record(method + ':' + message_type._type.rsplit('/', 1)[-1], msg,
                         start_ns=start, end_ns=end, thread_cpu_ns=cpu_end - cpu_start,
                         wire_bytes=data.tell() - offset if method == 'serialize' else len(data))
            return result

        setattr(message_type, method, measured)

    def restore(self):
        for message_type, method, original in reversed(self.originals):
            setattr(message_type, method, original)
        self.originals.clear()

    def save(self):
        if self.path is not None:
            with self.lock, self.path.open('x') as handle:
                json.dump(dict(pid=os.getpid(), rows=self.rows), handle, indent=2)

    @classmethod
    def for_node(cls, role):
        import rospy
        directory = rospy.get_param('/perf01a_wire_audit_directory', '')
        audit = cls(Path(directory) / (role + '-wire.json') if directory else None)
        if directory:
            rospy.on_shutdown(audit.save)
        return audit

#!/usr/bin/env python
"""Shared lifecycle and metadata IO for the asynchronous ROS fixture."""
import json
from pathlib import Path
import sys
import threading
import time

import rospy


def report_error(run_id, exc):
    message = type(exc).__name__ + ': ' + str(exc)
    rospy.logerr('PERF-01-A async: %s', message)
    rospy.set_param('~error', dict(run_id=run_id, message=message))
    return message


def write_audit(directory, filename, payload):
    with (Path(directory) / filename).open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write('\n')


def wait_ready(predicate, stop, timeout=15.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if stop.wait(.02) or rospy.is_shutdown():
            raise RuntimeError('shutdown before ready')
        if time.monotonic() >= deadline:
            raise RuntimeError('subscribers not ready')


def run_node(name, factory):
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required: ' + sys.executable)
    rospy.init_node(name)
    node = None
    try:
        node = factory()
        node.start()
    except Exception as exc:
        if node is None:
            report_error(rospy.get_param('~run_id', ''), exc)
        else:
            node.fail(exc)
    rospy.spin()


class AuditNode:
    def __init__(self):
        self.run_id = rospy.get_param('~run_id')
        self.profile = rospy.get_param('/perf01a_async_profile', {})
        self.duration_ns = int(rospy.get_param('/perf01a_async_duration_ns',
            round(float(rospy.get_param('~duration_s', 10.0)) * 1_000_000_000)))
        if self.duration_ns <= 0:
            raise ValueError('positive duration required')
        self.directory = Path(rospy.get_param('/perf01a_async_run_directory'))
        if not self.directory.is_dir():
            raise ValueError('runner must create run directory')
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.errors = []
        self.saved = False
        self.worker = None

    def fail(self, exc):
        self.stop.set()
        with self.lock:
            self.errors.append(report_error(self.run_id, exc))

    def start_worker(self, target):
        def guarded():
            try:
                target()
            except Exception as exc:
                self.fail(exc)
        self.worker = threading.Thread(target=guarded, daemon=True)
        self.worker.start()

    def stop_worker(self):
        self.stop.set()
        if self.worker is not None and self.worker is not threading.current_thread():
            self.worker.join()

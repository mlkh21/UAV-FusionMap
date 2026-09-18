"""SIM-00B原始遥测记录与短测判定；不发布控制或系统业务消息。"""
import collections
import json
import math
import sys
import threading
import time
from pathlib import Path

import rospy
from mavros.mavlink import convert_to_bytes
from mavros_msgs.msg import Mavlink
from pymavlink.dialects.v20 import common


def main():
    output = Path(sys.argv[1])
    rospy.init_node('sim00b_observer', disable_signals=True)
    lock = threading.Lock()
    state = {'counts': collections.Counter(), 'errors': [], 'first_usec': None,
             'last_usec': None, 'max_gap_usec': 0, 'heartbeat': False, 'armed': False}
    start = time.monotonic()
    decoder = common.MAVLink(None)
    stream = (output / 'mavlink.jsonl').open('x')

    def receive(msg):
        with lock:
            stream.write(json.dumps({'receipt_monotonic': time.monotonic(),
                                     'ros_receipt_ns': msg.header.stamp.to_nsec(),
                                     'framing': msg.framing_status, 'wire_hex': convert_to_bytes(msg).hex()}) + '\n')
            if msg.framing_status != Mavlink.FRAMING_OK:
                state['errors'].append('bad framing')
                return
            if msg.sysid != 1 or msg.compid != 1:
                return
            state['counts'][str(msg.msgid)] += 1
            if msg.msgid not in (0, 105, 331):
                return
            try:
                data = decoder.decode(convert_to_bytes(msg))
            except Exception as exc:
                state['errors'].append('decode: ' + str(exc))
                return
            if msg.msgid == 0:
                state['heartbeat'] = True
                state['armed'] |= bool(data.base_mode & 128)
            elif msg.msgid == 105:
                values = [getattr(data, key) for key in ('xacc', 'yacc', 'zacc', 'xgyro', 'ygyro', 'zgyro')]
                if not all(math.isfinite(v) for v in values) or data.time_usec <= 0:
                    state['errors'].append('invalid IMU sample')
                    return
                last = state['last_usec']
                if last is not None:
                    if data.time_usec < last:
                        state['errors'].append('sample time rollback')
                    state['max_gap_usec'] = max(state['max_gap_usec'], data.time_usec - last)
                if state['heartbeat'] and state['first_usec'] is None:
                    state['first_usec'] = data.time_usec
                state['last_usec'] = data.time_usec
                if data.time_usec >= 600_000_000:
                    state['errors'].append('600 second source-time limit')

    subscriber = None
    passed = False
    try:
        while time.monotonic() - start < 850:
            if subscriber is None:
                topics = [name for name, kind in rospy.get_published_topics() if kind == 'mavros_msgs/Mavlink' and name.endswith('/from')]
                if len(topics) == 1:
                    state['topic'] = topics[0]
                    subscriber = rospy.Subscriber(topics[0], Mavlink, receive, queue_size=10000)
            with lock:
                first, last = state['first_usec'], state['last_usec']
                if state['errors'] or state['armed']:
                    break
                if first is not None and last - first >= 120_000_000:
                    passed = state['max_gap_usec'] <= 500_000
                    if not passed:
                        state['errors'].append('IMU continuity gap exceeds 0.5 seconds')
                    break
                if first is None and time.monotonic() - start > 60:
                    state['errors'].append('60 second telemetry startup timeout')
                    break
            time.sleep(0.1)
    finally:
        if subscriber is not None:
            subscriber.unregister()
        with lock:
            stream.close()
            state['passed'] = passed
            state['wall_seconds'] = time.monotonic() - start
            state['sim_seconds'] = ((state['last_usec'] - state['first_usec']) / 1e6
                                    if state['first_usec'] is not None else 0)
            (output / 'telemetry-result.json').write_text(json.dumps(state, indent=2) + '\n')
            print(json.dumps(state), flush=True)
        rospy.signal_shutdown('short test complete')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())

"""实际SIM-01A链路记录与轻量判定；不发送控制指令。"""
import json
import math
import sys
import threading
import time
from pathlib import Path

import rospy
from diagnostic_msgs.msg import DiagnosticArray
from mavros.mavlink import convert_to_bytes
from mavros_msgs.msg import Mavlink
from pymavlink.dialects.v20 import common
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState
from ufm_ros_contract import from_ros_state


def main():
    run, run_id = Path(sys.argv[1]), sys.argv[2]
    rospy.init_node('sim01a_observer', disable_signals=True)
    lock = threading.Lock()
    errors, source, adapted, clocks = [], {}, {}, []
    raw_counts, diagnostics = {}, []
    files = {name: (run / (name + '.jsonl')).open('x') for name in ('mavlink', 'states', 'clock', 'diagnostics')}
    start = time.monotonic()

    def write(name, value):
        files[name].write(json.dumps(dict(receipt_monotonic=time.monotonic(), **value)) + '\n')

    def receive_state(msg, channel):
        with lock:
            try:
                state = from_ros_state(msg)
                write('states', dict(channel=channel, state=state))
                h = state['header']
                if h['run_id'] != run_id or h['clock_id'] != 'sim:' + run_id:
                    errors.append('state domain mismatch')
                if h['status'] == 'unavailable':
                    errors.append('upstream terminal: ' + h['reason'])
                    return
                target = source if channel == 'source' else adapted
                if h['sample_id'] in target:
                    errors.append('duplicate published state')
                if target and h['timestamp'] <= next(reversed(target.values()))['header']['timestamp']:
                    errors.append('published state time not increasing')
                target[h['sample_id']] = state
            except ValueError as exc:
                errors.append('state decode: ' + str(exc))

    def receive_clock(msg):
        with lock:
            ns = msg.clock.to_nsec()
            write('clock', dict(timestamp=ns))
            if clocks and ns <= clocks[-1]:
                errors.append('clock not strictly increasing')
            clocks.append(ns)
            if ns >= 600000000000:
                errors.append('600 second source safety limit')

    def raw(msg):
        with lock:
            wire = convert_to_bytes(msg)
            write('mavlink', dict(framing=msg.framing_status, wire_hex=wire.hex()))
            if msg.framing_status != 1:
                errors.append('MAVLink framing failed')
            if (msg.sysid, msg.compid) != (1, 1):
                return
            key = str(msg.msgid)
            raw_counts[key] = raw_counts.get(key, 0) + 1
            if msg.msgid == 0:
                if common.MAVLink(None).decode(wire).base_mode & 128:
                    errors.append('aircraft armed')

    def diagnostic(msg):
        with lock:
            items = [dict(name=d.name, level=d.level, message=d.message,
                          values={v.key: v.value for v in d.values}) for d in msg.status]
            diagnostics.extend(items)
            write('diagnostics', dict(items=items))
            for item in items:
                if item['level'] >= 2:
                    errors.append('fatal diagnostic: ' + item['name'] + ': ' + item['message'])

    subscribers = [rospy.Subscriber('/uav/sim/state', AircraftState, receive_state, 'source', queue_size=1000),
                   rospy.Subscriber('/uav/sensors/state', AircraftState, receive_state, 'adapted', queue_size=1000),
                   rospy.Subscriber('/clock', Clock, receive_clock, queue_size=1000),
                   rospy.Subscriber('/mavlink/from', Mavlink, raw, queue_size=10000),
                   rospy.Subscriber('/uav/diagnostics', DiagnosticArray, diagnostic, queue_size=1000)]
    passed = False
    try:
        while time.monotonic() - start < 150:
            with lock:
                if errors:
                    break
                if adapted:
                    values = list(adapted.values())
                    span = values[-1]['header']['timestamp'] - values[0]['header']['timestamp']
                    if span >= 30000000000 and len(adapted) >= 500:
                        passed = True
                        break
            time.sleep(.05)
        # 给不同话题最后的消息短暂接收机会；不以跨话题到达顺序推断业务门控。
        time.sleep(.2)
    finally:
        for sub in subscribers:
            sub.unregister()
        with lock:
            for key, state in adapted.items():
                original = source.get(key[len('sensors.state:'):])
                if original is None:
                    errors.append('adapted state has no recorded source')
                    continue
                h = state['header']
                if (h['timestamp'] != original['header']['timestamp'] or h['frame_id'] != 'odom' or
                    state['body_frame_id'] != 'base_link' or state['velocity_frame_id'] != 'base_link' or
                    h['source_type'] != 'derived' or state['state_source'] != 'estimated'):
                    errors.append('state metadata mismatch')
                p, v = original['position'], original['linear_velocity']
                if max(abs(a-b) for a,b in zip(state['position'], [p[1],p[0],-p[2]])) > 1e-6:
                    errors.append('position axis conversion mismatch')
                if max(abs(a-b) for a,b in zip(state['linear_velocity'], [v[0],-v[1],-v[2]])) > 1e-6:
                    errors.append('velocity frame conversion mismatch')
                if abs(math.sqrt(sum(x*x for x in state['orientation_xyzw']))-1) > 1e-6:
                    errors.append('invalid adapted quaternion')
                if (state['quality']['confidence'] is not None or
                    state['quality']['uncertainty']['status'] != 'unavailable' or
                    state['quality']['uncertainty']['value'] is not None):
                    errors.append('unknown quality not retained')
                if not clocks or h['timestamp'] > clocks[-1]:
                    errors.append('state exceeds recorded final clock')
            if not raw_counts.get('0') or not raw_counts.get('105') or not raw_counts.get('331'):
                errors.append('missing raw telemetry type')
            node_pythons = {d['name']:d['values']['python'] for d in diagnostics if 'python' in d['values']}
            expected = '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
            if len(node_pythons) != 2 or any(value != expected for value in node_pythons.values()):
                errors.append('node Python interpreter not verified')
            result = dict(passed=passed and not errors, errors=errors, source_states=len(source),
                          adapted_states=len(adapted), clocks=len(clocks), raw_counts=raw_counts,
                          valid_span_ns=(list(adapted.values())[-1]['header']['timestamp']-
                                         list(adapted.values())[0]['header']['timestamp']) if adapted else 0,
                          first_valid_ns=next(iter(adapted.values()))['header']['timestamp'] if adapted else None,
                          last_clock_ns=clocks[-1] if clocks else None, node_pythons=node_pythons,
                          observer_python=sys.executable, wall_seconds=time.monotonic()-start)
            for file in files.values():
                file.close()
            (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result),flush=True)
        rospy.signal_shutdown('SIM01A light test complete')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())

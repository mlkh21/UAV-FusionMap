"""复核落盘原始报文；按线格式计数，未知方言消息保留且不冒充独立CRC验证。"""
import collections
import json
import math
import sys
from pathlib import Path
from pymavlink.dialects.v20 import common

run = Path(sys.argv[1])
counts = collections.Counter()
unknown = collections.Counter()
decoder = common.MAVLink(None)
imus, heartbeats = [], []
frames = collections.Counter()
armed = 0
errors = []
for line in (run / 'mavlink.jsonl').read_text().splitlines():
    row = json.loads(line)
    raw = bytearray.fromhex(row['wire_hex'])
    assert row['framing'] == 1, 'MAVROS framing failure'
    if raw[0] == 253:
        sysid, compid, msgid = raw[5], raw[6], int.from_bytes(raw[7:10], 'little')
    else:
        assert raw[0] == 254
        sysid, compid, msgid = raw[3], raw[4], raw[5]
    if (sysid, compid) != (1, 1):
        continue
    counts[str(msgid)] += 1
    if msgid not in common.mavlink_map:
        unknown[str(msgid)] += 1
        continue
    msg = decoder.decode(raw)  # 已知消息独立核对CRC。
    if msgid == 105:
        assert all(math.isfinite(getattr(msg, k)) for k in ('xacc', 'yacc', 'zacc', 'xgyro', 'ygyro', 'zgyro'))
        imus.append(msg.time_usec)
    elif msgid == 0:
        armed += bool(msg.base_mode & 128)
        if imus:
            heartbeats.append(imus[-1])
    elif msgid == 331:
        frames[str((msg.frame_id, msg.child_frame_id))] += 1
        assert all(math.isfinite(v) for v in [msg.x, msg.y, msg.z, msg.vx, msg.vy, msg.vz, *msg.q])
expected = json.loads((run / 'telemetry-result.json').read_text())
assert dict(counts) == expected['counts'], 'wire counts differ from observer counts'
assert expected['passed'] and expected['sim_seconds'] >= 120
assert len(heartbeats) >= 60 and armed == 0
heartbeat_gap = max(b-a for a, b in zip(heartbeats, heartbeats[1:])) / 1e6
assert heartbeat_gap <= 2
assert all(0 < b-a <= 500000 for a, b in zip(imus, imus[1:]))
result = {'passed': True, 'wire_counts_match_observer': True,
          'known_message_crc_decode_passed': True, 'unknown_dialect_ids': dict(unknown),
          'unknown_crc_scope': 'MAVROS framing only; not independently decoded',
          'heartbeat_count': counts['0'], 'heartbeat_max_gap_s_using_latest_imu': heartbeat_gap,
          'armed_heartbeats': armed, 'imu_count': len(imus),
          'imu_rate_hz': (len(imus)-1)/((imus[-1]-imus[0])/1e6),
          'odometry_count': counts['331'], 'odometry_frames': dict(frames),
          'all_odometry_pose_velocity_finite': True}
with (run / 'recording-audit.json').open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps(result, indent=2))

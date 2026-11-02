"""Independent MAVLink byte decoding and host receipt audit; no command sender."""
import json
import math
from pathlib import Path
import struct


def verify(directory, identity, profile, expected, disconnect=False):
    from pymavlink.dialects.v20 import common
    from ufm_simulation.flight_contract import dumps, load_recording, validate_recording
    initial=json.loads((directory/'initial.json').read_text())
    rows=[json.loads(line) for line in (directory/'actuators.jsonl').read_text().splitlines()]
    terminal=json.loads((directory/'terminal.json').read_text())
    for key,target,tolerance in [('agl_m',expected['initial_agl_m'],1e-6),
            ('terrain_m',expected['initial_terrain_m'],1e-6),
            ('geodetic_altitude_m',expected['initial_geodetic_altitude_m'],1e-6),
            ('latitude_deg',profile['ic']['latitude_deg'],1e-9),
            ('longitude_deg',profile['ic']['longitude_deg'],1e-9),('vt_mps',0.,1e-9)]:
        if not math.isfinite(initial[key]) or abs(initial[key]-target)>tolerance:
            raise ValueError('initial readback: '+key)
    a,b=initial['ellipsoid_axes_m'];x,y,z=initial['ecef_m']
    if abs(a-6378137.)>1e-3 or abs(b-6356752.314245)>1e-3:raise ValueError('unexpected ellipsoid')
    radius=math.sqrt(x*x+y*y+z*z)
    sea_radius=1./math.sqrt(((x*x+y*y)/(a*a)+z*z/(b*b))/(radius*radius))
    if not math.isfinite(initial['asl_m']) or abs(initial['asl_m']-(radius-sea_radius))>1e-6:
        raise ValueError('radial ASL readback')
    if any(abs(a-b)>1e-9 for a,b in zip(initial['euler_deg'],expected['initial_euler_deg'])):
        raise ValueError('initial Euler readback')
    header=dict(schema_version='sim_flight_recording.v1',run_id=identity,clock_id='sim:'+identity,
        profile=profile,peer=initial['peer'],initial_properties=initial['initial_properties'],
        initial_wall_ns=initial['initial_wall_ns'])
    summary=validate_recording(header,iter(rows))
    recording=directory/'recording.jsonl'
    with recording.open('xb') as stream:
        for kind,value in [('header',header)]+[('record',r) for r in rows]:stream.write(dumps(kind,value)+b'\n')
    reread=load_recording(recording)
    if any(reread[key]!=value for key,value in summary.items()):raise ValueError('recording reload')
    parsers={direction:common.MAVLink(None) for direction in ('tx','rx')}
    decoded={direction:[] for direction in parsers}
    total=0
    with (directory/'wire.jsonl').open() as stream:
        for index,line in enumerate(iter(lambda:stream.readline(262145),'')):
            if len(line)>262144 or index>=12288:raise ValueError('wire line budget')
            item=json.loads(line);raw=bytes.fromhex(item['hex']);total+=len(raw)
            if len(raw)!=item['length'] or total>134217728:raise ValueError('wire bytes budget')
            if item['direction']=='tx' and item['sent']!=len(raw):raise ValueError('wire send failed')
            for byte in raw:
                try:message=parsers[item['direction']].parse_char(bytes([byte]))
                except common.MAVError as exc:raise ValueError('wire MAVLink framing or CRC') from exc
                if message:
                    decoded[item['direction']].append((item['step_index'],message))
    by_step={}
    for step,message in decoded['tx']:
        if message.get_msgId() not in expected['allowed_host_tx_ids']:raise ValueError('host sent command')
        if message.get_type()=='HIL_SENSOR':
            if step in by_step:raise ValueError('multiple raw HIL sensor per step')
            by_step[step]=message.time_usec
    incoming={}
    for step,message in decoded['rx']:
        if message.get_type()=='HIL_ACTUATOR_CONTROLS':
            if step in incoming:raise ValueError('multiple raw actuator per step')
            if message.get_srcSystem()!=1 or message.get_srcComponent()!=1:raise ValueError('wire source identity')
            incoming[step]=message
    deltas=[]
    for row in rows:
        step=row['step_index']
        if row['hil_sensor_time_us']!=by_step[step]:raise ValueError('HIL time not original wire')
        if row['has_actuator']!=(step in incoming):raise ValueError('actuator presence differs from raw wire')
        if row['has_actuator']:
            a=row['actuator'];message=incoming[step]
            if any(a[key]!=getattr(message,key) for key in ('time_usec','flags','mode')):
                raise ValueError('actuator metadata differs from raw wire')
            if struct.pack('<16f',*a['controls'])!=struct.pack('<16f',*message.controls):
                raise ValueError('actuator float32 bits changed')
            deltas.append(a['time_usec']-row['hil_sensor_time_us'])
        if not all(math.isfinite(x) for x in row['properties']['after']):raise ValueError('property finite')
    if len(by_step)!=len(rows) or len(incoming)!=summary['actuator_observations']:
        raise ValueError('wire/record totals differ')
    if len(rows)>expected['max_steps'] or rows[-1]['fdm']['sim_time_after_s']>1.+1e-9:
        raise ValueError('short diagnostic exceeded')
    reason=expected['disconnect_terminal'] if disconnect else expected['normal_terminal']
    if terminal['reason']!=reason:raise ValueError('terminal reason: '+terminal['reason'])
    if disconnect:
        if rows[-1]['fdm']['ran'] or not summary['terminal']:
            raise ValueError('disconnect did not stop before FDM')
    elif len(rows)!=250 or summary['fdm_successes']!=250:raise ValueError('incomplete normal window')
    if terminal['control_gate_accepted'] or summary['control_gate_accepted']:
        raise ValueError('unverified diagnostic cannot authorize control')
    return dict(passed=True,stream=summary,wire_bytes=total,tx_messages=len(decoded['tx']),
        rx_messages=len(decoded['rx']),actuator_hil_deltas_us=deltas,
        observed_equal_time_count=sum(delta==0 for delta in deltas),
        readiness='actuator_observed' if deltas else 'bootstrap_not_ready',
        binding_status='unverified',control_gate_accepted=False,terminal=terminal)

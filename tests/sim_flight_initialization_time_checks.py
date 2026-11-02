"""Independent source-receipt and transmitted HIL/GPS timestamp audit."""
from fractions import Fraction
import json

from pymavlink.dialects.v20 import common
from sim_flight_initialization_selector_checks import audit as audit_selector


def audit(directory):
    result=audit_selector(directory)
    wire={}
    parsers={name:common.MAVLink(None) for name in ('tx','rx')}
    with (directory/'diagnostics/wire.jsonl').open('rb') as stream:
        for raw in stream:
            item=json.loads(raw)
            for byte in bytes.fromhex(item['hex']):
                message=parsers[item['direction']].parse_char(bytes([byte]))
                if message is not None and item['direction']=='tx':
                    kind={'HIL_SENSOR':'hil_sensor','HIL_GPS':'hil_gps'}.get(message.get_type())
                    if kind is not None:
                        key=(kind,item['step_index']-1)
                        if key in wire:raise ValueError('duplicate time-bearing packet')
                        wire[key]=message.time_usec
    physics={row['source_step']:row for row in (json.loads(raw) for raw in
        (directory/'diagnostics/steps.jsonl').read_bytes().splitlines())}
    receipts={};total=0;largest_error=0
    with (directory/'diagnostics/time-grid.jsonl').open('rb') as stream:
        for raw in stream:
            total+=len(raw)
            if len(raw)>256 or total>1048576 or len(receipts)>=5000:
                raise ValueError('time source receipt budget')
            row=json.loads(raw)
            if set(row)!=set(('sensor_kind','source_step','source_time_s','time_usec')):
                raise ValueError('time source receipt fields')
            key=(row['sensor_kind'],row['source_step'])
            if (row['sensor_kind'] not in ('hil_sensor','hil_gps') or type(row['source_step']) is not int
                    or not 0<=row['source_step']<=2499 or key in receipts or key not in wire
                    or type(row['time_usec']) is not int or row['time_usec']!=row['source_step']*4000
                    or row['time_usec']!=wire[key]):
                raise ValueError('time source receipt identity or original wire')
            error=abs(Fraction(row['source_time_s'])*1000000000-row['source_step']*4000000)
            if error>1 or row['source_time_s']!=physics[row['source_step']]['fdm']['sim_time_before_s']:
                raise ValueError('time source receipt changed physical source')
            largest_error=max(largest_error,float(error));receipts[key]=row
    if set(receipts)!=set(wire):raise ValueError('time source receipt packet coverage')
    result.update(source_receipts=len(receipts),time_receipt_bytes=total,max_source_grid_error_ns=largest_error,
        hil_sensor_times_checked=sum(k[0]=='hil_sensor' for k in wire),gps_times_checked=sum(k[0]=='hil_gps' for k in wire),
        former_failure_step_wire_us=wire.get(('hil_sensor',1007)),
        source_times_preserved=True,wire_times_rewritten_after_receive=False)
    return result

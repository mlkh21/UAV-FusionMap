"""Compile the real C++ grid/MAVLink probe and compare it with frozen test literals."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from pymavlink.dialects.v20 import common
from sim_flight_initialization_selector_fixture import ROOT


def literals():
    return json.loads((ROOT/'tests/fixtures/sim_flight_initialization_time_cases.json').read_text())


def build_probe():
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    directory=ROOT/'.runtime/ros'/('flight-init-time-probe-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True)
    binary=directory/'time_probe'
    own=ROOT/'simulation/flight_initialization_time'
    command=['g++','-std=c++17','-O1','-Wno-address-of-packed-member','-I'+str(own),
        '-I'+str(ROOT/'.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0'),
        str(own/'time_probe.cpp'),'-o',str(binary)]
    with (directory/'build.log').open('x') as stream:
        child=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=30)
    if child.returncode:raise ValueError('C++ time probe build failed: '+str(directory))
    return binary


def execute(binary, trajectory=False):
    payload=''.join(row['seconds']+' '+str(row['step'])+'\n' for row in literals()['cases'])
    child=subprocess.run([str(binary)]+(['--trajectory'] if trajectory else []),
        input='' if trajectory else payload,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    if child.returncode or child.stderr:raise ValueError('C++ time probe execution failed')
    return [json.loads(line) for line in child.stdout.splitlines()]


def check_wire(row, expected):
    for name,kind in [('sensor_hex','HIL_SENSOR'),('gps_hex','HIL_GPS')]:
        parser=common.MAVLink(None)
        messages=[]
        for byte in bytes.fromhex(row[name]):
            message=parser.parse_char(bytes([byte]))
            if message is not None:messages.append(message)
        if (len(messages)!=1 or messages[0].get_type()!=kind or messages[0].time_usec!=expected
                or messages[0].get_srcSystem()!=1 or messages[0].get_srcComponent()!=200):
            raise ValueError('actual MAVLink bytes differ from independent time expectation')


def verify(binary):
    actual=execute(binary)
    if len(actual)!=len(literals()['cases']):raise ValueError('C++ boundary count')
    wire_count=0
    for expected,row in zip(literals()['cases'],actual):
        if row['accepted']!=expected['accepted']:raise ValueError('C++ acceptance: '+expected['name'])
        if row['accepted']:
            if row['time_usec']!=expected['microseconds']:raise ValueError('C++ time: '+expected['name'])
            check_wire(row,expected['microseconds']);wire_count+=2
        elif set(row)!={'accepted'}:raise ValueError('rejected source serialized a packet')
    trajectory=execute(binary,True)
    if len(trajectory)!=2501:raise ValueError('C++ trajectory count')
    for step,row in enumerate(trajectory):
        if not row['accepted'] or row['source_step']!=step or row['time_usec']!=step*4000:
            raise ValueError('C++ accumulated-double grid error')
        check_wire(row,step*4000);wire_count+=2
    return dict(boundary_cases=len(actual),accepted_cases=sum(row['accepted'] for row in actual),
        trajectory_records=len(trajectory),actual_mavlink_packets=wire_count,binding_status='unverified',control_gate_accepted=False)

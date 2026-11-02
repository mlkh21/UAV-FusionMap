import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from flight_bridge.adapt import adapt, replace_once
from sim_flight_diagnostic_run import create_ic
from ufm_simulation.flight_contract import load_profile
from sim_flight_fixture import record, header
from sim_flight_diagnostic_checks import verify

ROOT=Path(__file__).resolve().parents[1]
BRIDGE=ROOT/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'


class FlightDiagnosticsTests(unittest.TestCase):
    def test_actual_source_adaptations_have_exact_context(self):
        for name in ('jsbsim_bridge.cpp','mavlink_interface.cpp','actuator_plugin.cpp'):
            original=(BRIDGE/'src'/name).read_text()
            changed=adapt(name,original)
            self.assertNotEqual(changed,original)
            with self.assertRaises(ValueError):adapt(name,changed)
            self.assertEqual(original,(BRIDGE/'src'/name).read_text())

    def test_context_missing_or_repeated_is_rejected(self):
        for value in ('','old old'):
            with self.assertRaises(ValueError):replace_once(value,'old','new')
        self.assertEqual(replace_once('a old b','old','new'),'a new b')
        with self.assertRaises(ValueError):adapt('other.cpp','')

    def test_ground_ic_from_actual_source_keeps_original(self):
        profile=load_profile(ROOT/'configs/sim_flight_fixture.json')
        source=BRIDGE/'scene/LSZH.xml';before=source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory)/'initial.xml'
            create_ic(source,dest,profile)
            node=ET.parse(dest).getroot()
            self.assertEqual(node.find('altitude').get('unit'),'M')
            self.assertEqual(float(node.find('altitude').text),.5)
            self.assertEqual(float(node.find('elevation').text),419.2)
            self.assertEqual([float(node.find(key).text) for key in ('phi','theta','psi')],[0.,0.,90.])
            self.assertEqual(float(node.find('vt').text),0.)
            self.assertIsNone(node.find('gamma'))
            with self.assertRaises(FileExistsError):create_ic(source,dest,profile)
        self.assertEqual(source.read_bytes(),before)

    def test_incomplete_ic_refuses_to_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'bad.xml';source.write_text('<initialize/>')
            dest=Path(directory)/'out.xml'
            with self.assertRaises(ValueError):create_ic(source,dest,load_profile(ROOT/'configs/sim_flight_fixture.json'))
            self.assertFalse(dest.exists())

    def test_short_window_expectations_are_independent_of_long_profile(self):
        expected=json.loads((ROOT/'tests/fixtures/sim_flight_diagnostic_expectations.json').read_text())
        self.assertEqual(expected['max_steps'],250)
        self.assertEqual(expected['max_source_time_s'],1.)
        self.assertEqual(expected['allowed_host_tx_ids'],[107,113])
        self.assertFalse(expected['control_gate_accepted'])
        self.assertEqual(expected['binding_status'],'unverified')
        self.assertGreater(load_profile(ROOT/'configs/sim_flight_fixture.json')['time']['max_step'],250)

    def audit_fixture(self, directory, change=None):
        from pymavlink.dialects.v20 import common
        directory=Path(directory)
        expected=json.loads((ROOT/'tests/fixtures/sim_flight_diagnostic_expectations.json').read_text())
        first=record(1,present=True);last=record(2)
        last['fdm'].update(ran=False,result=None,sim_time_after_s=.004)
        meta=header();profile=meta['profile'];lat=math.radians(profile['ic']['latitude_deg'])
        lon=math.radians(profile['ic']['longitude_deg']);a,b=6378137.,6356752.314245
        eccentricity=1-(b/a)**2;n=a/math.sqrt(1-eccentricity*math.sin(lat)**2);height=419.7
        x,y=(n+height)*math.cos(lat)*math.cos(lon),(n+height)*math.cos(lat)*math.sin(lon)
        z=(n*(1-eccentricity)+height)*math.sin(lat);radius=math.sqrt(x*x+y*y+z*z)
        sea=1/math.sqrt(((x*x+y*y)/a**2+z*z/b**2)/radius**2)
        meta.update(agl_m=.5,terrain_m=419.2,geodetic_altitude_m=height,asl_m=radius-sea,
            latitude_deg=profile['ic']['latitude_deg'],longitude_deg=profile['ic']['longitude_deg'],
            vt_mps=0.,euler_deg=[0.,0.,90.],ellipsoid_axes_m=[a,b],ecef_m=[x,y,z])
        rows=[first,last];wire=[]
        tx=common.MAVLink(None,srcSystem=1,srcComponent=200)
        rx=common.MAVLink(None,srcSystem=1,srcComponent=1)
        for row in rows:
            raw=tx.hil_sensor_encode(row['hil_sensor_time_us'],*([0.]*13),8191).pack(tx)
            wire.append(dict(direction='tx',step_index=row['step_index'],length=len(raw),sent=len(raw),hex=raw.hex()))
            if row['has_actuator']:
                raw=rx.hil_actuator_controls_encode(row['actuator']['time_usec'],[0.]*16,1,1).pack(rx)
                wire.append(dict(direction='rx',step_index=row['step_index'],length=len(raw),sent=len(raw),hex=raw.hex()))
        terminal=dict(reason='peer_closed',control_gate_accepted=False)
        if change:change(meta,rows,wire,terminal)
        for name,value in [('initial.json',meta),('terminal.json',terminal)]:
            (directory/name).write_text(json.dumps(value))
        for name,values in [('actuators.jsonl',rows),('wire.jsonl',wire)]:
            (directory/name).write_text(''.join(json.dumps(value)+'\n' for value in values))
        return verify(directory,meta['run_id'],profile,expected,disconnect=True)

    def test_independent_mavlink_bytes_and_radial_height_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            result=self.audit_fixture(directory)
        self.assertEqual(result['stream']['actuator_observations'],1)
        self.assertEqual(result['actuator_hil_deltas_us'],[1])
        self.assertFalse(result['control_gate_accepted'])

    def test_mismatched_receipt_wire_crc_and_height_are_rejected(self):
        def altered_time(meta,rows,wire,terminal):rows[0]['actuator']['time_usec']+=1
        def corrupt_wire(meta,rows,wire,terminal):wire[0]['hex']=wire[0]['hex'][:-2]+'01'
        def wrong_asl(meta,rows,wire,terminal):meta['asl_m']=419.7
        def fake_control_gate(meta,rows,wire,terminal):terminal['control_gate_accepted']=True
        for change in (altered_time,corrupt_wire,wrong_asl,fake_control_gate):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):self.audit_fixture(directory,change)


if __name__=='__main__':unittest.main()

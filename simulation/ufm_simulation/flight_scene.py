"""Explicit ground flight v2 registration, continuous physical validation and readiness."""
import copy
from fractions import Fraction
import math

import numpy as np
from scipy.spatial.transform import Rotation

from ufm_flight_contract import contract as c
from ufm_flight_contract.profile import validate_profile
from . import flight_initialization_contract as physical
from .scene_motion import SceneTransactions

CHECKPOINTS = (125,250,500,1000,1500,2000,2500,5000,7000,7250,7500)
READY_CHECKPOINTS = (7000,7250,7500)
PROFILE_ID = 'sim-flight-scene-observe-v2'


def validate_source(value):
    c.fields(value, 'step_index sim_time_s ecef_ft R_ecef_frd uvw_ftps pqr_radps')
    c.integer(value['step_index'], c.MAX_STEPS)
    c.number(value['sim_time_s'])
    if abs(Fraction(value['sim_time_s'])*1000000000-value['step_index']*c.STEP_NS)>1:
        raise ValueError('flight_source_time')
    for key, size in (('ecef_ft',3),('R_ecef_frd',9),('uvw_ftps',3),('pqr_radps',3)):
        c.vector(value[key],size)
    rotation = np.array(value['R_ecef_frd']).reshape(3,3)
    if (not np.allclose(rotation@rotation.T,np.eye(3),rtol=0,atol=1e-9)
            or abs(np.linalg.det(rotation)-1)>1e-9):
        raise ValueError('flight_source_rotation')


class FlightRegistration:
    def __init__(self, initial, latitude_rad, longitude_rad, profile):
        validate_profile(profile); validate_source(initial)
        for value in (latitude_rad,longitude_rad): c.number(value)
        if initial['step_index']!=0 or not (-math.pi/2<=latitude_rad<=math.pi/2 and -math.pi<=longitude_rad<=math.pi):
            raise ValueError('flight_initial_registration')
        s,t = math.sin(latitude_rad),math.cos(latitude_rad)
        S,C = math.sin(longitude_rad),math.cos(longitude_rad)
        self.Q = np.array([[-S,C,0],[-s*C,-s*S,t],[t*C,t*S,s]])
        self.origin = np.array(initial['ecef_ft'])
        self.metadata = dict(registration_id=c.REGISTRATION, ecef_origin_ft=self.origin.tolist(),
            geodetic_latitude_rad=latitude_rad,longitude_rad=longitude_rad,
            Q_ecef_to_enu=self.Q.reshape(-1).tolist(),scene_anchor_m=list(c.ANCHOR_M),
            body_origin_policy=profile['body_origin_policy'])

    def convert(self, source, run_id):
        validate_source(source)
        index = source['step_index']
        rotation = self.Q@np.array(source['R_ecef_frd']).reshape(3,3)@np.diag([1.,-1.,-1.])
        position = np.array(c.ANCHOR_M)+self.Q@(np.array(source['ecef_ft'])-self.origin)*.3048
        value = dict(protocol_version=2,step_index=index,registration_id=c.REGISTRATION,
            angular_velocity_flu=(np.array(source['pqr_radps'])*[1.,-1.,-1.]).tolist(),state=dict(
                header=dict(schema_version='0.1',run_id=run_id,clock_id='sim:'+run_id,
                    timestamp=index*c.STEP_NS,sample_id='scene.frame:%s:%d'%(run_id,index),
                    frame_id='scene_world',source_type='simulation',status='valid',reason=''),
                position=position.tolist(),orientation_xyzw=Rotation.from_matrix(rotation).as_quat().tolist(),
                linear_velocity=(np.array(source['uvw_ftps'])*[.3048,-.3048,-.3048]).tolist(),
                body_frame_id='base_link',velocity_frame_id='base_link',state_source='ground_truth',
                quality=dict(confidence=None,uncertainty=dict(status='unavailable',kind='',value=None,
                    unit='',source=c.QUALITY_SOURCE))))
        c.validate_frame(value)
        return value


class FlightTransactions(SceneTransactions):
    validate_frame = staticmethod(c.validate_frame)
    validate_response = staticmethod(c.validate_response)


class PhysicalStream:
    def __init__(self, run_id, initial):
        self.run_id,self.initial = run_id,copy.deepcopy(initial)
        physical.validate_kinematics(initial['initial_kinematics'])
        physical.validate_ground(initial['initial_ground'])
        k = initial['initial_kinematics']
        if (k['sim_time_s']!=0 or abs(k['agl_m']-.5)>1e-6 or abs(k['terrain_m']-419.2)>1e-6
                or k['true_airspeed_mps']!=0 or any(abs(a-b)>1e-9 for a,b in zip(k['euler_deg'],[0,0,90]))
                or initial['initial_properties']!=[0,0,0,0]):
            raise ValueError('flight_initial_readback')
        self.previous,self.ground = k,initial['initial_ground']
        self.count=self.observed=self.settled=self.sequence=self.last_actuator=0
        self.wall=initial['initial_wall_ns']
        self.failed=False
        self.checkpoints={}

    def add(self, row):
        physical.validate_step_fields(row,'sim_flight_scene_step.v1',PROFILE_ID,10000)
        if (self.failed or row['run_id']!=self.run_id or row['step_index']!=self.count+1
                or row['kinematics_before']!=self.previous or row['ground_before']!=self.ground
                or row['wall']['hil_sent_ns']<self.wall):
            raise ValueError('flight_physical_continuity')
        if row['has_actuator']:
            a = row['actuator']
            if (a['peer']!=self.initial['peer'] or a['receive_sequence']!=self.sequence+1
                    or (self.observed and a['time_usec']<=self.last_actuator)):
                raise ValueError('flight_actuator_identity_or_sequence')
            self.sequence,self.last_actuator=a['receive_sequence'],a['time_usec']
            self.observed+=1
        elif self.observed and row['fdm']['ran']:
            raise ValueError('flight_missing_after_first')
        self.count+=1
        self.previous,self.ground=row['kinematics_after'],row['ground_after']
        self.wall=row['wall']['fdm_finished_ns']
        if self.wall-self.initial['initial_wall_ns']>240000000000:
            raise ValueError('flight_physical_deadline')
        safe = physical._safe(self.previous,self.initial['initial_kinematics'])
        self.failed = row['fdm']['result'] is not True or not safe
        sensor=row['fdm']['hil_sensor']
        stable = (not self.failed and any(g['wow'] for g in self.ground) and 0<=self.previous['agl_m']<=1
            and physical.norm(self.previous['vel_ned_mps'])<=.5
            and physical.norm(self.previous['pqr_radps'])<=math.radians(15)
            and 7.84532<=physical.norm(sensor['accel_mps2'])<=11.76798)
        self.settled=self.settled+1 if stable else 0
        if self.count in CHECKPOINTS:
            self.checkpoints[str(self.count)]=dict(input_settled=self.settled>=250,
                actuator_count=self.observed,last_hil_us=row['hil_sensor_time_us'],fdm_time_s=row['fdm']['sim_time_after_s'])
        return not self.failed

    def preparation_ready(self, readiness):
        values=[readiness.get(str(i),{}) for i in READY_CHECKPOINTS]
        if not all(v.get('ready') and self.checkpoints.get(str(i),{}).get('input_settled') for i,v in zip(READY_CHECKPOINTS,values)):
            return False
        if any(b[k]<=a[k] for a,b in zip(values,values[1:]) for k in ('attitude_sample','vehicle_sample')):
            return False
        return self.checkpoints['7500']['actuator_count']-self.checkpoints['7000']['actuator_count']>=2

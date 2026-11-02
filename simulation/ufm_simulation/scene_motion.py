"""Fixed JSBSim CG/ECEF registration and bounded single-flight transactions."""
import copy
import math

import numpy as np
from scipy.spatial.transform import Rotation

from ufm_scene_contract.contract import (QUALITY_SOURCE, REGISTRATION, STEP_NS,
    validate_frame, validate_response)
from ufm_scene_contract.profile import validate_profile, validate_source_sample


class SceneRegistration:
    def __init__(self, initial, latitude_rad, longitude_rad, profile):
        validate_profile(profile)
        validate_source_sample(initial, profile)
        if initial['step_index'] != 0 or any(type(v) not in (float, int) or
                not math.isfinite(v) for v in (latitude_rad, longitude_rad)):
            raise ValueError('scene_initial_registration')
        if not -math.pi/2 <= latitude_rad <= math.pi/2 or not -math.pi <= longitude_rad <= math.pi:
            raise ValueError('scene_initial_latitude_longitude')
        s, c = math.sin(latitude_rad), math.cos(latitude_rad)
        S, C = math.sin(longitude_rad), math.cos(longitude_rad)
        self.Q = np.array([[-S, C, 0.], [-s*C, -s*S, c], [c*C, c*S, s]])
        self.origin = np.array(initial['ecef_ft'])
        self.profile = copy.deepcopy(profile)
        self.metadata = dict(registration_id=REGISTRATION, ecef_origin_ft=self.origin.tolist(),
            geodetic_latitude_rad=latitude_rad, longitude_rad=longitude_rad,
            Q_ecef_to_enu=self.Q.reshape(-1).tolist(), scene_anchor_m=profile['scene_anchor_m'],
            body_origin_policy=profile['body_origin_policy'],
            earth_model='JSBSim WGS84; geodetic latitude from FGPropagate')

    def convert(self, sample, run_id):
        validate_source_sample(sample, self.profile)
        position = np.array(self.profile['scene_anchor_m']) + self.Q @ (np.array(sample['ecef_ft']) - self.origin) * .3048
        if np.linalg.norm(position - self.profile['scene_anchor_m']) > self.profile['max_anchor_distance_m']:
            raise ValueError('scene_registration_distance')
        if position[2] <= .5:
            raise ValueError('scene_ground_proximity')
        rotation = self.Q @ np.array(sample['R_ecef_frd']).reshape(3, 3) @ np.diag([1., -1., -1.])
        value = dict(protocol_version=1, step_index=sample['step_index'], registration_id=REGISTRATION,
            angular_velocity_flu=(np.array(sample['pqr_radps']) * [1., -1., -1.]).tolist(), state=dict(
                header=dict(schema_version='0.1', timestamp=sample['step_index'] * STEP_NS,
                    run_id=run_id, clock_id='sim:' + run_id,
                    sample_id='scene.frame:%s:%d' % (run_id, sample['step_index']),
                    frame_id='scene_world', source_type='simulation', status='valid', reason=''),
                position=position.tolist(), orientation_xyzw=Rotation.from_matrix(rotation).as_quat().tolist(),
                linear_velocity=(np.array(sample['uvw_ftps']) * [.3048, -.3048, -.3048]).tolist(),
                body_frame_id='base_link', velocity_frame_id='base_link', state_source='ground_truth',
                quality=dict(confidence=None, uncertainty=dict(status='unavailable', kind='', value=None,
                    unit='', source=QUALITY_SOURCE))))
        validate_frame(value)
        return value


class SceneTransactions:
    """One pending and one completed frame; failure cannot be revived by a late reply."""
    def __init__(self, run_id):
        self.run_id = run_id
        self.pending = self.completed = self.receipt = None
        self.failed = None

    def fail(self, reason):
        if self.failed is None:
            self.failed = reason
        self.pending = None

    def begin(self, frame):
        validate_frame(frame)
        if self.failed:
            raise ValueError('scene_run_locked')
        if frame['state']['header']['run_id'] != self.run_id:
            self.fail('scene_identity_changed')
            raise ValueError(self.failed)
        if self.pending is not None:
            raise ValueError('scene_transaction_pending')
        if self.completed is not None and frame['step_index'] == self.completed['step_index']:
            if frame != self.completed:
                self.fail('scene_step_conflict')
                raise ValueError(self.failed)
            return copy.deepcopy(self.receipt)
        wanted = 0 if self.completed is None else self.completed['step_index'] + 1
        if frame['step_index'] != wanted:
            raise ValueError('scene_step_sequence')
        self.pending = copy.deepcopy(frame)
        return None

    def finish(self, receipt):
        if self.failed or self.pending is None:
            raise ValueError('scene_no_pending_transaction')
        try:
            validate_response(receipt, request=dict(frame=self.pending))
            if not receipt['accepted']:
                raise ValueError(receipt['reason'])
        except ValueError as exc:
            self.fail(str(exc))
            raise
        self.completed, self.receipt = self.pending, copy.deepcopy(receipt)
        self.pending = None
        return copy.deepcopy(self.completed['state'])

    def terminal(self, reason):
        self.fail(reason)
        if self.completed is None:
            return None
        state = copy.deepcopy(self.completed['state'])
        state['header'].update(status='unavailable', reason='terminal:' + self.failed,
            sample_id='sim.terminal:%s:%d' % (self.failed, state['header']['timestamp']))
        # Unavailable slots are canonical placeholders, never a new geometric observation.
        state.update(position=[0., 0., 0.], orientation_xyzw=[0., 0., 0., 0.], linear_velocity=[0., 0., 0.])
        return state

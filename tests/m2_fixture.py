"""Test-only explicit occupied/free evidence, with no sensor or research imports."""
import copy
from pathlib import Path

import yaml
from ufm_mapping.m2_contract import validate_spec


CONFIG = Path(__file__).resolve().parents[1] / 'configs/m2_fixture.yaml'
SCENARIOS = {
    'positive_twice': ('occupied', 'occupied'),
    'negative_twice': ('free', 'free'),
    'positive_saturation_then_reverse': ('occupied', 'occupied', 'occupied', 'free'),
    'negative_saturation_then_reverse': ('free', 'free', 'free', 'occupied'),
    'reverse_to_free': ('occupied', 'occupied', 'free', 'free', 'free'),
    'cancel_to_unknown': ('occupied', 'free'),
    'neutral_without_history': ('neutral',),
    'no_evidence_without_history': ('unobserved', 'empty', 'no_return', 'unavailable'),
    'no_evidence_preserves_history': ('occupied', 'unobserved', 'empty', 'no_return',
                                      'neutral', 'unavailable', 'degraded'),
}


def load_spec(path=CONFIG):
    spec = yaml.safe_load(Path(path).read_text())
    validate_spec(spec)
    return spec


def observation(spec, run_id, sequence, kind):
    if kind not in {'occupied', 'free', 'neutral', 'unobserved', 'empty', 'no_return',
                    'unavailable', 'degraded'}:
        raise ValueError('unknown M2 fixture step: ' + kind)
    if type(sequence) is not int or sequence < 0 or not isinstance(run_id, str) or not run_id.strip():
        raise ValueError('M2 fixture requires run identity and nonnegative sequence')
    stamp = (sequence + 1) * spec['sample_period_ns']
    status = kind if kind in ('unavailable', 'degraded') else 'valid'
    identity = [float(row == col) for row in range(4) for col in range(4)]
    unknown = dict(status='unavailable', kind='', value=None, unit='', source='M2 arithmetic fixture')
    voxels = []
    if kind in ('occupied', 'free', 'neutral', 'unobserved'):
        field = {'occupied': 'occupied_probability', 'free': 'free_probability',
                 'neutral': 'neutral_probability', 'unobserved': 'neutral_probability'}[kind]
        voxels.append(dict(index=list(spec['cell_index']), probability=spec[field],
                           observed=kind != 'unobserved', confidence=None,
                           uncertainty=copy.deepcopy(unknown)))
    return dict(header=dict(schema_version='0.1', run_id=run_id, clock_id='sim:' + run_id,
        sample_id='perception.occupancy:m2-fixture:%s:%d' % (run_id, sequence),
        timestamp=stamp, frame_id='odom', source_type='fixture', status=status,
        reason='' if status == 'valid' else 'm2_fixture_' + kind),
        context=dict(reference_timestamp=stamp, clock_id='sim:' + run_id,
            source_frame_id='odom', mapping_frame_id='odom',
            T_mapping_source=list(identity), T_mapping_source_status='available',
            T_mapping_body=list(identity), T_mapping_body_status='available',
            calibration_id=spec['calibration_id'], state_source='fixture',
            pose_uncertainty=copy.deepcopy(unknown)),
        resolution=list(spec['resolution']), shape=list(spec['shape']), origin=list(spec['origin']),
        observed_domain_source=spec['observed_domain_source'], voxels=voxels)

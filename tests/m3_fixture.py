"""Test-only declared rational events and public M3 occupancy inputs; no map updates."""
import copy
from fractions import Fraction
from pathlib import Path

import yaml
from m2_fixture import observation as arithmetic_observation
from ufm_mapping.m3_contract import validate_spec, wire_probability


CONFIG = Path(__file__).resolve().parents[1] / 'configs/m3_fixture.yaml'


def load_spec(path=CONFIG):
    spec = yaml.safe_load(Path(path).read_text())
    validate_spec(spec)
    return spec


def interval_quality(spec, bounds, *, output=False):
    profile = spec['interval_profile']
    return dict(status='unavailable' if bounds is None else 'available', kind=profile['kind'],
        value=None if bounds is None else [float(Fraction(value)) for value in bounds],
        unit=profile['unit'], source=profile['unavailable_source'] if bounds is None else
        profile['output_source' if output else 'input_source'])


def scenarios(spec):
    arithmetic = spec['arithmetic']

    def series(kinds, missing=(), stamps=None):
        rows = []
        for index, kind in enumerate(kinds):
            if kind in ('occupied', 'free'):
                probability = str(Fraction(str(arithmetic[kind + '_probability'])))
                bounds = None if index in missing else [str(Fraction(str(value)))
                            for value in spec['evidence_intervals'][kind]]
            elif kind in ('neutral', 'unobserved'):
                probability, bounds = '1/2', ['1/2', '1/2'] if kind == 'neutral' else None
            else:
                probability, bounds = None, None
            rows.append(dict(kind=kind, timestamp=(index + 1) * arithmetic['sample_period_ns']
                if stamps is None else stamps[index], probability=probability, bounds=bounds))
        return rows

    point = dict(kind='occupied', probability='11744051/16777216',
                 bounds=['11744051/16777216'] * 2)  # binary32 nearest to decimal 0.7
    return {
        'bounded_positive_then_free': series(('occupied', 'occupied', 'free')),
        'positive_saturation_reverse': series(('occupied',) * 3 + ('free',) * 3),
        'negative_saturation_reverse': series(('free',) * 3 + ('occupied',) * 3),
        'zero_width_binary32': [dict(copy.deepcopy(point), timestamp=(i + 1) *
                                    arithmetic['sample_period_ns']) for i in range(2)],
        'missing_lock': series(('occupied', 'free', 'occupied'), missing=(1,)),
        'missing_then_ttl_restart': series(('occupied', 'free', 'empty', 'empty', 'occupied'),
            missing=(0,), stamps=(10_000_000, 20_000_000, 120_000_000, 120_000_001, 130_000_000)),
        'no_evidence_preserves_quality': series(('occupied', 'unobserved', 'empty', 'no_return',
                                                'neutral', 'unavailable', 'degraded')),
        'no_evidence_without_history': series(('unobserved', 'empty', 'no_return', 'neutral',
                                               'unavailable', 'degraded')),
        'zero_width_neutral': series(('neutral',)),
        'ttl_boundary': series(('occupied', 'empty', 'empty', 'free'),
            stamps=(10_000_000, 110_000_000, 110_000_001, 120_000_000)),
    }


def observation(spec, run_id, sequence, event):
    row = arithmetic_observation(spec['arithmetic'], run_id, sequence, event['kind'])
    row['header'].update(timestamp=event['timestamp'],
                         sample_id='perception.occupancy:m3-fixture:%s:%d' % (run_id, sequence))
    row['context']['reference_timestamp'] = event['timestamp']
    for voxel in row['voxels']:
        voxel['probability'] = wire_probability(float(Fraction(event['probability'])))
        voxel['uncertainty'] = interval_quality(spec, event['bounds'])
    return row

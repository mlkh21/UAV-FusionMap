"""Exact rational odds oracle; independent of fixture conversion and log-odds code."""
from fractions import Fraction


def expected_sequence(kinds, spec):
    prior = Fraction(str(spec['prior_probability']))
    low, high = (Fraction(str(spec[key])) for key in ('minimum_probability', 'maximum_probability'))
    prior_odds = prior / (1 - prior)
    low_odds, high_odds = low / (1 - low), high / (1 - high)
    odds, last_stamp, result = prior_odds, None, []
    for index, kind in enumerate(kinds):
        if kind in ('occupied', 'free'):
            if (last_stamp is not None and (index + 1) * spec['sample_period_ns'] - last_stamp >
                    spec['evidence_ttl_ns']):
                raise ValueError('M2-SW-01 oracle excludes TTL restart scenarios')
            probability = Fraction(str(spec[kind + '_probability']))
            odds = min(high_odds, max(low_odds, odds * probability / (1 - probability) / prior_odds))
            last_stamp = (index + 1) * spec['sample_period_ns']
        elif kind not in ('neutral', 'unobserved', 'empty', 'no_return', 'unavailable', 'degraded'):
            raise ValueError('oracle received unknown fixture event')
        probability = odds / (1 + odds) if last_stamp is not None else None
        result.append(dict(probability=float(probability) if probability is not None else None,
            probability_fraction=str(probability) if probability is not None else None,
            observed=last_stamp is not None, last_observed_timestamp=last_stamp))
    return result


def expected_timed_sequence(kinds, timestamps, spec):
    """SW-03 exact scalar evidence expectations with explicit event times and TTL restarts."""
    if len(kinds) != len(timestamps):
        raise ValueError('timed oracle event/time length differs')
    if any(type(stamp) is not int or not 0 <= stamp < 2**63 for stamp in timestamps) or any(
            later <= earlier for earlier, later in zip(timestamps, timestamps[1:])):
        raise ValueError('timed oracle requires strictly increasing nonnegative int64 time')
    prior = Fraction(str(spec['prior_probability']))
    lower, upper = (Fraction(str(spec[key])) for key in ('minimum_probability', 'maximum_probability'))
    prior_odds = prior / (1 - prior)
    bounds = lower / (1 - lower), upper / (1 - upper)
    odds, last_stamp, result = prior_odds, None, []
    for kind, stamp in zip(kinds, timestamps):
        if kind in ('occupied', 'free'):
            if last_stamp is not None and stamp - last_stamp > spec['evidence_ttl_ns']:
                odds = prior_odds
            evidence = Fraction(str(spec[kind + '_probability']))
            odds = min(bounds[1], max(bounds[0], odds * evidence / (1 - evidence) / prior_odds))
            last_stamp = stamp
        elif kind not in ('neutral', 'unobserved', 'empty', 'no_return', 'unavailable', 'degraded'):
            raise ValueError('timed oracle received unknown fixture event')
        probability = odds / (1 + odds) if last_stamp is not None else None
        result.append(dict(probability=float(probability) if probability is not None else None,
            probability_fraction=str(probability) if probability is not None else None,
            observed=last_stamp is not None, last_observed_timestamp=last_stamp))
    return result

"""Exact rational event oracle, independent of contracts, fixture builders and map code."""
from fractions import Fraction as F


def expected_sequence(events, arithmetic):
    stamps = [event['timestamp'] for event in events]
    if any(type(stamp) is not int or not 0 <= stamp < 2**63 for stamp in stamps) or any(
            b <= a for a, b in zip(stamps, stamps[1:])):
        raise ValueError('M3 oracle requires strictly increasing int64 event times')
    prior = F(str(arithmetic['prior_probability']))
    prior_odds = prior / (1 - prior)
    low, high = (F(str(arithmetic[key])) for key in ('minimum_probability', 'maximum_probability'))
    low_odds, high_odds = low / (1 - low), high / (1 - high)
    odds, bounds, last_stamp, revision, result = prior_odds, None, None, 0, []

    def update(previous_odds, evidence):
        return max(low_odds, min(high_odds, previous_odds * evidence / (1 - evidence) / prior_odds))

    for event in events:
        kind, stamp = event['kind'], event['timestamp']
        if kind in ('occupied', 'free'):
            evidence = F(event['probability'])
            if not 0 < evidence < 1 or evidence == prior:
                raise ValueError('M3 oracle contributing event needs nonneutral probability')
            interval = None if event['bounds'] is None else [F(value) for value in event['bounds']]
            if interval is not None and (len(interval) != 2 or not 0 < interval[0] <= evidence <= interval[1] < 1):
                raise ValueError('M3 oracle evidence interval invalid')
            if last_stamp is None or stamp - last_stamp > arithmetic['evidence_ttl_ns']:
                odds, bounds = prior_odds, [prior_odds, prior_odds]
            odds = update(odds, evidence)
            bounds = None if bounds is None or interval is None else [
                update(bounds[axis], interval[axis]) for axis in range(2)]
            last_stamp, revision = stamp, revision + 1
        elif kind not in ('neutral', 'unobserved', 'empty', 'no_return', 'unavailable', 'degraded'):
            raise ValueError('M3 oracle received unknown event kind')
        elif kind == 'neutral' and (F(event['probability']) != prior or
                event['bounds'] is not None and [F(value) for value in event['bounds']] != [prior, prior]):
            raise ValueError('M3 oracle excludes nonpoint neutral evidence')
        probability = None if last_stamp is None else odds / (1 + odds)
        interval = None if bounds is None else [value / (1 + value) for value in bounds]
        if interval is not None and not interval[0] <= probability <= interval[1]:
            raise ValueError('M3 oracle interval excludes nominal probability')
        if probability is None:
            status = 'unavailable'
        elif stamp - last_stamp > arithmetic['evidence_ttl_ns']:
            status = 'stale'
        elif probability >= F(str(arithmetic['occupied_threshold'])):
            status = 'occupied'
        elif probability <= F(str(arithmetic['free_threshold'])):
            status = 'free'
        else:
            status = 'unknown'
        result.append(dict(probability=None if probability is None else float(probability),
            probability_fraction=None if probability is None else str(probability),
            interval=None if interval is None else [float(value) for value in interval],
            interval_fractions=None if interval is None else [str(value) for value in interval],
            quality_available=interval is not None, observed=last_stamp is not None,
            last_observed_timestamp=last_stamp, revision=revision, status=status))
    return result

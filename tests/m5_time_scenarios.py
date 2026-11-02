"""Independent M5 sequence declarations; never import the terrain candidate."""
import copy
import json

from m5_fixture import query_request, unavailable_quality


def capacity_spec(baseline):
    spec = copy.deepcopy(baseline)
    spec['registration']['valid_interval_ns'] = [0,10000]
    spec['eligibility']['valid_interval_ns'] = [100,10000]
    spec['identity']['dataset_version'] = 'budget-v00'
    spec['grid'].update(rows=4,columns=4,heights=[float(i) for i in range(16)],
        no_data_mask=[False]*16,
        height_quality=[dict(status='unavailable',kind='',value=None,unit='',source='fixture') for _ in range(16)])
    length = len(json.dumps(spec,sort_keys=True,separators=(',',':')).encode('utf-8'))
    spec['identity']['source_ref'] += 'p'*(16000-length)
    return spec


def scenarios(baseline):
    cases = []

    def case(name, spec):
        value = dict(name=name, spec=copy.deepcopy(spec), events=[], expected=[])
        cases.append(value)
        return value

    def add(value, operation, stamp, outcome, revision, payload=None, result=None, point=(111.,179.)):
        event = dict(sequence=len(value['events']), operation=operation, timestamp_ns=stamp)
        if payload is not None:
            event['input'] = copy.deepcopy(payload)
        if operation in ('query', 'clock_reset'):
            event['request'] = query_request(value['spec'], stamp, point)
        value['events'].append(event)
        expected = dict(outcome=outcome, terrain_revision=revision)
        if result is not None:
            expected['result'] = result
        value['expected'].append(expected)

    def unavailable(reason):
        return dict(status='unavailable', reason=reason, height=None, source_time=None,
                    dataset_version=None, installed_timestamp=None, eligibility=None,
                    registration_validity=None, source_index=None, source_xy=None,
                    quality_contributors=None,
                    height_quality=dict(status='unavailable', value=None))

    def sample(spec, installed, status, reason, height, quality, index, xy):
        result = dict(status=status, reason=reason, height=height,
            dataset_version=spec['identity']['dataset_version'], source_time=copy.deepcopy(spec['source_time']),
            eligibility=copy.deepcopy(spec['eligibility']), installed_timestamp=installed,
            registration_validity=spec['registration']['valid_interval_ns'][:],
            source_index=index, source_xy=xy, height_quality=dict(status=quality))
        if quality == 'unavailable':
            result['height_quality']['value'] = None
        if index is not None:
            offset = index[0]*spec['grid']['columns']+index[1]
            result['quality_contributors'] = dict(sample=copy.deepcopy(spec['grid']['height_quality'][offset]),
                registration=copy.deepcopy(spec['registration']['height_quality']))
        return result

    spec = copy.deepcopy(baseline)
    spec['registration']['valid_interval_ns'] = [0,10000]
    long = case('eight_versions_64_events', spec)
    previous = None
    for index in range(8):
        stamp = 100+40*index
        version = copy.deepcopy(spec)
        version['identity']['dataset_version'] = 'sequence-v'+str(index)
        version['eligibility']['valid_interval_ns'] = [stamp,stamp+20]
        version['source_time'].update(acquisition_ns=10+index, publication_ns=20+index)
        version['grid']['heights'][0] = 10.+index
        version['grid']['height_quality'][0]['value'] = [9.75+index,10.25+index]
        if index % 3 == 1:
            version['grid']['height_quality'][0] = unavailable_quality()
        elif index % 3 == 2:
            version['grid']['heights'][0] = None
            version['grid']['no_data_mask'][0] = True
            version['grid']['height_quality'][0] = unavailable_quality()
        revision = index+1
        missing = index % 3 == 2
        height = None if missing else 13.+index
        quality = 'available' if index % 3 == 0 else 'unavailable'
        expected = sample(version,stamp,'unknown' if missing else 'valid','no_data' if missing else '',
                          height,quality,[0,0],[101.,199.])
        if quality == 'available':
            # Absolute source interval + absolute registration translation interval.
            expected['height_quality']['value'] = [12.65+index,13.35+index]
        add(long,'install',stamp,'installed',revision,version)
        add(long,'query',stamp+1,expected['status'],revision,result=expected)
        add(long,'query',stamp+2,'unknown',revision,point=(111.,177.),
            result=sample(version,stamp,'unknown','no_data',None,'unavailable',[1,0],[101.,197.]))
        conflict = copy.deepcopy(version)
        conflict['source_time']['publication_ns'] += 1
        add(long,'install_conflicting',stamp+3,'rejected',revision,conflict)
        add(long,'install_identical',stamp+19,'idempotent',revision,version)
        expired = copy.deepcopy(expected)
        expired.update(status='stale',reason='terrain_expired')
        add(long,'query',stamp+20,'stale',revision,result=expired)
        rejected = previous or copy.deepcopy(version)
        if previous is None:
            rejected['grid']['target'] = []
        add(long,'install_bad_tile',stamp+21,'rejected',revision,rejected)
        add(long,'query',stamp+22,'stale',revision,point=(115.,179.),
            result=sample(version,stamp,'stale','terrain_expired',None,'unavailable',None,None))
        previous = version

    value = case('delayed_activation_registration_reset', baseline)
    add(value,'query',99,'unavailable',0,result=unavailable('terrain_unavailable'))
    add(value,'install',100,'installed',1,baseline)
    version = copy.deepcopy(baseline)
    version['identity']['dataset_version'] = 'delayed-v2'
    version['eligibility']['valid_interval_ns'] = [150,250]
    version['grid']['heights'][0] = 20.
    version['grid']['height_quality'][0] = unavailable_quality()
    add(value,'install',120,'rejected',1,version)
    add(value,'query',120,'valid',1,result=sample(baseline,100,'valid','',13.,'available',[0,0],[101.,199.]))
    add(value,'install',150,'installed',2,version)
    add(value,'query',150,'valid',2,result=sample(version,150,'valid','',23.,'unavailable',[0,0],[101.,199.]))
    add(value,'query',250,'stale',2,result=sample(version,150,'stale','terrain_expired',23.,'unavailable',[0,0],[101.,199.]))
    add(value,'query',300,'unavailable',2,result=unavailable('registration_unavailable'))
    add(value,'clock_reset',149,'unavailable',2,result=unavailable('clock_reset_new_run_required'))
    add(value,'query',301,'unavailable',2,result=unavailable('clock_reset_new_run_required'))
    add(value,'install',301,'rejected',2,version)

    value = case('disable_survives_expiry_and_retry', baseline)
    add(value,'install',100,'installed',1,baseline)
    add(value,'disable',110,'disabled',1)
    add(value,'query',111,'unavailable',1,result=unavailable('terrain_disabled'))
    add(value,'install',112,'rejected',1,baseline)
    add(value,'query',200,'unavailable',1,result=unavailable('terrain_disabled'))

    fresh = copy.deepcopy(baseline)
    for field in ('registration','eligibility'):
        fresh[field].update(run_id='m5-fresh',clock_id='sim:m5-fresh')
    value = case('independent_new_run_domain', fresh)
    add(value,'install',101,'installed',1,fresh)
    add(value,'query',101,'valid',1,result=sample(fresh,101,'valid','',13.,'available',[0,0],[101.,199.]))
    add(value,'query',102,'unavailable',1,result=unavailable('run_clock_or_frame_mismatch'))
    value['events'][-1]['request'].update(run_id='m5-fixture',clock_id='sim:m5-fixture')
    add(value,'query',103,'valid',1,result=sample(fresh,101,'valid','',13.,'available',[0,0],[101.,199.]))
    return cases

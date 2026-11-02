"""Materialize test inputs and protocol examples without executing perception or maps."""
import copy
import io
import math
import struct

import yaml

from p5_contract import ROOT, bounded, expand
from ufm_simulation.perf01a_fixture import make_motion_state
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.perf01a_fixture import make_motion_radar, make_fake_infrared, build_sensor_bundle
from ufm_mapping.terrain_dataset import from_private_fixture, dataset_context
from m3_motion_fixture import motion_observation

FRAMES = dict(odom_origin_policy='px4_estimator_local_origin', body_origin_policy='source_body_virtual_flu')


def sample(run_id, sequence, stamp, args, point):
    speed, age, delta = (args.get(k, 0) for k in ('speed_mps','pose_age_ns','ir_delta_ns'))
    source = make_motion_state(run_id, sequence, stamp-age, speed)
    state = adapt_state(source, FRAMES)
    radar = make_motion_radar(run_id, sequence, stamp, speed, [point])
    infrared = make_fake_infrared(run_id, sequence, stamp+delta) if args.get('ir_present', True) else None
    bundle, reason = build_sensor_bundle(radar, infrared, [state])
    return dict(source_state=source, state=state, radar=radar, infrared=infrared,
                bundle=bundle, reason=reason)


def terrain_dataset(inputs, run_id):
    spec = yaml.safe_load((ROOT / inputs['profiles']['terrain']['config']).read_text())
    profile = inputs['profiles']['terrain']
    spec['registration'].update(run_id=run_id, clock_id='sim:'+run_id,
                                valid_interval_ns=profile['registration_interval_ns'])
    spec['eligibility'].update(run_id=run_id, clock_id='sim:'+run_id,
                               valid_interval_ns=profile['eligibility_interval_ns'])
    return from_private_fixture(spec)


def inverse_spec(inputs, run_id, sealed=2):
    spec = yaml.safe_load((ROOT / inputs['profiles']['B']['config']).read_text())
    spec['registration'].update(run_id=run_id, clock_id='sim:'+run_id)
    spec['max_sealed_submaps'] = sealed
    return spec


def inverse(spec, stamp, args, run_id):
    body = args['body_x']
    row = motion_observation(spec['local_map'], run_id, args['sequence'], kind=args['kind'],
        bounds='default' if args['quality'] == 'bounded' else None, stamp=stamp,
        body=[body,0.,0.], points=[args['point']], origin=[body-16.,-8.,-4.])
    row['header']['sample_id'] = 'perception.occupancy:p5:%s:%d' % (run_id,args['sequence'])
    return row


def materialize(inputs):
    cases = []
    for case in inputs['cases']:
        run_id = 'p5-'+case['id'].lower().replace('.','-')
        row = dict(id=case['id'], run_id=run_id, clock_id='sim:'+run_id,
                   terrain_dataset=terrain_dataset(inputs, run_id), samples=[], observations=[])
        if case['profile'] == 'B':
            row['map_spec'] = inverse_spec(inputs, run_id, case['settings']['max_sealed_submaps'])
        for sequence, event in enumerate(expand(case, inputs['sequences'])):
            name, op, stamp, _, args = event
            if op == 'sample':
                row['samples'].append(dict(event_id=name, **sample(run_id,sequence,stamp,args,
                                             inputs['profiles']['A']['world_point'])))
            elif op == 'observation':
                row['observations'].append(dict(event_id=name,
                    value=inverse(row['map_spec'], stamp,args,run_id)))
        cases.append(row)
    return cases


def _quality(value=None, source='p5_missing_height_quality_v1'):
    return dict(status='unavailable' if value is None else 'available',
        kind='' if value is None else 'height_interval', value=value,
        unit='' if value is None else 'm', source=source)


def wire_vectors(inputs):
    run, stamp = 'p5-wire', 150_000_000
    seed = sample(run,3,stamp,{},inputs['profiles']['A']['world_point'])
    bundle = seed['bundle']
    context = copy.deepcopy(bundle['context'])
    context.update(source_frame_id='odom', T_mapping_source=[float(i//4==i%4) for i in range(16)])
    header = dict(schema_version='0.1', run_id=run, clock_id='sim:'+run, timestamp=stamp,
        sample_id='perception.occupancy:p5-wire:3', frame_id='odom', source_type='fixture', status='valid',reason='')
    unavailable_quality = dict(status='unavailable',kind='',value=None,unit='',source='p5_fixture_no_calibrated_quality')
    voxel = dict(index=[34,24,8],probability=.9,observed=True,confidence=None,
                 uncertainty=unavailable_quality)
    observation = dict(header=header,context=context,voxels=[voxel],
        observed_domain_source='fixture_radar_point',resolution=[.5]*3,shape=[64,32,16],origin=[-16.,-8.,-4.])
    unavailable = copy.deepcopy(observation)
    unavailable['header'].update(status='unavailable',reason='fixture_backend_unavailable')
    unavailable['voxels'] = []
    spec = inverse_spec(inputs,run)
    explicit = inverse(spec,110_000_000,dict(sequence=0,body_x=0,kind='occupied',
                                        point=[8.25,.25,.25],quality='bounded'),run)
    snapshot = dict(header=dict(header,source_type='derived',sample_id='mapping.snapshot:p5-wire:4'),
        map_id='p5-local',revision=4,resolution=[.5]*3,shape=[64,32,16],origin=[-16.,-8.,-4.],
        coverage=[-16.,16.,-8.,8.,-4.,4.],source_types=['fixture'],
        cells=[dict(voxel,last_observed_timestamp=stamp)])
    request = dict(map_id='p5-local',frame_id='odom',run_id=run,clock_id='sim:'+run,
        query_timestamp=250_000_001,point=[1.25,4.25,.25],max_age_ns=100_000_000)
    result = {k:v for k,v in request.items() if k != 'max_age_ns'}
    result.update(revision=4,status='stale',reason='max_age_exceeded',index=[34,24,8],
        probability=.9,confidence=None,uncertainty=unavailable_quality,observed=True,last_observed_timestamp=stamp)
    occupied = dict(result,map_id='m4-scene-fixture',frame_id='map',point=[40.25,.25,.25],
        index=[80,32,8],status='occupied',reason='',probability=.75,
        uncertainty=dict(status='available',kind='occupancy_probability_interval',unit='dimensionless',
            value=[49/85,27/34],source='m3_fixture_bounded_accumulator_v1'))
    free = copy.deepcopy(occupied)
    free.update(status='free',probability=.25)
    free['uncertainty']['value'] = [.2,.3]
    unknown = dict(occupied,status='unknown',reason='no_observation',index=None,probability=None,
        observed=False,last_observed_timestamp=None,uncertainty=unavailable_quality)
    absent = dict(unknown,status='unavailable',reason='frame_mismatch')
    dataset = terrain_dataset(inputs,run)
    terrain_context = dataset_context(dataset,100_000_000)
    tq = dict(terrain_id='m5-terrain-fixture',frame_id='map',run_id=run,clock_id='sim:'+run,
        query_timestamp=stamp,point_xy=[111.,179.],pin_version=True,
        expected_provider_instance_id='p5-wire-instance',expected_terrain_revision=1)
    tr = dict(protocol_version=1,provider_instance_id='p5-wire-instance',terrain_id=tq['terrain_id'],
        frame_id='map',run_id=run,clock_id='sim:'+run,query_timestamp=stamp,point_xy=[111.,179.],
        evaluation_timestamp=stamp,terrain_revision=1,status='valid',reason='',context=terrain_context,
        height=13.,source_index=[0,0],source_xy=[101.,199.],
        height_quality=_quality([12.649999999999999,13.350000000000001],'fixture_height_bound_v1'),
        sample_quality=_quality([9.75,10.25],'fixture_height_bound_v1'))
    nodata = copy.deepcopy(tr)
    nodata.update(point_xy=[111.,177.],height=None,source_index=[1,0],source_xy=[101.,197.],
        status='unknown',reason='no_data',height_quality=_quality(),sample_quality=_quality())
    zero, negative = copy.deepcopy(tr), copy.deepcopy(tr)
    for row,height in ((zero,0.),(negative,-23.5)):
        row.update(height=height,height_quality=_quality(),sample_quality=_quality())
    stale = dict(tr,status='stale',reason='terrain_expired',evaluation_timestamp=1_500_000_000)
    expired = dict(tr,status='unavailable',reason='registration_unavailable',evaluation_timestamp=3_000_000_000,
        context=None,height=None,source_index=None,source_xy=None,height_quality=_quality(),sample_quality=_quality())
    ts = dict(protocol_version=1,provider_instance_id='p5-wire-instance',terrain_id=tq['terrain_id'],
        run_id=run,clock_id='sim:'+run,frame_id='map',status_sequence=1,terrain_revision=1,
        evaluation_timestamp=stamp,state='current',reason='',context=terrain_context,last_attempt_id=1,
        last_install_outcome='installed',last_install_reason='')
    return [dict(id=name,kind=kind,value=value) for name,kind,value in (
        ('state','AircraftState',seed['state']),('radar','RadarFrame',seed['radar']),
        ('infrared','InfraredFrame',seed['infrared']),('bundle','SensorBundle',bundle),
        ('occupancy','OccupancyObservation',observation),('unavailable','OccupancyObservation',unavailable),
        ('inverse','OccupancyObservation',explicit),('snapshot','MapSnapshot',snapshot),
        ('map_request','MapQueryRequest',request),('map_result','MapQueryResult',result),
        ('map_occupied','MapQueryResult',occupied),('map_free','MapQueryResult',free),
        ('map_unknown','MapQueryResult',unknown),('map_unavailable','MapQueryResult',absent),
        ('terrain_request','TerrainQueryRequest',tq),('terrain_result','TerrainQueryResult',tr),
        ('terrain_no_data','TerrainQueryResult',nodata),('terrain_zero','TerrainQueryResult',zero),
        ('terrain_negative','TerrainQueryResult',negative),('terrain_status','TerrainStatus',ts),
        ('terrain_stale','TerrainQueryResult',stale),('terrain_unavailable','TerrainQueryResult',expired),
        ('terrain_integer','TerrainQueryRequest',dict(tq,query_timestamp=2**53+1)))]


def roundtrip(kind, value):
    from ufm_ros_contract.codec import to_ros_state, from_ros_state
    from ufm_ros_contract import perf01a_codec as c
    from ufm_ros_contract.query_codec import to_ros_query_result, from_ros_query_result, from_ros_query_request
    from ufm_terrain_contract.codec import to_ros, from_ros
    from uav_fusionmap_msgs.srv import MapQueryRequest
    codecs = dict(AircraftState=(to_ros_state,from_ros_state), RadarFrame=(c.to_ros_radar,c.from_ros_radar),
        InfraredFrame=(c.to_ros_infrared,c.from_ros_infrared),SensorBundle=(c.to_ros_bundle,c.from_ros_bundle),
        OccupancyObservation=(c.to_ros_occupancy,c.from_ros_occupancy),MapSnapshot=(c.to_ros_snapshot,c.from_ros_snapshot),
        MapQueryResult=(to_ros_query_result,from_ros_query_result),
        MapQueryRequest=(lambda v: MapQueryRequest(**v),from_ros_query_request))
    bounded(value)
    if kind.startswith('Terrain'):
        encode, decode = lambda v:to_ros(kind,v), lambda m:from_ros(kind,m)
    else:
        encode, decode = codecs[kind]
    message, stream = encode(value), io.BytesIO()
    if not message._type.startswith(('uav_fusionmap_msgs/','uav_fusionmap_terrain_msgs/')):
        raise ValueError('P5 requires actual generated messages')
    message.serialize(stream)
    raw = stream.getvalue()
    decoded = decode(type(message)().deserialize(raw))
    if decode(encode(decoded)) != decoded:
        raise ValueError('P5 decoded logical fields unstable')
    return decoded, raw


def canonical(value):
    """Only probability/confidence are float32 in the selected non-terrain examples."""
    if type(value) is list:
        return [canonical(item) for item in value]
    if type(value) is dict:
        return {key: struct.unpack('<f',struct.pack('<f',item))[0]
                if key in ('probability','confidence') and item is not None else canonical(item)
                for key,item in value.items()}
    return value


def project(value, path):
    for key in path.split('.'):
        value = value[int(key)] if isinstance(value,list) else value[key]
    return value


def check_projections(decoded, expected):
    for path,wanted in expected.items():
        actual = project(decoded,path)
        if path.startswith('context.T_mapping_body.'):
            matches = type(actual) in (int,float) and math.isclose(actual,wanted,rel_tol=0.,abs_tol=1e-12)
        else:
            matches = actual == wanted
        if not matches:
            raise ValueError('P5 independent wire projection differs: '+path)

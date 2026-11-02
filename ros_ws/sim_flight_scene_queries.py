"""Owned-daemon readiness observations with an independent long-window query identity."""
import json
from pathlib import Path
import time

from sim_flight_uorb_probe import bounded_client, inspect_owner
from ufm_simulation import flight_initialization_selector as native
from ufm_simulation import flight_initialization_contract as physical
from ufm_simulation.flight_probe_contract import validate_owner
from ufm_simulation.flight_scene import CHECKPOINTS


def plan(run_id):
    physical.identity(dict(run_id=run_id,clock_id='sim:'+run_id))
    items=[(125,'parameter',p[0]) for p in physical.PARAMETERS]
    items += [(s,'topic',n) for s in CHECKPOINTS for n in native.TOPICS]
    return [dict(schema_version='sim_flight_scene_query.v1',run_id=run_id,clock_id='sim:'+run_id,
        checkpoint=s,query_index=i+1,kind=k,name=n) for i,(s,k,n) in enumerate(items)]


def observation_event(query,raw,owner,after,source,begin,end,payload):
    physical.fields(raw,'argv returncode stdout stderr')
    return dict(schema_version='sim_flight_scene_observation.v1',query=query,argv=raw['argv'],
        owner_before=owner,owner_after=after,last_hil_us=source['hil_sensor_time_us'],
        fdm_time_s=source['fdm']['sim_time_after_s'],wall_start_ns=begin,wall_end_ns=end,
        returncode=raw['returncode'],stdout=raw['stdout'],stderr=raw['stderr'],observation=payload,
        binding_status='unverified',control_gate_accepted=False)


class ReadyQueries:
    def __init__(self, root, run, px4, processes, guard, layouts):
        self.run,self.px4,self.processes,self.guard,self.layouts=run,px4,processes,guard,layouts
        self.binary_dir=root/'.runtime/build/px4-v1.13.3/bin'
        self.directory=run/'readiness';self.directory.mkdir()
        self.rows=[];self.readiness={};self.owner=None;self.native_times={};self.bytes=0
        self.expected=plan(run.name)

    def capture(self, row, kind):
        queries=[q for q in self.expected if q['checkpoint']==row['step_index'] and q['kind']==kind]
        if not queries: raise ValueError('flight_query_boundary')
        start=time.monotonic_ns(); deadline=start+400000000
        group=[]
        for query in queries:
            self.guard(deadline)
            if query!=self.expected[len(self.rows)]: raise ValueError('flight_query_order')
            begin=time.monotonic_ns(); end=min(deadline,begin+200000000)
            owner=inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            validate_owner(owner,self.binary_dir,self.run.name)
            if self.owner is not None and owner!=self.owner: raise ValueError('flight_query_owner_changed')
            self.owner=owner
            argv=[str(self.binary_dir/('px4-param' if kind=='parameter' else 'px4-listener')),'--instance','0']
            argv += ['show',query['name']] if kind=='parameter' else [query['name'],'-n','1']
            self.guard(end)
            raw=bounded_client(argv,end,self.processes,'flight-query-%03d'%query['query_index'])
            encoded=json.dumps(raw,allow_nan=False).encode()
            self.persist('%03d-raw.json'%query['query_index'],encoded)
            if 'error' in raw: raise ValueError(raw['error'])
            if raw['argv']!=argv:raise ValueError('flight_query_argv_changed')
            self.guard(end)
            after=inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            if after!=owner: raise ValueError('flight_query_owner_changed')
            payload=native.parse_native_payload(kind,query['name'],raw['stdout'],raw['stderr'],raw['returncode'],self.layouts)
            event=observation_event(query,raw,owner,after,row,begin,time.monotonic_ns(),payload)
            for item in payload['instances']:
                value=item['fields']
                if value is None:continue
                for name in ('timestamp','timestamp_sample'):
                    if name not in value:continue
                    key=(query['name'],item['instance'],name)
                    if not self.native_times.get(key,0)<=value[name]<=row['hil_sensor_time_us']:
                        raise ValueError('flight_native_time')
                    self.native_times[key]=value[name]
                if query['name']=='vehicle_control_mode' and value['flag_armed']:
                    raise ValueError('flight_observed_armed')
            self.persist('%03d-event.json'%query['query_index'],json.dumps(event,allow_nan=False).encode())
            self.rows.append(event);group.append(event);self.guard(end)
        if kind=='topic':self.readiness[str(row['step_index'])]=native.checkpoint_ready(group)
        self.guard(deadline)

    def persist(self, name, raw):
        if len(raw)>262144 or self.bytes+len(raw)>16777216: raise ValueError('flight_query_byte_limit')
        with (self.directory/name).open('xb') as stream:stream.write(raw)
        self.bytes+=len(raw)

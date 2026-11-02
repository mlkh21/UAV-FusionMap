"""Fixed read-only preparation queries, with owned daemon and wall-clock guards."""
import json
import time

from sim_flight_uorb_probe import bounded_client,inspect_owner
from ufm_simulation.flight_initialization_contract import argv_for,dumps,plan
from ufm_simulation.flight_initialization_observation import layouts_from_texts,parse_native


class InitializationQueries:
    def __init__(self,root,run,px4,processes,guard):
        self.run,self.px4,self.processes,self.guard=run,px4,processes,guard
        self.binary_dir=root/'.runtime/build/px4-v1.13.3/bin'
        frozen=json.loads((run/'sim_flight_initialization_native.json').read_text())['native_messages']
        self.layouts=layouts_from_texts(json.loads((run/'native-msg-before.json').read_text()),frozen)
        self.directory=run/'queries';self.directory.mkdir()
        self.rows=[];self.owner=None

    def budget(self,additional=0):
        metadata=('sim_flight_initialization_native.json','native-msg-before.json','quality-source-before.json')
        total=sum((self.run/n).stat().st_size for n in metadata)
        total+=sum(p.stat().st_size for p in self.directory.iterdir())
        if total+additional>16777216:raise ValueError('preparation query file budget')

    def save(self,name,raw):
        if len(raw)>262144:raise ValueError('preparation query record budget')
        self.budget(len(raw))
        with (self.directory/name).open('xb') as stream:stream.write(raw)

    def capture(self,source,kind):
        queries=[q for q in plan(self.run.name) if q['checkpoint']==source['step_index'] and q['kind']==kind]
        start=time.monotonic_ns();deadline=start+400000000
        for query in queries:
            self.guard(deadline)
            if query!=plan(self.run.name)[len(self.rows)]:raise ValueError('preparation query order')
            self.budget(524288)
            begin=time.monotonic_ns();client_deadline=min(deadline,begin+200000000)
            owner=inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            if self.owner is None:self.owner=owner
            if owner!=self.owner:raise ValueError('preparation daemon changed')
            argv=argv_for(self.binary_dir,query)
            self.guard(client_deadline)
            raw=bounded_client(argv,client_deadline,self.processes,'init-query-%02d'%query['query_index'])
            self.save('%02d-raw.json'%query['query_index'],json.dumps(raw,indent=2).encode())
            if 'error' in raw:raise ValueError(raw['error'])
            self.guard(client_deadline)
            after=inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            parsed=parse_native(query,raw['stdout'],raw['stderr'],raw['returncode'],self.layouts)
            row=dict(schema_version='sim_flight_initialization_observation.v1',query=query,argv=argv,
                owner_before=owner,owner_after=after,last_hil_us=source['hil_sensor_time_us'],
                fdm_time_s=source['fdm']['sim_time_after_s'],wall_start_ns=begin,wall_end_ns=time.monotonic_ns(),
                returncode=raw['returncode'],stdout=raw['stdout'],stderr=raw['stderr'],observation=parsed,
                binding_status='unverified',control_gate_accepted=False)
            encoded=dumps('observation',row,self.layouts,self.binary_dir)+b'\n'
            self.guard(client_deadline);self.budget(len(encoded))
            with (self.directory/'observations.jsonl').open('ab') as stream:stream.write(encoded)
            self.rows.append(row)
            self.guard(client_deadline)
        self.save('group-%d-%s.json'%(source['step_index'],kind),json.dumps(dict(
            checkpoint=source['step_index'],kind=kind,queries=len(queries),start_ns=start,
            end_ns=time.monotonic_ns(),deadline_ns=deadline)).encode())
        self.guard(deadline)

"""Independent fixed 98-query recorder for an owned observation-only PX4 daemon."""
import json
import time

from sim_flight_uorb_probe import bounded_client, inspect_owner
from ufm_simulation.flight_initialization_selector import argv_for, dumps, layouts_from_texts, parse_native, plan


class SelectorQueries:
    def __init__(self, root, run, px4, processes, guard):
        self.run,self.px4,self.processes,self.guard = run,px4,processes,guard
        self.binary_dir = root/'.runtime/build/px4-v1.13.3/bin'
        frozen = json.loads((run/'sim_flight_initialization_selector_native.json').read_text())['native_messages']
        self.layouts = layouts_from_texts(json.loads((run/'native-msg-before.json').read_text()), frozen)
        self.directory = run/'selector-queries'
        self.directory.mkdir()
        self.rows,self.owner,self.failed = [],None,False

    def budget(self, additional=0):
        metadata = ('sim_flight_initialization_selector_native.json', 'native-msg-before.json',
            'selector-source-before.json', 'quality-source-before.json',
            'sim_flight_initialization_selector_fixture.json', 'selector-header.json', 'header.json')
        total = sum((self.run/name).stat().st_size for name in metadata)
        total += sum(path.stat().st_size for path in self.directory.iterdir())
        if total+additional>16777216:
            raise ValueError('selector query file budget')

    def save(self, name, raw):
        if len(raw)>262144:
            raise ValueError('selector query record budget')
        self.budget(len(raw))
        with (self.directory/name).open('xb') as stream:
            stream.write(raw)

    def capture(self, source, kind):
        if self.failed:
            raise ValueError('selector recorder stopped')
        try:
            self._capture(source,kind)
        except Exception:
            self.failed = True
            raise

    def _capture(self, source, kind):
        expected = plan(self.run.name)
        queries = [q for q in expected if q['checkpoint']==source['step_index'] and q['kind']==kind]
        if not queries:
            raise ValueError('selector query checkpoint or kind')
        start = time.monotonic_ns()
        deadline = start+400000000
        for query in queries:
            self.guard(deadline)
            if len(self.rows)>=98 or query!=expected[len(self.rows)]:
                raise ValueError('selector query order')
            self.budget(524288)
            begin = time.monotonic_ns()
            client_deadline = min(deadline,begin+200000000)
            owner = inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            if self.owner is None:
                self.owner = owner
            if owner!=self.owner:
                raise ValueError('selector daemon changed')
            argv = argv_for(self.binary_dir,query)
            self.guard(client_deadline)
            raw = bounded_client(argv,client_deadline,self.processes,'selector-query-%02d'%query['query_index'])
            self.save('%02d-raw.json'%query['query_index'],json.dumps(raw,indent=2,allow_nan=False).encode())
            if 'error' in raw:
                raise ValueError(raw['error'])
            self.guard(client_deadline)
            after = inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            parsed = parse_native(query,raw['stdout'],raw['stderr'],raw['returncode'],self.layouts)
            row = dict(schema_version='sim_flight_initialization_selector_observation.v1',query=query,argv=argv,
                owner_before=owner,owner_after=after,last_hil_us=source['hil_sensor_time_us'],
                fdm_time_s=source['fdm']['sim_time_after_s'],wall_start_ns=begin,wall_end_ns=time.monotonic_ns(),
                returncode=raw['returncode'],stdout=raw['stdout'],stderr=raw['stderr'],observation=parsed,
                binding_status='unverified',control_gate_accepted=False)
            encoded = dumps('observation',row,self.layouts,self.binary_dir)+b'\n'
            self.guard(client_deadline)
            self.budget(len(encoded))
            with (self.directory/'observations.jsonl').open('ab') as stream:
                stream.write(encoded)
            self.rows.append(row)
            self.guard(client_deadline)
        self.save('group-%d-%s.json'%(source['step_index'],kind),json.dumps(dict(
            checkpoint=source['step_index'],kind=kind,queries=len(queries),start_ns=start,
            end_ns=time.monotonic_ns(),deadline_ns=deadline)).encode())
        self.guard(deadline)

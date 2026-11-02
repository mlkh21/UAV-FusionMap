"""Explicit diagnostic recorder using existing, owned, read-only PX4 clients."""
import json
import time

from sim_flight_uorb_probe import bounded_client, inspect_owner
from ufm_simulation.flight_probe_contract import (CLIENT_NS, GROUP_NS, RECORD_BYTES, FILE_BYTES,
    argv_for, layouts_from_texts, plan)
from ufm_simulation.flight_probe_diagnostic import dumps, observation_gate, parse_native, validate_stream


class UorbDiagnostics:
    def __init__(self, root, run, identity, px4, processes, bootstrap_deadline_ns, session_deadline_ns):
        self.run, self.identity, self.px4, self.processes = run, identity, px4, processes
        self.binary_dir = root/'.runtime/build/px4-v1.13.3/bin'
        self.layouts = layouts_from_texts(json.loads((run/'native-msg-before.json').read_text()))
        self.directory = run/'uorb-diagnostics'
        self.directory.mkdir()
        self.rows = []
        self.owner = None
        self.deadline_ns = min(bootstrap_deadline_ns, session_deadline_ns)
        self.last_group_deadline = self.deadline_ns
        self._write('native-layout-sources.json', (run/'native-msg-before.json').read_bytes())

    def guard(self, deadline_ns=None):
        if time.monotonic_ns() >= min(self.deadline_ns, deadline_ns or self.deadline_ns):
            raise ValueError('diagnostic_deadline')
        if self.px4.poll() is not None:
            raise ValueError('diagnostic_px4_died')

    def _budget(self, additional):
        if sum(path.stat().st_size for path in self.directory.iterdir())+additional > FILE_BYTES:
            raise ValueError('diagnostic_file_budget')

    def _write(self, name, raw):
        if len(raw) > RECORD_BYTES:
            raise ValueError('diagnostic_record_limit')
        self._budget(len(raw))
        with (self.directory/name).open('xb') as stream:
            stream.write(raw)

    def capture(self, source, kind='topic'):
        queries = [q for q in plan(self.identity) if q['checkpoint'] == source['step_index'] and q['kind'] == kind]
        if not queries:
            raise ValueError('diagnostic_checkpoint')
        group_start = time.monotonic_ns()
        deadline = min(group_start+GROUP_NS, self.deadline_ns)
        self.last_group_deadline = deadline
        for query in queries:
            self.guard(deadline)
            if len(self.rows) >= 21 or query != plan(self.identity)[len(self.rows)]:
                raise ValueError('diagnostic_query_order')
            self._budget(2*RECORD_BYTES)
            start = time.monotonic_ns()
            client_deadline = min(start+CLIENT_NS, deadline)
            owner = inspect_owner(self.px4.pid, self.binary_dir/'px4', self.run/'rootfs')
            if self.owner is None:
                self.owner = owner
            if owner != self.owner:
                raise ValueError('diagnostic_owner_changed')
            argv = argv_for(self.binary_dir, query)
            self.guard(client_deadline)
            result = bounded_client(argv, client_deadline, self.processes,
                'uorb-diagnostic-%02d' % query['query_index'])
            # Preserve raw output even when transport, parsing or subsequent identity checks fail.
            self._write('%02d-raw.json' % query['query_index'], json.dumps(result, indent=2).encode())
            if 'error' in result:
                raise ValueError(result['error'])
            self.guard(client_deadline)
            after = inspect_owner(self.px4.pid, self.binary_dir/'px4', self.run/'rootfs')
            observation = parse_native(query, result['stdout'], result['stderr'], result['returncode'], self.layouts)
            row = dict(schema_version='sim_flight_uorb_diagnostic.v1', query=query, argv=argv,
                owner_before=owner, owner_after=after, last_hil_us=source['hil_sensor_time_us'],
                fdm_time_s=source['fdm']['sim_time_after_s'], wall_start_ns=start, wall_end_ns=time.monotonic_ns(),
                returncode=result['returncode'], stdout=result['stdout'], stderr=result['stderr'],
                observation=observation, binding_status='unverified', control_gate_accepted=False)
            raw = dumps(row, self.layouts, self.binary_dir)+b'\n'
            self.guard(client_deadline)
            self._budget(len(raw))
            with (self.directory/'diagnostics.jsonl').open('ab') as stream:
                stream.write(raw)
            self.rows.append(row)
            observation_gate(query, observation)
            self.guard(client_deadline)
        end = time.monotonic_ns()
        self._write('group-%03d-%s.json' % (source['step_index'], kind), json.dumps(dict(
            checkpoint=source['step_index'], kind=kind, start_ns=group_start, end_ns=end,
            deadline_ns=deadline, queries=len(queries))).encode())
        self.guard(deadline)

    def finish(self):
        self.guard(self.last_group_deadline)
        result = validate_stream(self.rows, self.identity, self.layouts, self.binary_dir)
        self._write('verification.json', json.dumps(result, indent=2, allow_nan=False).encode())
        self.guard(self.last_group_deadline)
        return result

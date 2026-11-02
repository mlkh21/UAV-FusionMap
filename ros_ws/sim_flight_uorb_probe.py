"""Bounded fixed read-only PX4 daemon clients, tied to the supervisor's PX4 PID."""
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time

from ufm_simulation.flight_probe_contract import (CLIENT_NS,GROUP_NS,RAW_BYTES,FILE_BYTES,
    MESSAGE_FILES,argv_for,plan,parse_output,layouts_from_texts,dumps,validate_stream)


def inspect_owner(pid,binary,rootfs,proc=Path('/proc'),socket_path=Path('/tmp/px4-sock-0')):
    task=proc/str(pid)
    start=int((task/'stat').read_text().rsplit(')',1)[1].split()[19])
    if (task/'exe').resolve()!=binary.resolve() or (task/'cwd').resolve()!=rootfs.resolve():
        raise ValueError('probe_px4_process_identity')
    info=socket_path.lstat()
    if not stat.S_ISSOCK(info.st_mode):raise ValueError('probe_daemon_socket_type')
    matches=[]
    for line in (proc/'net/unix').read_text().splitlines()[1:]:
        columns=line.split()
        if len(columns)==8 and columns[7]==str(socket_path) and columns[3]=='00010000' and columns[4]=='0001':
            matches.append(int(columns[6]))
    if len(matches)!=1:raise ValueError('probe_daemon_socket_identity')
    owned=[]
    for descriptor in (task/'fd').iterdir():
        try:owned.append(os.readlink(descriptor))
        except FileNotFoundError:pass
    if 'socket:[%s]'%matches[0] not in owned:raise ValueError('probe_daemon_not_owned')
    again=socket_path.lstat()
    if (info.st_dev,info.st_ino)!=(again.st_dev,again.st_ino):raise ValueError('probe_daemon_replaced')
    if start!=int((task/'stat').read_text().rsplit(')',1)[1].split()[19]):raise ValueError('probe_px4_pid_reused')
    return dict(pid=pid,start_ticks=start,executable=str(binary.resolve()),rootfs=str(rootfs.resolve()),
        socket_path=str(socket_path),socket_dev=info.st_dev,socket_file_ino=info.st_ino,socket_kernel_ino=matches[0])


def bounded_client(argv,deadline_ns,processes,label):
    child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        cwd=processes.run,env=processes.env,start_new_session=True)
    processes.children[label]=child
    processes.manifest['commands'].append(dict(name=label,args=argv,pid=child.pid,read_only=True))
    chunks={'stdout':bytearray(),'stderr':bytearray()};failure=None
    try:
        with selectors.DefaultSelector() as selector:
            for name in chunks:
                stream=getattr(child,name);os.set_blocking(stream.fileno(),False)
                selector.register(stream,selectors.EVENT_READ,name)
            while selector.get_map():
                remaining=(deadline_ns-time.monotonic_ns())/1e9
                if remaining<=0:raise TimeoutError('probe_client_deadline')
                for key,_ in selector.select(min(remaining,.01)):
                    data=os.read(key.fd,4096)
                    if not data:selector.unregister(key.fileobj);continue
                    chunks[key.data].extend(data)
                    if sum(len(c) for c in chunks.values())>RAW_BYTES:raise ValueError('probe_client_output_limit')
            child.wait(timeout=max(.001,(deadline_ns-time.monotonic_ns())/1e9))
    except Exception as exc:
        failure=exc
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGKILL);processes.forced.append(label)
        child.wait(timeout=1.)
    finally:
        child.stdout.close();child.stderr.close();processes.stopped.add(label)
    result=dict(argv=argv,returncode=child.returncode)
    try:result.update({name:bytes(raw).decode('utf-8',errors='strict') for name,raw in chunks.items()})
    except UnicodeError:
        result.update(stdout=None,stderr=None,stdout_hex=chunks['stdout'].hex(),stderr_hex=chunks['stderr'].hex())
        failure=ValueError('probe_client_utf8')
    if failure:result['error']=str(failure)
    return result


class UorbProbe:
    def __init__(self,root,run,identity,px4,processes,bootstrap_deadline_ns,session_deadline_ns):
        self.root,self.run,self.identity,self.px4,self.processes=root,run,identity,px4,processes
        self.binary_dir=root/'.runtime/build/px4-v1.13.3/bin'
        texts=json.loads((run/'native-msg-before.json').read_text())
        self.layouts=layouts_from_texts(texts)
        self.directory=run/'uorb-probe';self.directory.mkdir()
        self.rows=[];self.bytes=0;self.owner=None
        self.bootstrap_deadline_ns,self.session_deadline_ns=bootstrap_deadline_ns,session_deadline_ns
        with (self.directory/'native-layout-sources.json').open('x') as stream:json.dump(texts,stream,indent=2)

    def _budget(self,additional):
        if sum(path.stat().st_size for path in self.directory.iterdir())+additional>FILE_BYTES:
            raise ValueError('probe_file_budget')

    def capture(self,source,kind='topic'):
        queries=[q for q in plan(self.identity) if q['checkpoint']==source['step_index'] and q['kind']==kind]
        deadline=min(time.monotonic_ns()+GROUP_NS,self.bootstrap_deadline_ns,self.session_deadline_ns)
        for query in queries:
            if self.px4.poll() is not None:raise ValueError('probe_px4_died')
            owner=inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            if self.owner is None:self.owner=owner
            if owner!=self.owner:raise ValueError('probe_owner_changed')
            argv=argv_for(self.binary_dir,query)
            start=time.monotonic_ns()
            result=bounded_client(argv,min(start+CLIENT_NS,deadline),self.processes,'uorb-query-%02d'%query['query_index'])
            # Raw evidence survives any projection or identity failure.
            raw_result=json.dumps(result,indent=2).encode('utf-8');self._budget(len(raw_result))
            with (self.directory/('%02d-raw.json'%query['query_index'])).open('xb') as stream:stream.write(raw_result)
            if 'error' in result:raise ValueError(result['error'])
            after=inspect_owner(self.px4.pid,self.binary_dir/'px4',self.run/'rootfs')
            end=time.monotonic_ns()
            if end>deadline:raise ValueError('probe_group_deadline')
            parsed=parse_output(query,result['stdout'],result['stderr'],result['returncode'],self.layouts)
            row=dict(schema_version='sim_flight_uorb_snapshot.v1',query=query,argv=argv,
                owner_before=owner,owner_after=after,last_hil_us=source['hil_sensor_time_us'],
                fdm_time_s=source['fdm']['sim_time_after_s'],wall_start_ns=start,wall_end_ns=end,
                returncode=result['returncode'],stdout=result['stdout'],stderr=result['stderr'],
                **parsed,binding_status='unverified',control_gate_accepted=False)
            raw=dumps(row,self.layouts,self.binary_dir)
            if self.bytes+len(raw)+1>FILE_BYTES or len(self.rows)>=32:raise ValueError('probe_file_budget')
            self._budget(len(raw)+1)
            with (self.directory/'snapshots.jsonl').open('ab') as stream:stream.write(raw+b'\n')
            self.bytes+=len(raw)+1;self.rows.append(row)
            if query['name']=='vehicle_control_mode' and parsed['observed']:
                if any(item['fields']['flag_armed'] for item in parsed['value']['instances']):
                    raise ValueError('probe_observation_armed')

    def finish(self):
        result=validate_stream(self.rows,self.identity,self.layouts,self.binary_dir)
        if sum(path.stat().st_size for path in self.directory.iterdir())>FILE_BYTES:raise ValueError('probe_file_budget')
        with (self.directory/'verification.json').open('x') as stream:json.dump(result,stream,indent=2)
        return result

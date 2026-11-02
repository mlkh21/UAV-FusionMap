"""P5 test source and public observer. Execution consumes inputs, never expectations."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from p5_contract import ROOT,expand
from p5_payloads import terrain_dataset,inverse_spec,inverse
from sim01b_runtime import write_json,rpc_proxy


class Case:
    def __init__(self,inputs,case,directory,run_id,processes):
        import rospy
        from ufm_application.terrain_client import TerrainClient
        from terrain_query_transport import TerrainQueryTransport
        self.ros,self.inputs,self.case,self.directory,self.run_id,self.processes = rospy,inputs,case,directory,run_id,processes
        self.events = expand(case,inputs['sequences'])
        self.lock = threading.RLock()
        self.messages,self.errors,self.receipts,self.queries = {},[],[],[]
        self.bytes = 0
        self.closed = False
        self.transcript = (directory/'public-receipts.jsonl').open('x')
        self.origin = time.monotonic_ns()
        self.terrain_alive,self.map_alive = True,True
        self.terrain_generation,self.pending_calls,self.raw_terrain = 0,0,None
        self.map_result,self.terrain_result,self.sensor_result = None,None,None
        self.recording_complete,self.recording_count,self.replay_result = None,None,None
        self.transport_state = None
        self.previous_group = None
        self.isolated_process,self.isolated_log = None,None
        self.transport = TerrainQueryTransport(discovery_s=.15,call_s=1.,call=self.terrain_call)
        self.client = TerrainClient(self.transport,'m5-terrain-fixture',run_id,'sim:'+run_id)
        self.subscribers = []
        self.setup_topics()

    def append(self,topic,value):
        with self.lock:
            if self.closed: return
            encoded = json.dumps(dict(topic=topic,receive_elapsed_ns=time.monotonic_ns()-self.origin,value=value),allow_nan=False)
            rows = self.messages.setdefault(topic,[])
            if len(rows) >= 256 or self.bytes+len(encoded.encode('utf-8')) > 16*1024*1024:
                self.errors.append('public receipt limit: '+topic)
                return
            self.bytes += len(encoded.encode('utf-8'))
            rows.append(copy.deepcopy(value))
            self.transcript.write(encoded+'\n'); self.transcript.flush()

    def latest(self,topic):
        with self.lock:
            rows = self.messages.get(topic,[])
            return copy.deepcopy(rows[-1]) if rows else None

    def count(self,topic):
        with self.lock:
            return len(self.messages.get(topic,[]))

    def wait(self,predicate,label,timeout=5.):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            self.processes.check()
            if self.errors:
                raise RuntimeError(str(self.errors))
            if predicate(): return
            time.sleep(.005)
        raise RuntimeError('P5 timeout: '+label)

    def setup_topics(self):
        from rosgraph_msgs.msg import Clock
        from std_msgs.msg import String
        from uav_fusionmap_msgs import msg
        from uav_fusionmap_terrain_msgs.msg import TerrainStatus
        from ufm_ros_contract import from_ros_state
        from ufm_ros_contract import perf01a_codec as c
        from ufm_terrain_contract.codec import from_ros
        def subscribe(topic,kind,decode):
            def receive(message):
                try:
                    value = decode(message)
                    self.append(topic,value)
                    if topic == '/uav/terrain/v1/status':
                        self.client.receive_status(value)
                except Exception as exc:
                    self.errors.append(topic+': '+repr(exc))
            self.subscribers.append(self.ros.Subscriber(topic,kind,receive,queue_size=256))
        for topic,kind,decode in [('/uav/sim/state',msg.AircraftState,from_ros_state),
            ('/uav/sensors/state',msg.AircraftState,from_ros_state),('/uav/sensors/radar',msg.RadarFrame,c.from_ros_radar),
            ('/uav/sensors/infrared',msg.InfraredFrame,c.from_ros_infrared),
            ('/uav/sensors/bundle',msg.SensorBundle,c.from_ros_bundle),
            ('/uav/perception/occupancy',msg.OccupancyObservation,c.from_ros_occupancy),
            ('/uav/map/snapshot',msg.MapSnapshot,c.from_ros_snapshot),
            ('/uav/terrain/v1/status',TerrainStatus,lambda m:from_ros('TerrainStatus',m)),
            ('/uav/perf/events',msg.PerfEvent,lambda m:{k:getattr(m,k) for k in m.__slots__})]:
            subscribe(topic,kind,decode)
        for topic in ('/p5/sensor/receipt','/p5/perception/worker','/p5/terrain/clock','/p5/map/entered'):
            subscribe(topic,String,lambda m:json.loads(m.data))
        self.clock = self.ros.Publisher('/clock',Clock,queue_size=100)
        if self.case['profile'] == 'A':
            self.state = self.ros.Publisher('/uav/sim/state',msg.AircraftState,queue_size=100)
        else:
            self.occupancy = self.ros.Publisher('/uav/perception/occupancy',msg.OccupancyObservation,queue_size=100)

    def start_terrain(self):
        self.terrain_generation += 1
        self.terrain_name = 'terrain-'+str(self.terrain_generation)
        command = [sys.executable,'-B',str(ROOT/'tests/p5_ros_nodes.py'),'terrain',
            '_enabled:=true','_dataset:='+str(self.directory/'dataset.json'),
            '_run_id:='+self.run_id,'_clock_id:=sim:'+self.run_id,'_clock_publisher:=/p5_source']
        if self.case['recording'] != 'off':
            command.append('_recording_directory:='+str(self.directory/'terrain-recording'))
        self.processes.spawn(self.terrain_name,command)
        self.terrain_alive = True
        self.wait(lambda:self.ros.get_param('/p5_terrain/ready','') == self.run_id and
                  self.clock.get_num_connections() >= (2 if self.case['profile']=='A' else 1),'terrain ready',15.)
        self.wait(lambda:self.node_outputs_ready('/p5_terrain',{'/p5/terrain/clock':1,
                  '/uav/terrain/v1/status':1}),'terrain TCPROS barriers',15.)

    def start(self):
        self.ros.set_param('/perf01a_require_observers',False)
        self.ros.set_param('/ufm_diagnostics_enabled',True)
        self.ros.set_param('/p5/backend','normal')
        write_json(self.directory/'dataset.json',terrain_dataset(self.inputs,self.run_id))
        args = [sys.executable,'-B',str(ROOT/'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
                '__name:=p5_map','_run_id:='+self.run_id,'_enable_query:=true']
        if self.case['profile'] == 'A':
            a = self.inputs['profiles']['A']
            args += ['_map_id:='+a['map_id'],'_free_threshold:=0.3','_occupied_threshold:=0.7']
            self.settings = dict(map_id=a['map_id'],resolution=a['resolution'],shape=a['shape'],origin=a['origin'],
                free_threshold=a['free_threshold'],occupied_threshold=a['occupied_threshold'],staleness_limit_ns=a['max_age_ns'])
            self.map_spec = None
            if self.case['id'] in ('S03.slow','S03.deadline'):
                slow = next(e[4] for e in self.events if e[1]=='backend' and e[4]['mode']=='slow')
                self.ros.set_param('/p5_perception/worker_enabled',True)
                self.ros.set_param('/p5_perception/worker_deadline_s',slow['deadline_ns']/1e9)
                self.ros.set_param('/p5/slow_duration_s',slow['duration_ns']/1e9)
            self.processes.spawn('perception',[sys.executable,'-B',str(ROOT/'tests/p5_ros_nodes.py'),'perception',
                '__name:=p5_perception','_run_id:='+self.run_id])
            self.processes.spawn('sensor',[sys.executable,'-B',str(ROOT/'tests/p5_ros_nodes.py'),'sensor',
                '--input',str(self.directory/'inputs.json'),'--case',self.case['id'],'_run_id:='+self.run_id])
        else:
            self.map_spec = inverse_spec(self.inputs,self.run_id,self.case['settings']['max_sealed_submaps'])
            write_json(self.directory/'m4-config.json',self.map_spec)
            self.settings = dict(rolling_enabled=True)
            args += ['_map_backend:=m4_fixture','_rolling_enabled:=true','_clock_id:=sim:'+self.run_id,
                     '_m4_fixture_config:='+str(self.directory/'m4-config.json')]
        if self.case['id'] == 'S07.map_block':
            args.append('/uav/map/query:=/p5/map/backend')
            self.processes.spawn('map-proxy',[sys.executable,'-B',str(ROOT/'tests/p5_ros_nodes.py'),'map_proxy'])
        self.processes.spawn('mapping',args)
        self.start_terrain()
        required = ['p5_map']+(['p5_sensor','p5_perception'] if self.case['profile']=='A' else [])
        self.wait(lambda:all(self.ros.get_param('/'+n+'/ready','') == self.run_id for n in required),'business ready',15.)
        self.wait(lambda:self.clock.get_num_connections() >= (2 if self.case['profile']=='A' else 1),'clock subscribers')
        self.wait(self.wires_ready,'business TCPROS connections',15.)
        self.graph_audit()
        if self.case['id']=='S07.map_block':
            folder = self.directory/'isolated-map-call'; folder.mkdir()
            self.isolated_log = (folder/'process.log').open('x')
            self.isolated_process = subprocess.Popen([sys.executable,'-B',str(ROOT/'tests/p5_map_call.py'),str(folder)],
                stdout=self.isolated_log,stderr=subprocess.STDOUT,start_new_session=True)
            self.wait(lambda:(folder/'ready.json').exists(),'isolated application prewarm')

    def node_outputs_ready(self,node,required):
        from p5_checkpoints import connected_outputs
        master = rpc_proxy(os.environ['ROS_MASTER_URI'])
        response = master.lookupNode('/p5_observer',node)
        if response[0] != 1: return False
        info = rpc_proxy(response[2]).getBusInfo('/p5_observer')
        return info[0]==1 and connected_outputs(info[2],required)

    def wires_ready(self):
        required = {'/p5_map':{'/uav/map/snapshot':1,'/uav/perf/events':1}}
        if self.case['profile']=='A':
            required.update({'/p5_sensor':{'/p5/sensor/receipt':1,'/uav/sensors/bundle':2,
                '/uav/sensors/radar':1,'/uav/sensors/infrared':1},
                '/p5_perception':{'/uav/perception/occupancy':2,'/uav/perf/events':1}})
        if self.case['id']=='S07.map_block':
            required['/p5_map_proxy'] = {'/p5/map/entered':1}
        return all(self.node_outputs_ready(node,topics) for node,topics in required.items())

    def graph_audit(self):
        result = rpc_proxy(os.environ['ROS_MASTER_URI']).getSystemState('/p5_observer')
        state = result[2]
        published,subscribed = dict(state[0]),dict(state[1])
        if published.get('/clock') != ['/p5_source']:
            raise ValueError('P5 requires one explicit clock source')
        expected = {'/p5_map':{'/uav/perception/occupancy'},'/p5_terrain':{'/clock'}}
        if self.case['profile']=='A':
            expected.update({'/p5_sensor':{'/clock','/uav/sim/state'},'/p5_perception':{'/uav/sensors/bundle'}})
        for node,topics in expected.items():
            actual = {t for t,nodes in subscribed.items() if node in nodes and t not in ('/rosout','/clock')}
            wanted = topics-{'/clock'}
            if actual != wanted:
                raise ValueError('P5 cross-layer subscriptions: '+node+' '+repr(actual))
        if any(any(k in topic.lower() for k in ('lidar','observed_mask','occupancy_target')) for topic in published):
            raise ValueError('P5 online graph contains training supervision')
        write_json(self.directory/'graph.json',state)

    def advance(self,stamp):
        from rosgraph_msgs.msg import Clock
        before = self.count('/p5/terrain/clock')
        sensor_before = sum(r.get('kind')=='clock' for r in self.messages.get('/p5/sensor/receipt',[]))
        self.clock.publish(Clock(clock=self.ros.Time(stamp//1_000_000_000,stamp%1_000_000_000)))
        if self.terrain_alive:
            self.wait(lambda:self.count('/p5/terrain/clock') > before,'terrain clock receipt')
        if self.case['profile']=='A':
            self.wait(lambda:sum(r.get('kind')=='clock' for r in self.messages.get('/p5/sensor/receipt',[])) > sensor_before,'sensor clock receipt')

    def map_done(self,before,snapshot_before):
        self.wait(lambda:sum(r['stage']=='map_snapshot_publish' for r in self.messages.get('/uav/perf/events',[])) > before,'map processing receipt')
        row = next(r for r in reversed(self.messages['/uav/perf/events']) if r['stage']=='map_snapshot_publish')
        if row['status'] == 'valid':
            self.wait(lambda:self.count('/uav/map/snapshot') > snapshot_before,'snapshot publish')

    def sample(self,index,event):
        from ufm_simulation.perf01a_fixture import make_motion_state
        from ufm_ros_contract import to_ros_state
        name,_,stamp,_,args = event
        self.advance(stamp)
        before = sum(r['stage']=='map_snapshot_publish' for r in self.messages.get('/uav/perf/events',[]))
        snapshot_before = self.count('/uav/map/snapshot')
        source = make_motion_state(self.run_id,index,stamp-args.get('pose_age_ns',0),args.get('speed_mps',0))
        self.state.publish(to_ros_state(source))
        self.wait(lambda:any(r.get('event')==name for r in self.messages.get('/p5/sensor/receipt',[])),'sensor sample '+name)
        receipt = next(r for r in reversed(self.messages['/p5/sensor/receipt']) if r.get('event')==name)
        self.sensor_result = receipt
        self.wait(lambda:any(r['header']['sample_id']==receipt['radar_id'] for r in self.messages.get('/uav/sensors/radar',[])),'radar public receipt')
        if not receipt['bundle_published']:
            time.sleep(.04)
            return
        self.wait(lambda:any(r['header']['sample_id']==receipt['bundle_id'] for r in self.messages.get('/uav/sensors/bundle',[])),'bundle public receipt')
        mode = self.ros.get_param('/p5/backend','normal')
        if mode == 'slow' and name == 'fault':
            self.wait(lambda:(self.latest('/p5/perception/worker') or {}).get('pending') == 1,'real worker active')
            return
        if mode == 'untrusted_context':
            self.wait(lambda:any(r['stage']=='occupancy_ready' and r['parent_sample_id']==receipt['bundle_id']
                                for r in self.messages.get('/uav/perf/events',[])),'untrusted rejection')
            time.sleep(.04)
            return
        self.wait(lambda:any(r['header']['timestamp']==stamp for r in self.messages.get('/uav/perception/occupancy',[])),'occupancy receipt')
        self.map_done(before,snapshot_before)

    def observation(self,event):
        from ufm_ros_contract.perf01a_codec import to_ros_occupancy
        _,_,stamp,_,args = event
        self.advance(stamp)
        before = sum(r['stage']=='map_snapshot_publish' for r in self.messages.get('/uav/perf/events',[]))
        snapshot_before = self.count('/uav/map/snapshot')
        self.occupancy.publish(to_ros_occupancy(inverse(self.map_spec,stamp,args,self.run_id)))
        self.map_done(before,snapshot_before)

    def map_request(self,stamp,args):
        point = args.get('point',self.inputs['profiles']['A']['world_point'] if self.case['profile']=='A' else [40.25,.25,.25])
        return dict(map_id='p5-local' if self.case['profile']=='A' else 'm4-scene-fixture',
            frame_id=args.get('frame_id','odom' if self.case['profile']=='A' else 'map'),
            run_id=self.run_id,clock_id='sim:'+self.run_id,query_timestamp=stamp,
            point=list(map(float,point)),max_age_ns=100_000_000)

    def query_map(self,stamp,args):
        from uav_fusionmap_msgs.srv import MapQuery,MapQueryRequest
        from ufm_ros_contract.query_codec import from_ros_query_result
        from ufm_application.query_client import MapQueryClient
        request = self.map_request(stamp,args)
        if 'external_deadline_ns' in args:
            folder = self.directory/'isolated-map-call'
            write_json(folder/'request.json',request)
            count = self.count('/p5/map/entered')
            child = self.isolated_process
            try:
                self.wait(lambda:self.count('/p5/map/entered')>count,'blocked service actually entered')
                try:
                    child.wait(timeout=args['external_deadline_ns']/1e9)
                    raise RuntimeError('blocked query unexpectedly returned')
                except subprocess.TimeoutExpired:
                    self.transport_state = 'external_deadline'
            finally:
                self.stop_isolated_call()
            self.map_result = None
            return
        self.transport_state = 'ok'
        def call(value):
            try:
                self.ros.wait_for_service('/uav/map/query',timeout=.15)
                response = self.ros.ServiceProxy('/uav/map/query',MapQuery)(MapQueryRequest(**value))
                return from_ros_query_result(response.result)
            except (self.ros.ROSException,self.ros.ServiceException) as exc:
                self.transport_state = 'unavailable'
                raise OSError('p5_map_transport_unavailable') from exc
        self.map_result = MapQueryClient(call).query(**request)
        record = dict(request=request,result=self.map_result,transport=self.transport_state)
        self.append('/p5/map/query',record)
        if self.transport_state == 'ok':
            self.queries.append(dict(request=request,result=copy.deepcopy(self.map_result)))

    def terrain_call(self,request):
        from uav_fusionmap_terrain_msgs.srv import TerrainQuery
        from ufm_terrain_contract.codec import to_ros,from_ros_response
        with self.lock: self.pending_calls += 1
        try:
            self.ros.wait_for_service('/uav/terrain/v1/query',timeout=.15)
            response = self.ros.ServiceProxy('/uav/terrain/v1/query',TerrainQuery)(to_ros('TerrainQueryRequest',request))
            result = from_ros_response(response,request=request)
            self.raw_terrain = copy.deepcopy(result)
            self.append('/p5/terrain/query',dict(request=request,result=result))
            return result
        except (self.ros.ROSException,self.ros.ServiceException) as exc:
            raise OSError('p5_terrain_transport_unavailable') from exc
        finally:
            with self.lock: self.pending_calls -= 1

    def query_terrain(self,stamp,args):
        points = [[111.,179.],[113.,179.],[111.,177.],[113.,177.]]
        request = dict(terrain_id='m5-terrain-fixture',run_id=self.run_id,clock_id='sim:'+self.run_id,
            frame_id='map',query_timestamp=stamp,point_xy=points[args['cell']],pin_version=False,
            expected_provider_instance_id='',expected_terrain_revision=0)
        if args.get('pin') == 'previous_group':
            if self.previous_group is None:
                raise ValueError('no actual previous group to pin')
            request.update(pin_version=True,expected_provider_instance_id=self.previous_group['provider_instance_id'],
                           expected_terrain_revision=self.previous_group['terrain_revision'])
        self.raw_terrain = None
        self.terrain_result = self.client.query(request)
        self.transport_state = 'unavailable' if not self.terrain_result['provider_instance_id'] else 'ok'
        if self.case['id'] == 'S07.instance' and self.previous_group is None:
            self.previous_group = self.client.sample_group()
            if self.previous_group is None:
                raise ValueError('first actual pinned group not established')
        self.append('/p5/application/terrain',self.terrain_result)

    def stop_terrain(self):
        self.processes.stop(self.terrain_name)
        self.terrain_alive = False

    def service(self,args):
        layer,action = args['layer'],args['action']
        if layer == 'terrain':
            if action == 'delay':
                self.ros.set_param('/p5/terrain_delay_s',args['duration_ns']/1e9)
            elif action == 'stop': self.stop_terrain()
            elif action == 'restart':
                self.stop_terrain()
                self.ros.delete_param('/p5_terrain/ready')
                self.start_terrain()
            else: raise ValueError('unsupported terrain service operation')
        elif action == 'stop':
            self.processes.stop('mapping'); self.map_alive = False
        elif action == 'block': self.ros.set_param('/p5/map_block',True)
        else: raise ValueError('unsupported map service operation')

    def recording(self,action):
        if action == 'start': return
        if action == 'close':
            self.stop_terrain()
            manifest = json.loads((self.directory/'terrain-recording/manifest.json').read_text())
            self.recording_complete,self.recording_count = manifest['recording_complete'],manifest['event_count']
        elif action == 'tamper_expected_height':
            import shutil
            target = self.directory/'tampered-recording'
            shutil.copytree(self.directory/'terrain-recording',target)
            path = target/'events.jsonl'
            events = [json.loads(line) for line in path.read_text().splitlines()]
            event = next(e for e in events if e['operation']=='query')
            event['result']['height'] += .1
            path.write_text(''.join(json.dumps(e)+'\n' for e in events))
        elif action == 'replay':
            source = self.directory/('tampered-recording' if self.case['recording']=='tampered' else 'terrain-recording')
            output = self.directory/'terrain-replay.json'
            subprocess.run([sys.executable,'-B',str(ROOT/'tests/p5_public_replay.py'),'terrain',str(source),str(output)],
                           check=True,timeout=10.,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.replay_result = json.loads(output.read_text())
        else: raise ValueError('unknown recording action')

    def values(self,before):
        snapshot = self.latest('/uav/map/snapshot')
        status = self.latest('/uav/terrain/v1/status')
        result = self.map_result
        values = dict(**{'map.revision':0 if snapshot is None else snapshot['revision'],
            'map.evidence_ns':None if snapshot is None else snapshot['header']['timestamp'],
            'bundle.delta':self.count('/uav/sensors/bundle')-before['bundle'],
            'occupancy.delta':self.count('/uav/perception/occupancy')-before['occupancy'],
            'radar.delta':self.count('/uav/sensors/radar')-before['radar']})
        index = [34,24,8] if self.case['profile']=='A' else [80,32,8]
        cell = next((c for c in (snapshot or {}).get('cells',[]) if c['index']==index),None)
        if result is not None:
            values.update({'map.state':result['status'],'map.probability':result['probability'],
                           'map.index':result['index'],'map.frame':result['frame_id']})
            values['map.evidence_ns'] = result['last_observed_timestamp']
            quality = result['uncertainty']
        else:
            values['map.probability'] = None if cell is None else cell['probability']
            quality = None if cell is None else cell['uncertainty']
        values['map.interval'] = None if quality is None or quality['status']=='unavailable' else quality['value']
        observation = self.latest('/uav/perception/occupancy')
        if observation:
            values.update({'occupancy.state':observation['header']['status'],'occupancy.voxels':len(observation['voxels'])})
        if self.sensor_result:
            values['bundle.reason'] = self.sensor_result['reason']
            bundle = next((b for b in reversed(self.messages.get('/uav/sensors/bundle',[])) if b['header']['sample_id']==self.sensor_result['bundle_id']),None)
            if bundle:
                values['bundle.pose_age_ns'] = bundle['pose_age_ns']
                point = [bundle['radar']['points'][0][k] for k in ('x','y','z')]+[1.]
                t = bundle['context']['T_mapping_source']
                world = [sum(t[4*i+j]*point[j] for j in range(4)) for i in range(3)]
                values.update({'geometry.point':world,'geometry.error_m':abs(world[1]-4.25)})
                if observation and observation['voxels']:
                    values['geometry.index'] = observation['voxels'][0]['index']
        sensor = self.latest('/p5/sensor/receipt')
        if sensor: values['clock.locked'] = sensor['locked']
        worker = self.latest('/p5/perception/worker')
        if worker: values['worker.pending'] = worker['pending']
        if self.case['id']=='S07.terrain_late': values['worker.pending'] = self.pending_calls
        values['worker.late_applied'] = sum(r['header']['status']=='valid' and r['header']['timestamp']==200_000_000
            for r in self.messages.get('/uav/perception/occupancy',[])) if self.case['id']=='S03.slow' else sum(
            r['status']!='unavailable' for r in self.messages.get('/p5/application/terrain',[]))
        if status: values['terrain.revision'] = status['terrain_revision']
        if self.terrain_result:
            tr = self.terrain_result
            values.update({'terrain.state':tr['status'],'terrain.height':tr['height'],'terrain.reason':tr['reason']})
            if self.raw_terrain:
                values.update({'terrain.instance':self.raw_terrain['provider_instance_id'],
                               'terrain.revision':self.raw_terrain['terrain_revision']})
        if self.previous_group:
            values['terrain.group'] = 'discarded' if self.client.current_group() is None else 'current'
        values.update({'transport.state':self.transport_state,'map.fallback_free':False if result is None else result['status']=='free'})
        if self.case['id']=='S07.map_block' and self.transport_state=='external_deadline':
            values['map.client_deadline'] = (self.directory/'isolated-map-call/result.json').exists()
        if self.case['id']=='S04.pause' and result is not None:
            values['map.clock_liveness_gate'] = result['status']=='unavailable'
        if self.recording_complete is not None:
            values.update({'recording.complete':self.recording_complete,'recording.event_ceiling':self.recording_count})
        if self.replay_result:
            values.update({'replay.executed':self.replay_result['executed'],'replay.matches':self.replay_result['matches']})
        return values

    def execute(self):
        last_wall,last_start = 0,time.monotonic()
        for index,event in enumerate(self.events):
            name,op,stamp,wall,args = event
            target = last_start+(wall-last_wall)/1e9
            time.sleep(max(0.,target-time.monotonic()))
            last_wall,last_start = wall,time.monotonic()
            before = dict(bundle=self.count('/uav/sensors/bundle'),occupancy=self.count('/uav/perception/occupancy'),radar=self.count('/uav/sensors/radar'))
            if op in ('sample','observation'):
                self.map_result = None
                (self.sample(index,event) if op=='sample' else self.observation(event))
            elif op == 'clock': self.advance(stamp)
            elif op in ('clock_repeat','clock_steps'):
                for i in range(args['count']):
                    target = last_start+i*args['period_ns']/1e9
                    time.sleep(max(0.,target-time.monotonic()))
                    self.advance(stamp+(i*args['period_ns'] if op=='clock_steps' else 0))
            elif op == 'backend': self.ros.set_param('/p5/backend',args['mode'])
            elif op == 'map_query': self.query_map(stamp,args)
            elif op == 'terrain_query': self.query_terrain(stamp,args)
            elif op == 'service': self.service(args)
            elif op == 'clock_control':
                if args['action']=='source_mismatch':
                    self.processes.spawn('foreign-clock',[sys.executable,'-B',str(ROOT/'tests/p5_ros_nodes.py'),'foreign_clock'])
                    self.wait(lambda:self.ros.get_param('/p5_foreign_clock/ready',False),'foreign source registered')
                    self.wait(lambda:(self.latest('/uav/terrain/v1/status') or {}).get('reason')=='clock_source_mismatch','source rejection')
            elif op == 'recording': self.recording(args['action'])
            elif op == 'poll': time.sleep(.03)
            else: raise ValueError('operation belongs to later work package: '+op)
            values = self.values(before)
            self.receipts.append(dict(event_id=name,operation=op,planned_wall_ns=wall,
                dispatch_elapsed_ns=int((last_start-self.origin/1e9)*1e9),completion_elapsed_ns=time.monotonic_ns()-self.origin,values=values))
        if self.errors: raise RuntimeError(str(self.errors))
        write_json(self.directory/'event-receipts.json',self.receipts)
        self.replay_map()

    def replay_map(self):
        write_json(self.directory/'map-observations.json',self.messages.get('/uav/perception/occupancy',[]))
        write_json(self.directory/'map-snapshots.json',self.messages.get('/uav/map/snapshot',[]))
        write_json(self.directory/'map-queries.json',self.queries)
        write_json(self.directory/'replay-config.json',dict(run_id=self.run_id,backend='latest' if self.map_spec is None else 'm4_fixture',
                    settings=self.settings,fixture_spec=self.map_spec))
        output = self.directory/'map-replay.json'
        subprocess.run([sys.executable,'-B',str(ROOT/'tests/p5_public_replay.py'),'map',str(self.directory),str(output)],
                       check=True,timeout=10.,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    def close(self):
        self.transport.close()
        self.stop_isolated_call()
        for subscriber in self.subscribers:
            subscriber.unregister()
        with self.lock:
            self.closed = True
            self.transcript.close()

    def stop_isolated_call(self):
        child = self.isolated_process
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGINT)
            try:
                child.wait(timeout=.05)
                termination = 'SIGINT'
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=3.)
                termination = 'SIGKILL'
            self.append('/p5/map/cancellation',dict(pid=child.pid,signal=termination,exit=child.returncode))
        if self.isolated_log is not None:
            self.isolated_log.close()

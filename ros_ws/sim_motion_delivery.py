"""Explicit SW-03 ROS assembly and public query/capture orchestration."""
import subprocess
import sys
import time

import rospy
import yaml
from uav_fusionmap_msgs.msg import SensorBundle, OccupancyObservation, MapSnapshot
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from visualization_msgs.msg import MarkerArray
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, from_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result
from sim01b_runtime import write_json


class Delivery:
    def __init__(self, root, run, identity, profile, processes, master, wall_call, native, previous_run):
        self.root, self.run, self.identity, self.profile = root, run, identity, profile
        self.processes, self.master, self.wall_call = processes, master, wall_call
        self.native, self.previous_run = native, previous_run
        self.queries = []
        self.rpc = rospy.ServiceProxy('/uav/map/query', MapQuery)
        self.receipts = None
        self.native_products = None
        self.last_snapshot = None
        expectations = dict(schema_version='test.sim_motion_delivery.v1', capture_timestamps_ns=[i*100000000 for i in range(1,11)],
            same_tick_pose=True, radar_ir_delta_ns=0, pose_age_ns=0,
            placeholder_probability=.9, forbidden_free=True, stale_age_ns=500000001,
            new_map_revision=0, native_stages=['before','after','history'] if native else [],
            first_capture_failure_committed_step=24, no_post_terminal_bundle=True)
        write_json(run/'delivery-expectations.json', expectations)
        (run/'figures').mkdir()
        settings = dict(profile['map'], schema_version='local_map_fixture.v1')
        (run/'map.yaml').write_text(yaml.safe_dump(settings, sort_keys=False))
        (run/'profile.yaml').write_text(yaml.safe_dump(profile, sort_keys=False))
        for key, value in (('/ufm_local_map_config',str(run/'map.yaml')),('/perf01a_require_observers',False),
                           ('/ufm_diagnostics_enabled',False),('/perf01a_image_buff_size',4*1024*1024)):
            master.setParam('/sim_motion_host',key,value)

    def streams(self):
        from motion_delivery_checks import bundle_summary
        return (('/uav/sensors/bundle','bundle',SensorBundle,bundle_summary),
                ('/uav/perception/occupancy','occupancy',OccupancyObservation,from_ros_occupancy),
                ('/uav/map/snapshot','snapshot',MapSnapshot,from_ros_snapshot),
                ('/uav/visual/map','visual',MarkerArray,lambda msg:[dict(ns=m.ns,action=m.action,
                    points=len(m.points)) for m in msg.markers]))

    def launch(self):
        p, root = self.processes, self.root
        p.spawn('sensor-adapter',[sys.executable,'-B',str(root/'ros_ws/scene_sensor_node.py'),
            '--run-id',self.identity,'--profile',str(self.run/'profile.yaml'),'--audit',str(self.run/'sensor-audit.json'),
            '--require-exact-pose'])
        p.spawn('placeholder',[sys.executable,'-B',str(root/'ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py'),
            '_run_id:='+self.identity,'_mode:=placeholder'])
        p.spawn('mapping',[sys.executable,'-B',str(root/'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
            '_run_id:='+self.identity,'_enable_query:=true','_free_threshold:=0.3','_occupied_threshold:=0.7'])
        p.spawn('map-visualizer',[sys.executable,'-B',str(root/'ros_ws/scene_map_viz.py'),
            '--clock-id','sim:'+self.identity,'--ttl-ns',str(self.profile['map']['staleness_limit_ns'])])
        for name, xyz, quaternion in (('radar',self.profile['radar_mount_xyz'],[0,0,0,1]),
                ('thermal_optical',self.profile['thermal_mount_xyz'],self.profile['thermal_optical_xyzw'])):
            p.spawn('mount-'+name,['/opt/ros/noetic/lib/tf2_ros/static_transform_publisher',
                *map(str,xyz+quaternion),'base_link',name])

    def prepare_native(self):
        if self.native:
            from sensor_scene_run import build_tools
            if self.profile['radar'].get('measurement_model')=='parameterized_v1':
                self.native_products,self.rviz=build_tools(self.root,self.run,self.processes.manifest,
                    output_directory=self.root/'.runtime/ros/report-native-build')
            else:
                self.native_products,self.rviz=build_tools(self.root,self.run,self.processes.manifest)

    def launch_native(self, environment):
        if not self.native:return
        env = dict(environment, UFM_SCENE_FIGURES=str(self.run/'figures'),
            UFM_SCENE_CAPTURE_REQUEST=str(self.run/'capture-request.txt'),UFM_SCENE_CLOCK_GUARD='1',
            QT_QPA_PLATFORM_PLUGIN_PATH='/usr/lib/x86_64-linux-gnu/qt5/plugins',QT_X11_NO_MITSHM='1',
            QT_AUTO_SCREEN_SCALE_FACTOR='0',QT_SCALE_FACTOR='1',QT_FONT_DPI='96')
        config = self.run/'motion.rviz'
        config.write_text(self.native_config())
        self.processes.spawn('gazebo-window',['/usr/bin/gzclient','--verbose'],extra_env=env)
        self.processes.spawn('rviz-window',[str(self.rviz),str(config)],extra_env=env)

    def native_config(self):
        if self.profile['radar'].get('measurement_model')=='parameterized_v1':
            value=yaml.safe_load((self.root/'configs/sensor_scene.rviz').read_text())
            manager=value['Visualization Manager']
            for display in manager['Displays']:
                if display['Class']=='rviz/Grid':
                    display.update({'Cell Size':5,'Plane Cell Count':40})
                elif display['Class']=='rviz/MarkerArray':
                    display['Enabled']=False
                elif display['Class']=='rviz/PointCloud2':
                    display.update({'Style':'Points','Size (Pixels)':4,'Size (m)':.12})
                elif display['Class']=='rviz/Image':
                    display['Normalize Range']=False
            manager['Views']['Current']['Distance']=95
            manager['Views']['Current']['Focal Point']={'X':35,'Y':0,'Z':5}
            return yaml.safe_dump(value,sort_keys=False)
        return (self.root/'configs/sensor_scene.rviz').read_text()

    def ready(self, wait, deadline):
        def parameters_ready():
            return all(self.master.getParam('/sim_motion_host', name)[2]==self.identity for name in
                ('/scene_sensor_adapter/ready','/perf01a_mapping/ready','/perf01a_placeholder_perception/ready'))
        wait(parameters_ready,deadline,'motion_delivery_nodes_not_ready')
        from motion_delivery_checks import check_graph
        graph=self.master.getSystemState('/sim_motion_host')[2]
        check_graph(graph)
        write_json(self.run/'delivery-graph.json',graph)
        rospy.wait_for_service('/uav/map/query',timeout=max(.01,deadline-time.monotonic()))
        initial = self.query([0.,0.,0.],0)
        if initial['status']!='unavailable' or initial['revision']!=0 or initial['last_observed_timestamp'] is not None:
            raise RuntimeError('motion_new_run_map_not_empty')
        if self.native:
            wait(lambda:(self.run/'figures/rviz-ready.json').exists() and
                (self.run/'figures/gazebo-ready.json').exists(),deadline,'motion_native_not_ready')

    def query(self, point, timestamp, run_id=None, max_age=None):
        request = dict(map_id=self.profile['map']['map_id'],frame_id='odom',run_id=run_id or self.identity,
            clock_id='sim:'+(run_id or self.identity),query_timestamp=timestamp,point=point,
            max_age_ns=self.profile['map']['staleness_limit_ns'] if max_age is None else max_age)
        result = from_ros_query_result(self.wall_call(lambda:self.rpc(MapQueryRequest(**request)),1.).result)
        self.queries.append(dict(request=request,result=result))
        return result

    def after_step(self, index, wait, deadline):
        if not index or index%25:return
        stamp=index*4000000
        wait(lambda:any(r['value']['header']['timestamp']==stamp for r in self.receipts.snapshot().get('snapshot',[])),
            min(deadline,time.monotonic()+3.),'motion_downstream_capture_not_delivered')
        snapshot=self.receipts.snapshot()['snapshot'][-1]['value']
        self.last_snapshot=snapshot
        if not snapshot['cells']:raise RuntimeError('motion_occupied_map_empty')
        cell=next(c for c in snapshot['cells'] if c['last_observed_timestamp']==stamp)
        point=[snapshot['origin'][a]+(cell['index'][a]+.5)*snapshot['resolution'][a] for a in range(3)]
        if self.query(point,stamp)['status']!='occupied':raise RuntimeError('motion_query_not_occupied')
        if index in (25,250) and self.native:
            self.capture('before' if index==25 else 'after',wait,deadline)

    def capture(self, stage, wait, deadline):
        # Hold the actual paused world while its existing buffers reach the two native views.
        time.sleep(.65)
        (self.run/'capture-request.txt').write_text(stage+'\n')
        wait(lambda:all((self.run/'figures'/('%s-%s.json'%(view,stage))).exists()
                       for view in ('rviz','gazebo')), min(deadline,time.monotonic()+3.),'motion_native_capture_timeout')

    def finish(self, wait, deadline, completed, fault):
        wait(lambda:self.master.getParam('/sim_motion_host','/scene_sensor_adapter/locked')[2] is True,
            min(deadline,time.monotonic()+2.),'motion_sensor_terminal_not_locked')
        before={k:len(self.receipts.snapshot().get(k,[])) for k in ('bundle','occupancy','snapshot')}
        if self.last_snapshot is not None:
            s=self.last_snapshot
            cell=next(c for c in s['cells'] if c['last_observed_timestamp']==s['header']['timestamp'])
            point=[s['origin'][a]+(cell['index'][a]+.5)*s['resolution'][a] for a in range(3)]
            stale=self.query(point,s['header']['timestamp']+self.profile['map']['staleness_limit_ns']+1)
            if stale['status']!='stale' or stale['last_observed_timestamp']!=cell['last_observed_timestamp']:
                raise RuntimeError('motion_query_aging_refreshed')
            if self.query([-3.75,-15.75,-3.75],s['header']['timestamp'])['status']!='unknown':
                raise RuntimeError('motion_unknown_became_free')
            if self.query(point,s['header']['timestamp'],run_id=self.previous_run or 'previous-run')['status']!='unavailable':
                raise RuntimeError('motion_old_run_query_not_rejected')
            command=[sys.executable,'-B',str(self.root/'ros_ws/map_query_client.py'),
                '--map-id',s['map_id'],'--frame-id','odom','--run-id',self.identity,'--clock-id','sim:'+self.identity,
                '--timestamp-ns',str(s['header']['timestamp']),'--max-age-ns',str(self.profile['map']['staleness_limit_ns']),
                '--point',*map(str,point)]
            with (self.run/'application-query.log').open('x') as stream:
                query=subprocess.run(command,cwd=self.root,env=self.processes.env,stdout=stream,stderr=subprocess.STDOUT,timeout=8.)
            self.processes.manifest['commands'].append(dict(name='application-query',args=command,exit=query.returncode))
            if query.returncode:raise RuntimeError('motion_independent_application_query_failed')
        # The map query itself uses explicit request time. Native wall liveness is separate.
        if self.native:
            wait(lambda:(self.run/'figures/rviz-history-ready.json').exists(),
                min(deadline,time.monotonic()+5.),'motion_history_view_not_cleared')
            self.capture('history',wait,deadline)
            if not fault:
                from check_motion_delivery_figures import verify_figures
                write_json(self.run/'figure-validation.json',verify_figures(self.run/'figures'))
        else:time.sleep(.15)
        after={k:len(self.receipts.snapshot().get(k,[])) for k in before}
        if after!=before:raise RuntimeError('motion_post_terminal_business_output')
        if self.native and self.last_snapshot is not None:
            markers=self.receipts.snapshot()['visual'][-1]['value']
            if (not any(m['ns']=='map_unavailable' and m['points'] for m in markers) or
                    any(m['ns']=='map_occupied' and m['points'] for m in markers)):
                raise RuntimeError('motion_map_history_not_unavailable')
        from motion_delivery_checks import verify_chain
        result, observations, snapshots=verify_chain(self.run,self.receipts.snapshot(),completed//25,self.profile)
        public=dict(observations=observations,snapshots=snapshots,queries=self.queries)
        write_json(self.run/'public-recording.json',public)
        from motion_delivery_checks import verify_public_replay
        settings=dict(self.profile['map'],free_threshold=.3,occupied_threshold=.7)
        rebuilt=verify_public_replay(observations,snapshots,self.identity,settings,self.queries)
        write_json(self.run/'public-replay.json',rebuilt)
        if observations:
            command=[sys.executable,'-B',str(self.root/'ros_ws/local_map_replay.py'),
                '--input',str(self.run/'public-recording.json'),'--run-id',self.identity,
                '--map-config',str(self.run/'map.yaml'),'--free-threshold','0.3','--occupied-threshold','0.7']
            with (self.run/'replay-process.log').open('x') as stream:
                replay=subprocess.run(command,cwd=self.root,env=self.processes.env,stdout=stream,stderr=subprocess.STDOUT,timeout=15.)
            self.processes.manifest['commands'].append(dict(name='public-replay-process',args=command,exit=replay.returncode))
            if replay.returncode:raise RuntimeError('motion_independent_replay_process_failed')
        result.update(public_queries=len(self.queries),public_replay_equal=True,independent_replay_process=bool(observations),
            terminal_locked=True,no_post_terminal_business=True,fault=fault,completed_step=completed)
        write_json(self.run/'delivery-validation.json',result)

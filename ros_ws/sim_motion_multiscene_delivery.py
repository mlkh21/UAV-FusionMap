"""Suite-specific ROS supervision, with no occupancy or map implementation."""
import json
import subprocess
import sys
import time

import yaml

import rospy
from gazebo_msgs.msg import ModelState
from gazebo_msgs.srv import GetModelState, GetWorldProperties, SetModelState

from sim01b_runtime import write_json
from sim_motion_delivery import Delivery


class MultisceneDelivery(Delivery):
    def native_config(self):
        value=yaml.safe_load(super().native_config())
        display=next(d for d in value['Visualization Manager']['Displays'] if d['Class']=='rviz/Image')
        # Five empty samples must not mask the first actual returning image.
        display['Median window']=1
        return yaml.safe_dump(value,sort_keys=False)

    def __init__(self,*args,spec,**kwargs):
        self.spec = spec
        self.geometry_events = []
        self.old_point = None
        super().__init__(*args,**kwargs)
        self.model_rpc = rospy.ServiceProxy('/gazebo/get_model_state',GetModelState)
        self.world_rpc = rospy.ServiceProxy('/gazebo/get_world_properties',GetWorldProperties)
        self.epoch_rpc = rospy.ServiceProxy('/uav/scene/geometry_epoch',SetModelState) if spec['epochs'] else None

    def ready(self,wait,deadline):
        super().ready(wait,deadline)
        rospy.wait_for_service('/gazebo/get_model_state',timeout=max(.01,deadline-time.monotonic()))
        world = self.wall_call(self.world_rpc,1.)
        names = sorted(world.model_names)
        expected = sorted(['sensor_aircraft'] + (['ground']+[o['name'] for o in self.profile['objects']]
            if self.spec['geometry']['inherit_legacy'] else [o['name'] for o in self.spec['geometry']['objects']]))
        if names != expected:raise RuntimeError('suite_installed_model_set')
        models = []
        for name in names:
            value = self.wall_call(lambda:self.model_rpc(name,'world'),1.)
            if not value.success:raise RuntimeError('suite_installed_model_readback')
            p,q = value.pose.position,value.pose.orientation
            models.append(dict(name=name,position=[p.x,p.y,p.z],orientation_xyzw=[q.x,q.y,q.z,q.w]))
        write_json(self.run/'installed-geometry.json',dict(world_time_s=world.sim_time,models=models))
        if self.epoch_rpc:
            rospy.wait_for_service('/uav/scene/geometry_epoch',timeout=max(.01,deadline-time.monotonic()))
            response = self.wall_call(lambda:self.epoch_rpc(self.epoch_message(self.spec['epochs'][0])),1.)
            if response.success or response.status_message!='scene_geometry_boundary':
                raise RuntimeError('suite_geometry_initial_boundary_not_rejected')
            write_json(self.run/'geometry-initial-rejection.json',dict(success=response.success,reason=response.status_message))

    @staticmethod
    def epoch_message(epoch):
        message = ModelState(model_name=epoch['obstacle_name'],reference_frame='world')
        message.pose.position.x,message.pose.position.y,message.pose.position.z = epoch['position']
        message.pose.orientation.w = 1.
        return message

    @staticmethod
    def cell_point(snapshot,cell):
        return [snapshot['origin'][a]+(cell['index'][a]+.5)*snapshot['resolution'][a] for a in range(3)]

    def after_step(self,index,wait,deadline):
        if not index or index%25:return
        stamp=index*4000000
        wait(lambda:any(r['value']['header']['timestamp']==stamp for r in self.receipts.snapshot().get('snapshot',[])),
            min(deadline,time.monotonic()+3.),'suite_downstream_not_delivered')
        snapshot=next(r['value'] for r in self.receipts.snapshot()['snapshot'] if r['value']['header']['timestamp']==stamp)
        self.last_snapshot=snapshot
        radar=next(r for r in self.receipts.snapshot()['radar'] if r['timestamp']==stamp)
        empty=self.spec['case_id']=='S06' or self.spec['case_id']=='S07' and 125<=index<=225
        if self.spec['case_id']!='S05' and (radar['points']==0)!=empty:
            raise RuntimeError('suite_actual_echo_domain')
        if self.spec['case_id']=='S05' and radar['points']==0:
            if not snapshot['cells'] or any(c['last_observed_timestamp']>=stamp for c in snapshot['cells']):
                raise RuntimeError('suite_occlusion_empty_refreshed_evidence')
            old=max(snapshot['cells'],key=lambda c:c['last_observed_timestamp'])
            result=self.query(self.cell_point(snapshot,old),stamp)
            expected='stale' if stamp-old['last_observed_timestamp']>500000000 else 'occupied'
            if result['status']!=expected or result['last_observed_timestamp']!=old['last_observed_timestamp']:
                raise RuntimeError('suite_occlusion_empty_history')
        elif empty:
            if self.spec['case_id']=='S06':
                if snapshot['cells']:raise RuntimeError('suite_empty_map_invented_cells')
                result=self.query([0.,0.,8.],stamp)
                if result['status']!='unknown' or result['last_observed_timestamp'] is not None:
                    raise RuntimeError('suite_empty_query_not_unknown')
            else:
                old=next(c for c in snapshot['cells'] if c['last_observed_timestamp']==400000000)
                self.old_point=self.cell_point(snapshot,old)
                if any(c['last_observed_timestamp']>400000000 for c in snapshot['cells']):
                    raise RuntimeError('suite_no_echo_refreshed_old_evidence')
                result=self.query(self.old_point,stamp)
                if result['status']!='occupied' or result['last_observed_timestamp']!=400000000:
                    raise RuntimeError('suite_no_echo_old_query')
                if index==225:
                    stale=self.query(self.old_point,900000001)
                    prior=self.query(self.old_point,899999999)
                    if (stale['status']!='stale' or stale['last_observed_timestamp']!=400000000 or
                            prior['reason']!='query_before_latest_map_time'):
                        raise RuntimeError('suite_ttl_boundary')
        else:
            cell=next(c for c in snapshot['cells'] if c['last_observed_timestamp']==stamp)
            if self.query(self.cell_point(snapshot,cell),stamp)['status']!='occupied':
                raise RuntimeError('suite_hit_query_not_occupied')
        if self.native and index in (25,225,250):
            if index!=225 or self.spec['case_id']=='S07':
                self.capture({25:'before',225:'empty',250:'after'}[index],wait,deadline)
        for epoch in self.spec['epochs']:
            if epoch['after_step']==index:self.apply_epoch(epoch)

    def apply_epoch(self,epoch):
        before=self.wall_call(self.world_rpc,1.)
        bad=self.epoch_message(epoch);bad.model_name='sensor_aircraft'
        rejected=self.wall_call(lambda:self.epoch_rpc(bad),1.)
        if rejected.success or rejected.status_message!='scene_geometry_request':
            raise RuntimeError('suite_geometry_wrong_object_not_rejected')
        answer=self.wall_call(lambda:self.epoch_rpc(self.epoch_message(epoch)),1.)
        if not answer.success:raise RuntimeError('suite_geometry_epoch:'+answer.status_message)
        receipt=json.loads(answer.status_message)
        after=self.wall_call(self.world_rpc,1.)
        state=self.wall_call(lambda:self.model_rpc(epoch['obstacle_name'],'world'),1.)
        p=state.pose.position
        if (not state.success or [p.x,p.y,p.z]!=epoch['position'] or before.sim_time!=after.sim_time or
                receipt['world_before_ns']!=epoch['after_step']*4000000 or
                receipt['world_after_ns']!=receipt['world_before_ns'] or not receipt['paused'] or
                receipt['run_id']!=self.identity or receipt['model_position']!=epoch['position'] or
                receipt['collision_position']!=epoch['position'] or receipt['visual_local_position']!=[0,0,0] or
                receipt['collision_size']!=[1,12,12] or receipt['visual_size']!=[1,12,12]):
            raise RuntimeError('suite_geometry_epoch_readback')
        receipt.update(wrong_object_rejection=rejected.status_message,model_api_position=[p.x,p.y,p.z])
        self.geometry_events.append(receipt)
        write_json(self.run/'geometry-events.json',self.geometry_events)

    def finish(self,wait,deadline,completed,fault):
        wait(lambda:self.master.getParam('/sim_motion_host','/scene_sensor_adapter/locked')[2] is True,
            min(deadline,time.monotonic()+2.),'suite_terminal_not_locked')
        before={k:len(self.receipts.snapshot().get(k,[])) for k in ('bundle','occupancy','snapshot')}
        s=self.last_snapshot
        if s is None:raise RuntimeError('suite_expected_map_snapshot_missing')
        if s['cells']:
            cell=max(s['cells'],key=lambda c:c['last_observed_timestamp'])
            point=self.cell_point(s,cell)
            stamp=s['header']['timestamp']
            stale=self.query(point,max(stamp,cell['last_observed_timestamp']+500000001))
            if stale['status']!='stale':raise RuntimeError('suite_final_query_not_stale')
        else:point=[0.,0.,8.];stamp=s['header']['timestamp']
        unknown=[s['origin'][a]+s['resolution'][a]*.5 for a in range(3)]
        if self.query(unknown,stamp)['status']!='unknown':raise RuntimeError('suite_unknown_became_free')
        if self.query(point,stamp,run_id=self.previous_run or 'previous-run')['status']!='unavailable':
            raise RuntimeError('suite_old_domain_not_rejected')
        command=[sys.executable,'-B',str(self.root/'ros_ws/map_query_client.py'),
            '--map-id',s['map_id'],'--frame-id','odom','--run-id',self.identity,'--clock-id','sim:'+self.identity,
            '--timestamp-ns',str(stamp),'--max-age-ns','500000000','--point',*map(str,point)]
        with (self.run/'application-query.log').open('x') as output:
            result=subprocess.run(command,cwd=self.root,env=self.processes.env,stdout=output,stderr=subprocess.STDOUT,timeout=8.)
        self.processes.manifest['commands'].append(dict(name='application-query',args=command,exit=result.returncode))
        if result.returncode:raise RuntimeError('suite_application_query_failed')
        if self.native:
            wait(lambda:(self.run/'figures/rviz-history-ready.json').exists(),
                min(deadline,time.monotonic()+5.),'suite_history_not_ready')
            self.capture('history',wait,deadline)
            markers=self.receipts.snapshot()['visual'][-1]['value']
            if (not any(m['ns']=='map_unavailable' and m['points'] for m in markers) or
                    any(m['ns']=='map_occupied' and m['points'] for m in markers)):
                raise RuntimeError('suite_map_history_not_unavailable')
            from sim_motion_multiscene_figures import verify_figures
            write_json(self.run/'figure-validation.json',verify_figures(self.run,self.spec['case_id'],self.receipts.snapshot()))
        else:time.sleep(.15)
        if before!={k:len(self.receipts.snapshot().get(k,[])) for k in before}:
            raise RuntimeError('suite_post_terminal_business')
        from motion_delivery_checks import verify_chain,verify_public_replay
        result,observations,snapshots=verify_chain(self.run,self.receipts.snapshot(),completed//25,self.profile)
        write_json(self.run/'public-recording.json',dict(observations=observations,snapshots=snapshots,queries=self.queries))
        settings=dict(self.profile['map'],free_threshold=.3,occupied_threshold=.7)
        write_json(self.run/'public-replay.json',verify_public_replay(observations,snapshots,self.identity,settings,self.queries))
        command=[sys.executable,'-B',str(self.root/'ros_ws/local_map_replay.py'),'--input',str(self.run/'public-recording.json'),
            '--run-id',self.identity,'--map-config',str(self.run/'map.yaml'),'--free-threshold','0.3','--occupied-threshold','0.7']
        with (self.run/'replay-process.log').open('x') as output:
            replay=subprocess.run(command,cwd=self.root,env=self.processes.env,stdout=output,stderr=subprocess.STDOUT,timeout=15.)
        self.processes.manifest['commands'].append(dict(name='public-replay-process',args=command,exit=replay.returncode))
        if replay.returncode:raise RuntimeError('suite_independent_replay_failed')
        from sim_motion_multiscene_live import verify_live
        geometry=verify_live(self.run,self.receipts.snapshot(),self.spec,completed)
        write_json(self.run/'multiscene-validation.json',geometry)
        result.update(case_id=self.spec['case_id'],public_queries=len(self.queries),public_replay_equal=True,
            independent_replay_process=True,terminal_locked=True,no_post_terminal_business=True,completed_step=completed,fault=fault)
        write_json(self.run/'delivery-validation.json',result)

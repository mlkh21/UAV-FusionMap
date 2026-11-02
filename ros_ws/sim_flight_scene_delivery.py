"""Flight-only activation and public map handoff over the existing five-layer nodes."""
import time

from sim_motion_delivery import Delivery
from sim01b_runtime import write_json
from ufm_flight_contract.contract import capture_step


class FlightDelivery(Delivery):
    def launch_native(self,environment):
        super().launch_native(dict(environment,UFM_FLIGHT_SCENE_VIEW='1'))

    def native_config(self):
        import yaml
        value=yaml.safe_load(super().native_config())
        image=next(d for d in value['Visualization Manager']['Displays'] if d['Class']=='rviz/Image')
        image['Median window']=1
        return yaml.safe_dump(value,sort_keys=False)

    def prepare_native(self):
        if self.native:
            from sensor_scene_run import build_tools
            self.native_products,self.rviz=build_tools(self.root,self.run,self.processes.manifest,
                output_directory=self.root/'.runtime/ros/flight-scene-native-build')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.capture_stamps=[]
        write_json(self.run/'flight-delivery-expectations.json',dict(
            first_capture_ns=30100000000,last_capture_ns=40000000000,captures=100,
            preparation_map_status='unavailable',same_tick_pose=True,forbidden_free=True))

    def after_step(self,index,wait,deadline):
        if index in (2500,7250,7500):
            result=self.query([0.,0.,0.],index*4000000)
            if result['status']!='unavailable' or result['revision']!=0:
                raise RuntimeError('flight_preparation_map_not_unavailable')
            rows=self.receipts.snapshot()
            if any(rows.get(k) for k in ('radar','infrared','ack','bundle','occupancy','snapshot')):
                raise RuntimeError('flight_preparation_published_capture')
        if not capture_step(index):return
        stamp=index*4000000
        wait(lambda:any(r['value']['header']['timestamp']==stamp for r in self.receipts.snapshot().get('snapshot',[])),
            min(deadline,time.monotonic()+3.),'flight_downstream_capture_missing')
        self.capture_stamps.append(stamp)
        snapshot=self.receipts.snapshot()['snapshot'][-1]['value'];self.last_snapshot=snapshot
        if not snapshot['cells']:raise RuntimeError('flight_occupied_map_empty')
        cell=next(c for c in snapshot['cells'] if c['last_observed_timestamp']==stamp)
        point=[snapshot['origin'][a]+(cell['index'][a]+.5)*snapshot['resolution'][a] for a in range(3)]
        if self.query(point,stamp)['status']!='occupied':raise RuntimeError('flight_query_not_occupied')
        if self.native and index in (7525,10000):
            self.capture('before' if index==7525 else 'after',wait,deadline)

    def finish(self,wait,deadline,completed,fault):
        wait(lambda:self.master.getParam('/sim_motion_host','/scene_sensor_adapter/locked')[2] is True,
            min(deadline,time.monotonic()+2.),'flight_terminal_not_locked')
        before={k:len(self.receipts.snapshot().get(k,[])) for k in ('bundle','occupancy','snapshot')}
        if self.last_snapshot:
            s=self.last_snapshot;cell=s['cells'][0]
            point=[s['origin'][a]+(cell['index'][a]+.5)*s['resolution'][a] for a in range(3)]
            stale=self.query(point,s['header']['timestamp']+self.profile['map']['staleness_limit_ns']+1)
            if stale['status']!='stale':raise RuntimeError('flight_map_not_stale')
            if self.query(point,s['header']['timestamp'],run_id=self.previous_run or 'previous-run')['status']!='unavailable':
                raise RuntimeError('flight_old_run_query_accepted')
            if self.query([-3.75,-15.75,-3.75],s['header']['timestamp'])['status']!='unknown':
                raise RuntimeError('flight_unknown_became_free')
        if self.native:
            wait(lambda:(self.run/'figures/rviz-history-ready.json').exists(),
                min(deadline,time.monotonic()+5.),'flight_history_not_ready')
            self.capture('history',wait,deadline)
            from sim_flight_scene_checks import verify_figures
            write_json(self.run/'figure-validation.json',verify_figures(self.run/'figures'))
        else:time.sleep(.15)
        if before!={k:len(self.receipts.snapshot().get(k,[])) for k in before}:
            raise RuntimeError('flight_post_terminal_business')
        from motion_delivery_checks import verify_chain, verify_public_replay
        result,observations,snapshots=verify_chain(self.run,self.receipts.snapshot(),len(self.capture_stamps),
            self.profile,timestamps=self.capture_stamps)
        write_json(self.run/'public-recording.json',dict(observations=observations,snapshots=snapshots,queries=self.queries))
        settings=dict(self.profile['map'],free_threshold=.3,occupied_threshold=.7)
        rebuilt=verify_public_replay(observations,snapshots,self.identity,settings,self.queries)
        write_json(self.run/'public-replay.json',rebuilt)
        result.update(public_queries=len(self.queries),public_replay_equal=True,
            terminal_locked=True,no_post_terminal_business=True,completed_step=completed,fault=fault)
        write_json(self.run/'delivery-validation.json',result)

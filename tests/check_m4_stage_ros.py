"""M4 actual ROS synthetic handoff using public occupancy, snapshot and query only."""
import argparse
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation, PerfEvent
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import to_ros_occupancy, from_ros_occupancy, from_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result
from m4_fixture import load_spec
from m3_motion_fixture import motion_observation
from check_local_map_query_ros import validate_mapping_graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'application'))
from ufm_application import MapQueryClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('run_id')
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('m4_stage_checker',disable_signals=True)
    spec=load_spec(args.run/'m4-config.yaml')
    snapshots,events,observations,queries,outcomes,checks,clock_times=[],[],[],[],[],[],[]
    errors=[]
    subscribers=[rospy.Subscriber('/uav/map/snapshot',MapSnapshot,
        lambda msg:snapshots.append(from_ros_snapshot(msg)),queue_size=100),
        rospy.Subscriber('/uav/perf/events',PerfEvent,lambda msg:events.append(msg),queue_size=100)]
    publisher=rospy.Publisher('/uav/perception/occupancy',OccupancyObservation,queue_size=100)
    clock=rospy.Publisher('/clock',Clock,queue_size=100)

    def advance(stamp):
        if not clock_times or stamp>clock_times[-1]:
            clock_times.append(stamp)
            clock.publish(Clock(clock=rospy.Time(stamp//1_000_000_000,stamp%1_000_000_000)))

    def require(condition,label):
        checks.append(dict(name=label,passed=bool(condition)))
        if not condition:raise AssertionError(label)

    def wait(condition,label):
        deadline=time.monotonic()+6.
        while time.monotonic()<deadline:
            if condition():return
            time.sleep(.01)
        raise RuntimeError('timeout: '+label)

    def row(sequence,stamp,kind='occupied',body=0.,point=(8.25,.25,.25),bounds='default'):
        return motion_observation(spec['local_map'],args.run_id,sequence,kind=kind,
            stamp=stamp,body=(body,0.,0.),points=(point,),origin=(body-16.,-8.,-4.),bounds=bounds)

    def send(value,outcome,revision,evidence):
        count,previous=len(events),len(snapshots)
        message=to_ros_occupancy(value)
        stream=io.BytesIO()
        message.serialize(stream)
        message=type(message)().deserialize(stream.getvalue())
        observations.append(from_ros_occupancy(message))
        if outcome!='rejected':advance(value['header']['timestamp'])
        publisher.publish(message)
        wait(lambda:len(events)>count,'occupancy receipt')
        event=events[-1]
        actual='fused' if event.status=='valid' else ('not_fused' if event.reason=='observation_not_fused' else 'rejected')
        outcomes.append(actual)
        require(actual==outcome,'occupancy '+outcome)
        if actual=='fused':wait(lambda:len(snapshots)==previous+1,'snapshot')
        require(len(snapshots)==revision,'snapshot count')
        if snapshots:
            last=snapshots[-1]
            require(last['revision']==revision and last['header']['timestamp']==evidence,'revision/evidence time')
            require(last['header']['frame_id']=='map' and last['map_id']=='m4-scene-fixture','Scene identity')
            require(len({tuple(c['index']) for c in last['cells']})==len(last['cells']),'unique Scene cells')

    def query(stamp,status,probability=None,bounds=None,point=(40.25,.25,.25),**changes):
        advance(stamp)
        request=dict(map_id='m4-scene-fixture',frame_id='map',run_id=args.run_id,
            clock_id='sim:'+args.run_id,query_timestamp=stamp,max_age_ns=999_000_000,point=list(point))
        request.update(changes)
        result=client.query(**request)
        queries.append(dict(request=request,result=result))
        require(result['status']==status,'query '+status)
        require(result['probability'] is None if probability is None else
            result['probability'] is not None and abs(result['probability']-probability)<1e-6,'query probability')
        require(result['confidence'] is None,'no fabricated confidence')
        quality=result['uncertainty']
        if bounds is None:
            require(quality['status']=='unavailable' and quality['value'] is None,'missing range preserved')
            if result['observed']:
                require(quality['source']==spec['local_map']['interval_profile']['unavailable_source'],'missing provenance')
        else:
            require(quality['status']=='available' and quality['kind']=='occupancy_probability_interval' and
                quality['unit']=='dimensionless' and quality['source']==
                spec['local_map']['interval_profile']['output_source'],'range metadata')
            require(len(quality['value'])==2 and all(abs(a-b)<1e-12 for a,b in zip(quality['value'],bounds)),
                    'independent interval endpoints')
        return result

    try:
        wait(lambda:publisher.get_num_connections()==1 and
            rospy.get_param('/perf01a_mapping/ready','')==args.run_id,'mapping ready')
        rospy.wait_for_service('/uav/map/query',timeout=5.)
        service=rospy.ServiceProxy('/uav/map/query',MapQuery)
        client=MapQueryClient(lambda request:from_ros_query_result(service(MapQueryRequest(**request)).result))
        require(rospy.get_param('/perf01a_mapping/resolved_map_backend')=='m4_fixture','explicit backend')
        query(0,'unavailable')
        first=row(0,10_000_000)
        send(first,'fused',1,10_000_000)
        require(query(10_000_000,'occupied',.75,(.7,.8))['index']==[80,32,8],'nonzero registered index')
        query(10_000_000,'unknown',point=(8.25,.25,.25))
        query(10_000_000,'unavailable',frame_id='odom')
        send(first,'not_fused',1,10_000_000)
        conflict=copy.deepcopy(first)
        conflict['voxels'][0]['uncertainty']['value']=[.72,.8]
        send(conflict,'rejected',1,10_000_000)
        send(row(1,20_000_000,body=40.,point=(48.25,.25,.25)),'fused',2,20_000_000)
        require(query(20_000_000,'occupied',.75,(.7,.8))['last_observed_timestamp']==10_000_000,'sealed original time')
        query(20_000_000,'occupied',.75,(.7,.8),point=(80.25,.25,.25))
        send(row(2,15_000_000),'rejected',2,20_000_000)
        send(row(3,800_000_000,'empty',body=200.),'rejected',2,20_000_000)
        bad=row(4,700_000_000)
        bad['voxels'].append(copy.deepcopy(bad['voxels'][0]))
        bad['voxels'][-1]['index']=[40,16,8]
        bad['voxels'][-1]['uncertainty']['unit']='m2'
        send(bad,'rejected',2,20_000_000)
        gap=row(5,30_000_000,'unavailable',body=200.)
        gap['context']['T_mapping_body_status']='unavailable'
        gap['context']['T_mapping_body']=[0.]*16
        send(gap,'not_fused',2,20_000_000)
        query(110_000_000,'occupied',.75,(.7,.8))
        query(110_000_001,'stale',.75,(.7,.8))
        query(110_000_001,'occupied',.75,(.7,.8),point=(80.25,.25,.25))
        send(row(6,120_000_001,body=80.,point=(88.25,.25,.25)),'fused',3,120_000_001)
        query(120_000_001,'unknown')
        query(120_000_001,'stale',.75,(.7,.8),point=(80.25,.25,.25))
        send(row(7,130_000_001,'free'),'fused',4,130_000_001)
        query(130_000_001,'free',.25,(.2,.3))
        query(130_000_001,'unknown',point=(80.25,.25,.25))
        send(row(8,140_000_001),'fused',5,140_000_001)
        require(query(140_000_001,'unknown',.5,(7/19,12/19))['observed'],'conflict remains observed')
        send(row(9,150_000_001,bounds=None),'fused',6,150_000_001)
        query(150_000_001,'occupied',.75)
        send(row(10,160_000_001),'fused',7,160_000_001)
        query(160_000_001,'occupied',.9)
        send(row(11,270_000_002,'empty',body=.5),'fused',8,160_000_001)
        query(260_000_001,'unavailable')
        query(270_000_002,'stale',.9)
        send(row(12,280_000_002,body=.5),'fused',9,280_000_002)
        query(280_000_002,'occupied',.75,(.7,.8))
        query(1_000_000_000,'unavailable')
        cli=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/map_query_client.py'),
            '--map-id','m4-scene-fixture','--frame-id','map','--run-id',args.run_id,
            '--clock-id','sim:'+args.run_id,'--timestamp-ns','280000002','--max-age-ns','100000000',
            '--point','40.25','.25','.25'],text=True,capture_output=True,timeout=10)
        result=json.loads(cli.stdout)
        require(cli.returncode==0 and result['status']=='occupied' and result['index']==[80,32,8] and
                result['uncertainty']['status']=='available','independent map application CLI')
        graph=rospy.get_master().getSystemState()[2]
        subscriptions=validate_mapping_graph(graph,'/m4_stage_checker')
        require(not any('lidar' in topic.lower() or 'training' in topic.lower()
                for topic,nodes in graph[0]+graph[1]),'no training or LiDAR graph')
        (args.run/'graph.json').write_text(json.dumps(dict(system=graph,mapping_subscriptions=subscriptions),indent=2))
        (args.run/'application-cli.json').write_text(json.dumps(dict(result=result,exit=cli.returncode,stderr=cli.stderr),indent=2))
    except Exception as exc:
        errors.append(type(exc).__name__+':'+str(exc))
    (args.run/'receipts.json').write_text(json.dumps(dict(observations=observations,snapshots=snapshots,
        queries=queries,outcomes=outcomes,clock_times=clock_times,
        events=[dict(status=e.status,reason=e.reason,parent_sample_id=e.parent_sample_id) for e in events]),indent=2))
    (args.run/'validation.json').write_text(json.dumps(dict(passed=not errors,errors=errors,checks=checks,
        observation_count=len(observations),snapshot_count=len(snapshots),query_count=len(queries),
        application_statuses=sorted({q['result']['status'] for q in queries})),indent=2))
    return int(bool(errors))


if __name__=='__main__':
    sys.exit(main())

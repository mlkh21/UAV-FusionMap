"""Real client/markers/deadline acceptance with an independently controlled clock."""
import argparse
import json
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'application'))
import rospy
from rosgraph_msgs.msg import Clock
from visualization_msgs.msg import MarkerArray, Marker
from uav_fusionmap_terrain_msgs.msg import TerrainStatus
from uav_fusionmap_terrain_msgs.srv import TerrainQuery
from ufm_terrain_contract.codec import from_ros, to_ros_response
from ufm_application.terrain_client import TerrainClient
from terrain_query_transport import TerrainQueryTransport


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--with-rviz',action='store_true')
    args=parser.parse_args()
    rospy.init_node('terrain_delivery_checker',disable_signals=True)
    states,markers,recorded,checks,errors=[],[],[],[],[]
    transport=TerrainQueryTransport()
    client=TerrainClient(transport,'m5-terrain-fixture',args.run_id,'sim:'+args.run_id)
    def status(message):
        value=from_ros('TerrainStatus',message)
        states.append(value)
        client.receive_status(value)
    subscribers=[rospy.Subscriber('/uav/terrain/v1/status',TerrainStatus,status,queue_size=4),
        rospy.Subscriber('/uav/terrain/v1/markers',MarkerArray,lambda m:markers.append(m),queue_size=2),
        rospy.Subscriber('/uav/terrain/recorded/markers',MarkerArray,lambda m:recorded.append(m),queue_size=2)]
    publisher=rospy.Publisher('/clock',Clock,queue_size=1)
    stamp,pause=[100],[False]
    stop=threading.Event()
    def clock_loop():
        while not stop.is_set():
            if not pause[0]:publisher.publish(Clock(clock=rospy.Time(0,stamp[0])))
            stop.wait(.25)
    worker=threading.Thread(target=clock_loop);worker.start()
    def require(test,label):
        checks.append(dict(label=label,passed=bool(test)))
        if not test:raise AssertionError(label)
    def wait(predicate,label):
        deadline=time.monotonic()+8.
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.03)
        raise RuntimeError('timeout: '+label)
    def cubes():return [m for m in markers[-1].markers if m.type==Marker.CUBE and m.action==Marker.ADD] if markers else []
    def capture(label,topic='/uav/terrain/v1/markers'):
        if args.with_rviz:
            time.sleep(.5)
            (args.run/'capture-request.json').write_text(json.dumps(dict(label=label,topic=topic)))
            wait(lambda:(args.run/('capture-'+label+'.json')).exists(),'capture '+label)
    released=threading.Event()
    slow=None
    groups=[]
    try:
        rospy.wait_for_service('/uav/terrain/v1/query',timeout=8.)
        wait(lambda:states and states[-1]['state']=='current','current status')
        group=client.sample_group()
        require(group is not None and len(group['results'])==4,'real four point pin group')
        groups.append(group)
        wait(lambda:len(cubes())==3,'three measured heights without no-data surface')
        require(sorted(m.pose.position.z for m in cubes())==[1.,13.,14.],'render actual heights only')
        require(any(m.color.b>m.color.g for m in cubes()),'missing quality uses separate color')
        capture('01-current')
        # Close the short bounded recording before the fault scenarios; replay is checked by supervisor.
        old=states[-1]['provider_instance_id']
        (args.run/'restart-request.json').write_text('{}')
        wait(lambda:states[-1]['provider_instance_id']!=old and states[-1]['state']=='current','new instance')
        wait(lambda:client.sample_group() is not None,'client rebound')
        require(client.current_group()['provider_instance_id']!=old,'restart clears old instance group')
        stamp[0]=200
        wait(lambda:states[-1]['state']=='expired','expired status')
        wait(lambda:cubes() and all(m.color.r>m.color.g for m in cubes()),'stale markers')
        capture('02-stale')
        pause[0]=True
        wait(lambda:states[-1]['reason']=='clock_transport_unavailable','clock dropout')
        wait(lambda:markers and not cubes(),'marker clear on unavailable')
        require(client.current_group() is None,'client clears stale current group')
        capture('03-unavailable')
        # A real ROS server deliberately holds one test call; it is not a model substitute.
        row=group['results'][0]
        def blocked(_request):
            released.wait(4.)
            return to_ros_response(row)
        slow=rospy.Service('/uav/terrain/test/blocked',TerrainQuery,blocked)
        blocked_transport=TerrainQueryTransport(service='/uav/terrain/test/blocked')
        req=dict(terrain_id='m5-terrain-fixture',run_id=args.run_id,clock_id='sim:'+args.run_id,frame_id='map',
            query_timestamp=100,point_xy=[111.,179.],pin_version=False,expected_provider_instance_id='',expected_terrain_revision=0)
        started=time.monotonic()
        try:blocked_transport(req)
        except TimeoutError:require(time.monotonic()-started<1.5,'actual service call wall deadline')
        else:raise AssertionError('blocked call accepted')
        try:blocked_transport(req)
        except OSError:require(True,'one unfinished real ROS call')
        else:raise AssertionError('pending call queued')
        released.set();blocked_transport._worker.join(3.)
        blocked_transport.close()
        require(not blocked_transport._worker.is_alive(),'late call finishes without becoming current')
        pause[0]=False;stamp[0]=200
        wait(lambda:states[-1]['state']=='expired','clock restored')
        (args.run/'stop-request.json').write_text('{}')
        wait(lambda:'/uav/terrain/v1/query' not in dict(rospy.get_master().getSystemState()[2][2]),'service gone')
        result=client.query(req)
        require(result['status']=='unavailable' and result['provider_instance_id']=='' and result['height'] is None,
                'missing service produces local empty-instance envelope')
        wait(lambda:client.current_group() is None and not cubes(),'status timeout after provider stop')
        graph=rospy.get_master().getSystemState()[2]
        subscriptions={t for t,n in graph[1] if '/terrain_rviz_markers' in n}
        require(subscriptions<={'/clock','/uav/terrain/v1/status'},'display consumes public terrain only')
        require(not any('lidar' in t.lower() or 'training' in t.lower() for t,n in graph[0]+graph[1]),'no training graph')
        wait(lambda:recorded,'recorded history markers')
        require(any(m.type==Marker.TEXT_VIEW_FACING and m.text.startswith('recorded') for m in recorded[-1].markers),
                'recorded display uses separate namespace and label')
        capture('04-recorded','/uav/terrain/recorded/markers')
    except Exception as exc:errors.append(type(exc).__name__+':'+str(exc))
    finally:
        released.set()
        if slow:slow.shutdown('done')
        stop.set();worker.join(2.);transport.close()
        for s in subscribers:s.unregister()
        publisher.unregister()
    (args.run/'client-receipts.json').write_text(json.dumps(dict(statuses=states,groups=groups),indent=2))
    (args.run/'validation.json').write_text(json.dumps(dict(passed=not errors,checks=checks,errors=errors,
        status_count=len(states),marker_count=len(markers)),indent=2))
    return int(bool(errors))


if __name__=='__main__':sys.exit(main())

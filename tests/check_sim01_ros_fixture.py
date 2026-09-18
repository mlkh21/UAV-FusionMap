"""实际ROS传输fixture：状态先到、超时、终止优先和run锁定。"""
import copy
import json
import sys
import threading
import time
from pathlib import Path

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState
from ufm_ros_contract import to_ros_state, from_ros_state


def main():
    run, run_id = Path(sys.argv[1]), sys.argv[2]
    rospy.init_node('sim01a_fixture', disable_signals=True)
    lock, received = threading.Lock(), []
    stream = (run/'fixture-states.jsonl').open('x')
    errors, checks = [], []

    def receive(msg):
        with lock:
            value = from_ros_state(msg)
            received.append(value)
            stream.write(json.dumps(value)+'\n')

    sub = rospy.Subscriber('/uav/sensors/state', AircraftState, receive, queue_size=100)
    pub = rospy.Publisher('/uav/sim/state', AircraftState, queue_size=100)
    clock = rospy.Publisher('/clock', Clock, queue_size=100)
    source = dict(header=dict(schema_version='0.1', timestamp=2000000000,
                             clock_id='sim:'+run_id, run_id=run_id, sample_id='fixture:early',
                             frame_id='world_ned', source_type='simulation', status='valid', reason=''),
                  position=[1.,2.,3.], orientation_xyzw=[0.,0.,0.,1.], linear_velocity=[4.,5.,6.],
                  body_frame_id='body_frd', velocity_frame_id='body_frd', state_source='estimated',
                  quality=dict(confidence=None, uncertainty=dict(status='unavailable',kind='pose_covariance',
                               value=None,unit='mixed',source='fixture unknown covariance')))

    def wait(predicate, timeout=3.):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if predicate():
                return True
            time.sleep(.01)
        return False

    def check(condition, name):
        checks.append(dict(name=name,passed=bool(condition)))
        if not condition:
            errors.append(name)

    def count():
        with lock:
            return len(received)

    try:
        check(wait(lambda: pub.get_num_connections()==1 and clock.get_num_connections()>=1), 'ROS connections ready')
        pub.publish(to_ros_state(source))
        time.sleep(.15)
        check(count()==0, 'state waits for clock')
        clock.publish(Clock(clock=rospy.Time(1,0)))
        time.sleep(.1)
        check(count()==0, 'insufficient clock cannot release state')
        clock.publish(Clock(clock=rospy.Time(2,0)))
        check(wait(lambda: count()==1), 'covering clock releases state')
        with lock:
            if received:
                check(received[0]['position']==[2.,1.,-3.] and received[0]['linear_velocity']==[4.,-5.,-6.],
                      'actual ROS axis conversion')
        pub.publish(to_ros_state(source))
        time.sleep(.1)
        check(count()==1,'duplicate does not publish twice')
        future=copy.deepcopy(source)
        future['header'].update(timestamp=3000000000,sample_id='fixture:expired')
        pub.publish(to_ros_state(future))
        time.sleep(.65)
        clock.publish(Clock(clock=rospy.Time(3,0)))
        time.sleep(.1)
        check(count()==1,'expired pending state does not release')
        future['header'].update(timestamp=4000000000,sample_id='fixture:pending')
        pub.publish(to_ros_state(future))
        terminal=copy.deepcopy(source)
        terminal['header'].update(timestamp=0,sample_id='sim.terminal:fixture_failure:0',
                                  status='unavailable',reason='terminal:fixture_failure')
        terminal['orientation_xyzw']=[0.,0.,0.,0.]
        pub.publish(to_ros_state(terminal))
        check(wait(lambda: count()==2),'terminal bypasses watermark and invalid geometry')
        pub.publish(to_ros_state(terminal))
        clock.publish(Clock(clock=rospy.Time(5,0)))
        future['header'].update(timestamp=5000000000,sample_id='fixture:after_fault')
        pub.publish(to_ros_state(future))
        time.sleep(.2)
        check(count()==2,'terminal clears pending and locks run')
        with lock:
            if len(received)>1:
                check(received[-1]['header']['reason']=='terminal:fixture_failure' and
                      received[-1]['header']['sample_id']=='sensors.state:sim.terminal:fixture_failure:0',
                      'terminal keeps reason and independent identity')
        check(sys.executable=='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python','fixture uses Conda Python')
    except (Exception, KeyboardInterrupt) as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    finally:
        sub.unregister()
        with lock:
            stream.close()
        result=dict(passed=not errors and len(checks)>=11,errors=errors,checks=checks,received_states=count(),python=sys.executable)
        (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        rospy.signal_shutdown('fixture complete')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())

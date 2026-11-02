"""Explicit P5 ROS test adapters; each role wraps its existing business layer."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]


def load_wrapper(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sensor(inputs, case):
    import rospy
    from std_msgs.msg import String
    from ufm_ros_contract.perf01a_codec import to_ros_bundle, to_ros_radar, to_ros_infrared
    from ufm_sensors.perf01a_fixture import make_motion_radar, make_fake_infrared, build_sensor_bundle
    from p5_contract import expand
    base = load_wrapper('p5_sensor_wrapper','ros_ws/src/uav_fusionmap_sensors/scripts/perf01a_sensor_node.py')
    events = expand(case,inputs['sequences'])

    class Fixture(base.SensorFixture):
        def __init__(self):
            self.receipts = rospy.Publisher('/p5/sensor/receipt',String,queue_size=100)
            self.clock_count = 0
            super().__init__()

        def receive_clock(self, message):
            super().receive_clock(message)
            self.clock_count += 1
            self.receipts.publish(String(data=json.dumps(dict(kind='clock',count=self.clock_count,
                timestamp=message.clock.to_nsec(),locked=self.gate.locked))))

        def tick(self, state):
            sequence = int(state['header']['sample_id'].rsplit(':',1)[1])
            name,op,stamp,_,args = events[sequence]
            if op != 'sample':
                raise ValueError('P5 state does not name a sample event')
            radar = make_motion_radar(self.run_id,sequence,stamp,args.get('speed_mps',0),
                                      [inputs['profiles']['A']['world_point']])
            infrared = make_fake_infrared(self.run_id,sequence,stamp+args.get('ir_delta_ns',0)) if args.get('ir_present',True) else None
            mode = rospy.get_param('/p5/backend','normal')
            if mode != 'normal':
                radar['header']['sample_id'] += ':p5_'+mode
            bundle,reason = build_sensor_bundle(radar,infrared,[state])
            self.radar_pub.publish(to_ros_radar(radar))
            if infrared is not None:
                self.ir_pub.publish(to_ros_infrared(infrared))
            if bundle is not None:
                if mode == 'untrusted_context':
                    bundle['context']['clock_id'] = 'sim:p5_foreign'
                self.bundle_pub.publish(to_ros_bundle(bundle))
            self.receipts.publish(String(data=json.dumps(dict(kind='sample',event=name,reason=reason,
                radar_id=radar['header']['sample_id'],bundle_id=None if bundle is None else bundle['header']['sample_id'],
                bundle_published=bundle is not None,locked=self.gate.locked))))

    rospy.init_node('p5_sensor')
    Fixture()
    rospy.spin()


def perception():
    import rospy
    from std_msgs.msg import String
    from p5_test_engine import TaggedEngine
    from ufm_perception import worker as worker_module

    class DiagnosticWorker(worker_module.BoundedPerceptionWorker):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.publisher = rospy.Publisher('/p5/perception/worker',String,queue_size=100)
            self.previous = None

        def emit(self):
            value = dict(pending=int(self.active_pid is not None),discarded_results=self.discarded_results)
            if value != self.previous:
                self.publisher.publish(String(data=json.dumps(value)))
                self.previous = value

        def submit(self,bundle):
            result = super().submit(bundle)
            self.emit()
            return result

        def poll(self):
            result = super().poll()
            self.emit()
            return result

    worker_module.BoundedPerceptionWorker = DiagnosticWorker
    node = load_wrapper('p5_perception_wrapper',
        'ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py')
    node.main(engine_factory=TaggedEngine)


def terrain():
    import rospy
    from std_msgs.msg import String
    from terrain_ros import TerrainNode

    class Fixture(TerrainNode):
        def __init__(self):
            self.ack = rospy.Publisher('/p5/terrain/clock',String,queue_size=100)
            self.count = 0
            super().__init__(rospy)

        def receive_clock(self,message):
            super().receive_clock(message)
            # Test source barriers use the same public tick as the wall heartbeat.
            self.tick()
            self.count += 1
            self.ack.publish(String(data=json.dumps(dict(count=self.count,timestamp=message.clock.to_nsec()))))

        def query(self,message):
            result = super().query(message)
            delay = rospy.get_param('/p5/terrain_delay_s',0.)
            if delay:
                self._stop.wait(delay)
            return result

    rospy.init_node('p5_terrain')
    Fixture().run()


def map_proxy():
    import rospy
    from std_msgs.msg import String
    from uav_fusionmap_msgs.srv import MapQuery
    rospy.init_node('p5_map_proxy')
    entered = rospy.Publisher('/p5/map/entered',String,queue_size=10)
    stopped = threading.Event()
    rospy.on_shutdown(stopped.set)

    def query(request):
        entered.publish(String(data='{"entered":true}'))
        while rospy.get_param('/p5/map_block',False) and not stopped.wait(.02):
            pass
        if stopped.is_set():
            raise rospy.ServiceException('p5_proxy_stopped')
        return rospy.ServiceProxy('/p5/map/backend',MapQuery)(request)
    rospy.Service('/uav/map/query',MapQuery,query)
    rospy.set_param('~ready',True)
    rospy.spin()


def foreign_clock():
    import rospy
    from rosgraph_msgs.msg import Clock
    rospy.init_node('p5_foreign_clock')
    publisher = rospy.Publisher('/clock',Clock,queue_size=1)
    rospy.set_param('~ready',True)
    rospy.spin()


def main():
    import rospy
    parser = argparse.ArgumentParser()
    parser.add_argument('role',choices=['sensor','perception','terrain','map_proxy','foreign_clock'])
    parser.add_argument('--input',type=Path)
    parser.add_argument('--case')
    args = parser.parse_args(rospy.myargv()[1:])
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if args.role == 'sensor':
        from p5_contract import load,validate_inputs
        inputs = load(args.input); validate_inputs(inputs)
        sensor(inputs,next(c for c in inputs['cases'] if c['id'] == args.case))
    else:
        dict(perception=perception,terrain=terrain,map_proxy=map_proxy,foreign_clock=foreign_clock)[args.role]()


if __name__ == '__main__':
    main()

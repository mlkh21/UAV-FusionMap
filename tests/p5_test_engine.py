"""Pickleable CPU fault backend for the P5 test wrapper; never a research backend."""
import time
from ufm_perception.engine import PerceptionEngine


class TaggedEngine(PerceptionEngine):
    def __init__(self,*args,**kwargs):
        import rospy
        super().__init__(*args,**kwargs)
        self.slow_duration_s = rospy.get_param('/p5/slow_duration_s',1.5)

    def _infer(self,bundle):
        identity = bundle['header']['sample_id']
        if identity.endswith(':p5_exception'):
            raise ValueError('p5_test_backend_exception')
        if identity.endswith(':p5_slow'):
            time.sleep(self.slow_duration_s)
        result = super()._infer(bundle)
        if identity.endswith(':p5_bad_output'):
            result['header']['frame_id'] = 'map'
        return result

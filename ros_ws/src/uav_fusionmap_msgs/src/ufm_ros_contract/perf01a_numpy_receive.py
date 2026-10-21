"""可选的生成代码NumPy解码候选；在ROS边界恢复原有Python容器。"""
import sys


def numpy_list_receive_type(message_type):
    import numpy
    if sys.byteorder != 'little':
        raise RuntimeError('this generated NumPy receive candidate is validated only on little-endian hosts')

    def materialize(message, fields=None):
        for name in message.__slots__ if fields is None else fields:
            value = getattr(message, name)
            if isinstance(value, numpy.ndarray):
                setattr(message, name, value.tolist())
            elif hasattr(value, '_slot_types'):
                materialize(value)
            elif isinstance(value, list):
                for item in value:
                    if hasattr(item, '_slot_types'):
                        materialize(item)

    class NumpyListReceive(message_type):
        __slots__ = ()

        def deserialize(self, data):
            message_type.deserialize_numpy(self, data, numpy)
            materialize(self, message_type.__slots__)
            return self

    return NumpyListReceive

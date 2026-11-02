"""有界采样身份历史；淘汰时间及更旧输入不能重新进入等待队列。"""
import copy
import heapq
import math


def same_sample(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_sample(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same_sample(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


class IdentityHistory:
    def __init__(self, capacity):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('invalid_identity_history_limit')
        self.capacity = capacity
        self.records = {}
        self._by_time = []
        self.retired_through = -1

    def remember(self, sample):
        header = sample['header']
        key, stamp = header['sample_id'], header['timestamp']
        if key in self.records:
            if not same_sample(self.records[key], sample):
                raise ValueError('sample_identity_conflict')
            return 'duplicate'
        if stamp <= self.retired_through:
            return 'retired'
        self.records[key] = copy.deepcopy(sample)
        heapq.heappush(self._by_time, (stamp, key))
        if len(self.records) > self.capacity:
            retired_stamp, retired_key = heapq.heappop(self._by_time)
            del self.records[retired_key]
            self.retired_through = retired_stamp
        return 'new'

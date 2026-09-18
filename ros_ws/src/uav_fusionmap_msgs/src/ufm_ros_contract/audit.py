"""可选的ROS发布调用审计；不改变消息，不将publish返回解释为网络ACK。"""
from collections import Counter
import io
import json
import os
from pathlib import Path
import sys


class PublicationAudit:
    def __init__(self, path=''):
        self.path = Path(path) if path else None
        self.file = self.path.open('x') if self.path else None
        self.records = 0
        self.counts = Counter()
        self.failed = False
        self.closed = False
        self.ready_written = False

    def record(self, topic, msg):
        if self.file is None:
            return
        try:
            if self.closed:
                raise RuntimeError('publication audit already closed')
            stream = io.BytesIO()
            msg.serialize(stream)
            header = getattr(msg, 'header', None)
            row = dict(seq=self.records + 1, topic=topic,
                       timestamp=header.timestamp if header is not None else msg.clock.to_nsec(),
                       sample_id=header.sample_id if header is not None else None,
                       wire_hex=stream.getvalue().hex())
            self.file.write(json.dumps(row, separators=(',', ':')) + '\n')
            self.records += 1
            self.counts[topic] += 1
        except Exception:
            self.failed = True
            raise

    def ready(self):
        if not self.path or self.ready_written:
            return
        try:
            with Path(str(self.path) + '.ready.json').open('x') as output:
                json.dump(dict(ready=True, python=sys.executable), output)
            self.ready_written = True
        except Exception:
            self.failed = True
            raise

    def close(self, **details):
        if self.file is None or self.closed:
            return
        try:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            with Path(str(self.path) + '.closed.json').open('x') as output:
                json.dump(dict(passed=not self.failed, records=self.records,
                               topic_counts=dict(self.counts), python=sys.executable,
                               **details), output, indent=2)
        finally:
            self.closed = True

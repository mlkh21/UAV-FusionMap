"""使用真实ROS消息验证可关闭的发布台账及错误证据。"""
import io
import json
from pathlib import Path
import tempfile
import unittest

from rosgraph_msgs.msg import Clock
import rospy
from ufm_ros_contract.audit import PublicationAudit


class PublicationAuditTest(unittest.TestCase):
    def test_default_disabled_creates_no_files(self):
        audit = PublicationAudit()
        audit.record('/clock', Clock(clock=rospy.Time(2, 3)))
        audit.ready()
        audit.close()
        self.assertIsNone(audit.path)

    def test_serialized_clock_and_sealed_counter(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audit.jsonl'
            audit = PublicationAudit(str(path))
            msg = Clock(clock=rospy.Time(2, 3))
            audit.ready()
            audit.ready()
            audit.record('/clock', msg)
            audit.close(pending_count=0)
            row = json.loads(path.read_text())
            stream = io.BytesIO()
            msg.serialize(stream)
            self.assertEqual(row, dict(seq=1, topic='/clock', timestamp=2000000003,
                                       sample_id=None, wire_hex=stream.getvalue().hex()))
            marker = json.loads(Path(str(path) + '.closed.json').read_text())
            self.assertTrue(marker['passed'])
            self.assertEqual(marker['topic_counts'], {'/clock': 1})
            self.assertEqual(marker['pending_count'], 0)

    def test_existing_history_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audit.jsonl'
            path.write_text('existing history')
            with self.assertRaises(FileExistsError):
                PublicationAudit(str(path))
            self.assertEqual(path.read_text(), 'existing history')

    def test_write_error_cannot_seal_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audit.jsonl'
            audit = PublicationAudit(str(path))
            class BrokenMessage:
                def serialize(self, stream):
                    raise OSError('test IO failure')
            with self.assertRaises(OSError):
                audit.record('/clock', BrokenMessage())
            audit.close()
            marker = json.loads(Path(str(path) + '.closed.json').read_text())
            self.assertFalse(marker['passed'])
            self.assertEqual(marker['records'], 0)


if __name__ == '__main__':
    unittest.main()

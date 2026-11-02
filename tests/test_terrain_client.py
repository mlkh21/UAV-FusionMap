"""Independent public client and transport deadline/late response acceptance."""
import copy
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from m5_iface_fixture import request, result, status
from ufm_application.terrain_client import TerrainClient
from ufm_application.terrain_visualization import marker_rows,recorded_groups
from terrain_query_transport import TerrainQueryTransport


class TerrainClientTest(unittest.TestCase):
    def client(self, transport=None):
        self.wall = 0.
        return TerrainClient(transport or (lambda req: result()), 'm5-terrain-fixture', 'm5-fixture',
                             'sim:m5-fixture', monotonic=lambda: self.wall)

    def group_transport(self, req):
        index = [[111,179],[113,179],[111,177],[113,177]].index(req['point_xy'])
        return result(index)

    def test_latched_status_is_not_liveness_and_active_query_proves_instance(self):
        client = self.client(self.group_transport)
        self.assertFalse(client.receive_status(status()))
        self.assertIsNone(client.current_group())
        group = client.sample_group()
        self.assertEqual(len(group['results']), 4)
        self.assertEqual([r['height'] for r in group['results']], [13,14,None,1])
        self.assertIsNotNone(client.current_group())

    def test_status_sequence_advances_and_timeout_clears_current_group(self):
        client = self.client(self.group_transport)
        client.receive_status(status())
        self.assertTrue(client.receive_status(dict(status(), status_sequence=2)))
        self.assertIsNotNone(client.sample_group())
        self.wall = 1.5
        self.assertIsNone(client.current_group())
        self.assertFalse(client.receive_status(dict(status(), status_sequence=2)))

    def test_instance_change_and_sequence_rollback_clear_old_state(self):
        client = self.client(self.group_transport)
        client.receive_status(status())
        client.sample_group()
        self.assertFalse(client.receive_status(status()))
        self.assertIsNone(client.current_group())
        self.assertFalse(client.receive_status(dict(status(), provider_instance_id='new', status_sequence=1)))
        self.assertIsNone(client.sample_group())  # Replies remain bound to the old instance.

    def test_bad_version_domain_and_quality_clear_without_fallback(self):
        client = self.client()
        for key, value in (('protocol_version', 2), ('run_id', 'foreign'), ('state', 'occupied')):
            self.assertFalse(client.receive_status(dict(status(), **{key:value})))
        bad = result()
        bad['height_quality']['kind'] = 'occupancy_variance'
        client.transport = lambda req: bad
        value = client.query(request())
        self.assertEqual((value['status'],value['provider_instance_id'],value['height']), ('unavailable','',None))

    def test_entire_group_discarded_on_mid_batch_revision_or_instance_change(self):
        client = self.client()
        count = [0]
        def transport(req):
            count[0] += 1
            row = self.group_transport(req)
            if count[0] == 2:
                client.receive_status(dict(status(), provider_instance_id='new', status_sequence=1))
            return row
        client.transport = transport
        client.receive_status(status())
        self.assertIsNone(client.sample_group())
        self.assertIsNone(client.current_group())

    def test_timeout_is_local_no_instance_and_late_result_never_becomes_current(self):
        entered, release = threading.Event(), threading.Event()
        def block(req):
            entered.set()
            release.wait(3.)
            return result()
        transport = TerrainQueryTransport(call=block, call_s=.03)
        client = self.client(transport)
        client.receive_status(status())
        try:
            value = client.query(request())
            self.assertTrue(entered.is_set())
            self.assertEqual((value['provider_instance_id'],value['evaluation_timestamp']), ('',None))
            self.assertIsNone(client.current_group())
            with self.assertRaises(OSError): transport(request())
            self.assertEqual(sum(t.name == 'terrain-query' for t in threading.enumerate()), 1)
        finally:
            release.set()
            transport._worker.join(2.)
            transport.close()
        self.assertIsNone(client.current_group())

    def test_transport_reuses_slot_only_when_timed_out_worker_has_finished(self):
        release = threading.Event()
        transport = TerrainQueryTransport(call=lambda req: (release.wait(2.), result())[1], call_s=.02)
        try:
            with self.assertRaises(TimeoutError): transport(request())
            with self.assertRaises(OSError): transport(request())
            release.set()
            transport._worker.join(2.)
            self.assertEqual(transport(request())['height'],13)
        finally: release.set(); transport.close()

    def test_marker_rows_preserve_missing_negative_zero_and_quality_roles(self):
        group = dict(mode='live', provider_instance_id='terrain-instance-a', terrain_revision=1,
                     context=status()['context'], results=[result(i) for i in range(4)])
        rows = marker_rows(group)
        self.assertEqual(len(rows),3)
        self.assertEqual([r['point'][2] for r in rows],[13,14,1])
        group['results'][0]['height'] = 0.
        group['results'][1]['height'] = -2.
        self.assertEqual([r['point'][2] for r in marker_rows(group)][:2],[0.,-2.])
        group['mode']='recorded'
        self.assertTrue(all(r['mode']=='recorded' for r in marker_rows(group)))
        self.assertEqual(marker_rows(None),[])

    def test_recorded_public_outputs_are_bounded_separate_and_no_private_input(self):
        receipt=dict(mode='recorded',playback_session_id='playback-a',provider_instance_id='terrain-instance-a',
            event_count=8,passed=True,results=[result(i) for i in range(4)],statuses=[status()])
        groups=recorded_groups(receipt)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(marker_rows(groups[0])),3)
        self.assertEqual(groups[0]['mode'],'recorded')
        receipt['mode']='live'
        with self.assertRaises(ValueError):recorded_groups(receipt)

    def test_expiry_during_group_cannot_mix_current_and_stale_geometry(self):
        client=self.client()
        counter=[0]
        def reply(req):
            row=self.group_transport(req)
            counter[0]+=1
            if counter[0]==2:row.update(status='stale',reason='terrain_expired',evaluation_timestamp=200)
            return row
        client.transport=reply
        client.receive_status(status())
        self.assertIsNone(client.sample_group())
        self.assertIsNone(client.current_group())

    def test_real_generated_marker_array_deletes_old_ids_and_preserves_historical_label(self):
        from terrain_rviz_node import build_markers
        from visualization_msgs.msg import Marker
        group=dict(mode='recorded',provider_instance_id='terrain-instance-a',terrain_revision=1,
                   context=status()['context'],results=[result(i) for i in range(4)])
        message=build_markers(marker_rows(group))
        self.assertEqual(message.markers[0].action,Marker.DELETEALL)
        self.assertEqual(sum(m.type==Marker.CUBE and m.action==Marker.ADD for m in message.markers),3)
        self.assertTrue(message.markers[-1].text.startswith('recorded'))
        self.assertEqual(len(build_markers([]).markers),1)


if __name__ == '__main__': unittest.main()

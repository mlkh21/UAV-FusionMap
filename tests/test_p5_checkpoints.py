"""Independent receipt comparisons cannot accept echoed declarations as observations."""
import copy
import unittest

from p5_checkpoints import compare,verify_receipts,float32,connected_outputs


class CheckpointTest(unittest.TestCase):
    def test_integer_time_revision_and_bool_flags_remain_exact_types(self):
        for actual,wanted in [(True,1),(1.,1),(0,False)]:
            self.assertTrue(compare({'map.revision':actual},{'map.revision':wanted},{}))
        self.assertFalse(compare({'map.evidence_ns':2**53+1},{'map.evidence_ns':2**53+1},{}))

    def test_physical_height_keeps_exact_value_without_requiring_json_integer_type(self):
        self.assertFalse(compare({'terrain.height':13.},{'terrain.height':13},{}))
        for height in (13.000001,True,None):
            self.assertTrue(compare({'terrain.height':height},{'terrain.height':13},{}))

    def test_float32_probability_and_fraction_bounds_have_declared_precision(self):
        values = {'map.probability':float32(.9),'map.interval':[49/85,27/34]}
        expected = {'map.probability':.9,'map.interval':['49/85','27/34']}
        self.assertFalse(compare(values,expected,{}))
        for key in values:
            bad = copy.deepcopy(values)
            bad[key] = .9 if key.endswith('probability') else [.57,.8]
            self.assertTrue(compare(bad,expected,{}))

    def test_provider_symbol_binding_requires_actual_nonempty_instance_and_difference(self):
        bindings = {}
        self.assertTrue(compare({'terrain.instance':'new'},{'terrain.instance':'$different'},bindings))
        self.assertTrue(compare({'terrain.instance':''},{'terrain.instance':'$first'},bindings))
        self.assertFalse(compare({'terrain.instance':'old'},{'terrain.instance':'$first'},bindings))
        self.assertTrue(compare({'terrain.instance':'old'},{'terrain.instance':'$different'},bindings))
        self.assertFalse(compare({'terrain.instance':'new'},{'terrain.instance':'$different'},bindings))

    def test_recording_ceiling_compares_actual_event_count_not_the_declared_budget(self):
        self.assertFalse(compare({'recording.event_ceiling':22},{'recording.event_ceiling':33},{}))
        for value in (34,True,None,-1):
            self.assertTrue(compare({'recording.event_ceiling':value},{'recording.event_ceiling':33},{}))

    def test_missing_duplicate_and_changed_actual_checkpoint_fail(self):
        expected = {'checks':[{'after':'event','values':{'map.revision':4},'declared':{'owner':'active'}}]}
        row = {'event_id':'event','values':{'map.revision':4}}
        self.assertTrue(verify_receipts(expected,[row])['passed'])
        self.assertFalse(verify_receipts(expected,[])['passed'])
        self.assertFalse(verify_receipts(expected,[dict(row,values={})])['passed'])
        with self.assertRaises(ValueError): verify_receipts(expected,[row,row])

    def test_geometry_tolerance_never_applies_to_cell_index_or_height(self):
        self.assertFalse(compare({'geometry.point':[1.25,4.25+1e-10,.25]},
                                 {'geometry.point':[1.25,4.25,.25]},{}))
        self.assertTrue(compare({'geometry.index':[34,23,8]},{'geometry.index':[34,24,8]},{}))

    def test_bus_barrier_requires_connected_outgoing_connections_for_both_consumers(self):
        rows = [[1,'/observer','o','TCPROS','/occupancy',True],
                [2,'/mapping','o','TCPROS','/occupancy',False],
                [3,'/mapping','i','TCPROS','/occupancy',True]]
        self.assertFalse(connected_outputs(rows,{'/occupancy':2}))
        rows[1][5] = True
        self.assertTrue(connected_outputs(rows,{'/occupancy':2}))


if __name__ == '__main__':
    unittest.main()

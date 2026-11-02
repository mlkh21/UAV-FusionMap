"""Matrix acceptance rejects partial, mixed, failed or over-budget evidence."""
import copy
import unittest

from sim_motion_matrix_run import ORDER,validate_totals


class MatrixAcceptanceTests(unittest.TestCase):
    def rows(self):
        return [dict(id=name,passed=True,cleanup_passed=True,source_unchanged=True,
            committed_ns=496000000 if name=='S08' else 1000000000,
            wire_bytes=1000000,session_seconds=20.,artifact_bytes=2000000) for name in ORDER]

    def test_complete_ordered_matrix_counts_committed_time(self):
        self.assertEqual(validate_totals(self.rows(),300.,24000000)['committed_source_ns'],8496000000)

    def test_missing_duplicate_or_reordered_case_cannot_close_matrix(self):
        rows=self.rows()
        for bad in (rows[:-1],rows+[rows[-1]],list(reversed(rows))):
            with self.assertRaisesRegex(ValueError,'incomplete'):validate_totals(bad,300.,24000000)

    def test_failed_cleanup_or_mixed_source_cannot_close_matrix(self):
        for field in ('passed','cleanup_passed','source_unchanged'):
            rows=self.rows();rows[4][field]=False
            with self.assertRaisesRegex(ValueError,'accepted'):validate_totals(rows,300.,24000000)

    def test_source_time_wire_session_and_artifact_budgets_are_required(self):
        for field,value in (('committed_ns',1000000001),('wire_bytes',16*1024**2+1),
                            ('session_seconds',120.001),('artifact_bytes',256*1024**2+1)):
            rows=copy.deepcopy(self.rows());rows[0][field]=value
            with self.assertRaises(ValueError):validate_totals(rows,300.,24000000)
        for wall,size in ((1800.001,24000000),(300.,3*1024**3+1)):
            with self.assertRaisesRegex(ValueError,'suite_budget'):validate_totals(self.rows(),wall,size)


if __name__=='__main__':unittest.main()

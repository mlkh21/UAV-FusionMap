"""Hand-calculated TTL oracle expectations, independent of map implementation."""
import unittest

from m2_fixture import load_spec
from m2_oracle import expected_timed_sequence


class TimedOracleTest(unittest.TestCase):
    def test_exact_ttl_boundary_and_expiry_restart(self):
        spec = load_spec()
        result = expected_timed_sequence(('occupied', 'occupied', 'neutral', 'occupied', 'free'),
            (10_000_000, 20_000_000, 120_000_000, 130_000_000, 140_000_000), spec)
        self.assertEqual([row['probability_fraction'] for row in result],
                         ['3/4', '9/10', '9/10', '3/4', '1/2'])
        self.assertEqual(result[2]['last_observed_timestamp'], 20_000_000)
        boundary = expected_timed_sequence(('occupied', 'occupied'), (10_000_000, 110_000_000), spec)
        self.assertEqual(boundary[-1]['probability_fraction'], '9/10')

    def test_invalid_time_order_is_not_sorted_or_silently_fixed(self):
        for stamps in ((20, 10), (10, 10), (-1, 10), (0, 2**63)):
            with self.subTest(stamps=stamps), self.assertRaises(ValueError):
                expected_timed_sequence(('occupied', 'free'), stamps, load_spec())


if __name__ == '__main__':
    unittest.main()

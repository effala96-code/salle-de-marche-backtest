import unittest

import numpy as np

from order_effects_test import order_effect_test, simulate


class OrderEffectsTests(unittest.TestCase):
    def test_mismatched_lengths_are_rejected(self):
        with self.assertRaises(ValueError):
            order_effect_test([1, 2], [1], [0.1, 0.2])

    def test_non_finite_and_symmetric_pairs_are_excluded(self):
        T, p, n = order_effect_test(
            [1.0, 2.0, np.nan, 3.0],
            [1.0, 1.0, 4.0, 3.0],
            [0.1, 0.2, 0.3, 0.4],
            n_perm=100,
        )
        self.assertEqual(n, 1)
        self.assertTrue(np.isfinite(T))
        self.assertTrue(0 < p <= 1)

    def test_no_usable_pairs_are_rejected(self):
        with self.assertRaises(ValueError):
            order_effect_test([1, 2], [1, 2], [0.1, 0.2])

    def test_commutative_and_recency_cases(self):
        neutral = order_effect_test(*simulate(recency=0.0), n_perm=500)
        recency = order_effect_test(*simulate(recency=0.3), n_perm=500)
        self.assertGreaterEqual(neutral[1], recency[1])
        self.assertLess(recency[0], 0)


if __name__ == "__main__":
    unittest.main()

import unittest
from statistics import fmean, pstdev

from moonface.research.matrix.causal.scaler import CausalStandardScaler


class ScalerTest(unittest.TestCase):
    def test_stats_come_from_train_only(self):
        train = [[0.0, 10.0], [2.0, 14.0], [4.0, 18.0]]
        sc = CausalStandardScaler().fit(train)
        self.assertEqual(sc.means[0], fmean([0.0, 2.0, 4.0]))
        self.assertEqual(sc.stds[1], pstdev([10.0, 14.0, 18.0]))
        z = sc.transform(train)
        self.assertAlmostEqual(fmean([r[0] for r in z]), 0.0, places=9)

    def test_test_rows_use_frozen_train_stats(self):
        train = [[0.0], [2.0], [4.0]]
        sc = CausalStandardScaler().fit(train)
        got = sc.transform([[2.0], [1e9]])[0][0]
        self.assertAlmostEqual(got, 0.0, places=9)

    def test_zero_variance_column_is_safe(self):
        sc = CausalStandardScaler().fit([[5.0], [5.0], [5.0]])
        self.assertEqual(sc.transform([[5.0]]), [[0.0]])


if __name__ == "__main__":
    unittest.main()

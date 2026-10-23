import unittest

from moonface.core.models import Candle
from moonface.research.edge.ob_imbalance_signals import (
    bar_mean_imbalance, make_ob_imbalance_follow)

H4 = 4 * 3_600_000


def _c(i, close=100.0):
    return Candle(i * H4, close, close + 1, close - 1, close, 1000.0)


class TestBarMeanImbalance(unittest.TestCase):
    def test_means_snapshots_inside_each_bar(self):
        candles = [_c(0), _c(1), _c(2)]
        # bar 0 = [0, H4): two snapshots 0.2 and 0.4 -> mean 0.3
        # bar 1 = [H4, 2H4): one snapshot -0.5
        # bar 2 = [2H4, 3H4): no snapshots -> None
        points = [(10, 0.2), (H4 - 5, 0.4), (H4 + 10, -0.5)]
        series = bar_mean_imbalance(candles, points)
        self.assertEqual(len(series), 3)
        self.assertAlmostEqual(series[0], 0.3)
        self.assertAlmostEqual(series[1], -0.5)
        self.assertIsNone(series[2])

    def test_empty_points_all_none(self):
        candles = [_c(0), _c(1)]
        self.assertEqual(bar_mean_imbalance(candles, []), [None, None])

    def test_snapshot_on_bar_start_is_included(self):
        # half-open [start, end): a snapshot exactly on a bar's start timestamp
        # belongs to THAT bar, not the previous one.
        candles = [_c(0), _c(1)]
        points = [(0, 0.5), (H4, 0.7)]   # 0 -> bar0 start, H4 -> bar1 start
        series = bar_mean_imbalance(candles, points)
        self.assertEqual(series, [0.5, 0.7])


class TestObImbalanceFollow(unittest.TestCase):
    def _ramp_candles(self, n):
        return [_c(i) for i in range(n)]

    def test_high_bid_imbalance_goes_long(self):
        n = 40
        candles = self._ramp_candles(n)
        # flat imbalance then a strong positive (bid-side) spike at i=30
        feature = [0.0] * n
        feature[30] = 5.0
        gen = make_ob_imbalance_follow(feature)
        out = gen(candles, {"window": 20, "z_thr": 1.5})
        self.assertIn((30, "LONG"), out)

    def test_strong_ask_imbalance_goes_short(self):
        n = 40
        candles = self._ramp_candles(n)
        feature = [0.0] * n
        feature[30] = -5.0
        gen = make_ob_imbalance_follow(feature)
        out = gen(candles, {"window": 20, "z_thr": 1.5})
        self.assertIn((30, "SHORT"), out)

    def test_symmetry_mirrored_feature_mirrors_sides(self):
        n = 40
        candles = self._ramp_candles(n)
        feature = [0.0] * n
        feature[30] = 4.0
        pos = make_ob_imbalance_follow(feature)(candles,
                                                {"window": 20, "z_thr": 1.5})
        neg_feat = [-v for v in feature]
        neg = make_ob_imbalance_follow(neg_feat)(candles,
                                                 {"window": 20, "z_thr": 1.5})
        flip = {(i, "SHORT" if s == "LONG" else "LONG") for i, s in pos}
        self.assertEqual(set(neg), flip)


if __name__ == "__main__":
    unittest.main()

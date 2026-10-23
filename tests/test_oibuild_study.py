# tests/test_oibuild_study.py
import unittest

from moonface.research.universe_data import DailyRow
from moonface.features.oi_features import (asset_stats, binom_p_geq,
                                             event_returns, nonoverlap,
                                             select_universe, stouffer,
                                             verdict_from)

DAY = 86_400_000


class TestStats(unittest.TestCase):
    def test_exact_one_sided_binomial(self):
        self.assertAlmostEqual(binom_p_geq(5, 5), 1 / 32)
        self.assertAlmostEqual(binom_p_geq(4, 5), 6 / 32)
        self.assertAlmostEqual(binom_p_geq(0, 5), 1.0)

    def test_stouffer_z(self):
        self.assertAlmostEqual(stouffer([1.0, 1.0, 1.0, 1.0]), 2.0)
        self.assertAlmostEqual(stouffer([]), 0.0)

    def test_asset_stats_hand_computed(self):
        s = asset_stats([0.01, 0.03])
        self.assertEqual(s["n"], 2)
        self.assertAlmostEqual(s["mean"], 0.02)
        self.assertAlmostEqual(s["t"], 2.0, places=6)

    def test_asset_stats_degenerate(self):
        self.assertEqual(asset_stats([])["n"], 0)
        self.assertEqual(asset_stats([0.01])["t"], 0.0)
        self.assertEqual(asset_stats([0.01, 0.01])["t"], 0.0)  # zero variance


class TestEvents(unittest.TestCase):
    def test_nonoverlap_drops_events_within_horizon(self):
        events = [(5, "LONG"), (10, "SHORT"), (29, "LONG"), (53, "SHORT")]
        self.assertEqual(nonoverlap(events, h=24),
                         [(5, "LONG"), (29, "LONG"), (53, "SHORT")])

    def test_event_returns_directional_and_bounded(self):
        closes = [100.0, 110.0, 121.0, 133.1, 146.41]
        # LONG at 0 with h=2: 121/100-1 = +0.21
        # SHORT at 1 with h=2: -(133.1/110-1) = -0.21
        # event at 3 has no bar 5 -> dropped
        rets = event_returns(closes, [(0, "LONG"), (1, "SHORT"), (3, "LONG")],
                             h=2)
        self.assertEqual(len(rets), 2)
        self.assertAlmostEqual(rets[0], 0.21)
        self.assertAlmostEqual(rets[1], -0.21)


class TestUniverse(unittest.TestCase):
    def test_ranks_by_volume_asof_window_start_with_listing_floor(self):
        def rows(qvol, n_days, start_day=0):
            return [DailyRow((start_day + i) * DAY, 100.0, qvol)
                    for i in range(n_days)]
        daily = {
            "AUSDT": rows(5000, 100),
            "BUSDT": rows(9000, 100),
            "CUSDT": rows(99000, 30, start_day=70),   # listed too late
            "BTCUSDT": rows(7000, 100),               # excluded by rule
        }
        got = select_universe(daily, window_start=100 * DAY,
                              exclude={"BTCUSDT"}, top_k=24, vol_days=30,
                              min_history_days=90)
        self.assertEqual(got, ["BUSDT", "AUSDT"])


class TestVerdict(unittest.TestCase):
    @staticmethod
    def _stat(mean, t):
        return {"n": 30, "mean": mean, "t": t}

    def test_exists_when_both_coprimaries_pass(self):
        stats = [self._stat(0.01, 2.5)] * 9
        v = verdict_from(stats, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_exists")
        self.assertAlmostEqual(v["p_sign"], 1 / 512)
        self.assertAlmostEqual(v["stouffer_z"], 7.5)

    def test_does_not_exist_when_pooled_mean_nonpositive(self):
        stats = [self._stat(-0.01, -1.0)] * 6 + [self._stat(0.005, 0.5)] * 3
        v = verdict_from(stats, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_does_not_exist")

    def test_inconclusive_when_positive_but_weak(self):
        stats = ([self._stat(0.004, 0.4)] * 5
                 + [self._stat(-0.002, -0.2)] * 3)
        v = verdict_from(stats, min_assets=8)
        self.assertEqual(v["verdict"], "inconclusive")

    def test_insufficient_assets_is_inconclusive(self):
        v = verdict_from([self._stat(0.01, 3.0)] * 5, min_assets=8)
        self.assertEqual(v["verdict"], "inconclusive")
        self.assertIn("insufficient", v["reason"])


if __name__ == "__main__":
    unittest.main()

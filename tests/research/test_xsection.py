# tests/test_xsection.py
import math
import unittest

from moonface.research.universe_data import DailyRow
from moonface.research.xsection import (build_universe, carry_signal,
                                        gate_construction, momentum_signal,
                                        simulate)

DAY = 86_400_000


def _rows(closes, qvol=1000.0, start_day=0):
    return [DailyRow((start_day + i) * DAY, c, qvol)
            for i, c in enumerate(closes)]


class TestUniverse(unittest.TestCase):
    def test_top_n_by_trailing_quote_volume_with_listing_floor(self):
        daily = {
            "AUSDT": _rows([100] * 40, qvol=5000.0),
            "BUSDT": _rows([100] * 40, qvol=3000.0),
            "CUSDT": _rows([100] * 5, qvol=9000.0, start_day=35),  # too young
            "DUSDT": _rows([100] * 40, qvol=1000.0),
        }
        got = build_universe(daily, asof=39 * DAY, top_n=2,
                             min_history_days=30, vol_days=10)
        self.assertEqual(got, ["AUSDT", "BUSDT"])

    def test_symbol_without_recent_volume_is_excluded(self):
        daily = {
            "AUSDT": _rows([100] * 10, qvol=5000.0),  # ends day 9
            "BUSDT": _rows([100] * 40, qvol=10.0),
        }
        got = build_universe(daily, asof=39 * DAY, top_n=2,
                             min_history_days=5, vol_days=10)
        self.assertEqual(got, ["BUSDT"])


class TestSignals(unittest.TestCase):
    def test_momentum_is_trailing_return(self):
        idx = {r.ts_ms: r for r in _rows([100, 110, 121])}
        self.assertAlmostEqual(momentum_signal(idx, 2 * DAY, days=2), 0.21)
        self.assertIsNone(momentum_signal(idx, 2 * DAY, days=5))

    def test_carry_is_trailing_mean_daily_funding(self):
        funding_day = {0: 0.001, DAY: 0.003}
        self.assertAlmostEqual(carry_signal(funding_day, DAY, days=2), 0.002)
        self.assertAlmostEqual(carry_signal(funding_day, 3 * DAY, days=2), 0.0)


class TestSimulate(unittest.TestCase):
    def test_long_short_with_fees_and_funding(self):
        daily = {
            "AUSDT": _rows([100.0, 110.0, 121.0, 133.1]),
            "BUSDT": _rows([100.0, 90.0, 81.0, 72.9]),
            "CUSDT": _rows([100.0] * 4),
            "DUSDT": _rows([100.0] * 4),
        }
        funding = {"BUSDT": {2 * DAY: 0.001}}
        rets = simulate(daily, funding, kind="momentum", days=1,
                        start_ms=0, end_ms=4 * DAY, top_n=4, quintile=4,
                        rebalance_days=2, fee=0.0005, min_history_days=0,
                        vol_days=2)
        self.assertEqual([ts for ts, _ in rets], [DAY, 2 * DAY, 3 * DAY])
        by_ts = dict(rets)
        # d1: no positions yet; rebalance happens (long A, short B),
        # turnover 2.0 -> fee 0.001
        self.assertAlmostEqual(by_ts[DAY], -0.001)
        # d2: +10% on the long, +10% on the short, short receives B's funding
        self.assertAlmostEqual(by_ts[2 * DAY], 0.2 + 0.001)
        # d3: same book re-derived (turnover 0 -> no fee), no funding
        self.assertAlmostEqual(by_ts[3 * DAY], 0.2)

    def test_carry_longs_low_funding_and_shorts_high(self):
        daily = {s: _rows([100.0] * 4) for s in
                 ("AUSDT", "BUSDT", "CUSDT", "DUSDT")}
        funding = {"AUSDT": {0: -0.002, DAY: -0.002, 2 * DAY: -0.002},
                   "BUSDT": {0: 0.003, DAY: 0.003, 2 * DAY: 0.003}}
        rets = simulate(daily, funding, kind="carry", days=1,
                        start_ms=0, end_ms=4 * DAY, top_n=4, quintile=4,
                        rebalance_days=2, fee=0.0, min_history_days=0,
                        vol_days=2)
        by_ts = dict(rets)
        # long A (lowest funding, negative -> long receives 0.002),
        # short B (highest -> short receives 0.003)
        self.assertAlmostEqual(by_ts[2 * DAY], 0.002 + 0.003)


class TestGates(unittest.TestCase):
    def test_steady_positive_curve_passes_all_stages(self):
        returns = [0.004 if i % 7 else -0.002 for i in range(500)]
        m = gate_construction(returns, fence_idx=400)
        self.assertTrue(m["stage1_pass"])
        self.assertTrue(m["stage2_pass"])
        self.assertGreater(m["research_sharpe"], 0.0)
        self.assertEqual(m["tail_days"], 100)

    def test_negative_screen_fails_stage1(self):
        m = gate_construction([-0.001] * 500, fence_idx=400)
        self.assertFalse(m["stage1_pass"])

    def test_holdout_drawdown_budget_fails_stage2(self):
        # positive screen, then a crash in the holdout segment
        returns = [0.002] * 280 + [-0.05] * 10 + [0.002] * 110 + [0.0] * 100
        m = gate_construction(returns, fence_idx=400)
        self.assertTrue(m["stage1_pass"])
        self.assertFalse(m["stage2_pass"])
        self.assertFalse(math.isnan(m["holdout_mar"]))


if __name__ == "__main__":
    unittest.main()

import unittest

from moonface.core.models import Candle
from moonface.research.liqrev import (detect_events, event_net_returns,
                                      liqrev_verdict, pooled)

H4 = 4 * 3_600_000


def candle(i, close):
    return Candle(i * H4, close, close, close, close, 1000.0)


class TestLiqrevEvents(unittest.TestCase):
    def test_detects_joint_price_shock_and_oi_collapse_without_lookahead(self):
        closes = [100.0 + i for i in range(30)]
        closes[20] = 80.0
        candles = [candle(i, c) for i, c in enumerate(closes)]
        oi = [100.0 + i for i in range(30)]
        oi[20] = 70.0

        events = detect_events(candles, oi, lookback=10, q=0.95)

        self.assertEqual(events, [(20, "LONG")])

    def test_event_returns_fade_the_shock_and_subtract_cost(self):
        closes = [100.0] * 30
        closes[10] = 80.0
        closes[16] = 88.0
        candles = [candle(i, c) for i, c in enumerate(closes)]

        rets = event_net_returns(candles, [(10, "LONG")], h=6, cost=0.001)

        self.assertEqual(len(rets), 1)
        self.assertAlmostEqual(rets[0], 88.0 / 80.0 - 1.0 - 0.001)

    def test_short_event_profits_when_price_reverts_down(self):
        closes = [100.0] * 30
        closes[10] = 120.0
        closes[16] = 108.0
        candles = [candle(i, c) for i, c in enumerate(closes)]

        rets = event_net_returns(candles, [(10, "SHORT")], h=6, cost=0.001)

        self.assertAlmostEqual(rets[0], -(108.0 / 120.0 - 1.0) - 0.001)


class TestLiqrevVerdict(unittest.TestCase):
    @staticmethod
    def stat(mean, t):
        return {"n": 20, "mean": mean, "t": t}

    def test_pooled_summary_uses_sign_count_and_stouffer(self):
        got = pooled([self.stat(0.01, 1.0), self.stat(-0.01, -0.5)])
        self.assertEqual(got["m"], 2)
        self.assertEqual(got["k_positive"], 1)
        self.assertAlmostEqual(got["stouffer_z"], (1.0 - 0.5) / 2 ** 0.5)

    def test_verdict_passes_only_when_gate_and_robustness_clear(self):
        stats = [self.stat(0.01, 1.0)] * 12 + [self.stat(-0.001, -0.1)] * 4
        robustness = {
            "time_first_half": {"pooled_mean": 0.002},
            "time_second_half": {"pooled_mean": 0.003},
            "leave_one_out_pooled_mean": {"min": 0.001, "max": 0.004},
        }
        v = liqrev_verdict(stats, robustness, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_exists")

    def test_verdict_closes_when_pooled_mean_nonpositive(self):
        stats = [self.stat(-0.01, -1.0)] * 8
        robustness = {
            "time_first_half": {"pooled_mean": -0.01},
            "time_second_half": {"pooled_mean": -0.01},
            "leave_one_out_pooled_mean": {"min": -0.01, "max": -0.01},
        }
        v = liqrev_verdict(stats, robustness, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_does_not_exist")

    def test_verdict_closes_when_time_or_leave_one_out_fails(self):
        stats = [self.stat(0.01, 1.0)] * 12 + [self.stat(-0.001, -0.1)] * 4
        robustness = {
            "time_first_half": {"pooled_mean": 0.002},
            "time_second_half": {"pooled_mean": -0.001},
            "leave_one_out_pooled_mean": {"min": 0.001, "max": 0.004},
        }
        v = liqrev_verdict(stats, robustness, min_assets=8)
        self.assertEqual(v["verdict"], "non_robust")
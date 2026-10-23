import unittest

from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.liqladder import (atr_series, detect_events,
                                         liqladder_verdict)

H1 = 3_600_000


def candle(i, close, high=None, low=None):
    high = close + 1.0 if high is None else high
    low = close - 1.0 if low is None else low
    return Candle(i * H1, close, high, low, close, 1000.0)


def base_fixture(n, oi_flat_after=None, sweep_at=None, oi_zero_at=None,
                 oi_decay_at=None):
    candles = []
    oi = []
    for i in range(n):
        low = 96.0 if sweep_at is not None and i == sweep_at else 99.0
        candles.append(candle(i, 100.0, low=low))
        if oi_flat_after is not None and i > oi_flat_after:
            oi.append(oi[oi_flat_after])
        else:
            oi.append(1000.0 + 10.0 * i)
    if oi_zero_at is not None:
        for i in range(oi_zero_at, n):
            oi[i] = 0.0
    if oi_decay_at is not None:
        for i in range(oi_decay_at, n):
            oi[i] = oi[oi_decay_at - 1] * 0.9
    ratio = [9.0] * n
    return candles, oi, ratio


class TestAtrSeries(unittest.TestCase):
    def test_matches_foundation_atr_at_every_prefix(self):
        closes = [100.0, 103.0, 99.0, 105.0, 104.0, 90.0, 95.0, 96.0,
                  120.0, 118.0, 117.0, 119.0, 100.0, 101.0, 99.5, 103.0]
        candles = [Candle(i * H1, c, c + 2.0 + (i % 3), c - 1.0 - (i % 2), c,
                          1000.0) for i, c in enumerate(closes)]
        series = atr_series(candles, period=5)
        for i in range(len(candles)):
            self.assertAlmostEqual(series[i], atr(candles[: i + 1], 5),
                                   msg=f"prefix {i}")


class TestLiqladderEvents(unittest.TestCase):
    def test_long_heavy_ladder_below_spot_triggers_short_continuation(self):
        candles, oi, ratio = base_fixture(20)
        events = detect_events(candles, oi, ratio)
        self.assertTrue(events)
        self.assertTrue(all(side == "SHORT" for _, side in events))
        self.assertTrue(all(i >= 14 for i, _ in events))

    def test_sweep_consumes_downside_bins_and_flips_magnet_upward(self):
        candles, oi, ratio = base_fixture(28, oi_flat_after=12, sweep_at=20)
        events = detect_events(candles, oi, ratio)
        before = [side for i, side in events if i < 20]
        after = [side for i, side in events if i >= 20]
        self.assertTrue(before and all(s == "SHORT" for s in before))
        self.assertTrue(after and all(s == "LONG" for s in after))

    def test_oi_wipeout_clears_the_ladder_and_silences_events(self):
        candles, oi, ratio = base_fixture(30, oi_zero_at=16)
        events = detect_events(candles, oi, ratio)
        self.assertTrue(any(i < 16 for i, _ in events))
        self.assertFalse([e for e in events if e[0] >= 16])

    def test_proportional_oi_decay_preserves_asymmetry_and_events(self):
        candles, oi, ratio = base_fixture(24, oi_decay_at=16)
        events = detect_events(candles, oi, ratio)
        self.assertTrue(any(i >= 17 for i, _ in events))
        self.assertTrue(all(side == "SHORT" for _, side in events))


class TestLiqladderVerdict(unittest.TestCase):
    @staticmethod
    def stat(mean, t):
        return {"n": 20, "mean": mean, "t": t}

    def test_verdict_passes_only_when_gate_and_robustness_clear(self):
        stats = [self.stat(0.01, 1.0)] * 12 + [self.stat(-0.001, -0.1)] * 4
        robustness = {
            "time_first_half": {"pooled_mean": 0.002},
            "time_second_half": {"pooled_mean": 0.003},
            "leave_one_out_pooled_mean": {"min": 0.001, "max": 0.004},
        }
        v = liqladder_verdict(stats, robustness, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_exists")

    def test_verdict_closes_when_pooled_mean_nonpositive(self):
        stats = [self.stat(-0.01, -1.0)] * 8
        robustness = {
            "time_first_half": {"pooled_mean": -0.01},
            "time_second_half": {"pooled_mean": -0.01},
            "leave_one_out_pooled_mean": {"min": -0.01, "max": -0.01},
        }
        v = liqladder_verdict(stats, robustness, min_assets=8)
        self.assertEqual(v["verdict"], "mechanism_does_not_exist")

    def test_verdict_closes_when_time_or_leave_one_out_fails(self):
        stats = [self.stat(0.01, 1.0)] * 12 + [self.stat(-0.001, -0.1)] * 4
        robustness = {
            "time_first_half": {"pooled_mean": 0.002},
            "time_second_half": {"pooled_mean": -0.001},
            "leave_one_out_pooled_mean": {"min": 0.001, "max": 0.004},
        }
        v = liqladder_verdict(stats, robustness, min_assets=8)
        self.assertEqual(v["verdict"], "non_robust")

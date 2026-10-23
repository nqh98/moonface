import unittest
from moonface.core.models import Candle
from moonface.research.edge.forced_error_signals import (
    failed_breakout_naive, make_failed_breakout_harvest,
    make_failed_fade_squeeze, make_funding_fade_long, _percentile)


def _c(ts, o, h, low_, cl, v=100.0):
    return Candle(timestamp_ms=ts, open=o, high=h, low=low_, close=cl, volume=v)


class TestPercentile(unittest.TestCase):
    def test_linear_interpolation(self):
        self.assertAlmostEqual(_percentile([0, 10], 0.2), 2.0)
        self.assertAlmostEqual(_percentile([1, 2, 3, 4, 5], 0.0), 1.0)
        self.assertAlmostEqual(_percentile([1, 2, 3, 4, 5], 1.0), 5.0)


class TestFailedBreakoutNaive(unittest.TestCase):
    def _series(self):
        # 5 flat bars at high=10, then bar pierces to 12 but closes back at 9.
        cs = [_c(i, 9, 10, 8, 9) for i in range(5)]
        cs.append(_c(5, 9, 12, 8, 9))   # pierce (12>10) and close inside (9<10)
        cs.append(_c(6, 9, 9, 8, 9))     # trailing bar (loop needs i < n-1)
        return cs

    def test_fires_short_on_failed_pierce(self):
        out = failed_breakout_naive(self._series(), {"donchian_n": 5})
        self.assertIn((5, "SHORT"), out)

    def test_no_fire_when_close_holds_above(self):
        cs = self._series()
        cs[5] = _c(5, 9, 12, 8, 11)      # closes above resistance -> not a failure
        out = failed_breakout_naive(cs, {"donchian_n": 5})
        self.assertEqual(out, [])


class TestFailedBreakoutHarvest(unittest.TestCase):
    def test_requires_oi_and_volume_gates(self):
        n = 200
        cs = [_c(i, 9, 10, 8, 9, v=100.0) for i in range(n)]
        cs[190] = _c(190, 9, 12, 8, 9, v=100000.0)   # pierce+fail, volume spike
        oi = [100.0] * n
        for j in range(185, 191):
            oi[j] = 100.0 + (j - 184) * 50.0          # OI ramps up into the event
        gen = make_failed_breakout_harvest(oi)
        params = {"donchian_n": 24, "window": 180, "lookback": 3, "k": 1.5,
                  "use_volume": True}
        out = gen(cs, params)
        self.assertIn((190, "SHORT"), out)

    def test_ablation_drops_volume_gate(self):
        # use_volume=False must still fire without any volume spike present.
        n = 200
        cs = [_c(i, 9, 10, 8, 9, v=100.0) for i in range(n)]
        cs[190] = _c(190, 9, 12, 8, 9, v=100.0)       # NO volume spike
        oi = [100.0] * n
        for j in range(185, 191):
            oi[j] = 100.0 + (j - 184) * 50.0
        gen = make_failed_breakout_harvest(oi)
        base = {"donchian_n": 24, "window": 180, "lookback": 3, "k": 1.5}
        self.assertNotIn((190, "SHORT"), gen(cs, {**base, "use_volume": True}))
        self.assertIn((190, "SHORT"), gen(cs, {**base, "use_volume": False}))


class TestFailedFadeSqueeze(unittest.TestCase):
    def test_long_on_absorbed_rally_with_negative_funding(self):
        n = 200
        # Uptrend so z_r is high at the event; absorption bar probes lower, closes up.
        cs = [_c(i, 100 + i, 101 + i, 99 + i, 100 + i, v=100.0) for i in range(n)]
        cs[189] = _c(189, 289, 290, 288, 289)
        cs[190] = _c(190, 289, 292, 287, 291)          # low<prev low, close>prev close
        oi = [100.0 + i for i in range(n)]              # OI climbing
        funding = [-0.01] * n                           # deeply negative throughout
        gen = make_failed_fade_squeeze(oi, funding)
        out = gen(cs, {"window": 180, "lookback": 3, "k": 1.0,
                       "funding_pct": 0.5, "funding_window": 50})
        self.assertIn((190, "LONG"), out)

    def test_no_fire_when_funding_not_negative_enough(self):
        n = 200
        cs = [_c(i, 100 + i, 101 + i, 99 + i, 100 + i) for i in range(n)]
        cs[190] = _c(190, 289, 292, 287, 291)
        oi = [100.0 + i for i in range(n)]
        funding = [0.01] * n                            # positive funding
        gen = make_failed_fade_squeeze(oi, funding)
        out = gen(cs, {"window": 180, "lookback": 3, "k": 1.0,
                       "funding_pct": 0.5, "funding_window": 50})
        self.assertEqual(out, [])


class TestFundingFadeLong(unittest.TestCase):
    def test_long_only_on_low_percentile_funding(self):
        n = 100
        cs = [_c(i, 9, 10, 8, 9) for i in range(n)]
        funding = [0.01] * n
        funding[80] = -0.05                             # bottom of the window
        gen = make_funding_fade_long(funding)
        out = gen(cs, {"funding_pct": 0.2, "funding_window": 50})
        self.assertTrue(all(side == "LONG" for _, side in out))
        self.assertIn(80, [i for i, _ in out])

    def test_no_fire_when_bottom_percentile_is_still_positive(self):
        # All funding positive: the bottom percentile is positive, so the
        # deeply-negative (<0) requirement must suppress every fire. This mirrors
        # the treatment's negativity gate so the control is a clean isolation.
        n = 100
        cs = [_c(i, 9, 10, 8, 9) for i in range(n)]
        funding = [0.02] * n
        funding[80] = 0.001                             # low percentile but > 0
        gen = make_funding_fade_long(funding)
        out = gen(cs, {"funding_pct": 0.2, "funding_window": 50})
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()

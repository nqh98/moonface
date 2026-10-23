import unittest

from moonface.core.models import Candle
from moonface.models.engine.honesty import COST_FRACTION
from moonface.models.matrix.governor import GovernorParams
from moonface.research.matrix.primaries import MatrixTrade
from moonface.research.matrix import evaluate as ev


def _mt(ex_ts, gross, af=0.01, ei=0):
    return MatrixTrade(primary="funding_fade", entry_index=ei, exit_index=ei + 1,
                       entry_ts_ms=ex_ts - 1, exit_ts_ms=ex_ts, direction=1,
                       gross_r=gross, atr_frac=af, mae_r=0.0, state_tag="s")


def _flat_candles(n):
    return [Candle(1000 * i, 100.0, 100.0, 100.0, 100.0, 1.0) for i in range(n)]


class TestGovernedMetrics(unittest.TestCase):
    def test_cost_scaling_identity(self):
        panel = [_mt(1000, gross=2.0)]
        p = GovernorParams(target_vol=0.01, size_min=0.5, size_max=0.5,
                           dd_budget=100.0)
        pairs = ev.govern(panel, _flat_candles(50), p, vol_lookback=20)
        self.assertEqual(len(pairs), 1)
        trade, af_eff = pairs[0]
        expected_net = 0.5 * (2.0 - COST_FRACTION / 0.01)
        self.assertAlmostEqual(trade.net_r, expected_net, places=6)
        self.assertAlmostEqual(af_eff, 0.01 / 0.5, places=6)

    def test_zero_size_trades_retained_as_flat(self):
        # Slice-1b: throttled/zero-size trades are RETAINED (net_r=0, af=0) so the
        # sample cannot self-collapse; cost_stress adds nothing when af<=0.
        panel = [_mt(1000 + i, gross=-1.0) for i in range(40)]
        p = GovernorParams(target_vol=0.01, size_min=0.0, size_max=1.0,
                           dd_budget=2.0)
        pairs = ev.govern(panel, _flat_candles(60), p, vol_lookback=20)
        self.assertEqual(len(pairs), 40)               # n preserved
        self.assertTrue(all(t.net_r == 0.0 for t, _ in pairs))
        self.assertTrue(all(af == 0.0 for _, af in pairs))
        m = ev.governed_metrics(pairs)
        self.assertEqual(m["n"], 40)
        self.assertEqual(m["net_r"], 0.0)
        self.assertEqual(m["cost_stress"]["net_r_3x"], 0.0)  # af<=0 -> no cost


if __name__ == "__main__":
    unittest.main()

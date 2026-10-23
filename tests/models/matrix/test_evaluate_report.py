import unittest

from moonface.core.models import Candle
from moonface.models.matrix.governor import GovernorParams
from moonface.research.matrix.primaries import MatrixTrade
from moonface.research.matrix import evaluate as ev


def _flat(n):
    return [Candle(1000 * i, 100.0, 100.0, 100.0, 100.0, 1.0) for i in range(n)]


def _panel_win(n, start_ts, step, ei0):
    return [MatrixTrade("funding_fade", ei0 + i, ei0 + i + 1,
                        start_ts + i * step - 1, start_ts + i * step, 1,
                        gross_r=1.0, atr_frac=0.05, mae_r=0.0, state_tag="s")
            for i in range(n)]


class TestFitAndGates(unittest.TestCase):
    def test_fit_respects_dd_cap(self):
        candles = _flat(300)
        panel = _panel_win(250, ev.TRAIN_END_TS_MS - 250 * 10, 10, 0)
        p = ev.fit_governor(panel, candles, baseline_dd=-5.0, vol_lookback=20)
        self.assertIsInstance(p, GovernorParams)
        self.assertEqual(p.dd_budget, 5.0)

    def test_recalibrated_floor_not_tripped_below_200(self):
        # Slice-1b: floor is 40 (non-overlapping), so a 45-trade val panel is not
        # failed on n (the old PANEL_FLOOR=200 was structurally unreachable here).
        self.assertEqual(ev.MIN_VAL_TRADES, 40)
        candles = _flat(120)
        panel = _panel_win(45, ev.TRAIN_END_TS_MS + ev.PURGE_MS + 5, 10, 0)
        p = GovernorParams(0.01, 0.5, 0.5, 100.0)  # size_min forces nonzero on flat vol
        g1 = ev.gate1_validation(ev.govern(panel, candles, p, 20), baseline_val_dd=-999.0)
        self.assertEqual(g1["n"], 45)
        self.assertGreaterEqual(g1["n"], ev.MIN_VAL_TRADES)

    def test_gate1_shape(self):
        candles = _flat(300)
        panel = _panel_win(250, ev.TRAIN_END_TS_MS + ev.PURGE_MS + 5, 10, 0)
        p = GovernorParams(0.01, 0.5, 0.5, 100.0)
        pairs = ev.govern(panel, candles, p, 20)
        g1 = ev.gate1_validation(pairs, baseline_val_dd=-999.0)
        self.assertIn("passed", g1)
        self.assertIn("net_r_3x", g1)
        self.assertIn("ci", g1)


if __name__ == "__main__":
    unittest.main()

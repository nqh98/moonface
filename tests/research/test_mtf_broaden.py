import unittest

from moonface.core.models import Candle
from moonface.research.mtf.grid import (BIAS_FNS, BROADEN_BEST_LABEL,
                                        HEADLINE_LABEL, bias_trend_strength,
                                        broaden_best_cell, broadened_cells)


def _c(close: float, i: int = 0) -> Candle:
    return Candle(timestamp_ms=i * 900_000, open=close, high=close,
                  low=close, close=close, volume=1.0)


class TrendStrengthBiasTest(unittest.TestCase):
    def test_chop_is_flat_strong_trend_is_directional(self):
        # n=5, k=1.0. A flat-ish series (tiny deviations) -> 0 (no trade);
        # a strong breakout above the mean by > 1 sigma -> +1.
        flat = [_c(100.0 + (j % 2) * 0.01, j) for j in range(6)]
        out = bias_trend_strength(flat, {"n": 5, "k": 1.0})
        self.assertEqual(out[-1], 0)  # price hugs its mean -> chop -> no trade

        rising = [_c(c, j) for j, c in enumerate([100, 100, 100, 100, 100, 130])]
        out = bias_trend_strength(rising, {"n": 5, "k": 1.0})
        self.assertEqual(out[-1], 1)  # close far above mean -> strong uptrend

    def test_warmup_is_zero(self):
        s = [_c(100.0, j) for j in range(4)]
        out = bias_trend_strength(s, {"n": 5, "k": 1.0})
        self.assertTrue(all(v == 0 for v in out))

    def test_registered_in_bias_fns(self):
        self.assertIs(BIAS_FNS["trend_strength"], bias_trend_strength)


class BroadenedGridTest(unittest.TestCase):
    def test_shape_and_unique_labels(self):
        cells = broadened_cells()
        self.assertEqual(len(cells), 72)            # 2 HTF x 3 bias x 3 trig x 4
        self.assertEqual(len({c.label for c in cells}), 72)  # all labels unique

    def test_holds_present_and_h_matches(self):
        for c in broadened_cells():
            hold = int(c.label.rsplit("@", 1)[1].rstrip("d"))
            self.assertIn(hold, (1, 2))
            self.assertEqual(c.h, hold * 96)        # h in 15m bars

    def test_includes_frozen_headline_as_control(self):
        labels = {c.label for c in broadened_cells()}
        self.assertIn(f"{HEADLINE_LABEL}@2d", labels)

    def test_uses_all_three_biases(self):
        biases = {c.bias_fn for c in broadened_cells()}
        self.assertEqual(biases, {"price_vs_sma", "roc", "trend_strength"})

    def test_broaden_best_cell_is_frozen_spec(self):
        cell = broaden_best_cell()
        self.assertEqual(cell.label, BROADEN_BEST_LABEL)
        self.assertEqual(cell.htf, "4h")
        self.assertEqual(cell.bias_fn, "trend_strength")
        self.assertEqual(cell.trigger_fn, "rsi_reversion")
        self.assertEqual(cell.exit_name, "horizon_hold")
        self.assertEqual(cell.h, 2 * 96)              # 2-day hold in 15m bars
        self.assertIn(cell.label, {c.label for c in broadened_cells()})


if __name__ == "__main__":
    unittest.main()

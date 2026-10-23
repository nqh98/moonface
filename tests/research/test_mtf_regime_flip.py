import unittest

from moonface.core.metrics import COST_FRACTION
from moonface.core.models import Candle
from moonface.core.risk import risk_unit
from moonface.research.mtf.grid import (BROADEN_BEST_LABEL, REGIME_FLIP_LABEL,
                                        broaden_best_cell, broadened_cells,
                                        regime_flip_cell)
from moonface.research.mtf.regime_exit import regime_flip_r


def _c(close: float, i: int, rng: float = 1.0) -> Candle:
    return Candle(timestamp_ms=i * 900_000, open=close, high=close + rng,
                  low=close - rng, close=close, volume=1.0)


def _expected_net(candles, i, exit_idx, side, atr_period) -> float:
    """The exact net-R the resolver should produce, via the shared R math."""
    unit = risk_unit(candles, i, 1.0, atr_period)
    sign = 1.0 if side == "LONG" else -1.0
    gross = sign * (candles[exit_idx].close - candles[i].close) / unit
    return round(gross - COST_FRACTION / (unit / candles[i].close), 4)


class RegimeFlipCellTest(unittest.TestCase):
    def test_is_broaden_best_gate_with_only_the_exit_swapped(self):
        c, bb = regime_flip_cell(), broaden_best_cell()
        self.assertEqual(c.label, REGIME_FLIP_LABEL)
        self.assertEqual(c.exit_name, "regime_flip")
        self.assertEqual(c.exit_params, {"max_bars": 2 * 96, "atr_period": 14})
        # entry side is provably identical: same gate + trigger, only exit differs
        self.assertEqual(
            (c.htf, c.bias_fn, c.bias_params, c.trigger_fn, c.trigger_params, c.h),
            (bb.htf, bb.bias_fn, bb.bias_params, bb.trigger_fn, bb.trigger_params,
             bb.h))
        self.assertNotEqual(c.exit_name, bb.exit_name)

    def test_not_a_member_of_the_frozen_broadened_grid(self):
        # parallel sibling, carries no DSR deflation against the 72-cell grid
        self.assertNotIn(REGIME_FLIP_LABEL, {x.label for x in broadened_cells()})
        self.assertEqual(len(broadened_cells()), 72)
        self.assertEqual(BROADEN_BEST_LABEL,
                         "4h:trend_strength|rsi_reversion|horizon_hold@2d")


class RegimeFlipExitTest(unittest.TestCase):
    def test_exits_at_first_bar_the_bias_stops_supporting_the_trade(self):
        # steadily rising price; bias supports LONG (+1) until it decays to chop
        # (0) at bar 8. The exit must fire at bar 8, marked to bar 8's close.
        candles = [_c(100.0 + j, j) for j in range(20)]
        bias = [1] * 20
        bias[8] = 0  # regime decays into chop
        p = {"max_bars": 15, "atr_period": 3}
        res = regime_flip_r(candles, 4, "LONG", p, bias)
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res[0], _expected_net(candles, 4, 8, "LONG", 3),
                               places=4)

    def test_short_exits_on_bias_sign_flip(self):
        candles = [_c(100.0 - j, j) for j in range(20)]  # falling: SHORT profits
        bias = [-1] * 20
        bias[7] = 1  # regime flips to the opposite (uptrend)
        p = {"max_bars": 15, "atr_period": 3}
        res = regime_flip_r(candles, 3, "SHORT", p, bias)
        self.assertIsNotNone(res)
        # SHORT held from bar 3 to bar 7 in a falling market -> positive gross
        self.assertGreater(res[0], 0.0)

    def test_backstop_caps_the_hold_when_bias_never_flips(self):
        candles = [_c(100.0 + j, j) for j in range(30)]
        bias = [1] * 30                       # regime supports the trade forever
        p = {"max_bars": 5, "atr_period": 3}  # so max_bars is the binding exit
        res = regime_flip_r(candles, 4, "LONG", p, bias)
        self.assertIsNotNone(res)
        # exit forced at the backstop bar 4+5=9
        self.assertAlmostEqual(res[0], _expected_net(candles, 4, 9, "LONG", 3),
                               places=4)

    def test_untradeable_entry_returns_none(self):
        candles = [_c(100.0, j, rng=0.0) for j in range(3)]  # ATR 0 -> no risk unit
        res = regime_flip_r(candles, 1, "LONG", {"max_bars": 2, "atr_period": 3},
                            [1, 1, 1])
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()

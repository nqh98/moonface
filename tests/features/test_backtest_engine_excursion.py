from __future__ import annotations

import unittest

from moonface.features.simulate import simulate_market_entry, simulate_trade
from moonface.core.models import ActionPlan, Candle


def candle(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(1780275600000 + index * 3_600_000, open_, high, low, close, 1.0)


def long_plan() -> ActionPlan:
    return ActionPlan("BUY", "LONG", entry=100.0, stop_loss=95.0,
                      take_profit_1=105.0, take_profit_2=110.0,
                      risk_percentage=1.0, source_timeframe="H1")


class ExcursionTest(unittest.TestCase):
    def test_records_mfe_mae_and_bars(self) -> None:
        # fills bar 0 (low 100), runs to 104 favorable (+0.8R) then back, stops bar 2
        future = [
            candle(0, 100, 103, 100, 102),  # fav 0.6R, adv 0.0R
            candle(1, 102, 104, 101, 103),  # fav 0.8R, adv 0.0R (peak)
            candle(2, 103, 103, 94, 96),    # hits stop 95
        ]
        trade = simulate_trade(long_plan(), future, fee_rate=0.0, slippage=0.0)
        assert trade is not None
        self.assertEqual(trade.outcome, "SL")
        self.assertAlmostEqual(trade.mfe_r, 0.8, places=2)
        self.assertAlmostEqual(trade.mae_r, 1.2, places=2)
        self.assertEqual(trade.bars_to_fill, 0)
        self.assertEqual(trade.bars_to_resolve, 2)

    def test_no_fill_has_zero_path(self) -> None:
        future = [candle(0, 120, 121, 119, 120)]  # never trades through 100
        trade = simulate_trade(long_plan(), future, fee_rate=0.0, slippage=0.0)
        assert trade is not None
        self.assertEqual(trade.outcome, "NO_FILL")
        self.assertEqual(trade.mfe_r, 0.0)
        self.assertEqual(trade.mae_r, 0.0)

    def test_market_entry_fills_at_first_open(self) -> None:
        # market enter at first bar open (100), reaches tp2 110
        future = [candle(0, 100, 111, 100, 110)]
        trade = simulate_market_entry(long_plan(), future, fee_rate=0.0, slippage=0.0)
        assert trade is not None
        self.assertEqual(trade.outcome, "TP2")
        self.assertAlmostEqual(trade.r_multiple, 2.0, places=2)

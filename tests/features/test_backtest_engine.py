from __future__ import annotations

import unittest

from moonface.features.simulate import simulate_trade
from moonface.core.models import ActionPlan, Candle


def candle(index: int, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(1780275600000 + index * 3_600_000, open_, high, low, close, 1.0)


def long_plan() -> ActionPlan:
    return ActionPlan("BUY", "LONG", entry=100.0, stop_loss=95.0,
                      take_profit_1=105.0, take_profit_2=110.0,
                      risk_percentage=1.0, source_timeframe="H1")


class SimulateTradeTest(unittest.TestCase):
    def test_long_take_profit_2_hit(self) -> None:
        future = [candle(0, 100, 111, 100, 110)]  # reaches 110 (tp2)
        trade = simulate_trade(long_plan(), future, fee_rate=0.0, slippage=0.0)
        assert trade is not None
        self.assertEqual(trade.outcome, "TP2")
        self.assertAlmostEqual(trade.r_multiple, 2.0, places=2)

    def test_long_stop_loss_hit(self) -> None:
        future = [candle(0, 100, 101, 94, 96)]  # drops to 94 (below sl 95)
        trade = simulate_trade(long_plan(), future, fee_rate=0.0, slippage=0.0)
        assert trade is not None
        self.assertEqual(trade.outcome, "SL")
        self.assertAlmostEqual(trade.r_multiple, -1.0, places=2)

    def test_ambiguous_bar_assumes_stop_first(self) -> None:
        future = [candle(0, 100, 111, 94, 100)]  # both tp2 and sl touched
        trade = simulate_trade(long_plan(), future, fee_rate=0.0, slippage=0.0)
        assert trade is not None
        self.assertEqual(trade.outcome, "SL")

    def test_fees_reduce_r_multiple(self) -> None:
        future = [candle(0, 100, 111, 100, 110)]
        clean = simulate_trade(long_plan(), future, fee_rate=0.0, slippage=0.0)
        with_fees = simulate_trade(long_plan(), future, fee_rate=0.001, slippage=0.0)
        assert clean is not None and with_fees is not None
        self.assertLess(with_fees.r_multiple, clean.r_multiple)

from __future__ import annotations

import unittest

from moonface.features.simulate import Trade
from moonface.research.metrics_extra import summarize


def trade(r: float) -> Trade:
    return Trade(
        side="BUY",
        entry=100.0,
        stop_loss=95.0,
        take_profit_1=105.0,
        take_profit_2=110.0,
        rr1=1.0,
        rr2=2.0,
        outcome="TP2" if r > 0 else "SL",
        r_multiple=r,
    )


class MetricsTest(unittest.TestCase):
    def test_summary_of_known_trades(self) -> None:
        trades = [trade(2.0), trade(-1.0), trade(2.0), trade(-1.0)]
        summary = summarize(trades)
        self.assertEqual(summary.trade_count, 4)
        self.assertAlmostEqual(summary.win_rate, 0.5)
        self.assertAlmostEqual(summary.expectancy_r, 0.5)
        self.assertAlmostEqual(summary.profit_factor, 2.0)
        self.assertLessEqual(summary.max_drawdown_r, 0.0)

    def test_empty_trades(self) -> None:
        summary = summarize([])
        self.assertEqual(summary.trade_count, 0)
        self.assertEqual(summary.expectancy_r, 0.0)

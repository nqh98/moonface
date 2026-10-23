# tests/test_edge_exit_score.py
from __future__ import annotations

import unittest

from moonface.research.edge.exit_score import (
    exit_gate,
    run_exit_battery,
    score_exit,
)
from moonface.core.metrics import Summary
from moonface.core.models import Candle

_HOUR = 3_600_000


def _summary(expectancy_r: float, trade_count: int, max_drawdown_r: float) -> Summary:
    return Summary(trade_count=trade_count, win_rate=0.5, expectancy_r=expectancy_r,
                   profit_factor=1.5, max_drawdown_r=max_drawdown_r,
                   total_r=expectancy_r * trade_count)


class ExitGateTest(unittest.TestCase):
    def test_passes_when_all_conditions_hold(self) -> None:
        research = _summary(0.2, 50, -5.0)
        tail = _summary(0.1, 40, -3.0)
        self.assertTrue(exit_gate(research, tail))

    def test_fails_on_negative_research(self) -> None:
        self.assertFalse(exit_gate(_summary(-0.1, 50, -5.0), _summary(0.1, 40, -3.0)))

    def test_fails_on_negative_oos(self) -> None:
        self.assertFalse(exit_gate(_summary(0.2, 50, -5.0), _summary(-0.1, 40, -3.0)))

    def test_fails_on_too_few_oos_trades(self) -> None:
        self.assertFalse(exit_gate(_summary(0.2, 50, -5.0), _summary(0.1, 20, -3.0)))

    def test_fails_on_excess_research_drawdown(self) -> None:
        self.assertFalse(exit_gate(_summary(0.2, 50, -20.0), _summary(0.1, 40, -3.0)))


class ScoreExitTest(unittest.TestCase):
    def test_splits_entries_at_tail_start(self) -> None:
        h1: list[Candle] = []  # the stub exit ignores h1
        entries = [(10, "LONG"), (20, "LONG"), (200, "LONG"), (210, "LONG")]
        row = score_exit(h1, "e", {"p": 1}, entries, "x",
                         lambda i, side, h, params: 1.0, {}, tail_start=100)
        self.assertEqual(row.research_trades, 2)
        self.assertEqual(row.oos_trades, 2)
        self.assertEqual(row.oos_expectancy_r, 1.0)

    def test_drops_none_results(self) -> None:
        entries = [(10, "LONG"), (20, "LONG")]
        row = score_exit([], "e", {}, entries, "x",
                         lambda i, side, h, params: None, {}, tail_start=100)
        self.assertEqual(row.research_trades, 0)


class RunExitBatteryTest(unittest.TestCase):
    def test_sorts_rows_by_oos_expectancy_desc(self) -> None:
        h1 = [Candle(i * _HOUR, 100, 100, 100, 100, 1.0) for i in range(300)]
        entry_specs = [("entryA", lambda h, p: [(50, "LONG"), (250, "LONG")], {})]
        registry = {
            "exitA": (lambda i, side, h, params: 0.5, [{}]),
            "exitB": (lambda i, side, h, params: 0.2, [{}]),
        }
        rows = run_exit_battery(h1, entry_specs, registry, oos_tail_bars=100,
                                warmup=60, future_bars=48)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].exit, "exitA")
        self.assertGreaterEqual(rows[0].oos_expectancy_r, rows[1].oos_expectancy_r)


class EntrySpecsByTfTest(unittest.TestCase):
    def test_h1_entry_set_intact(self) -> None:
        from moonface.research.edge.exit_score import ENTRY_SPECS_BY_TF
        names = [name for name, _gen, _params in ENTRY_SPECS_BY_TF["1h"]]
        self.assertEqual(names, ["atr_channel_break", "ma_cross", "donchian_break"])

    def test_has_h4_key(self) -> None:
        from moonface.research.edge.exit_score import ENTRY_SPECS_BY_TF
        self.assertIn("4h", ENTRY_SPECS_BY_TF)


class ExitRStreamsTest(unittest.TestCase):
    def _candles(self) -> list:
        from moonface.core.models import Candle
        # 5 bars, timestamps 0,1,2,3,4 days; OHLC irrelevant (exit is stubbed)
        day = 86_400_000
        return [Candle(timestamp_ms=i * day, open=1.0, high=1.0, low=1.0,
                       close=1.0, volume=0.0) for i in range(5)]

    def test_splits_and_drops_none(self) -> None:
        from moonface.research.edge.exit_score import exit_r_streams
        candles = self._candles()
        entries = [(0, "LONG"), (1, "LONG"), (3, "LONG"), (4, "LONG")]
        # stub exit: r = entry index, but bar 1 returns None (dropped)
        def stub(i, side, h1, params):
            return None if i == 1 else float(i)
        research, tail = exit_r_streams(candles, entries, stub, {}, tail_start=3)
        # research = i < 3 (bar 0 kept, bar 1 dropped); tail = i >= 3
        self.assertEqual(research, [(0, 0.0)])
        self.assertEqual(tail, [(3 * 86_400_000, 3.0), (4 * 86_400_000, 4.0)])
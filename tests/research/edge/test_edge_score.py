from __future__ import annotations

import unittest

from moonface.research.edge.score import ProbeRow, run_probe_battery, score_signal
from moonface.core.models import Candle


def series(closes: list[float]) -> list[Candle]:
    return [Candle(1780275600000 + i * 3_600_000, c, c + 1, c - 1, c, 1.0)
            for i, c in enumerate(closes)]


def always_long(h1, params):
    # Emit a LONG every 3rd bar (never on the last) so we get a sizable sample.
    return [(i, "LONG") for i in range(60, len(h1) - 1) if i % 3 == 0]


class ScoreSignalTest(unittest.TestCase):
    def test_partitions_and_scores_both_evaluators(self) -> None:
        h1 = series([float(100 + (i % 5)) for i in range(600)])
        row = score_signal(
            h1, "always_long", always_long, {}, k=1.0, m=2.0, n_bars=12,
            atr_period=14, fee_rate=0.0, slippage=0.0,
            oos_tail_bars=120, warmup=60, future_bars=12,
            min_trades=30, max_drawdown_r=15.0,
        )
        self.assertIsInstance(row, ProbeRow)
        self.assertEqual(row.signal, "always_long")
        self.assertGreater(row.bracket_trades, 0)
        self.assertGreater(row.horizon_trades, 0)
        self.assertIsInstance(row.bracket_valid, bool)

    def test_battery_sorted_by_bracket_expectancy_desc(self) -> None:
        h1 = series([float(100 + (i % 5)) for i in range(600)])
        registry = {"a": (always_long, [{}]), "b": (always_long, [{}])}
        rows = run_probe_battery(
            h1, registry, k=1.0, m=2.0, n_bars=12, atr_period=14,
            fee_rate=0.0, slippage=0.0, oos_tail_bars=120, warmup=60,
            future_bars=12, min_trades=30, max_drawdown_r=15.0,
        )
        exps = [r.bracket_expectancy_r for r in rows]
        self.assertEqual(exps, sorted(exps, reverse=True))


class OosHorizonTest(unittest.TestCase):
    def test_oos_horizon_fields_populate(self) -> None:
        h1 = series([float(100 + (i % 5)) for i in range(600)])
        row = score_signal(
            h1, "always_long", always_long, {}, k=1.0, m=2.0, n_bars=12,
            atr_period=14, fee_rate=0.0, slippage=0.0,
            oos_tail_bars=120, warmup=60, future_bars=12,
        )
        # Tail entries exist (always_long fires through the end), so OOS horizon
        # has trades and a finite expectancy.
        self.assertGreater(row.horizon_oos_trades, 0)
        self.assertIsInstance(row.horizon_oos_expectancy_r, float)

    def test_oos_horizon_zero_when_no_tail_entries(self) -> None:
        h1 = series([float(100 + (i % 5)) for i in range(600)])
        # Entries only in the research fold (well before the 120-bar tail).
        def early_long(h1, params):
            return [(i, "LONG") for i in range(60, 120) if i % 3 == 0]
        row = score_signal(
            h1, "early_long", early_long, {}, k=1.0, m=2.0, n_bars=12,
            atr_period=14, fee_rate=0.0, slippage=0.0,
            oos_tail_bars=120, warmup=60, future_bars=12,
        )
        self.assertEqual(row.horizon_oos_trades, 0)
        self.assertEqual(row.horizon_oos_expectancy_r, 0.0)

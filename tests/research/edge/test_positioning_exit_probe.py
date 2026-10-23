from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.research.edge.exit_score import ExitRow, run_exit_battery
from moonface.core.exits import EXIT_REGISTRY
from moonface.core.models import Candle


def _candles(n: int) -> list[Candle]:
    h4 = 14_400_000
    return [Candle(timestamp_ms=i * h4, open=1.0, high=1.05, low=0.95,
                   close=1.0, volume=1.0) for i in range(n)]


class BuildEntrySpecsTest(unittest.TestCase):
    def test_three_frozen_specs(self) -> None:
        from tools.lanes.positioning_exit_probe import build_entry_specs
        specs = build_entry_specs([0.0] * 10, [0.0] * 10)
        names = [(name, params) for name, _gen, params in specs]
        self.assertEqual(names, [
            ("basis_discount", {"window": 60, "pct": 5}),
            ("basis_discount", {"window": 180, "pct": 5}),
            ("funding_fade", {"window": 60, "z_thr": 1.5}),
        ])
        for _name, gen, _params in specs:
            self.assertTrue(callable(gen))

    def test_basis_closure_emits_long_on_deep_discount(self) -> None:
        # basis path: warmup then a deep relative discount at the last bar.
        # The frozen specs use window=60 -> too short here; call the same
        # factory directly to confirm wiring with a small window.
        basis = [0.10, 0.12, 0.11, 0.08]
        from moonface.research.edge.basis_signals import make_basis_discount_reversion
        gen = make_basis_discount_reversion(basis)
        self.assertEqual(gen(_candles(4), {"window": 4, "pct": 10}), [(3, "LONG")])


def _row(entry: str, entry_params: dict, exit_name: str, valid: bool) -> ExitRow:
    return ExitRow(
        entry=entry, entry_params=entry_params, exit=exit_name,
        exit_params={"atr_period": 14}, research_trades=40, research_net_r=1.0,
        research_expectancy_r=0.1, research_max_dd_r=-5.0, oos_trades=35,
        oos_net_r=1.0, oos_expectancy_r=0.1, valid=valid)


class RobustnessVerdictTest(unittest.TestCase):
    def test_survivor_when_style_passes_two_entries(self) -> None:
        from tools.lanes.positioning_exit_probe import robustness_verdict
        rows = [
            _row("basis_discount", {"window": 60, "pct": 5}, "atr_trail", True),
            _row("basis_discount", {"window": 180, "pct": 5}, "atr_trail", True),
            _row("funding_fade", {"window": 60, "z_thr": 1.5}, "fixed_bracket", True),
        ]
        outcome, survivors, _passing = robustness_verdict(rows)
        self.assertEqual(outcome, "B")
        self.assertEqual(survivors, ["atr_trail"])  # fixed_bracket only 1 entry

    def test_outcome_a_when_no_style_reaches_two_entries(self) -> None:
        from tools.lanes.positioning_exit_probe import robustness_verdict
        rows = [
            _row("basis_discount", {"window": 60, "pct": 5}, "atr_trail", True),
            _row("funding_fade", {"window": 60, "z_thr": 1.5}, "fixed_bracket", True),
        ]
        outcome, survivors, _passing = robustness_verdict(rows)
        self.assertEqual(outcome, "A")
        self.assertEqual(survivors, [])

    def test_horizon_hold_never_counts_as_survivor(self) -> None:
        from tools.lanes.positioning_exit_probe import robustness_verdict
        rows = [
            _row("basis_discount", {"window": 60, "pct": 5}, "horizon_hold", True),
            _row("basis_discount", {"window": 180, "pct": 5}, "horizon_hold", True),
        ]
        outcome, survivors, _passing = robustness_verdict(rows)
        self.assertEqual(outcome, "A")
        self.assertEqual(survivors, [])


class WriteReportTest(unittest.TestCase):
    def test_writes_json_and_md_with_verdict(self) -> None:
        from tools.lanes.positioning_exit_probe import build_entry_specs, write_report
        perp = _candles(300)
        basis = [0.0001 if (i // 5) % 2 else -0.0001 for i in range(300)]
        funding = [0.0001 if (i // 7) % 2 else -0.0001 for i in range(300)]
        specs = build_entry_specs(basis, funding)
        rows = run_exit_battery(perp, specs, EXIT_REGISTRY, oos_tail_bars=50,
                                warmup=10, future_bars=10)
        # 3 entries x 10 exit configs.
        self.assertEqual(len(rows), 30)
        with TemporaryDirectory() as d:
            out = write_report(Path(d) / "run", rows, timeframe="4h",
                               spot_symbol="BTC/USDT", perp_symbol="BTC/USDT:USDT")
            self.assertTrue((out / "positioning_exit_probe.json").exists())
            self.assertTrue((out / "positioning_exit_probe.md").exists())
            payload = json.loads((out / "positioning_exit_probe.json").read_text())
            self.assertEqual(len(payload), 30)
            md = (out / "positioning_exit_probe.md").read_text()
            self.assertIn("Positioning-Entry Exit Probe", md)
            self.assertIn("Verdict", md)
            self.assertIn("Outcome", md)

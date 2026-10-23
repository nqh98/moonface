# tests/test_liqprem_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.research.universe_data import DailyRow
from tools.lanes.liqprem import (_funding_day_sums, _kill_branch, _render_report,
                           cmd_register, run_pipeline)

DAY = 86_400_000


class TestRegister(unittest.TestCase):
    def test_writes_frozen_window_and_fence(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "liqprem"
            cmd_register(out, now_ms=1_000 * DAY)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["end_ms"], 1_000 * DAY)
            self.assertEqual(reg["start_ms"],
                             1_000 * DAY - int(3.0 * 365 * DAY))
            self.assertLess(reg["start_ms"], reg["fence_ts"])
            self.assertLess(reg["fence_ts"], reg["end_ms"])

    def test_frozen_punitive_costs_and_universe_floor(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "liqprem"
            cmd_register(out, now_ms=1_000 * DAY)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["fee_illiquid"], 0.0025)
            self.assertEqual(reg["fee_liquid"], 0.0005)
            self.assertEqual(reg["min_median_dollar_vol"], 1_000_000.0)
            self.assertEqual(reg["min_history_days"], 365)
            self.assertEqual(reg["quintile"], 5)
            self.assertEqual(reg["rebalance_days"], 7)
            self.assertEqual(reg["n_trials"], 1)
            self.assertEqual(len(reg["constructions"]), 1)

    def test_second_register_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "liqprem"
            cmd_register(out, now_ms=1_000 * DAY)
            with self.assertRaises(SystemExit):
                cmd_register(out, now_ms=2_000 * DAY)


def _cfg(days=400):
    return {
        "start_ms": 0, "end_ms": days * DAY,
        "fence_ts": int(days * DAY * 0.8),
        "quintile": 5, "amihud_days": 30, "lookback_days": 60,
        "rebalance_days": 7, "fee_illiquid": 0.0025, "fee_liquid": 0.0005,
        "min_history_days": 0, "vol_days": 30,
        "min_median_dollar_vol": 1_000_000.0, "n_trials": 1,
        "constructions": [{"name": "liqprem_1", "amihud_days": 30}],
    }


def _loaders(n=400):
    vols = {"A": 1_100_000.0, "B": 3_000_000.0, "C": 8_000_000.0,
            "D": 20_000_000.0, "E": 60_000_000.0}
    daily = {}
    for sym, qv in vols.items():
        closes, px = [], 100.0
        for i in range(n):
            px *= 1.0 + 0.01 * ((i % 5) - 2)
            closes.append(DailyRow(i * DAY, px, qv))
        daily[sym] = closes

    def fetch_daily(symbol, start_ms, end_ms):
        return [r for r in daily[symbol] if start_ms <= r.ts_ms < end_ms]

    def fetch_funding(symbol, start_ms, end_ms):
        return []

    return sorted(daily), fetch_daily, fetch_funding


class TestKillBranch(unittest.TestCase):
    def test_no_gross_premium_is_the_no_premium_branch(self):
        self.assertEqual(
            _kill_branch({"gross_z": -0.4, "net_z": -1.2}), "no_premium")

    def test_gross_but_not_net_is_the_unharvestable_branch(self):
        self.assertEqual(
            _kill_branch({"gross_z": 2.5, "net_z": -0.8}), "unharvestable")

    def test_passing_pre_screen_has_no_kill_branch(self):
        self.assertIsNone(_kill_branch({"gross_z": 2.5, "net_z": 1.4}))


class TestFundingDaySums(unittest.TestCase):
    def test_intraday_rates_sum_into_their_utc_day(self):
        pts = [(DAY, 0.001), (DAY + 3_600_000, 0.002), (2 * DAY, 0.005)]
        self.assertEqual(_funding_day_sums(pts),
                         {DAY: 0.003, 2 * DAY: 0.005})


class TestRunPipeline(unittest.TestCase):
    def test_writes_verdict_and_report_and_is_one_touch(self):
        symbols, fd, ff = _loaders()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "liqprem"
            v = run_pipeline(_cfg(), symbols, fd, ff, out)
            self.assertIn(v["status"],
                          ("closed_positive", "closed_negative"))
            self.assertTrue((out / "verdict.json").exists())
            self.assertTrue((out / "report.md").exists())
            with self.assertRaises(SystemExit):
                run_pipeline(_cfg(), symbols, fd, ff, out)

    def test_cost_dead_construction_skips_the_ladder(self):
        symbols, fd, ff = _loaders()
        cfg = _cfg()
        cfg["fee_illiquid"] = 1.0  # 100% per side: nothing survives
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "liqprem"
            v = run_pipeline(cfg, symbols, fd, ff, out)
            row = v["constructions"][0]
            self.assertFalse(row["cost_first_pass"])
            self.assertIsNotNone(row["kill_branch"])
            self.assertNotIn("stage1_pass", row)
            self.assertEqual(v["status"], "closed_negative")


class TestReport(unittest.TestCase):
    def _verdict(self, **over):
        row = {"name": "liqprem_1", "gross_mean": 0.0001, "gross_z": 2.1,
               "net_mean": -0.00005, "net_z": -0.9,
               "cost_first_pass": False, "kill_branch": "unharvestable",
               "dsr": None}
        row.update(over)
        return {"status": "closed_negative", "generated_utc": "2026-07-28",
                "universe_symbols": 300, "viability_members": 120,
                "funding_symbols": 120, "constructions": [row]}

    def test_names_the_kill_branch_in_the_decision_section(self):
        md = _render_report(_cfg(), self._verdict())
        self.assertIn("unharvestable", md)
        self.assertIn("real but unharvestable", md)

    def test_cost_dead_row_reports_the_ladder_as_skipped(self):
        md = _render_report(_cfg(), self._verdict())
        self.assertIn("cost-dead, ladder skipped", md)

    def test_no_premium_branch_is_spelled_out(self):
        md = _render_report(_cfg(), self._verdict(
            gross_z=-0.3, kill_branch="no_premium"))
        self.assertIn("no liquidity premium exists", md)


if __name__ == "__main__":
    unittest.main()

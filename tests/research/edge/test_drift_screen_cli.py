# tests/test_drift_screen_cli.py
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.lanes.drift_screen import (cmd_phase_a, cmd_register, cmd_run,
                                 resolve_signal, DESIGN, load_edge_rows,
                                 load_positioning_rows, compute_floor_from_rows)

H4 = 4 * 3_600_000


class TestPhaseAFloor(unittest.TestCase):
    def test_floor_is_max_ratio_among_dead_rows(self):
        # each row: forward drift R and the adverse drawdown R it lived through.
        # All rows are known-dead (invalid). Floor must exceed every dead ratio
        # so the screen rejects them, i.e. floor = max(dead ratios) (exclusive
        # bar applied at >= in the gate, so we record max + a tiny epsilon).
        dead = [
            {"drift_r": 1.63, "dd_r": 114.0},   # funding_fade horizon_hold
            {"drift_r": 1.13, "dd_r": 32.0},    # funding_fade fixed_bracket
            {"drift_r": 0.60, "dd_r": 60.0},
        ]
        floor = compute_floor_from_rows(dead)
        # ratios: 0.0143, 0.0353, 0.0100 -> max 0.0353
        self.assertAlmostEqual(floor, 0.0353, places=3)

    def test_empty_rows_floor_is_one(self):
        # with no evidence, fall back to the conservative a-priori bar 1.0
        self.assertEqual(compute_floor_from_rows([]), 1.0)


class TestPhaseAReport(unittest.TestCase):
    def test_positioning_rows_extract_drift_and_dd(self):
        payload = {"rows": [
            {"oos_expectancy_r": 1.63, "research_max_dd_r": -114.0},
            {"oos_expectancy_r": -0.2, "research_max_dd_r": -50.0},
        ]}
        rows = load_positioning_rows(payload)
        # only positive-drift rows are dead-but-drifting evidence
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["drift_r"], 1.63)
        self.assertAlmostEqual(rows[0]["dd_r"], 114.0)

    def test_edge_rows_extract_horizon_drift(self):
        payload = {"rows": [
            {"horizon_oos_expectancy_r": 1.27, "bracket_net_r": -9.6},
            {"horizon_oos_expectancy_r": -0.1, "bracket_net_r": -1.0},
        ]}
        rows = load_edge_rows(payload)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["drift_r"], 1.27)
        # pins the spec-correct proxy: |bracket_net_r| (9.6), NOT bracket_expectancy
        self.assertAlmostEqual(rows[0]["dd_r"], 9.6)

    def test_loaders_accept_bare_list_too(self):
        # the REAL result files are flat lists, not {"rows": [...]} dicts
        bare = [{"oos_expectancy_r": 1.0, "research_max_dd_r": -10.0}]
        self.assertEqual(len(load_positioning_rows(bare)), 1)
        bare_edge = [{"horizon_oos_expectancy_r": 0.5, "bracket_net_r": -5.0}]
        self.assertEqual(len(load_edge_rows(bare_edge)), 1)

    def test_cmd_phase_a_writes_report_and_floor(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            pos = out / "pos.json"
            edge = out / "edge.json"
            pos.write_text(json.dumps({"rows": [
                {"oos_expectancy_r": 1.63, "research_max_dd_r": -114.0}]}))
            edge.write_text(json.dumps({"rows": [
                {"horizon_oos_expectancy_r": 1.27, "bracket_net_r": -9.6}]}))
            floor = cmd_phase_a(out, positioning=pos, edge=edge)
            self.assertTrue((out / "phaseA_gap.md").exists())
            self.assertGreater(floor, 0.0)
            report = (out / "phaseA_gap.md").read_text()
            self.assertIn("calibrated floor", report.lower())


class TestRegister(unittest.TestCase):
    def test_register_freezes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            cmd_register(out, floor=0.05)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["floor"], 0.05)
            self.assertEqual(reg["h"], DESIGN["h"])
            self.assertNotIn("BTCUSDT", reg["universe"])
            self.assertTrue(len(reg["signals"]) >= 3)
            with self.assertRaises(SystemExit):
                cmd_register(out, floor=0.05)


class TestRun(unittest.TestCase):
    def test_resolve_signal_maps_name_to_generator(self):
        gen = resolve_signal("donchian_break")
        from moonface.research.edge.signals import donchian_break
        self.assertIs(gen, donchian_break)

    def test_run_writes_leaderboard_from_loader(self):
        def _asset():
            flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(40)]
            up = [Candle((40 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                         100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(40)]
            return flat + up

        reg = {"timeframe": "4h", "h": 3, "atr_period": 14,
               "min_events": 1, "min_assets": 8, "floor": 0.05,
               "universe": [f"A{j}" for j in range(9)],
               "signals": [{"name": "donchian_break", "params": {"n": 10}}]}

        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "registration.json").write_text(json.dumps(reg))
            cmd_run(out, loader=lambda sym, tf: _asset())
            board = json.loads((out / "leaderboard.json").read_text())
            self.assertEqual(len(board), 1)
            self.assertEqual(board[0]["signal"], "donchian_break")
            self.assertIn("verdict", board[0])
            self.assertTrue((out / "leaderboard.md").exists())

    def test_run_skips_missing_assets(self):
        reg = {"timeframe": "4h", "h": 3, "atr_period": 14,
               "min_events": 1, "min_assets": 8, "floor": 0.05,
               "universe": ["PRESENT", "MISSING"],
               "signals": [{"name": "donchian_break", "params": {"n": 10}}]}
        present = [Candle(i * H4, 100, 101, 99, 100 + i, 1000.0) for i in range(50)]

        def loader(sym, tf):
            return present if sym == "PRESENT" else None

        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            (out / "registration.json").write_text(json.dumps(reg))
            cmd_run(out, loader=loader)  # must not raise on MISSING
            board = json.loads((out / "leaderboard.json").read_text())
            self.assertEqual(len(board), 1)


class TestEntrypoint(unittest.TestCase):
    def test_help_lists_subcommands(self):
        out = subprocess.run(
            [sys.executable, "tools/lanes/drift_screen.py", "--help"],
            capture_output=True, text=True)
        self.assertIn("phase-a", out.stdout)
        self.assertIn("register", out.stdout)
        self.assertIn("run", out.stdout)

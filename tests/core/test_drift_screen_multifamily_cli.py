import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.core.models import Candle

import importlib.util
import sys

_CLI = Path(__file__).resolve().parents[2] / "tools" / "lanes" / "drift_screen_multifamily.py"
_spec = importlib.util.spec_from_file_location("dsm_cli", _CLI)
dsm = importlib.util.module_from_spec(_spec)
sys.modules["dsm_cli"] = dsm
_spec.loader.exec_module(dsm)

H4 = 4 * 3_600_000


class TestPhaseA(unittest.TestCase):
    def test_floor_at_horizon_from_dead_rows(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            pos = out / "pos.json"
            edge = out / "edge.json"
            pos.write_text(json.dumps(
                [{"oos_expectancy_r": 0.5, "research_max_dd_r": -10.0}]))
            edge.write_text(json.dumps(
                [{"horizon_oos_expectancy_r": 1.0, "bracket_net_r": -8.0}]))
            floor = dsm.cmd_phase_a(out, positioning=pos, edge=edge, h=3)
            # largest ratio among dead rows: max(0.5/10, 1.0/8) = 0.125
            self.assertAlmostEqual(floor, 0.125, places=4)
            self.assertTrue((out / "phaseA_gap_h3.md").exists())


class TestRegisterAndRun(unittest.TestCase):
    def _pool_readers(self):
        n = 60
        flat = [Candle(i * H4, 100, 100.5, 99.5, 100, 1000.0) for i in range(30)]
        up = [Candle((30 + i) * H4, 100 + 2 * i, 100 + 2 * i + 1,
                     100 + 2 * i - 1, 100 + 2 * i, 1000.0) for i in range(30)]
        bars = flat + up
        book = [0.0] * n
        for i in range(28, 58):
            book[i] = 4.0
        return {
            "candles": lambda sym, tf: bars,
            "funding": lambda sym: [0.01] * n,
            "metrics": lambda sym, field: [5.0 + (i % 3) for i in range(n)],
            "bookdepth": lambda sym: book,
        }

    def test_register_then_run_writes_leaderboard(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            dsm.cmd_register(out, floors={"3": 0.1, "6": 0.1319})
            self.assertTrue((out / "registration.json").exists())
            dsm.cmd_run(out, readers=self._pool_readers(),
                        symbols=[f"A{j}" for j in range(9)])
            lb = json.loads((out / "leaderboard.json").read_text())
            self.assertEqual(len(lb), len(dsm.FAMILIES))
            for row in lb:
                self.assertIn("verdict", row)
                self.assertIn("curve", row)            # descriptive curve attached
                self.assertIn(row["verdict"]["verdict"],
                              ("mechanism_exists", "mechanism_does_not_exist",
                               "inconclusive"))

    def test_register_is_frozen(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            dsm.cmd_register(out, floors={"3": 0.1, "6": 0.1319})
            with self.assertRaises(SystemExit):
                dsm.cmd_register(out, floors={"3": 0.2, "6": 0.2})

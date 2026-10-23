# tests/test_xsection_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.research.universe_data import DailyRow
from tools.lanes.xsection import cmd_register, run_pipeline

DAY = 86_400_000


def _daily(closes, qvol=1000.0):
    return [DailyRow(i * DAY, c, qvol) for i, c in enumerate(closes)]


def _cfg(days=200):
    return {
        "start_ms": 0, "end_ms": days * DAY,
        "fence_ts": int(days * DAY * 0.8),
        "top_n": 4, "quintile": 4, "rebalance_days": 7, "fee": 0.0005,
        "min_history_days": 0, "vol_days": 10, "n_trials": 3,
        "constructions": [
            {"name": "mom_7", "kind": "momentum", "days": 7},
            {"name": "mom_30", "kind": "momentum", "days": 30},
            {"name": "carry_7", "kind": "carry", "days": 7},
        ],
    }


def _loaders(trend=True):
    n = 200
    up = [100.0 * 1.01 ** i for i in range(n)]
    down = [100.0 * 0.99 ** i for i in range(n)]
    flat = [100.0] * n
    daily = {"AUSDT": _daily(up), "BUSDT": _daily(down),
             "CUSDT": _daily(flat), "DUSDT": _daily(flat)}
    if not trend:
        daily = {s: _daily(flat) for s in daily}

    def fetch_daily(symbol, start_ms, end_ms):
        return [r for r in daily[symbol] if start_ms <= r.ts_ms < end_ms]

    def fetch_funding(symbol, start_ms, end_ms):
        return []

    return list(daily), fetch_daily, fetch_funding


class TestRegister(unittest.TestCase):
    def test_register_freezes_window_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd_register(Path(tmp), now_ms=1_780_000_000_000)
            reg = json.loads((Path(tmp) / "registration.json").read_text())
            window = reg["end_ms"] - reg["start_ms"]
            self.assertAlmostEqual(
                (reg["end_ms"] - reg["fence_ts"]) / window, 0.2, places=3)
            self.assertEqual(reg["top_n"], 20)
            self.assertEqual([c["name"] for c in reg["constructions"]],
                             ["mom_7", "mom_30", "carry_7"])
            with self.assertRaises(SystemExit):
                cmd_register(Path(tmp), now_ms=1_780_000_000_000)


class TestRunPipeline(unittest.TestCase):
    def test_writes_report_and_verdict_once(self):
        symbols, fd, ff = _loaders()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            verdict = run_pipeline(_cfg(), symbols, fd, ff, out)
            self.assertIn(verdict["status"],
                          ("closed_positive", "closed_negative"))
            self.assertEqual(len(verdict["constructions"]), 3)
            self.assertTrue((out / "report.md").exists())
            self.assertTrue((out / "verdict.json").exists())
            with self.assertRaises(SystemExit):  # one-touch
                run_pipeline(_cfg(), symbols, fd, ff, out)

    def test_flat_market_closes_negative(self):
        symbols, fd, ff = _loaders(trend=False)
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_pipeline(_cfg(), symbols, fd, ff, Path(tmp))
            self.assertEqual(verdict["status"], "closed_negative")

    def test_dsr_only_computed_for_oos_passers(self):
        symbols, fd, ff = _loaders()
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_pipeline(_cfg(), symbols, fd, ff, Path(tmp))
            for c in verdict["constructions"]:
                if not (c["stage1_pass"] and c["stage2_pass"]):
                    self.assertIsNone(c["dsr"])


if __name__ == "__main__":
    unittest.main()

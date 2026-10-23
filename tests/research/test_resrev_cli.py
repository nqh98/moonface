# tests/test_resrev_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.research.universe_data import DailyRow
from tools.lanes.resrev import cmd_register, run_pipeline

DAY = 86_400_000


def _daily(closes, qvol=1000.0):
    return [DailyRow(i * DAY, c, qvol) for i, c in enumerate(closes)]


def _cfg(days=300):
    return {
        "start_ms": 0, "end_ms": days * DAY,
        "fence_ts": int(days * DAY * 0.8),
        "top_n": 4, "decile": 2, "lookback_days": 60, "rebalance_days": 1,
        "fee": 0.0005, "min_history_days": 0, "vol_days": 10, "n_trials": 1,
        "constructions": [{"name": "resrev_1", "lookback_days": 60}],
    }


def _loaders():
    n = 300
    idx_path = [0.01 * ((i % 5) - 2) for i in range(n)]
    daily = {}
    for name, phase in [("A", 0), ("B", 1), ("C", 2), ("D", 3)]:
        closes = [100.0]
        for i in range(1, n):
            idio = 0.02 * (1 if (i % 4) == phase else -0.3)
            closes.append(closes[-1] * (1.0 + idx_path[i] + idio))
        daily[name] = _daily(closes)

    def fetch_daily(symbol, start_ms, end_ms):
        return [r for r in daily[symbol] if start_ms <= r.ts_ms < end_ms]

    def fetch_funding(symbol, start_ms, end_ms):
        return []

    return list(daily), fetch_daily, fetch_funding


class TestRegister(unittest.TestCase):
    def test_register_freezes_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd_register(Path(tmp), now_ms=1_780_000_000_000)
            reg = json.loads((Path(tmp) / "registration.json").read_text())
            window = reg["end_ms"] - reg["start_ms"]
            self.assertAlmostEqual(
                (reg["end_ms"] - reg["fence_ts"]) / window, 0.2, places=3)
            self.assertEqual(reg["decile"], 10)
            self.assertEqual(reg["rebalance_days"], 1)
            self.assertEqual([c["name"] for c in reg["constructions"]],
                             ["resrev_1"])
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
            row = verdict["constructions"][0]
            self.assertIn("cost_first_pass", row)
            self.assertIn("gross_mean", row)
            self.assertTrue((out / "report.md").exists())
            with self.assertRaises(SystemExit):  # one-touch
                run_pipeline(_cfg(), symbols, fd, ff, out)

    def test_cost_dead_skips_ladder(self):
        # huge fee makes the net mean negative -> cost-first fails, no stages
        symbols, fd, ff = _loaders()
        cfg = _cfg()
        cfg["fee"] = 0.5
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_pipeline(cfg, symbols, fd, ff, Path(tmp))
            row = verdict["constructions"][0]
            self.assertFalse(row["cost_first_pass"])
            self.assertIsNone(row["dsr"])
            self.assertNotIn("stage1_pass", row)
            self.assertEqual(verdict["status"], "closed_negative")


if __name__ == "__main__":
    unittest.main()

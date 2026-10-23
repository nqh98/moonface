# tests/test_bab_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.research.universe_data import DailyRow
from tools.lanes.bab import cmd_register, run_pipeline

DAY = 86_400_000


def _daily(closes, qvol=1000.0):
    return [DailyRow(i * DAY, c, qvol) for i, c in enumerate(closes)]


def _cfg(days=300):
    return {
        "start_ms": 0, "end_ms": days * DAY,
        "fence_ts": int(days * DAY * 0.8),
        "top_n": 4, "quintile": 2, "rebalance_days": 7, "fee": 0.0005,
        "min_history_days": 0, "vol_days": 10, "n_trials": 1,
        "constructions": [{"name": "bab_60", "lookback_days": 60}],
    }


def _loaders():
    n = 300
    base = [100.0]
    lo = [100.0]
    hi = [100.0]
    for i in range(1, n):
        mkt = 0.01 * ((i % 5) - 2)
        base.append(base[-1] * (1.0 + mkt))
        lo.append(lo[-1] * (1.0 + 0.5 * mkt))
        hi.append(hi[-1] * (1.0 + 2.0 * mkt))
    daily = {"LO1": _daily(lo), "LO2": _daily(lo),
             "HI1": _daily(hi), "HI2": _daily(hi)}

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
            self.assertEqual(reg["n_trials"], 1)
            self.assertEqual([c["name"] for c in reg["constructions"]],
                             ["bab_60"])
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
            self.assertEqual(len(verdict["constructions"]), 1)
            self.assertTrue((out / "report.md").exists())
            self.assertTrue((out / "verdict.json").exists())
            with self.assertRaises(SystemExit):  # one-touch
                run_pipeline(_cfg(), symbols, fd, ff, out)

    def test_dsr_only_computed_for_oos_passers(self):
        symbols, fd, ff = _loaders()
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_pipeline(_cfg(), symbols, fd, ff, Path(tmp))
            c = verdict["constructions"][0]
            if not (c["stage1_pass"] and c["stage2_pass"]):
                self.assertIsNone(c["dsr"])


if __name__ == "__main__":
    unittest.main()

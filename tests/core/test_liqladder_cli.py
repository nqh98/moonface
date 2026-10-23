import json
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.lanes.liqladder import DESIGN, cmd_register, run_analysis

H1 = 3_600_000
N = 120


def _candles():
    return [Candle(i * H1, 100.0, 101.0, 99.0, 100.0, 1000.0)
            for i in range(N)]


def _metric_rows():
    return [(i * H1, {"sum_open_interest": 1000.0 + 10.0 * i,
                      "count_long_short_ratio": 9.0}) for i in range(N)]


class TestLiqladderRegister(unittest.TestCase):
    def test_register_freezes_design_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, candidates=["AUSDT", "BUSDT"],
                         now_ms=1_780_000_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["interval"], "1h")
            self.assertEqual(reg["oi_field"], "sum_open_interest")
            self.assertEqual(reg["ratio_field"], "count_long_short_ratio")
            self.assertEqual(reg["h"], 6)
            self.assertEqual(reg["cost"], 0.001)
            self.assertEqual(reg["a_thr"], 0.6)
            self.assertEqual(reg["delta"], 0.05)
            self.assertEqual(reg["tiers"], [10.0, 25.0, 50.0, 100.0])
            self.assertEqual(reg["discovery"], ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            self.assertEqual(reg["end_ms"] - reg["start_ms"], 730 * 86_400_000)
            with self.assertRaises(SystemExit):
                cmd_register(out, candidates=["AUSDT"],
                             now_ms=1_780_000_000_000)


class TestLiqladderAnalysis(unittest.TestCase):
    def test_flat_price_yields_cost_negative_verdict_and_is_one_touch(self):
        candidates = [f"SYM{i}USDT" for i in range(16)]

        def fetch_candles(symbol, start_ms, end_ms):
            return _candles()

        def fetch_metrics(symbol, start_ms, end_ms):
            return _metric_rows()

        cfg = dict(DESIGN)
        cfg.update({"start_ms": 0, "end_ms": N * H1, "candidates": candidates})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            verdict = run_analysis(cfg, fetch_candles, fetch_metrics, out)
            self.assertEqual(verdict["verdict"], "mechanism_does_not_exist")
            self.assertEqual(verdict["m_assets"], 16)
            self.assertTrue((out / "verdict.json").exists())
            self.assertTrue((out / "report.md").exists())
            with self.assertRaises(SystemExit):
                run_analysis(cfg, fetch_candles, fetch_metrics, out)

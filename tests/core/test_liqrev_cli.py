import json
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.lanes.liqrev import DESIGN, cmd_register, run_analysis

H4 = 4 * 3_600_000
N = 80


def _candles(up_after=True):
    closes = [100.0 + 0.05 * i for i in range(N)]
    closes[30] = 80.0
    closes[36] = 90.0 if up_after else 70.0
    return [Candle(i * H4, c, c, c, c, 1000.0) for i, c in enumerate(closes)]


def _oi_points():
    vals = [100.0 + i for i in range(N)]
    vals[30] = 60.0
    return [(i * H4, vals[i]) for i in range(N)]


class TestLiqrevRegister(unittest.TestCase):
    def test_register_freezes_design_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, candidates=["AUSDT", "BUSDT"],
                         now_ms=1_780_000_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["interval"], "4h")
            self.assertEqual(reg["metrics_field"], "sum_open_interest")
            self.assertEqual(reg["lookback"], 20)
            self.assertEqual(reg["q"], 0.95)
            self.assertEqual(reg["h"], 6)
            self.assertEqual(reg["cost"], 0.001)
            self.assertEqual(reg["discovery"], ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            self.assertEqual(reg["end_ms"] - reg["start_ms"], 730 * 86_400_000)
            with self.assertRaises(SystemExit):
                cmd_register(out, candidates=["AUSDT"],
                             now_ms=1_780_000_000_000)


class TestLiqrevAnalysis(unittest.TestCase):
    def test_fabricated_reversion_writes_report_and_is_one_touch(self):
        candidates = [f"SYM{i}USDT" for i in range(16)]

        def fetch_candles(symbol, start_ms, end_ms):
            return _candles(up_after=True)

        def fetch_metric(symbol, start_ms, end_ms):
            return _oi_points()

        cfg = dict(DESIGN)
        cfg.update({"start_ms": 0, "end_ms": N * H4, "candidates": candidates})
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            verdict = run_analysis(cfg, fetch_candles, fetch_metric, out)
            self.assertIn(verdict["verdict"], {"mechanism_exists", "inconclusive"})
            self.assertTrue((out / "verdict.json").exists())
            self.assertTrue((out / "report.md").exists())
            with self.assertRaises(SystemExit):
                run_analysis(cfg, fetch_candles, fetch_metric, out)

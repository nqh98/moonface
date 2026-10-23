import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.lanes.calseason import DESIGN, cmd_register, run_analysis


def ts(year, month, day, hour):
    return int(dt.datetime(year, month, day, hour, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _candles(days=20):
    out = []
    close = 100.0
    start = dt.datetime(2026, 1, 5, 0, tzinfo=dt.timezone.utc)
    for i in range(days * 6):
        cur = start + dt.timedelta(hours=4 * i)
        if i > 0:
            if cur.hour == 4:
                close *= 1.01
            else:
                close *= 1.0001
        ms = int(cur.timestamp() * 1000)
        out.append(Candle(ms, close, close, close, close, 1000.0))
    return out


class TestCalseasonRegister(unittest.TestCase):
    def test_register_freezes_design_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, candidates=["AUSDT", "BUSDT"],
                         now_ms=1_780_000_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["interval"], "4h")
            self.assertEqual(reg["cells"],
                             ["funding_pre", "funding_post", "weekend", "weekday"])
            self.assertEqual(reg["n_confirm"], 16)
            self.assertEqual(reg["discovery"], ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            self.assertEqual(reg["end_ms"] - reg["start_ms"], 730 * 86_400_000)
            with self.assertRaises(SystemExit):
                cmd_register(out, candidates=["AUSDT"],
                             now_ms=1_780_000_000_000)


class TestCalseasonAnalysis(unittest.TestCase):
    def test_writes_report_and_refuses_second_run(self):
        candidates = [f"SYM{i}USDT" for i in range(16)]

        def fetch_candles(symbol, start_ms, end_ms):
            return _candles(days=60)

        cfg = dict(DESIGN)
        cfg.update({
            "start_ms": ts(2026, 1, 1, 0),
            "end_ms": ts(2026, 3, 1, 0),
            "candidates": candidates,
            "min_returns": 10,
        })
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            verdict = run_analysis(cfg, fetch_candles, out)
            self.assertIn(verdict["status"],
                          ("closed_positive", "closed_negative"))
            self.assertTrue((out / "verdict.json").exists())
            self.assertTrue((out / "report.md").exists())
            with self.assertRaises(SystemExit):
                run_analysis(cfg, fetch_candles, out)

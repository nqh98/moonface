import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.lanes.macro_event import DESIGN, cmd_register, run_analysis

_HOUR_MS = 3_600_000


def _utc_ms(year, month, day):
    return int(dt.datetime(year, month, day,
                           tzinfo=dt.timezone.utc).timestamp() * 1000)


class TestRegister(unittest.TestCase):
    def test_register_freezes_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, now_ms=1_783_000_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["symbol"], "BTCUSDT")
            self.assertEqual(reg["interval"], "1h")
            self.assertEqual(reg["direction"], "long")
            self.assertEqual(reg["n_fomc"], 36)
            self.assertEqual(reg["n_cpi"], 53)
            self.assertEqual(len(reg["fomc_ts_ms"]), 36)
            self.assertEqual(len(reg["cpi_ts_ms"]), 53)
            self.assertEqual(reg["alpha_bonferroni"], 0.0125)
            self.assertEqual(reg["start_ms"], _utc_ms(2022, 1, 1))
            self.assertEqual(reg["end_ms"], 1_783_000_000_000)
            with self.assertRaises(SystemExit):
                cmd_register(out, now_ms=1_783_000_000_000)


class TestRunAnalysis(unittest.TestCase):
    def _cfg(self):
        cfg = dict(DESIGN)
        cfg["start_ms"] = _utc_ms(2022, 1, 1)
        cfg["end_ms"] = _utc_ms(2026, 7, 1)
        return cfg

    def test_one_touch_run_writes_verdict_and_report(self):
        fetched = []

        def fetch_candles(symbol, start_ms, end_ms):
            fetched.append((symbol, start_ms, end_ms))
            candles = []
            close = 100.0
            ts = start_ms
            while ts < end_ms:
                close *= 1.00001
                candles.append(Candle(ts, close, close, close, close, 1.0))
                ts += _HOUR_MS
            return candles

        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            v = run_analysis(cfg, fetch_candles, out)
            self.assertIn(v["status"], ("forward_candidate", "closed_negative"))
            self.assertEqual(fetched[0][0], "BTCUSDT")
            # 48h pre-margin so the first pre-window is computable
            self.assertEqual(fetched[0][1], cfg["start_ms"] - 2 * 86_400_000)
            for name in ("fomc_pre24h", "fomc_post24h",
                         "cpi_pre24h", "cpi_post24h"):
                self.assertIn(name, v["cells"])
                self.assertGreaterEqual(v["cells"][name]["n"], 20)
            self.assertTrue((out / "verdict.json").exists())
            report = (out / "report.md").read_text()
            self.assertIn("status:", report)
            self.assertIn("cpi_post24h", report)
            with self.assertRaises(SystemExit):
                run_analysis(cfg, fetch_candles, out)

    def test_no_data_yields_closed_negative_not_crash(self):
        cfg = self._cfg()
        with tempfile.TemporaryDirectory() as tmp:
            v = run_analysis(cfg, lambda s, a, b: [], Path(tmp))
            self.assertEqual(v["status"], "closed_negative")
            for cell in v["cells"].values():
                self.assertEqual(cell["n"], 0)

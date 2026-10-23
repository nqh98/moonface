import json
import tempfile
import unittest
from pathlib import Path

from moonface.research import funding_fade_fwd as fwd
from tools.lanes.funding_fade_fwd import cmd_analyze, cmd_dryrun, cmd_identity


def _fake_loader(n=1300, spikes=(200, 250)):
    # Helpers duplicated from tests/test_funding_fade_fwd.py on purpose —
    # the tests/ tree is not an importable package.
    from moonface.core.models import Candle
    start_ms = fwd.CUTOFF_MS - (n + 1) * 14_400_000
    candles = []
    for i in range(n):
        close = 100.0 + 0.1 * i
        candles.append(Candle(timestamp_ms=start_ms + i * 14_400_000,
                              open=close - 0.05, high=close + 0.5,
                              low=close - 0.5, close=close, volume=1.0))
    funding = [1e-4 if i % 2 == 0 else -1e-4 for i in range(n)]
    for i in spikes:
        funding[i] = 1e-2
    return candles, funding


class DryrunCliTest(unittest.TestCase):
    def test_mismatch_returns_1_and_writes_report(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            code = cmd_dryrun(cache_dir="unused", out_root=out,
                              loader=lambda _: _fake_loader())
            self.assertEqual(code, 1)  # synthetic data cannot match ARCHIVED
            report = json.loads((out / "dryrun_report.json").read_text())
            self.assertFalse(report["reproduced"])
            self.assertEqual(report["archived"], fwd.ARCHIVED)
            streams = json.loads((out / "streams.json").read_text())
            self.assertEqual(len(streams["research"]), 1)
            self.assertEqual(len(streams["tail"]), 1)


class AnalyzeCliTest(unittest.TestCase):
    def test_analyze_writes_tables_from_streams(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            day = 86_400_000
            research = [[1_600_000_000_000 + i * day,
                         (-2.0 if i % 4 == 0 else 1.0)] for i in range(120)]
            tail = [[1_700_000_000_000 + i * day, 1.0] for i in range(40)]
            (out / "streams.json").write_text(
                json.dumps({"research": research, "tail": tail}))
            code = cmd_analyze(out_root=out, budgets=[-40.0, -50.0, -64.0],
                               months=12, resamples=200)
            self.assertEqual(code, 0)
            analysis = json.loads((out / "analysis.json").read_text())
            self.assertEqual([b["budget_r"] for b in analysis["budgets"]],
                             [-40.0, -50.0, -64.0])
            for b in analysis["budgets"]:
                for key in ("p_ruin_measured", "p_ruin_zero_edge",
                            "p_ruin_measured_peak_relative",
                            "capital_at_risk_pct"):
                    self.assertIn(key, b)
            self.assertIn("required_n_power50", analysis["trigger"])
            self.assertIn("required_n_power80", analysis["trigger"])
            self.assertTrue((out / "analysis.md").exists())


class IdentityCliTest(unittest.TestCase):
    def test_identity_prints_hash(self):
        self.assertEqual(cmd_identity(-50.0, 123, 12), 0)

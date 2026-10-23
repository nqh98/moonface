import json
import tempfile
import unittest
from pathlib import Path

from tools.collect.newdata import cmd_assess, cmd_candidates, cmd_register


class TestNewDataCli(unittest.TestCase):
    def test_candidates_writes_frozen_candidate_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_candidates(out)
            payload = json.loads((out / "candidates.json").read_text())

        self.assertEqual(payload["data_classes"][0], "l2_orderbook")
        self.assertIn("aggressor_trades", payload["data_classes"])
        self.assertIn("ohlcv", payload["excluded"])

    def test_register_writes_design_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, provider="ExampleVendor", data_class="l2_orderbook")
            reg = json.loads((out / "registration.json").read_text())

            self.assertEqual(reg["provider"], "ExampleVendor")
            self.assertEqual(reg["data_class"], "l2_orderbook")
            self.assertEqual(reg["purpose"], "data readiness only")
            with self.assertRaises(SystemExit):
                cmd_register(out, provider="OtherVendor", data_class="aggressor_trades")

    def test_assess_writes_readiness_and_refuses_rerun(self):
        manifest = {
            "provider": "ExampleVendor",
            "data_class": "account_positioning",
            "symbols": ["BTCUSDT"],
            "history_days": 240,
            "cadence_ms": 300000,
            "coverage_ratio": 0.97,
            "monotonic_timestamps": True,
            "duplicate_timestamp_ratio": 0.0,
            "fields": ["ts_ms", "symbol", "long_ratio", "short_ratio"],
            "license": {
                "research_allowed": True,
                "derived_features_allowed": True,
                "retention_allowed": True,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest_path = out / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            verdict = cmd_assess(out, manifest_path)

            self.assertEqual(verdict["status"], "ready")
            self.assertTrue((out / "readiness.json").exists())
            self.assertTrue((out / "report.md").exists())
            with self.assertRaises(SystemExit):
                cmd_assess(out, manifest_path)

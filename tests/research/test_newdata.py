import unittest
from moonface.research.newdata import (
    DATA_CLASSES,
    REQUIRED_FIELDS,
    assess_manifest,
    render_report,
)


class TestNewDataReadiness(unittest.TestCase):
    def test_frozen_data_classes_exclude_free_data_variants(self):
        self.assertEqual(
            DATA_CLASSES,
            ("l2_orderbook", "aggressor_trades", "account_positioning",
             "macro_series", "implied_vol", "options_chain"),
        )
        self.assertNotIn("ohlcv", DATA_CLASSES)
        self.assertNotIn("funding", DATA_CLASSES)
        self.assertEqual(
            REQUIRED_FIELDS["aggressor_trades"],
            ("ts_ms", "symbol", "side", "price", "size"),
        )
        self.assertEqual(
            REQUIRED_FIELDS["options_chain"],
            ("ts_ms", "symbol", "expiry_ms", "strike", "option_type",
             "oi", "iv", "underlying_price"),
        )

    def test_options_chain_manifest_requires_btc_currency_and_history(self):
        manifest = {
            "provider": "deribit",
            "data_class": "options_chain",
            "symbols": ["ETH"],
            "history_days": 2,
            "cadence_ms": 86_400_000,
            "coverage_ratio": 1.0,
            "monotonic_timestamps": True,
            "duplicate_timestamp_ratio": 0.0,
            "fields": ["ts_ms", "symbol", "expiry_ms", "strike", "option_type",
                       "oi", "iv", "underlying_price"],
            "license": {
                "research_allowed": True,
                "derived_features_allowed": True,
                "retention_allowed": True,
            },
        }

        got = assess_manifest(manifest)

        self.assertEqual(got["status"], "blocked")
        self.assertIn("BTC coverage is required", got["failures"])
        self.assertIn("history_days must be at least 180", got["failures"])

        manifest["symbols"] = ["BTC"]
        manifest["history_days"] = 200
        self.assertEqual(assess_manifest(manifest)["status"], "ready")

    def test_assess_manifest_passes_quality_gate(self):
        manifest = {
            "provider": "ExampleVendor",
            "data_class": "aggressor_trades",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "history_days": 365,
            "cadence_ms": 1000,
            "coverage_ratio": 0.981,
            "monotonic_timestamps": True,
            "duplicate_timestamp_ratio": 0.002,
            "fields": ["ts_ms", "symbol", "side", "price", "size", "trade_id"],
            "license": {
                "research_allowed": True,
                "derived_features_allowed": True,
                "retention_allowed": True,
            },
        }

        got = assess_manifest(manifest)

        self.assertEqual(got["status"], "ready")
        self.assertEqual(got["provider"], "ExampleVendor")
        self.assertEqual(got["data_class"], "aggressor_trades")
        self.assertEqual(got["failures"], [])

    def test_assess_manifest_fails_missing_quality_and_license(self):
        manifest = {
            "provider": "WeakVendor",
            "data_class": "ohlcv",
            "symbols": ["ETHUSDT"],
            "history_days": 90,
            "cadence_ms": 1000,
            "coverage_ratio": 0.90,
            "monotonic_timestamps": False,
            "duplicate_timestamp_ratio": 0.03,
            "fields": ["ts_ms", "symbol", "close"],
            "license": {
                "research_allowed": True,
                "derived_features_allowed": False,
                "retention_allowed": True,
            },
        }

        got = assess_manifest(manifest)

        self.assertEqual(got["status"], "blocked")
        self.assertIn("data_class must be one of the frozen new-data classes", got["failures"])
        self.assertIn("history_days must be at least 180", got["failures"])
        self.assertIn("coverage_ratio must be at least 0.95", got["failures"])
        self.assertIn("timestamps must be monotonic", got["failures"])
        self.assertIn("duplicate_timestamp_ratio must be <= 0.01", got["failures"])
        self.assertIn("derived feature retention/use must be licensed", got["failures"])

    def test_render_report_records_no_alpha_work(self):
        verdict = {
            "status": "ready",
            "provider": "ExampleVendor",
            "data_class": "l2_orderbook",
            "failures": [],
            "checks": {"history_days": 365},
        }

        report = render_report(verdict)

        self.assertIn("status: ready", report)
        self.assertIn("No signal tests, return tests, or strategy backtests were run.", report)

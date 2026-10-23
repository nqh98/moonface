import json
import sys
import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.advval.advval import DESIGN, cmd_register, main


class RegisterTest(unittest.TestCase):
    def test_design_frozen_constants(self):
        self.assertEqual(DESIGN["era_split_ms"], 1704844800000)
        self.assertEqual(DESIGN["window_start_ms"], 1640995200000)
        self.assertEqual(DESIGN["symbol"], "BTCUSDT")
        self.assertEqual(DESIGN["metrics_field"], "sum_open_interest")
        self.assertEqual(
            DESIGN["gbt"],
            {"rounds": 200, "lr": 0.1, "min_leaf": 20},
        )
        self.assertEqual(DESIGN["cv"], {"n_folds": 5, "embargo": 90})
        self.assertEqual(
            DESIGN["bootstrap"],
            {"n_boot": 2000, "seed": 20260706},
        )
        self.assertEqual(
            DESIGN["cells"],
            ["price_4h", "price_1d", "funding_8h", "oi_4h"],
        )
        self.assertEqual(
            DESIGN["price_features"],
            ["abs_ret_z", "close_loc", "log_ret", "range_frac", "up_frac_30", "vol_z"],
        )
        self.assertEqual(
            DESIGN["funding_features"],
            ["abs_rate_z", "pos_frac_30", "rate", "rate_chg", "rate_z"],
        )
        self.assertEqual(
            DESIGN["oi_features"],
            ["abs_chg_z", "oi_chg", "oi_chg30", "oi_chg_z"],
        )
        self.assertEqual(
            DESIGN["kill_rule"],
            "kill unless rho > 0 AND ci_low > 0 (90% percentile CI)",
        )

    def test_register_writes_and_freezes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "advval"
            cmd_register(out, now_ms=1_751_760_000_000)

            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["window_end_ms"], 1_751_760_000_000)
            self.assertEqual(reg["n_studies"], 18)
            self.assertEqual(reg["cells"], ["price_4h", "price_1d", "funding_8h", "oi_4h"])

            prereg = (out / "PREREGISTRATION.md").read_text()
            self.assertIn("kill unless rho > 0 AND ci_low > 0", prereg)
            self.assertIn("xsection_mom_30", prereg)
            self.assertIn("EXCLUDED", prereg)

            with self.assertRaises(SystemExit):
                cmd_register(out, now_ms=1_751_760_000_000)

    def test_register_does_not_freeze_if_prereg_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "advval"
            original_write_text = Path.write_text

            def failing_write_text(self, text, *args, **kwargs):
                if self.name == "PREREGISTRATION.md":
                    raise OSError("boom")
                return original_write_text(self, text, *args, **kwargs)

            with patch.object(Path, "write_text", failing_write_text):
                with self.assertRaises(OSError):
                    cmd_register(out, now_ms=1_751_760_000_000)
            self.assertFalse((out / "registration.json").exists())

    def test_register_does_not_freeze_if_registration_write_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "advval"
            original_write_text = Path.write_text

            def failing_write_text(self, text, *args, **kwargs):
                if self.name == "registration.json":
                    raise OSError("boom")
                return original_write_text(self, text, *args, **kwargs)

            with patch.object(Path, "write_text", failing_write_text):
                with self.assertRaises(OSError):
                    cmd_register(out, now_ms=1_751_760_000_000)
            self.assertFalse((out / "registration.json").exists())
            self.assertFalse((out / "PREREGISTRATION.md").exists())

    def test_register_does_not_freeze_if_replace_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "advval"

            def failing_replace(self, target):
                raise OSError("boom")

            with patch.object(Path, "replace", failing_replace):
                with self.assertRaises(OSError):
                    cmd_register(out, now_ms=1_751_760_000_000)
            self.assertFalse(out.exists())

    def test_main_register_uses_default_out_dir(self):
        with patch("tools.advval.advval.cmd_register") as register:
            main(["--register"])
        register.assert_called_once_with(Path("experiments/advval"))

    def test_main_run_routes_defaults(self):
        calls = []

        def fake_run(out_dir, cache_dir):
            calls.append((out_dir, cache_dir))

        mod = types.ModuleType("tools.advval.advval_run")
        mod.cmd_run = fake_run
        with patch.dict(sys.modules, {"tools.advval.advval_run": mod}):
            main(["--run"])

        self.assertEqual(calls, [(Path("experiments/advval"), ".backtest_cache")])

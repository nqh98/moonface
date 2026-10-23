import json
import tempfile
import unittest
from pathlib import Path

from tools.eventtime.eventtime import DESIGN, cmd_register, main


class RegisterTest(unittest.TestCase):
    def test_design_frozen_constants(self):
        self.assertEqual(DESIGN["symbol"], "BTCUSDT")
        self.assertEqual(DESIGN["exchange"], "binanceusdm")
        self.assertEqual(
            DESIGN["entry"],
            {"family": "donchian_break", "params": {"n": 55}},
        )
        self.assertEqual(DESIGN["calib_start_ms"], 1577836800000)
        self.assertEqual(DESIGN["calib_end_ms"], 1672531200000)
        self.assertEqual(DESIGN["test_start_ms"], 1672531200000)
        self.assertEqual(DESIGN["bar_size_window_min"], 240)
        self.assertEqual(DESIGN["fence_fraction"], 0.75)
        self.assertEqual(DESIGN["fraction"], 0.1)
        self.assertEqual(DESIGN["grid_size"], 10)
        self.assertEqual(DESIGN["min_improve"], 0.5)
        self.assertEqual(len(DESIGN["exit_rows"]), 10)

    def test_register_writes_and_freezes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eventtime"
            cmd_register(out, now_ms=1_751_760_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["test_end_ms"], 1_751_760_000_000)
            self.assertEqual(reg["entry"]["params"]["n"], 55)
            prereg = (out / "PREREGISTRATION.md").read_text()
            self.assertIn("KILL", prereg)
            self.assertIn("dollar", prereg.lower())
            self.assertIn("50%", prereg)
            self.assertIn("frozen exit", prereg.lower())
            with self.assertRaises(SystemExit):
                cmd_register(out, now_ms=1_751_760_000_000)

    def test_main_register_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "eventtime"
            main(["--register", "--out-dir", str(out)])
            self.assertTrue((out / "registration.json").exists())

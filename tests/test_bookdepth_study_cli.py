# tests/test_bookdepth_study_cli.py
import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.lanes.bookdepth_study import DESIGN, cmd_register, resolve_candidates

DAY = 86_400_000


class TestRegister(unittest.TestCase):
    def test_register_freezes_level_follow_design_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, candidates=["BTCUSDT", "AUSDT"],
                         now_ms=1_780_000_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["generator"], "level_follow")
            self.assertEqual(reg["interval"], "1h")
            self.assertEqual(reg["h"], 6)
            self.assertEqual(reg["window"], 180)
            self.assertEqual(reg["max_age_ms"], 3_600_000)
            self.assertEqual(reg["discovery"], [])  # external-prior study
            self.assertEqual(reg["candidates"], ["BTCUSDT", "AUSDT"])
            self.assertEqual(reg["end_ms"] - reg["start_ms"],
                             730 * DAY)
            with self.assertRaises(SystemExit):
                cmd_register(out, candidates=["AUSDT"],
                             now_ms=1_780_000_000_000)


class TestResolution(unittest.TestCase):
    def test_no_exclusions_keeps_the_majors(self):
        now = 1_781_245_000_000
        window_start = now - DESIGN["window_days"] * DAY
        cache_start = now - 1095 * DAY + int(0.7 * DAY)
        with tempfile.TemporaryDirectory() as tmp:
            for sym, qvol in (("BTCUSDT", 9000.0), ("AUSDT", 5000.0)):
                with open(Path(tmp) / f"uni1d_{sym}.csv", "w",
                          newline="") as fh:
                    w = csv.writer(fh)
                    ts = cache_start
                    while ts < now:
                        w.writerow([ts, 100.0, qvol])
                        ts += DAY
            got = resolve_candidates(tmp, window_start)
            self.assertEqual(got, ["BTCUSDT", "AUSDT"])


if __name__ == "__main__":
    unittest.main()

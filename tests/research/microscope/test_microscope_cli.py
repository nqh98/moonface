import tempfile
import unittest
from pathlib import Path

from tools.microscope.microscope import (
    build_argparser, parse_events_csv, run_matrix, run_study, UNIVERSE,
)
from tests.helpers_microscope import STEP_MS, TS0, make_pool
from moonface.research.microscope.events import Event
from moonface.research.microscope.report import HEADER


class ParserTest(unittest.TestCase):
    def test_universe_includes_btc(self):
        self.assertIn("BTCUSDT", UNIVERSE)
        self.assertEqual(len(UNIVERSE), 17)

    def test_matrix_defaults(self):
        args = build_argparser().parse_args(["matrix"])
        self.assertEqual(args.cmd, "matrix")
        self.assertEqual(args.cache_dir, "cache")
        self.assertEqual(args.out, "experiments/microscope")

    def test_study_requires_events(self):
        with self.assertRaises(SystemExit):
            build_argparser().parse_args(["study"])


class EventsCsvTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            path.write_text("ts_ms,symbol,direction\n"
                            f"{TS0},XUSDT,1\n{TS0 + STEP_MS},YUSDT,-1\n")
            events = parse_events_csv(path)
        self.assertEqual(events,
                         [Event(ts_ms=TS0, symbol="XUSDT", direction=1),
                          Event(ts_ms=TS0 + STEP_MS, symbol="YUSDT",
                                direction=-1)])


class RunTest(unittest.TestCase):
    def test_run_matrix_writes_csvs(self):
        pool = make_pool(n=320, n_assets=10, seed=23)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            built = run_matrix(pool, out)
            self.assertEqual(built["n_bars"], 320)
            for name in ("features.csv", "states.csv", "pool.csv"):
                self.assertTrue((out / name).exists(), name)
            head = (out / "features.csv").read_text().splitlines()[0]
            self.assertTrue(head.startswith("symbol,ts_ms,ret_1_z"))

    def test_run_study_writes_report(self):
        pool = make_pool(n=320, n_assets=10, seed=29)
        events = [Event(ts_ms=TS0 + t * STEP_MS, symbol=sym, direction=+1)
                  for t in range(200, 260, 2)
                  for sym in ("A00USDT", "A03USDT", "BTCUSDT")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            text = run_study(pool, events, out, seed=1)
            self.assertIn(HEADER, text)
            self.assertTrue((out / "outcomes.csv").exists())
            self.assertEqual((out / "report.md").read_text(), text)


if __name__ == "__main__":
    unittest.main()

# tests/test_oibuild_study_cli.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.lanes.oibuild_study import cmd_register, run_analysis

H4 = 4 * 3_600_000
N_BARS = 120


def _candles(up=True):
    # phase wiggle keeps per-event forward returns positive but unequal,
    # so the per-asset t-stat is well-defined (zero variance -> t = 0)
    closes = [100.0 * (1.01 if up else 0.99) ** i * (1 + 0.001 * (i % 7))
              for i in range(N_BARS)]
    return [Candle(i * H4, c, c, c, c, 1000.0) for i, c in enumerate(closes)]


def _oi_points():
    """OI spikes every 5 bars: lookback-2 change z clears 1.5 at each spike."""
    return [(i * H4, 200.0 if i % 5 == 0 else 100.0) for i in range(N_BARS)]


def _cfg(candidates):
    return {
        "start_ms": 0, "end_ms": N_BARS * H4,
        "window": 10, "lookback": 2, "z_thr": 1.5, "h": 4,
        "h_secondary": [2, 8], "lookback_secondary": 5,
        "cost": 0.001, "n_confirm": 9, "min_assets": 8, "min_events": 10,
        "min_coverage": 0.8, "metrics_field": "sum_open_interest",
        "candidates": candidates, "discovery": [],
    }


def _loaders():
    def fetch_candles(symbol, start_ms, end_ms):
        return _candles(up=True)

    def fetch_metric(symbol, start_ms, end_ms):
        return _oi_points()

    return fetch_candles, fetch_metric


class TestCandidateResolution(unittest.TestCase):
    def test_cache_truncated_listing_history_still_qualifies(self):
        """uni1d caches begin at the xsection window start, so a symbol
        listed years earlier has its first cached row at the cache boundary —
        the listing floor must tolerate that, not exclude everything."""
        import csv

        from tools.lanes.oibuild_study import DESIGN, _candidates_from_caches
        day = 86_400_000
        now = 1_781_245_000_000
        window_start = now - DESIGN["window_days"] * day
        # the 3y uni1d cache boundary, plus UTC-midnight kline alignment:
        # the first cached row lands up to ~24h after the nominal start
        cache_start = now - 1095 * day + int(0.7 * day)
        with tempfile.TemporaryDirectory() as tmp:
            for sym, qvol in (("OLDUSDT", 5000.0), ("NEWUSDT", 9000.0)):
                first = cache_start if sym == "OLDUSDT" else now - 400 * day
                with open(Path(tmp) / f"uni1d_{sym}.csv", "w",
                          newline="") as fh:
                    w = csv.writer(fh)
                    ts = first
                    while ts < now:
                        w.writerow([ts, 100.0, qvol])
                        ts += day
            got = _candidates_from_caches(tmp, window_start)
            # OLDUSDT's true listing predates the cache; it must qualify.
            # NEWUSDT listed 400d ago: after the window started -> excluded.
            self.assertEqual(got, ["OLDUSDT"])


class TestRegister(unittest.TestCase):
    def test_register_freezes_design_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cmd_register(out, candidates=["AUSDT", "BUSDT"],
                         now_ms=1_780_000_000_000)
            reg = json.loads((out / "registration.json").read_text())
            self.assertEqual(reg["window"], 180)
            self.assertEqual(reg["lookback"], 6)
            self.assertEqual(reg["z_thr"], 1.5)
            self.assertEqual(reg["h"], 24)
            self.assertEqual(reg["end_ms"] - reg["start_ms"],
                             730 * 86_400_000)
            self.assertEqual(reg["candidates"], ["AUSDT", "BUSDT"])
            self.assertEqual(reg["discovery"],
                             ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            with self.assertRaises(SystemExit):
                cmd_register(out, candidates=["AUSDT"],
                             now_ms=1_780_000_000_000)


class TestAnalysis(unittest.TestCase):
    def test_fabricated_signal_yields_exists_and_one_touch(self):
        candidates = [f"SYM{i}USDT" for i in range(9)]
        fc, fm = _loaders()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            verdict = run_analysis(_cfg(candidates), fc, fm, out)
            self.assertEqual(verdict["verdict"], "mechanism_exists")
            self.assertEqual(verdict["m_assets"], 9)
            for a in verdict["assets"]:
                self.assertGreaterEqual(a["n"], 10)
                self.assertGreater(a["mean"], 0.0)
            self.assertIn("descriptive", verdict)
            self.assertTrue((out / "report.md").exists())
            self.assertTrue((out / "verdict.json").exists())
            with self.assertRaises(SystemExit):  # one-touch
                run_analysis(_cfg(candidates), fc, fm, out)

    def test_level_follow_generator_dispatch(self):
        """cfg generator='level_follow' uses the level z-score (toptrader
        machinery): a feature LEVEL spike fires events even when the
        change-z would not, and the inert lookback descriptive is omitted."""
        candidates = [f"SYM{i}USDT" for i in range(9)]
        fc, _ = _loaders()

        def fetch_metric(symbol, start_ms, end_ms):
            # level spikes every 5 bars; flat in between
            return [(i * H4, 50.0 if i % 5 == 0 else 1.0)
                    for i in range(N_BARS)]

        cfg = _cfg(candidates)
        cfg["generator"] = "level_follow"
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_analysis(cfg, fc, fetch_metric, Path(tmp))
            self.assertEqual(verdict["verdict"], "mechanism_exists")
            self.assertNotIn(f"lookback_{cfg['lookback_secondary']}",
                             verdict["descriptive"])

    def test_time_halves_use_the_dispatched_generator(self):
        """The time-stability descriptive regenerates events; with
        generator='level_follow' it must use the level generator, not the
        hardcoded change-momentum one (which sees zero events at lookback=0
        and silently reports all-zero halves)."""
        candidates = [f"SYM{i}USDT" for i in range(9)]
        fc, _ = _loaders()

        def fetch_metric(symbol, start_ms, end_ms):
            return [(i * H4, 50.0 if i % 5 == 0 else 1.0)
                    for i in range(N_BARS)]

        cfg = _cfg(candidates)
        cfg["generator"] = "level_follow"
        cfg["lookback"] = 0  # inert for level generators, as registered
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_analysis(cfg, fc, fetch_metric, Path(tmp))
            for key in ("time_first_half", "time_second_half"):
                self.assertGreater(verdict["descriptive"][key]["k"], 0, key)

    def test_max_age_freshness_gate(self):
        """A metrics feed denser than the default daily staleness bound can
        still fail a stricter cfg max_age_ms."""
        candidates = [f"SYM{i}USDT" for i in range(9)]
        fc, _ = _loaders()

        def fetch_metric(symbol, start_ms, end_ms):
            # one point every 3 bars (12h): fresh at 1d, stale at 1h
            return [(i * H4, 100.0) for i in range(0, N_BARS, 3)]

        cfg = _cfg(candidates)
        cfg["max_age_ms"] = 3_600_000
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_analysis(cfg, fc, fetch_metric, Path(tmp))
            self.assertEqual(verdict["m_assets"], 0)
            self.assertEqual(len(verdict["skipped"]), 9)

    def test_insufficient_coverage_assets_are_skipped(self):
        candidates = [f"SYM{i}USDT" for i in range(9)] + ["THINUSDT"]
        fc, fm = _loaders()

        def fetch_metric(symbol, start_ms, end_ms):
            if symbol == "THINUSDT":
                return _oi_points()[:10]  # <80% aligned coverage
            return _oi_points()

        cfg = _cfg(candidates)
        cfg["n_confirm"] = 10
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_analysis(cfg, fc, fetch_metric, Path(tmp))
            self.assertEqual(verdict["m_assets"], 9)
            self.assertIn("THINUSDT", verdict["skipped"])


if __name__ == "__main__":
    unittest.main()

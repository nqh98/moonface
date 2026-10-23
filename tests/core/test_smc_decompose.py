from __future__ import annotations

import argparse
import csv
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from tools.engine.smc_decompose import aggregate_4h
from tools.engine.smc_decompose import REF_HORIZON, score_variant
from tools.engine.smc_decompose import slice_events
from tools.engine.smc_decompose import GRID, cmd_run, render_report

import pytest

pytestmark = pytest.mark.slow

H1 = 3_600_000


def c(ts, o, h, lo, v) -> Candle:
    return Candle(ts, o, h, lo, (o + h + lo) / 3, v)


class Aggregate4hTest(unittest.TestCase):
    def test_four_hourly_candles_roll_up_to_one(self) -> None:
        base = 4 * H1  # 04:00 UTC boundary
        ones = [
            c(base + 0 * H1, 100, 102, 99, 1.0),
            c(base + 1 * H1, 100, 105, 100, 2.0),
            c(base + 2 * H1, 100, 101, 98, 3.0),
            c(base + 3 * H1, 100, 104, 100, 4.0),
        ]
        out = aggregate_4h(ones)
        self.assertEqual(len(out), 1)
        bar = out[0]
        self.assertEqual(bar.timestamp_ms, base)
        self.assertEqual(bar.open, 100)          # first open
        self.assertEqual(bar.high, 105)          # max high
        self.assertEqual(bar.low, 98)            # min low
        self.assertEqual(bar.volume, 10.0)       # sum volume

    def test_two_buckets_when_straddling_boundary(self) -> None:
        ones = [c(i * H1, 100, 101, 99, 1.0) for i in range(8)]  # 00:00..07:00
        out = aggregate_4h(ones)
        self.assertEqual(len(out), 2)
        self.assertEqual([b.timestamp_ms for b in out], [0, 4 * H1])


def rising_after_entry() -> list[Candle]:
    """100 bars: flat at 100 through bar 60, then a monotone rise with the low
    pinned at 100 so a LONG entered at 60 has zero adverse excursion."""
    bars = []
    for i in range(100):
        if i <= 60:
            bars.append(Candle(i * H1, 100, 101, 99, 100, 1.0))
        else:
            k = i - 60
            bars.append(Candle(i * H1, 100 + k, 105 + k, 100, 100 + k, 1.0))
    return bars


class ScoreVariantTest(unittest.TestCase):
    def test_known_long_has_positive_drift_zero_mae(self) -> None:
        candles = rising_after_entry()
        def gen(c, p):
            return [(60, "LONG")]
        doc = score_variant(candles, gen, {})
        for h in (6, 12, 18, 30):
            block = doc["horizons"][h]
            self.assertEqual(block["n"], 1)
            self.assertEqual(block["win_rate"], 1.0)
            self.assertGreater(block["mean_ret_r"], 0.0)
            self.assertEqual(block["mean_mae_r"], 0.0)
            self.assertGreater(block["mean_mfe_r"], 0.0)
            self.assertGreaterEqual(block["ci_lo"], 0.0)
            self.assertGreaterEqual(block["ci_hi"], block["ci_lo"])

    def test_event_records_carry_regime_tags(self) -> None:
        candles = rising_after_entry()
        def gen(c, p):
            return [(60, "LONG")]
        doc = score_variant(candles, gen, {})
        self.assertEqual(len(doc["events"]), 1)
        rec = doc["events"][0]
        self.assertEqual(rec["side"], "LONG")
        self.assertIn(rec["structure"], ("BULLISH", "BEARISH", "NEUTRAL"))
        self.assertIn(rec["atr_tercile"], ("low", "mid", "high"))
        self.assertEqual(rec["h"], REF_HORIZON)


class SliceEventsTest(unittest.TestCase):
    def _rec(self, ts, side, structure, tercile, ret_r):
        return {"ts": ts, "side": side, "structure": structure,
                "atr_tercile": tercile, "ret_r": ret_r, "mae_r": -1.0, "mfe_r": 1.0}

    def test_groups_by_structure_side_tercile(self) -> None:
        recs = [
            self._rec(1, "LONG", "BULLISH", "low", 1.0),
            self._rec(2, "LONG", "BULLISH", "low", -1.0),
            self._rec(3, "SHORT", "BEARISH", "high", 2.0),
        ]
        out = slice_events(recs)
        self.assertEqual(out["side"]["LONG"]["n"], 2)
        self.assertEqual(out["side"]["LONG"]["win_rate"], 0.5)
        self.assertEqual(out["structure"]["BEARISH"]["n"], 1)
        self.assertEqual(out["atr_tercile"]["high"]["mean_ret_r"], 2.0)

    def test_half_split_is_time_ordered(self) -> None:
        recs = [self._rec(ts, "LONG", "BULLISH", "mid", float(ts))
                for ts in range(4)]
        out = slice_events(recs)
        self.assertEqual(out["half"]["first"]["n"], 2)
        self.assertEqual(out["half"]["second"]["n"], 2)
        self.assertLess(out["half"]["first"]["mean_ret_r"],
                        out["half"]["second"]["mean_ret_r"])

    def test_empty_records(self) -> None:
        out = slice_events([])
        self.assertEqual(out["half"]["first"]["n"], 0)


def _write_cache(tmp: str) -> None:
    # ~130 bars: flat warmup then a rising leg, enough for warmup + max horizon.
    rows = []
    for i in range(130):
        c = 100 + max(0, i - 70) * 0.5
        rows.append([i * H1, c, c + 2, c - 2, c, 1.0])
    with open(f"{tmp}/BTC_USDT:USDT_1h.csv", "w", newline="") as fh:
        csv.writer(fh).writerows(rows)


class CliSmokeTest(unittest.TestCase):
    def test_cmd_run_all_variants_emits_expected_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_cache(tmp)
            with tempfile.TemporaryDirectory() as outdir:
                args = argparse.Namespace(
                    symbol="BTC/USDT:USDT", tf="1h",
                    start_ms=0, end_ms=2_000_000_000_000,
                    cache_dir=tmp, out_dir=Path(outdir), from_1h=False)
                doc = cmd_run(args)
                self.assertEqual(doc["tf"], "1h")
                self.assertEqual(set(doc["variants"]), set(GRID))
                for name, results in doc["variants"].items():
                    self.assertTrue(len(results) >= 1)
                    for row in results:
                        for h in (6, 12, 18, 30):
                            self.assertIn(h, row["horizons"])
                self.assertTrue((Path(outdir) / "results_1h.json").exists())

    def test_render_report_mentions_research_only_and_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_cache(tmp)
            with tempfile.TemporaryDirectory() as outdir:
                args = argparse.Namespace(
                    symbol="BTC/USDT:USDT", tf="1h",
                    start_ms=0, end_ms=2_000_000_000_000,
                    cache_dir=tmp, out_dir=Path(outdir), from_1h=False)
                doc = cmd_run(args)
                md = render_report({outdir: doc})
                self.assertIn("RESEARCH-ONLY", md)
                self.assertIn("full_reversal", md)
                self.assertIn("flip", md)


if __name__ == "__main__":
    unittest.main()

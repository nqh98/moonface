from __future__ import annotations

import argparse
import csv
import tempfile
import unittest
from pathlib import Path

from moonface.core.models import Candle
from moonface.research.edge.signals import bb_revert
from tools.lanes.bb_revert import GRID, cmd_run, render_report


def series(closes: list[float]) -> list[Candle]:
    return [Candle(1_780_275_600_000 + i * 3_600_000, c, c + 1, c - 1, c, 1.0)
            for i, c in enumerate(closes)]


class BbRevertSignalTest(unittest.TestCase):
    def test_long_on_lower_band_cross_down(self):
        # Flat at 100 (std=0 -> bands pinned at 100), then a drop below -> LONG fade.
        closes = [100.0] * 20 + [90.0, 90.0]
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertIn((20, "LONG"), out)
        self.assertFalse(any(s == "SHORT" for _, s in out))

    def test_short_on_upper_band_cross_up(self):
        closes = [100.0] * 20 + [110.0, 110.0]
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertIn((20, "SHORT"), out)
        self.assertFalse(any(s == "LONG" for _, s in out))

    def test_no_event_while_inside_bands(self):
        # Price constant at the mean -> never crosses either band.
        closes = [100.0] * 30
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertEqual(out, [])

    def test_entries_never_on_final_bar(self):
        closes = [100.0] * 25 + [90.0, 110.0, 90.0, 110.0]
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertTrue(all(0 <= i < len(closes) - 1 for i, _ in out))
        self.assertTrue(all(s in ("LONG", "SHORT") for _, s in out))


H1 = 3_600_000


def _write_cache(tmp: str) -> None:
    # ~130 bars: flat warmup then a rising leg -> upper-band crossings fire.
    rows = []
    for i in range(130):
        c = 100 + max(0, i - 70) * 0.5
        rows.append([i * H1, c, c + 2, c - 2, c, 1.0])
    with open(f"{tmp}/BTC_USDT:USDT_1h.csv", "w", newline="") as fh:
        csv.writer(fh).writerows(rows)


class BbRevertCliTest(unittest.TestCase):
    def _args(self, tmp, outdir):
        return argparse.Namespace(
            symbol="BTC/USDT:USDT", tf="1h",
            start_ms=0, end_ms=2_000_000_000_000,
            cache_dir=tmp, out_dir=Path(outdir), from_1h=False)

    def test_cmd_run_emits_expected_shape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outdir:
            _write_cache(tmp)
            doc = cmd_run(self._args(tmp, outdir))
            self.assertEqual(doc["tf"], "1h")
            self.assertEqual(set(doc["variants"]), set(GRID))
            for results in doc["variants"].values():
                self.assertEqual(len(results), 6)  # period{20,50} x mult{2,2.5,3}
                for row in results:
                    for h in (6, 12, 18, 30):
                        self.assertIn(h, row["horizons"])
            self.assertTrue((Path(outdir) / "results_1h.json").exists())

    def test_render_report_mentions_research_only_and_bb(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outdir:
            _write_cache(tmp)
            doc = cmd_run(self._args(tmp, outdir))
            md = render_report({outdir: doc})
            self.assertIn("RESEARCH-ONLY", md)
            self.assertIn("bb_revert", md)


if __name__ == "__main__":
    unittest.main()

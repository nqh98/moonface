from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class PartitionTest(unittest.TestCase):
    def test_strips_timestamps_and_computes_spans(self) -> None:
        from tools.size import partition
        day = 86_400_000
        research_pairs = [(0, 1.0), (day, -1.0)]
        tail_pairs = [(2 * day, 2.0), (3 * day, -1.0)]
        rs, ts, rsd, tsd = partition(research_pairs, tail_pairs)
        self.assertEqual(rs, [1.0, -1.0])
        self.assertEqual(ts, [2.0, -1.0])
        self.assertAlmostEqual(rsd, 1.0)  # (day - 0) / day
        self.assertAlmostEqual(tsd, 1.0)  # (3day - 2day) / day

    def test_single_or_empty_stream_has_zero_span(self) -> None:
        from tools.size import partition
        rs, ts, rsd, tsd = partition([(5, 1.0)], [])
        self.assertEqual(rs, [1.0])
        self.assertEqual(ts, [])
        self.assertEqual(rsd, 0.0)
        self.assertEqual(tsd, 0.0)


class WriteReportTest(unittest.TestCase):
    def test_writes_json_and_md_with_all_entries(self) -> None:
        from moonface.research.sizing import size_report
        from tools.size import write_sizing_report
        with TemporaryDirectory() as d:
            results = [
                ("donchian_break", {"n": 100},
                 size_report([2.0, -1.0, 2.0], [2.0, -1.0], resamples=200, seed=1)),
                ("atr_channel_break", {"k": 1.5},
                 size_report([2.0, -1.0, 2.0], [2.0, -1.0], resamples=200, seed=1)),
            ]
            out = write_sizing_report(Path(d) / "run", results, timeframe="4h")
            self.assertTrue((out / "sizing.json").exists())
            self.assertTrue((out / "sizing.md").exists())
            payload = json.loads((out / "sizing.json").read_text())
            self.assertEqual(payload["timeframe"], "4h")
            self.assertEqual([e["entry"] for e in payload["entries"]],
                             ["donchian_break", "atr_channel_break"])
            self.assertIn("chosen_f", payload["entries"][0]["report"])
            md = (out / "sizing.md").read_text()
            self.assertIn("donchian_break", md)
            self.assertIn("atr_channel_break", md)

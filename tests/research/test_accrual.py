# tests/test_accrual.py
import json
import tempfile
import unittest
from pathlib import Path

from moonface.research.accrual import (StreamStatus, newest_ts_from_jsonl,
                                       newest_ts_from_manifest, stream_status,
                                       worst_status)

HOUR = 3_600_000
NOW = 1_785_000_000_000


class TestStreamStatus(unittest.TestCase):
    def test_fresh_stream_is_ok(self):
        s = stream_status("v2.2", NOW - 2 * HOUR, NOW, max_age_hours=12)
        self.assertFalse(s.stale)
        self.assertAlmostEqual(s.age_hours, 2.0, places=3)
        self.assertEqual(s.level, "OK")

    def test_stream_past_its_threshold_is_stale(self):
        s = stream_status("v2.2", NOW - 20 * HOUR, NOW, max_age_hours=12)
        self.assertTrue(s.stale)
        self.assertEqual(s.level, "STALE")

    def test_boundary_is_not_stale(self):
        s = stream_status("v2.2", NOW - 12 * HOUR, NOW, max_age_hours=12)
        self.assertFalse(s.stale)

    def test_no_output_at_all_is_critical_not_merely_stale(self):
        """The failure mode that hid three times: a collector that was shipped
        or scheduled but never produced a single row. Age is undefined, so a
        threshold comparison cannot catch it — it needs its own level."""
        s = stream_status("deribit", None, NOW, max_age_hours=48)
        self.assertTrue(s.stale)
        self.assertEqual(s.level, "NO_OUTPUT")
        self.assertIsNone(s.age_hours)

    def test_future_timestamp_clamps_to_zero_age(self):
        s = stream_status("x", NOW + 5 * HOUR, NOW, max_age_hours=12)
        self.assertEqual(s.age_hours, 0.0)
        self.assertFalse(s.stale)


class TestWorstStatus(unittest.TestCase):
    def _s(self, level):
        return StreamStatus("n", None, None, 1.0, level != "OK", level)

    def test_all_ok_is_ok(self):
        self.assertEqual(worst_status([self._s("OK"), self._s("OK")]), "OK")

    def test_no_output_outranks_stale(self):
        self.assertEqual(
            worst_status([self._s("STALE"), self._s("NO_OUTPUT")]), "NO_OUTPUT")

    def test_stale_outranks_ok(self):
        self.assertEqual(
            worst_status([self._s("OK"), self._s("STALE")]), "STALE")

    def test_empty_is_ok(self):
        self.assertEqual(worst_status([]), "OK")


class TestReaders(unittest.TestCase):
    def test_newest_ts_from_jsonl_reads_the_last_row(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "j.jsonl"
            p.write_text("\n".join(json.dumps({"ts_ms": t})
                                   for t in (100, 200, 300)) + "\n")
            self.assertEqual(newest_ts_from_jsonl(p, "ts_ms"), 300)

    def test_newest_ts_from_jsonl_scans_all_rows_not_just_the_last(self):
        # journal rows are appended per candle close but a restart can
        # interleave; take the max, not the tail
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "j.jsonl"
            p.write_text("\n".join(json.dumps({"ts_ms": t})
                                   for t in (100, 900, 300)) + "\n")
            self.assertEqual(newest_ts_from_jsonl(p, "ts_ms"), 900)

    def test_newest_ts_from_jsonl_missing_file_is_none(self):
        self.assertIsNone(newest_ts_from_jsonl(Path("/nope/x.jsonl"), "ts_ms"))

    def test_newest_ts_from_jsonl_ignores_unparseable_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "j.jsonl"
            p.write_text('{"ts_ms": 100}\nnot json\n{"nots": 1}\n')
            self.assertEqual(newest_ts_from_jsonl(p, "ts_ms"), 100)

    def test_newest_ts_from_manifest_reads_collection_last_ts(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps({"collection": {"rows": 5,
                                                    "last_ts_ms": 777}}))
            self.assertEqual(newest_ts_from_manifest(p), 777)

    def test_manifest_with_zero_rows_reports_no_output(self):
        """Exactly the liquidation collector's 16-day state: manifest present
        and well-formed, rows 0. Must NOT be read as a timestamp of 0."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "manifest.json"
            p.write_text(json.dumps({"collection": {"rows": 0,
                                                    "last_ts_ms": 0}}))
            self.assertIsNone(newest_ts_from_manifest(p))

    def test_newest_ts_from_manifest_missing_file_is_none(self):
        self.assertIsNone(newest_ts_from_manifest(Path("/nope/manifest.json")))


class TestAccrualCheckCli(unittest.TestCase):
    """End-to-end over a fake repo root, so the wiring (paths, fields,
    thresholds, exit code) is covered and not just the pure core."""

    def _root(self, d, journal_ts=None, liq_rows=0, deribit_ts=None):
        root = Path(d)
        (root / "journal").mkdir(parents=True, exist_ok=True)
        if journal_ts is not None:
            (root / "journal" / "signals.jsonl").write_text(
                json.dumps({"candle_ts_ms": journal_ts}) + "\n")
        liq = root / "experiments/newdata/liquidations"
        liq.mkdir(parents=True, exist_ok=True)
        (liq / "manifest.json").write_text(json.dumps(
            {"collection": {"rows": liq_rows, "last_ts_ms": NOW - HOUR}}))
        der = root / "experiments/newdata/deribit_chain"
        der.mkdir(parents=True, exist_ok=True)
        if deribit_ts is not None:
            (der / "manifest.json").write_text(json.dumps(
                {"collection": {"rows": 10, "last_ts_ms": deribit_ts}}))
        return root

    def test_all_fresh_is_ok(self):
        from tools.accrual_check import collect
        with tempfile.TemporaryDirectory() as d:
            root = self._root(d, journal_ts=NOW - HOUR, liq_rows=5,
                              deribit_ts=NOW - HOUR)
            st = collect(root, NOW)
            self.assertEqual(worst_status(st), "OK")

    def test_reproduces_the_2026_07_29_audit(self):
        """The real state that day: journal 20 days behind, liquidations with
        rows:0, deribit 26 days behind."""
        from tools.accrual_check import collect
        with tempfile.TemporaryDirectory() as d:
            root = self._root(d, journal_ts=NOW - 20 * 24 * HOUR, liq_rows=0,
                              deribit_ts=NOW - 26 * 24 * HOUR)
            st = {s.name: s for s in collect(root, NOW)}
            self.assertEqual(st["confluence_v2.2_journal"].level, "STALE")
            self.assertEqual(st["liquidations_usdm"].level, "NO_OUTPUT")
            self.assertEqual(st["deribit_options_chain"].level, "STALE")
            self.assertEqual(worst_status(list(st.values())), "NO_OUTPUT")

    def test_missing_files_report_no_output_not_a_crash(self):
        from tools.accrual_check import collect
        with tempfile.TemporaryDirectory() as d:
            st = collect(Path(d), NOW)
            self.assertTrue(all(s.level == "NO_OUTPUT" for s in st))


if __name__ == "__main__":
    unittest.main()

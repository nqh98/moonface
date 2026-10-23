import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from moonface.collect.deribit_chain import (
    append_snapshot,
    collect_once,
    bucket_of,
    DAY_MS,
    HOUR_MS,
    csv_path,
    parse_book_summary,
    parse_instrument_name,
    snapshot_stats,
)
from moonface.research.newdata import assess_manifest, load_manifest


def _ts(year, month, day, hour=0):
    return int(dt.datetime(year, month, day, hour, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _payload(names_oi):
    return {"result": [
        {"instrument_name": name, "open_interest": oi, "mark_iv": 45.5,
         "underlying_price": 100_000.0}
        for name, oi in names_oi
    ]}


class TestInstrumentParse(unittest.TestCase):
    def test_expiry_strike_type(self):
        expiry_ms, strike, opt = parse_instrument_name("BTC-26DEC26-100000-C")
        self.assertEqual(
            expiry_ms,
            int(dt.datetime(2026, 12, 26, 8, tzinfo=dt.timezone.utc).timestamp() * 1000))
        self.assertEqual(strike, 100000.0)
        self.assertEqual(opt, "C")

    def test_single_digit_day_and_put(self):
        expiry_ms, strike, opt = parse_instrument_name("BTC-3JUL26-108500-P")
        self.assertEqual(
            expiry_ms,
            int(dt.datetime(2026, 7, 3, 8, tzinfo=dt.timezone.utc).timestamp() * 1000))
        self.assertEqual(strike, 108500.0)
        self.assertEqual(opt, "P")

    def test_decimal_strike_marker(self):
        _, strike, _ = parse_instrument_name("BTC-3JUL26-0d5-C")
        self.assertEqual(strike, 0.5)

    def test_malformed_names_raise(self):
        for bad in ("BTC-PERPETUAL", "BTC-3JUL26-100-X", "nonsense"):
            with self.assertRaises((ValueError, KeyError)):
                parse_instrument_name(bad)


class TestParseBookSummary(unittest.TestCase):
    def test_rows_stamped_sorted_and_skips_counted(self):
        payload = _payload([
            ("BTC-26DEC26-100000-C", 12.3),
            ("BTC-3JUL26-90000-P", 4.0),
            ("BTC-PERPETUAL", 0.0),  # unparseable → skipped, not fatal
        ])
        rows, skipped = parse_book_summary(payload, _ts(2026, 7, 3, 12))
        self.assertEqual(skipped, 1)
        self.assertEqual([r.symbol for r in rows],
                         ["BTC-3JUL26-90000-P", "BTC-26DEC26-100000-C"])
        self.assertTrue(all(r.ts_ms == _ts(2026, 7, 3, 12) for r in rows))
        self.assertEqual(rows[0].oi, 4.0)
        self.assertEqual(rows[0].iv, 45.5)
        self.assertEqual(rows[0].underlying_price, 100_000.0)

    def test_empty_payload(self):
        rows, skipped = parse_book_summary({"result": []}, 1)
        self.assertEqual((rows, skipped), ([], 0))


class TestCollectOnce(unittest.TestCase):
    def test_collects_once_per_utc_day_and_writes_manifest(self):
        payload = _payload([("BTC-26DEC26-100000-C", 12.3),
                            ("BTC-26DEC26-100000-P", 3.0)])
        calls = []

        def get_json(url):
            calls.append(url)
            return payload

        with tempfile.TemporaryDirectory() as tmp:
            first = collect_once(tmp, now_ms=_ts(2026, 7, 3, 0), get_json=get_json,
                                 cadence_ms=DAY_MS)
            self.assertEqual(first["status"], "collected")
            self.assertEqual(first["appended"], 2)

            again = collect_once(tmp, now_ms=_ts(2026, 7, 3, 12), get_json=get_json,
                                 cadence_ms=DAY_MS)
            self.assertEqual(again["status"], "already_collected")
            self.assertEqual(again["appended"], 0)
            self.assertEqual(len(calls), 1)  # no second network call same day

            nxt = collect_once(tmp, now_ms=_ts(2026, 7, 4, 0), get_json=get_json,
                               cadence_ms=DAY_MS)
            self.assertEqual(nxt["status"], "collected")

            stats = snapshot_stats(csv_path(tmp), cadence_ms=DAY_MS)
            self.assertEqual(stats["rows"], 4)
            self.assertEqual(stats["days"], 2)
            self.assertEqual(stats["history_days"], 2)
            self.assertEqual(stats["coverage_ratio"], 1.0)
            self.assertTrue(stats["monotonic_timestamps"])
            self.assertEqual(stats["duplicate_timestamp_ratio"], 0.0)

            manifest = load_manifest(Path(tmp) / "manifest.json")
            self.assertEqual(manifest["data_class"], "options_chain")
            self.assertEqual(manifest["symbols"], ["BTC"])
            verdict = assess_manifest(manifest)
            self.assertEqual(verdict["status"], "blocked")  # history < 180d for now
            self.assertEqual(verdict["failures"], ["history_days must be at least 180"])

    def test_empty_payload_appends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = collect_once(tmp, now_ms=_ts(2026, 7, 3),
                               get_json=lambda url: {"result": []})
            self.assertEqual(got["status"], "empty_payload")
            self.assertFalse(csv_path(tmp).exists())


class TestSnapshotStats(unittest.TestCase):
    def test_missing_file_is_empty(self):
        stats = snapshot_stats(Path("/nonexistent/chain_BTC.csv"))
        self.assertEqual(stats["rows"], 0)
        self.assertEqual(stats["coverage_ratio"], 0.0)

    def test_gap_lowers_coverage(self):
        payload = _payload([("BTC-26DEC26-100000-C", 1.0)])
        rows, _ = parse_book_summary(payload, _ts(2026, 7, 1))
        with tempfile.TemporaryDirectory() as tmp:
            path = csv_path(tmp)
            append_snapshot(path, rows)
            rows2, _ = parse_book_summary(payload, _ts(2026, 7, 4))
            append_snapshot(path, rows2)
            stats = snapshot_stats(path)
            self.assertEqual(stats["days"], 2)
            self.assertEqual(stats["history_days"], 4)
            self.assertEqual(stats["coverage_ratio"], 0.5)


class TestIntradayCadence(unittest.TestCase):
    """The collector was daily-only, which structurally cannot test an
    intraday dealer-hedging hypothesis: one snapshot per UTC day gives the
    gamma STATE once a day, never the flow within it. Cadence is now a
    parameter. See docs/findings/COLLECTOR_AUDIT_2026-07-29.md."""

    def _collector(self):
        calls = []
        payload = _payload([("BTC-26DEC26-100000-C", 1.0),
                            ("BTC-26DEC26-100000-P", 3.0)])

        def get_json(url):
            calls.append(url)
            return payload
        return calls, get_json

    def test_hourly_cadence_collects_each_hour(self):
        calls, get_json = self._collector()
        with tempfile.TemporaryDirectory() as tmp:
            a = collect_once(tmp, now_ms=_ts(2026, 7, 3, 0), get_json=get_json,
                             cadence_ms=HOUR_MS)
            b = collect_once(tmp, now_ms=_ts(2026, 7, 3, 1), get_json=get_json,
                             cadence_ms=HOUR_MS)
            self.assertEqual(a["status"], "collected")
            self.assertEqual(b["status"], "collected")
            self.assertEqual(len(calls), 2)

    def test_hourly_cadence_is_idempotent_within_the_hour(self):
        calls, get_json = self._collector()
        with tempfile.TemporaryDirectory() as tmp:
            collect_once(tmp, now_ms=_ts(2026, 7, 3, 0), get_json=get_json,
                         cadence_ms=HOUR_MS)
            again = collect_once(tmp, now_ms=_ts(2026, 7, 3, 0) + 59 * 60_000,
                                 get_json=get_json, cadence_ms=HOUR_MS)
            self.assertEqual(again["status"], "already_collected")
            self.assertEqual(len(calls), 1)  # no second network call

    def test_daily_cadence_still_available_and_unchanged(self):
        calls, get_json = self._collector()
        with tempfile.TemporaryDirectory() as tmp:
            collect_once(tmp, now_ms=_ts(2026, 7, 3, 0), get_json=get_json,
                         cadence_ms=DAY_MS)
            again = collect_once(tmp, now_ms=_ts(2026, 7, 3, 12),
                                 get_json=get_json, cadence_ms=DAY_MS)
            self.assertEqual(again["status"], "already_collected")
            self.assertEqual(len(calls), 1)

    def test_bucket_of_floors_to_the_cadence_grid(self):
        t = _ts(2026, 7, 3, 5) + 42 * 60_000
        self.assertEqual(bucket_of(t, HOUR_MS), _ts(2026, 7, 3, 5) // HOUR_MS)
        self.assertEqual(bucket_of(t, DAY_MS), _ts(2026, 7, 3, 0) // DAY_MS)

    def test_stats_report_buckets_without_breaking_the_day_gate(self):
        """history_days / coverage_ratio feed newdata.assess_manifest and must
        stay day-based; bucket metrics are additive."""
        _calls, get_json = self._collector()
        with tempfile.TemporaryDirectory() as tmp:
            for h in (0, 1, 2):
                collect_once(tmp, now_ms=_ts(2026, 7, 3, h),
                             get_json=get_json, cadence_ms=HOUR_MS)
            s = snapshot_stats(csv_path(tmp), cadence_ms=HOUR_MS)
            self.assertEqual(s["days"], 1)          # unchanged semantics
            self.assertEqual(s["history_days"], 1)
            self.assertEqual(s["coverage_ratio"], 1.0)
            self.assertEqual(s["buckets"], 3)       # new
            self.assertEqual(s["bucket_coverage_ratio"], 1.0)
            self.assertEqual(s["rows"], 6)
            self.assertTrue(s["monotonic_timestamps"])
            self.assertEqual(s["duplicate_timestamp_ratio"], 0.0)

    def test_manifest_cadence_reflects_reality(self):
        _calls, get_json = self._collector()
        with tempfile.TemporaryDirectory() as tmp:
            collect_once(tmp, now_ms=_ts(2026, 7, 3, 0), get_json=get_json,
                         cadence_ms=HOUR_MS)
            m = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(m["cadence_ms"], HOUR_MS)

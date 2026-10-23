import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from moonface.data.aggtrades import (
    export_window,
    fetch_aggsec_history,
    parse_aggtrades_day,
)

DAY_MS = 86_400_000

CSV_WITH_HEADER = (
    "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
    "1,100.0,0.5,1,1,1000,false\n"
    "2,100.5,0.2,2,2,1400,false\n"
    "3,99.5,1.0,3,3,1900,true\n"
    "4,99.0,0.1,4,5,2100,true\n"
)


def zip_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("day.csv", text)
    return buf.getvalue()


class TestParseAggtradesDay(unittest.TestCase):
    def test_reduces_trades_to_per_second_side_counts_and_last_price(self):
        rows = parse_aggtrades_day(io.StringIO(CSV_WITH_HEADER))

        self.assertEqual(
            rows,
            [
                (1000, 2, 1, 99.5),  # two buy aggressors, one sell; last print 99.5
                (2000, 0, 1, 99.0),
            ],
        )

    def test_handles_headerless_csv(self):
        headerless = "\n".join(CSV_WITH_HEADER.splitlines()[1:]) + "\n"

        rows = parse_aggtrades_day(io.StringIO(headerless))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], 1000)


class TestFetchAggsecHistory(unittest.TestCase):
    def test_walk_is_resumable_and_records_missing_days(self):
        day0 = 0
        payloads = {0: zip_bytes(CSV_WITH_HEADER), 2: zip_bytes(CSV_WITH_HEADER)}
        calls: list[int] = []

        def download(symbol, day_ms):
            calls.append(day_ms)
            return payloads.get(day_ms // DAY_MS)

        with tempfile.TemporaryDirectory() as tmp:
            now = 100 * DAY_MS  # every walked day is old -> 404 means missing
            stats = fetch_aggsec_history(
                "BTCUSDT", day0, 3 * DAY_MS, tmp, download=download, now_ms=now)

            self.assertEqual(stats["fetched_days"], 2)
            self.assertEqual(stats["missing_days"], 1)
            cache = Path(stats["cache"]).read_text().splitlines()
            self.assertEqual(cache[0], "ts_ms,symbol,buy_count,sell_count,last_price")
            self.assertEqual(len(cache), 5)  # 2 days x 2 active seconds

            calls.clear()
            again = fetch_aggsec_history(
                "BTCUSDT", day0, 3 * DAY_MS, tmp, download=download, now_ms=now)

            self.assertEqual(calls, [])  # ledger skips all recorded days
            self.assertEqual(again["fetched_days"], 0)

    def test_recent_archive_lag_stops_the_walk_without_marking_missing(self):
        def download(symbol, day_ms):
            return None

        with tempfile.TemporaryDirectory() as tmp:
            stats = fetch_aggsec_history(
                "BTCUSDT", 0, 2 * DAY_MS, tmp, download=download, now_ms=DAY_MS)

            self.assertEqual(stats["fetched_days"], 0)
            self.assertEqual(stats["missing_days"], 0)

    def test_export_window_slices_the_cache_stream(self):
        def download(symbol, day_ms):
            return zip_bytes(CSV_WITH_HEADER)

        with tempfile.TemporaryDirectory() as tmp:
            fetch_aggsec_history("BTCUSDT", 0, DAY_MS, tmp,
                                 download=download, now_ms=100 * DAY_MS)
            out = Path(tmp) / "window.csv"

            n = export_window("BTCUSDT", 0, 1500, tmp, out)

            lines = out.read_text().splitlines()
            self.assertEqual(n, 1)
            self.assertEqual(len(lines), 2)
            self.assertTrue(lines[1].startswith("1000,BTCUSDT,2,1,"))

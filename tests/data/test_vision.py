import tempfile
import unittest
from pathlib import Path

from moonface.data.vision import (
    MinuteBar,
    fetch_vision_1m,
    parse_vision_klines_csv,
)


class TestParseVisionKlinesCsv(unittest.TestCase):
    def test_parses_rows_and_normalizes_microsecond_timestamps(self):
        text = (
            "open_time,open,high,low,close,volume,close_time,quote_volume,"
            "trades,taker_base,taker_quote,ignore\n"
            "1704067200000123,100.0,101.0,99.5,100.5,12.5,1704067259999123,"
            "1256.25,42,6.0,603.0,0\n"
            "1704067260000,100.5,102.0,100.0,101.5,9.0,1704067319999,912.0,"
            "13,4.0,406.0,0\n"
        )

        self.assertEqual(
            parse_vision_klines_csv(text),
            [
                MinuteBar(
                    ts_ms=1704067200000,
                    open=100.0,
                    high=101.0,
                    low=99.5,
                    close=100.5,
                    base_volume=12.5,
                    quote_volume=1256.25,
                ),
                MinuteBar(
                    ts_ms=1704067260000,
                    open=100.5,
                    high=102.0,
                    low=100.0,
                    close=101.5,
                    base_volume=9.0,
                    quote_volume=912.0,
                ),
            ],
        )


class TestFetchVision1m(unittest.TestCase):
    def test_uses_month_cache_filters_range_dedupes_and_sorts(self):
        jan_csv = (
            "open_time,open,high,low,close,volume,close_time,quote_volume,"
            "trades,taker_base,taker_quote,ignore\n"
            "1704067260000000,100.5,102.0,100.0,101.5,9.0,1704067319999000,"
            "912.0,13,4.0,406.0,0\n"
            "1704067200000000,100.0,101.0,99.5,100.5,12.5,1704067259999000,"
            "1256.25,42,6.0,603.0,0\n"
            "1704067200000000,100.0,101.0,99.5,100.5,12.5,1704067259999000,"
            "1256.25,42,6.0,603.0,0\n"
        )
        feb_csv = (
            "open_time,open,high,low,close,volume,close_time,quote_volume,"
            "trades,taker_base,taker_quote,ignore\n"
            "1706745600000,102.0,103.0,101.5,102.5,7.5,1706745659999,765.0,"
            "19,3.0,306.0,0\n"
        )
        calls = []

        def download(symbol, year, month):
            calls.append((symbol, year, month))
            if (year, month) == (2024, 1):
                return jan_csv
            if (year, month) == (2024, 2):
                return feb_csv
            return None

        with tempfile.TemporaryDirectory() as tmp:
            bars = fetch_vision_1m(
                "BTCUSDT",
                1704067200000,
                1706832000000,
                tmp,
                download=download,
            )
            self.assertEqual(
                bars,
                [
                    MinuteBar(1704067200000, 100.0, 101.0, 99.5, 100.5, 12.5, 1256.25),
                    MinuteBar(1704067260000, 100.5, 102.0, 100.0, 101.5, 9.0, 912.0),
                    MinuteBar(1706745600000, 102.0, 103.0, 101.5, 102.5, 7.5, 765.0),
                ],
            )
            self.assertEqual(calls, [("BTCUSDT", 2024, 1), ("BTCUSDT", 2024, 2)])

            cached = fetch_vision_1m(
                "BTCUSDT",
                1706745600000,
                1706749200000,
                tmp,
                download=download,
            )
            self.assertEqual(cached, [MinuteBar(1706745600000, 102.0, 103.0, 101.5, 102.5, 7.5, 765.0)])
            self.assertEqual(calls, [("BTCUSDT", 2024, 1), ("BTCUSDT", 2024, 2)])

    def test_caches_absent_months_as_empty_results(self):
        calls = []

        def download(symbol, year, month):
            calls.append((symbol, year, month))
            return None

        with tempfile.TemporaryDirectory() as tmp:
            bars = fetch_vision_1m(
                "BTCUSDT",
                1704067200000,
                1704067260000,
                tmp,
                download=download,
            )
            self.assertEqual(bars, [])
            self.assertEqual(calls, [("BTCUSDT", 2024, 1)])

            cached = fetch_vision_1m(
                "BTCUSDT",
                1704067200000,
                1704067260000,
                tmp,
                download=download,
            )
            self.assertEqual(cached, [])
            self.assertEqual(calls, [("BTCUSDT", 2024, 1)])

    def test_stale_empty_cache_without_marker_is_refreshed(self):
        calls = []

        def download(symbol, year, month):
            calls.append((symbol, year, month))
            return (
                "open_time,open,high,low,close,volume,close_time,quote_volume,"
                "trades,taker_base,taker_quote,ignore\n"
                "1704067200000000,100.0,101.0,99.5,100.5,12.5,1704067259999000,"
                "1256.25,42,6.0,603.0,0\n"
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BTCUSDT" / "2024-01.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

            bars = fetch_vision_1m(
                "BTCUSDT",
                1704067200000,
                1704067260000,
                tmp,
                download=download,
            )
            self.assertEqual(len(bars), 1)
            self.assertEqual(calls, [("BTCUSDT", 2024, 1)])
            self.assertTrue((path.with_suffix(".csv.ok")).exists())

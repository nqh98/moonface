# tests/test_universe_data.py
import re
import tempfile
import unittest

from moonface.data.universe import (DailyRow, load_daily_cache,
                                             parse_klines_payload,
                                             parse_symbol_listing,
                                             save_daily_cache)

_LISTING_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>data.binance.vision</Name>
  <Prefix>data/futures/um/monthly/klines/</Prefix>
  <IsTruncated>false</IsTruncated>
  <CommonPrefixes><Prefix>data/futures/um/monthly/klines/BTCUSDT/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/futures/um/monthly/klines/ETHUSDT/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/futures/um/monthly/klines/FTTUSDT/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/futures/um/monthly/klines/BTCUSDT_230929/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/futures/um/monthly/klines/ETHBUSD/</Prefix></CommonPrefixes>
  <CommonPrefixes><Prefix>data/futures/um/monthly/klines/BTCDOMUSDT/</Prefix></CommonPrefixes>
</ListBucketResult>"""


class TestParsers(unittest.TestCase):
    def test_symbol_listing_keeps_usdt_perps_only(self):
        symbols, truncated, marker = parse_symbol_listing(_LISTING_XML)
        # delisted FTT stays (survivorship-clean); dated futures and BUSD
        # pairs are not perpetuals; BTCDOMUSDT is an index product
        self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT", "FTTUSDT",
                                   "BTCDOMUSDT"])
        self.assertFalse(truncated)
        self.assertIsNone(marker)

    def test_symbol_listing_reports_truncation_marker(self):
        xml = _LISTING_XML.replace(
            "<IsTruncated>false</IsTruncated>",
            "<IsTruncated>true</IsTruncated>"
            "<NextMarker>data/futures/um/monthly/klines/M/</NextMarker>")
        _, truncated, marker = parse_symbol_listing(xml)
        self.assertTrue(truncated)
        self.assertEqual(marker, "data/futures/um/monthly/klines/M/")

    def test_parse_klines_payload(self):
        payload = [
            [1700000000000, "100.0", "110.0", "90.0", "105.0", "1234.5",
             1700086399999, "129622.5", 100, "600.0", "63000.0", "0"],
            [1700086400000, "105.0", "112.0", "101.0", "110.0", "2000.0",
             1700172799999, "215000.0", 120, "900.0", "97000.0", "0"],
        ]
        rows = parse_klines_payload(payload)
        self.assertEqual(rows, [
            DailyRow(ts_ms=1700000000000, close=105.0, quote_volume=129622.5),
            DailyRow(ts_ms=1700086400000, close=110.0, quote_volume=215000.0),
        ])

    def test_daily_cache_round_trip(self):
        rows = [DailyRow(1700000000000, 105.0, 129622.5),
                DailyRow(1700086400000, 110.0, 215000.0)]
        with tempfile.TemporaryDirectory() as tmp:
            save_daily_cache(tmp, "BTCUSDT", rows)
            self.assertEqual(load_daily_cache(tmp, "BTCUSDT"), rows)
            self.assertIsNone(load_daily_cache(tmp, "ETHUSDT"))


class TestRetry(unittest.TestCase):
    def test_transient_errors_are_retried(self):
        import urllib.error

        from moonface.data.universe import retrying
        attempts = []

        def flaky(url):
            attempts.append(url)
            if len(attempts) < 3:
                raise urllib.error.URLError("handshake timed out")
            return "ok"

        self.assertEqual(retrying(flaky, sleep=lambda _s: None)("u"), "ok")
        self.assertEqual(len(attempts), 3)

    def test_http_errors_are_not_retried(self):
        import io
        import urllib.error

        from moonface.data.universe import retrying
        attempts = []

        def bad_request(url):
            attempts.append(url)
            raise urllib.error.HTTPError(url, 400, "Bad Request", None,
                                         io.BytesIO(b'{"code":-1121}'))

        with self.assertRaises(urllib.error.HTTPError):
            retrying(bad_request, sleep=lambda _s: None)("u")
        self.assertEqual(len(attempts), 1)

    def test_persistent_errors_raise_after_max_attempts(self):
        import urllib.error

        from moonface.data.universe import retrying

        def dead(url):
            raise urllib.error.URLError("down")

        with self.assertRaises(urllib.error.URLError):
            retrying(dead, sleep=lambda _s: None)("u")


class TestFetchers(unittest.TestCase):
    def test_list_symbols_follows_truncation_marker(self):
        from moonface.data.universe import list_um_perp_symbols
        page1 = _LISTING_XML.replace(
            "<IsTruncated>false</IsTruncated>",
            "<IsTruncated>true</IsTruncated>"
            "<NextMarker>data/futures/um/monthly/klines/M/</NextMarker>")
        page2 = _LISTING_XML.replace("BTCUSDT", "SOLUSDT")
        calls = []

        def get_text(url):
            calls.append(url)
            return page2 if "marker=" in url else page1

        symbols = list_um_perp_symbols(get_text=get_text)
        self.assertEqual(len(calls), 2)
        self.assertIn("marker=data/futures/um/monthly/klines/M/", calls[1])
        self.assertEqual(symbols, ["BTCDOMUSDT", "BTCUSDT", "ETHUSDT",
                                   "FTTUSDT", "SOLUSDT"])

    def test_fetch_daily_klines_caches_and_filters(self):
        from moonface.data.universe import fetch_daily_klines
        day = 86_400_000
        payload = [[i * day, "1", "1", "1", str(100 + i), "10",
                    (i + 1) * day - 1, str(1000.0 * i), 1, "5", "500", "0"]
                   for i in range(3)]
        calls = []

        def get_json(url):
            calls.append(url)
            return payload

        with tempfile.TemporaryDirectory() as tmp:
            rows = fetch_daily_klines("BTCUSDT", 0, 3 * day, tmp,
                                      get_json=get_json)
            self.assertEqual(len(rows), 3)
            self.assertEqual(len(calls), 1)
            # second call is served from cache, window-filtered
            again = fetch_daily_klines("BTCUSDT", day, 2 * day, tmp,
                                       get_json=get_json)
            self.assertEqual(len(calls), 1)
            self.assertEqual(again, [DailyRow(day, 101.0, 1000.0)])

    def test_get_json_parses_http_error_bodies(self):
        import io
        import urllib.error
        from unittest import mock

        from moonface.data import universe as universe_data

        def raise_400(url):
            raise urllib.error.HTTPError(url, 400, "Bad Request", None,
                                         io.BytesIO(b'{"code":-1121}'))

        with mock.patch.object(universe_data, "_get_text", raise_400):
            self.assertEqual(universe_data._get_json("u"), {"code": -1121})

    def test_fetch_daily_klines_treats_api_error_as_empty(self):
        from moonface.data.universe import fetch_daily_klines
        calls = []

        def get_json(url):
            calls.append(url)
            return {"code": -1121, "msg": "Invalid symbol."}

        with tempfile.TemporaryDirectory() as tmp:
            rows = fetch_daily_klines("GONEUSDT", 0, 86_400_000, tmp,
                                      get_json=get_json)
            self.assertEqual(rows, [])
            # the empty result is cached, no second request
            fetch_daily_klines("GONEUSDT", 0, 86_400_000, tmp,
                               get_json=get_json)
            self.assertEqual(len(calls), 1)

    def test_fetch_funding_paginates_and_caches(self):
        from moonface.data.universe import fetch_funding_rates
        page1 = [{"fundingTime": i, "fundingRate": "0.0001"}
                 for i in range(1000)]
        page2 = [{"fundingTime": 1000 + i, "fundingRate": "0.0002"}
                 for i in range(5)]
        calls = []

        def get_json(url):
            calls.append(url)
            return page1 if len(calls) == 1 else page2

        with tempfile.TemporaryDirectory() as tmp:
            points = fetch_funding_rates("BTCUSDT", 0, 2000, tmp,
                                         get_json=get_json)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(points), 1005)
            self.assertEqual(points[-1], (1004, 0.0002))
            # cached on the second call
            again = fetch_funding_rates("BTCUSDT", 0, 1000, tmp,
                                        get_json=get_json)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(again), 1000)


class TestFetchPerpCandles(unittest.TestCase):
    def test_fetches_caches_and_tolerates_errors(self):
        from moonface.data.universe import fetch_perp_candles
        h4 = 4 * 3_600_000
        payload = [[i * h4, "10", "12", "9", "11", "100",
                    (i + 1) * h4 - 1, "1100", 5, "50", "550", "0"]
                   for i in range(3)]
        calls = []

        def get_json(url):
            calls.append(url)
            return payload if "GONE" not in url else {"code": -1121}

        with tempfile.TemporaryDirectory() as tmp:
            candles = fetch_perp_candles("AVAXUSDT", "4h", 0, 3 * h4, tmp,
                                         get_json=get_json)
            self.assertEqual(len(candles), 3)
            self.assertEqual(candles[1].timestamp_ms, h4)
            self.assertEqual(candles[1].close, 11.0)
            # served from the OhlcvCache file on the second call
            again = fetch_perp_candles("AVAXUSDT", "4h", 0, 3 * h4, tmp,
                                       get_json=get_json)
            self.assertEqual(len(calls), 1)
            self.assertEqual(again, candles)
            self.assertEqual(
                fetch_perp_candles("GONEUSDT", "4h", 0, 3 * h4, tmp,
                                   get_json=get_json), [])


_H4 = 4 * 3_600_000
_DAY = 86_400_000


def _perp_source(lo=0, hi=15):
    """Faithful get_json for 4h klines over a fixed universe [lo, hi); returns
    only bars whose ts falls in the URL's [startTime, endTime], like fapi."""
    calls = []

    def get_json(url):
        calls.append(url)
        m = re.search(r"startTime=(\d+)&endTime=(\d+)", url)
        s, e = int(m.group(1)), int(m.group(2))
        out = []
        for i in range(lo, hi):
            ts = i * _H4
            if s <= ts <= e:
                out.append([ts, "10", "12", "9", str(100 + i), "100",
                            ts + _H4 - 1, "1100", 5, "50", "550", "0"])
        return out

    return get_json, calls


def _daily_source(lo=0, hi=15):
    calls = []

    def get_json(url):
        calls.append(url)
        m = re.search(r"startTime=(\d+)&endTime=(\d+)", url)
        s, e = int(m.group(1)), int(m.group(2))
        out = []
        for i in range(lo, hi):
            ts = i * _DAY
            if s <= ts <= e:
                out.append([ts, "1", "1", "1", str(100 + i), "10",
                            ts + _DAY - 1, str(1000.0 * i), 1, "5", "500", "0"])
        return out

    return get_json, calls


class TestKlineBackfill(unittest.TestCase):
    def test_perp_backfills_older_than_cache(self):
        from moonface.data.universe import fetch_perp_candles
        gj, _ = _perp_source(0, 15)
        with tempfile.TemporaryDirectory() as tmp:
            first = fetch_perp_candles("BTCUSDT", "4h", 5 * _H4, 15 * _H4, tmp,
                                       get_json=gj)
            self.assertEqual([c.timestamp_ms for c in first],
                             [i * _H4 for i in range(5, 15)])
            wide = fetch_perp_candles("BTCUSDT", "4h", 0, 15 * _H4, tmp,
                                      get_json=gj)
            self.assertEqual([c.timestamp_ms for c in wide],
                             [i * _H4 for i in range(15)])
            self.assertEqual(wide[0].close, 100.0)

    def test_perp_backfills_newer_than_cache(self):
        from moonface.data.universe import fetch_perp_candles
        gj, _ = _perp_source(0, 15)
        with tempfile.TemporaryDirectory() as tmp:
            fetch_perp_candles("BTCUSDT", "4h", 0, 10 * _H4, tmp, get_json=gj)
            wide = fetch_perp_candles("BTCUSDT", "4h", 0, 15 * _H4, tmp,
                                      get_json=gj)
            self.assertEqual([c.timestamp_ms for c in wide],
                             [i * _H4 for i in range(15)])

    def test_perp_legacy_cache_without_sidecar_backfills(self):
        # THE eventtime scenario: a pre-existing cache with no .cov sidecar,
        # then a wider (older) request must self-heal instead of truncating.
        from moonface.data.ohlcv import OhlcvCache
        from moonface.core.models import Candle
        from moonface.data.universe import fetch_perp_candles
        with tempfile.TemporaryDirectory() as tmp:
            OhlcvCache(tmp).save(
                "BTCUSDT", "4h",
                [Candle(i * _H4, 10.0, 12.0, 9.0, 100.0 + i, 100.0)
                 for i in range(5, 15)])
            gj, _ = _perp_source(0, 15)
            wide = fetch_perp_candles("BTCUSDT", "4h", 0, 15 * _H4, tmp,
                                      get_json=gj)
            self.assertEqual([c.timestamp_ms for c in wide],
                             [i * _H4 for i in range(15)])

    def test_perp_remembers_empty_pre_listing_and_no_refetch(self):
        # Symbol has no data before 5*_H4; a request from 0 backfills once,
        # records the widened coverage, and never re-requests the empty window.
        from moonface.data.universe import fetch_perp_candles
        gj, calls = _perp_source(5, 15)   # universe starts at 5*_H4
        with tempfile.TemporaryDirectory() as tmp:
            fetch_perp_candles("BTCUSDT", "4h", 5 * _H4, 15 * _H4, tmp,
                               get_json=gj)
            fetch_perp_candles("BTCUSDT", "4h", 0, 15 * _H4, tmp, get_json=gj)
            n_after_backfill = len(calls)
            out = fetch_perp_candles("BTCUSDT", "4h", 0, 15 * _H4, tmp,
                                     get_json=gj)
            self.assertEqual(len(calls), n_after_backfill)  # no re-fetch
            self.assertEqual([c.timestamp_ms for c in out],
                             [i * _H4 for i in range(5, 15)])

    def test_daily_backfills_older_than_cache(self):
        from moonface.data.universe import fetch_daily_klines
        gj, _ = _daily_source(0, 15)
        with tempfile.TemporaryDirectory() as tmp:
            fetch_daily_klines("BTCUSDT", 5 * _DAY, 15 * _DAY, tmp,
                               get_json=gj)
            wide = fetch_daily_klines("BTCUSDT", 0, 15 * _DAY, tmp,
                                      get_json=gj)
            self.assertEqual([r.ts_ms for r in wide],
                             [i * _DAY for i in range(15)])


if __name__ == "__main__":
    unittest.main()

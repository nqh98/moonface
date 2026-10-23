from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from unittest import mock


class FundingCacheTest(unittest.TestCase):
    def test_round_trip(self) -> None:
        from moonface.data.series import FundingCache
        with TemporaryDirectory() as d:
            cache = FundingCache(d)
            points = [(0, 0.0001), (28_800_000, -0.0002)]
            cache.save("BTC/USDT:USDT", points)
            self.assertEqual(cache.load("BTC/USDT:USDT"), points)

    def test_load_missing_is_none(self) -> None:
        from moonface.data.series import FundingCache
        with TemporaryDirectory() as d:
            self.assertIsNone(FundingCache(d).load("BTC/USDT:USDT"))


class FetchFundingHistoryTest(unittest.TestCase):
    def test_cache_hit_filters_without_network(self) -> None:
        # Cache present -> returns range-filtered points and never touches ccxt.
        from moonface.data.series import FundingCache, fetch_funding_history
        with TemporaryDirectory() as d:
            cache = FundingCache(d)
            cache.save("BTC/USDT:USDT",
                       [(0, 0.0001), (10, 0.0002), (20, 0.0003)])
            out = fetch_funding_history(
                "binance", "BTC/USDT:USDT", start_ms=10, end_ms=20, cache=cache)
            self.assertEqual(out, [(10, 0.0002)])


class AlignFundingTest(unittest.TestCase):
    def _candle(self, ts: int):
        from moonface.core.models import Candle
        return Candle(timestamp_ms=ts, open=1.0, high=1.0, low=1.0,
                      close=1.0, volume=0.0)

    def test_strict_as_of_no_lookahead(self) -> None:
        from moonface.data.series import align_funding
        # A point settled exactly at the bar open is known; one a ms later is NOT.
        candles = [self._candle(1000)]
        points = [(1000, 0.01), (1001, 0.02)]
        self.assertEqual(align_funding(candles, points), [0.01])

    def test_pre_history_is_none(self) -> None:
        from moonface.data.series import align_funding
        candles = [self._candle(999)]
        points = [(1000, 0.01)]
        self.assertEqual(align_funding(candles, points), [None])

    def test_8h_funding_spans_two_4h_bars(self) -> None:
        from moonface.data.series import align_funding
        h4 = 14_400_000
        f8 = 28_800_000
        candles = [self._candle(0), self._candle(h4),
                   self._candle(f8), self._candle(f8 + h4)]
        points = [(0, 0.01), (f8, 0.02)]
        self.assertEqual(align_funding(candles, points), [0.01, 0.01, 0.02, 0.02])

    def test_empty_points_all_none(self) -> None:
        from moonface.data.series import align_funding
        self.assertEqual(align_funding([self._candle(0), self._candle(1)], []),
                         [None, None])


_8H = 8 * 3_600_000


def test_fetch_funding_history_refreshes_stale_cache_head(tmp_path):
    from moonface.data.series import FundingCache, fetch_funding_history
    cache = FundingCache(str(tmp_path))
    cache.save("BTC/USDT:USDT", [(i * _8H, 0.0001) for i in range(10)])
    fresh_rows = [{"timestamp": ts, "fundingRate": 0.0002}
                  for ts in range(10 * _8H, 15 * _8H, _8H)]
    fake_ex = mock.Mock()
    fake_ex.fetch_funding_rate_history.return_value = fresh_rows
    with mock.patch("moonface.data.series.ccxt") as fake_ccxt:
        fake_ccxt.binance = mock.Mock(return_value=fake_ex)
        out = fetch_funding_history("binance", "BTC/USDT:USDT",
                                    0, 15 * _8H, cache)
    assert len(out) == 15
    assert out[-1] == (14 * _8H, 0.0002)
    assert len(cache.load("BTC/USDT:USDT")) == 15


def test_fetch_funding_history_backfills_older_than_cache(tmp_path):
    # Cache starts at 5*_8H; a request from 0 must backfill the missing older
    # window [0, 5*_8H) from the exchange, prepend it, and persist.
    from moonface.data.series import FundingCache, fetch_funding_history
    cache = FundingCache(str(tmp_path))
    cache.save("BTC/USDT:USDT", [(i * _8H, 0.0001) for i in range(5, 15)])
    older_rows = [{"timestamp": i * _8H, "fundingRate": 0.0003}
                  for i in range(5)]
    fake_ex = mock.Mock()
    fake_ex.fetch_funding_rate_history.return_value = older_rows
    with mock.patch("moonface.data.series.ccxt") as fake_ccxt:
        fake_ccxt.binance = mock.Mock(return_value=fake_ex)
        out = fetch_funding_history("binance", "BTC/USDT:USDT",
                                    0, 15 * _8H, cache)
    assert [ts for ts, _ in out] == [i * _8H for i in range(15)]
    assert out[0] == (0, 0.0003)          # older value carried through
    assert out[5] == (5 * _8H, 0.0001)    # boundary: original cache preserved
    assert cache.load("BTC/USDT:USDT")[0] == (0, 0.0003)  # persisted


def test_fetch_funding_history_no_backfill_when_cache_covers(tmp_path):
    # start_ms >= cache start AND head covered -> the exchange is never touched
    # (proves the backward-backfill branch is strictly additive).
    from moonface.data.series import FundingCache, fetch_funding_history
    cache = FundingCache(str(tmp_path))
    cache.save("BTC/USDT:USDT", [(i * _8H, 0.0001) for i in range(10)])
    with mock.patch("moonface.data.series.ccxt") as fake_ccxt:
        fake_ccxt.binance = mock.Mock(side_effect=AssertionError("no network"))
        out = fetch_funding_history("binance", "BTC/USDT:USDT",
                                    2 * _8H, 8 * _8H, cache)
    assert [ts for ts, _ in out] == [i * _8H for i in range(2, 8)]

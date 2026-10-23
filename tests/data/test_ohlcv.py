from __future__ import annotations

import unittest
from unittest import mock

from moonface.data.ohlcv import OhlcvCache, TIMEFRAME_MS, fetch_history, align_to_h1, paginate_ranges
from moonface.core.models import Candle

H4 = TIMEFRAME_MS["4h"]


def _candle(ts, price=100.0):
    return Candle(ts, price, price, price, price, 1.0)


class PaginateRangesTest(unittest.TestCase):
    def test_splits_into_pages(self) -> None:
        # 3 pages of 1000 bars at 1h, starting at t0.
        start = 0
        pages = paginate_ranges(start_ms=start, end_ms=start + 2500 * 3_600_000,
                                timeframe_ms=3_600_000, page_limit=1000)
        self.assertEqual(len(pages), 3)
        self.assertEqual(pages[0], 0)
        self.assertEqual(pages[1], 1000 * 3_600_000)


class AlignTest(unittest.TestCase):
    def test_align_returns_only_closed_htf_candles(self) -> None:
        # one H4 candle opened at t=0 closes at t=4h; at H1 index for t=3h it is NOT closed.
        from moonface.core.models import Candle

        def c(ts: int, close: float) -> Candle:
            return Candle(ts, close, close + 1, close - 1, close, 1.0)

        h4 = [c(0, 100), c(4 * 3_600_000, 110)]
        # current H1 open time = 3h -> only htf candle fully closed before 3h: none
        closed = align_to_h1(h4, current_open_ms=3 * 3_600_000, timeframe_ms=4 * 3_600_000)
        self.assertEqual(closed, [])
        # current H1 open time = 5h -> first H4 candle (closes at 4h) is closed
        closed = align_to_h1(h4, current_open_ms=5 * 3_600_000, timeframe_ms=4 * 3_600_000)
        self.assertEqual(len(closed), 1)


def test_fetch_history_refreshes_stale_cache_head(tmp_path):
    cache = OhlcvCache(str(tmp_path))
    cached = [_candle(i * H4) for i in range(10)]          # ends at bar 9
    cache.save("BTC/USDT", "4h", cached)
    fresh_rows = [[ts, 1.0, 1.0, 1.0, 1.0, 1.0]
                  for ts in range(10 * H4, 15 * H4, H4)]   # bars 10..14
    fake_ex = mock.Mock()
    fake_ex.fetch_ohlcv.return_value = fresh_rows
    with mock.patch("moonface.data.ohlcv.ccxt") as fake_ccxt:
        fake_ccxt.binance = mock.Mock(return_value=fake_ex)
        out = fetch_history("binance", "BTC/USDT", "4h", 0, 15 * H4, cache)
    assert len(out) == 15
    assert out[-1].timestamp_ms == 14 * H4
    # and the cache itself was extended:
    assert len(cache.load("BTC/USDT", "4h")) == 15


def test_fetch_history_serves_fresh_cache_without_network(tmp_path):
    cache = OhlcvCache(str(tmp_path))
    cache.save("BTC/USDT", "4h", [_candle(i * H4) for i in range(10)])
    with mock.patch("moonface.data.ohlcv.ccxt") as fake_ccxt:
        out = fetch_history("binance", "BTC/USDT", "4h", 0, 10 * H4, cache)
        fake_ccxt.assert_not_called()
    assert len(out) == 10

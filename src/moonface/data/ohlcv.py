from __future__ import annotations

import csv
import os
from dataclasses import dataclass

import ccxt

from moonface.core.models import Candle

TIMEFRAME_MS = {
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 4 * 3_600_000,
    "1d": 86_400_000,
    "1w": 7 * 86_400_000,
}

# Milliseconds per candle keyed by the advisor's timeframe labels.
TF_MS = {
    "H1": 3_600_000,
    "H4": 4 * 3_600_000,
    "D1": 86_400_000,
    "W1": 7 * 86_400_000,
}


def paginate_ranges(start_ms: int, end_ms: int, timeframe_ms: int, page_limit: int) -> list[int]:
    step = page_limit * timeframe_ms
    starts: list[int] = []
    cursor = start_ms
    while cursor < end_ms:
        starts.append(cursor)
        cursor += step
    return starts


def align_to_h1(htf: list[Candle], current_open_ms: int, timeframe_ms: int) -> list[Candle]:
    """Return only HTF candles that have fully closed by `current_open_ms` (no look-ahead)."""
    return [c for c in htf if c.timestamp_ms + timeframe_ms <= current_open_ms]


@dataclass
class OhlcvCache:
    directory: str

    def path(self, symbol: str, timeframe: str) -> str:
        safe = symbol.replace("/", "_")
        return os.path.join(self.directory, f"{safe}_{timeframe}.csv")

    def load(self, symbol: str, timeframe: str) -> list[Candle] | None:
        path = self.path(symbol, timeframe)
        if not os.path.exists(path):
            return None
        rows: list[Candle] = []
        with open(path, newline="") as handle:
            for row in csv.reader(handle):
                rows.append(Candle.from_ccxt([float(x) for x in row]))
        return rows

    def save(self, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        os.makedirs(self.directory, exist_ok=True)
        with open(self.path(symbol, timeframe), "w", newline="") as handle:
            writer = csv.writer(handle)
            for c in candles:
                writer.writerow([c.timestamp_ms, c.open, c.high, c.low, c.close, c.volume])


def fetch_history(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    cache: OhlcvCache | None = None,
    page_limit: int = 1000,
) -> list[Candle]:
    if cache is not None:
        cached = cache.load(symbol, timeframe)
        if cached:
            tf_ms = TIMEFRAME_MS[timeframe]
            head_start = cached[-1].timestamp_ms + tf_ms
            if head_start <= end_ms - tf_ms:  # last full candle is missing
                fresh = fetch_history(exchange_name, symbol, timeframe,
                                      head_start, end_ms, cache=None,
                                      page_limit=page_limit)
                fresh = [c for c in fresh
                         if c.timestamp_ms >= head_start]
                if fresh:
                    cached = cached + fresh
                    cache.save(symbol, timeframe, cached)
            return [c for c in cached if start_ms <= c.timestamp_ms < end_ms]
    exchange = getattr(ccxt, exchange_name)({"enableRateLimit": True})
    tf_ms = TIMEFRAME_MS[timeframe]
    candles: list[Candle] = []
    for page_start in paginate_ranges(start_ms, end_ms, tf_ms, page_limit):
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=page_start, limit=page_limit)
        for row in rows:
            if row[0] >= end_ms:
                break
            candles.append(Candle.from_ccxt(row))
    candles.sort(key=lambda c: c.timestamp_ms)
    deduped: list[Candle] = []
    seen: set[int] = set()
    for c in candles:
        if c.timestamp_ms not in seen:
            seen.add(c.timestamp_ms)
            deduped.append(c)
    if cache is not None:
        cache.save(symbol, timeframe, deduped)
    return deduped

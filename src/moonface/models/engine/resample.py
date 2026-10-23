# src/moonface/signal/engine/resample.py
from __future__ import annotations

from moonface.data.ohlcv import TIMEFRAME_MS
from moonface.core.models import Candle

_HOUR_MS = TIMEFRAME_MS["1h"]
_WEEK_ANCHOR_MS = 345_600_000
_WEEK_MS = TIMEFRAME_MS["1w"]

_SUPPORTED_TF = {"4h", "1d", "1w"}


def _bucket_start(timestamp_ms: int, tf: str) -> int:
    if tf == "1w":
        return ((timestamp_ms - _WEEK_ANCHOR_MS) // _WEEK_MS) * _WEEK_MS + _WEEK_ANCHOR_MS
    timeframe_ms = TIMEFRAME_MS[tf]
    return (timestamp_ms // timeframe_ms) * timeframe_ms


def _closed_bar_count(tf: str) -> int:
    return TIMEFRAME_MS[tf] // _HOUR_MS


def resample(candles_1h: list[Candle], tf: str) -> list[Candle]:
    if tf not in _SUPPORTED_TF:
        raise ValueError(f"Unsupported timeframe: {tf}")

    groups: dict[int, list[Candle]] = {}
    order: list[int] = []
    for candle in candles_1h:
        start = _bucket_start(candle.timestamp_ms, tf)
        if start not in groups:
            groups[start] = []
            order.append(start)
        groups[start].append(candle)

    expected = _closed_bar_count(tf)
    out: list[Candle] = []
    for start in order:
        bars = groups[start]
        if len(bars) < expected:
            continue
        out.append(Candle(
            timestamp_ms=start,
            open=bars[0].open,
            high=max(bar.high for bar in bars),
            low=min(bar.low for bar in bars),
            close=bars[-1].close,
            volume=sum(bar.volume for bar in bars),
        ))
    return out


def resample_to_4h(candles_1h: list[Candle]) -> list[Candle]:
    return resample(candles_1h, "4h")

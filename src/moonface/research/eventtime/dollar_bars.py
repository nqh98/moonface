"""Dollar-bar helpers built from minute-level Vision klines."""
from __future__ import annotations

from statistics import median

from moonface.core.models import Candle
from moonface.research.eventtime.vision_klines import MinuteBar


def rolling_dollar_volume(minutes: list[MinuteBar], window_min: int = 240) -> list[float]:
    if window_min <= 0:
        raise ValueError("window_min must be positive")
    if len(minutes) < window_min:
        return []

    out: list[float] = []
    running = 0.0
    window: list[float] = []
    for bar in minutes:
        running += bar.quote_volume
        window.append(bar.quote_volume)
        if len(window) > window_min:
            running -= window.pop(0)
        if len(window) == window_min:
            out.append(running)
    return out


def calibrate_bar_size(
    minutes: list[MinuteBar],
    calib_start_ms: int,
    calib_end_ms: int,
    window_min: int = 240,
) -> float:
    if calib_end_ms <= calib_start_ms:
        raise ValueError("calib_end_ms must be greater than calib_start_ms")

    calib_minutes = [
        bar
        for bar in minutes
        if calib_start_ms <= bar.ts_ms < calib_end_ms
    ]
    volumes = rolling_dollar_volume(calib_minutes, window_min=window_min)
    if not volumes:
        raise ValueError("no full window exists in calibration range")
    return float(median(volumes))


def build_dollar_bars(minutes: list[MinuteBar], dollar_threshold: float) -> list[Candle]:
    if dollar_threshold <= 0:
        raise ValueError("dollar_threshold must be positive")

    bars = sorted(minutes, key=lambda bar: bar.ts_ms)
    out: list[Candle] = []

    bucket_start: MinuteBar | None = None
    bucket_high = 0.0
    bucket_low = 0.0
    bucket_close = 0.0
    bucket_quote_volume = 0.0
    bucket_base_volume = 0.0

    for bar in bars:
        if bucket_start is None:
            bucket_start = bar
            bucket_high = bar.high
            bucket_low = bar.low
            bucket_close = bar.close
            bucket_quote_volume = 0.0
            bucket_base_volume = 0.0

        bucket_high = max(bucket_high, bar.high)
        bucket_low = min(bucket_low, bar.low)
        bucket_close = bar.close
        bucket_quote_volume += bar.quote_volume
        bucket_base_volume += bar.base_volume

        if bucket_quote_volume >= dollar_threshold:
            out.append(
                Candle(
                    timestamp_ms=bucket_start.ts_ms,
                    open=bucket_start.open,
                    high=bucket_high,
                    low=bucket_low,
                    close=bucket_close,
                    volume=bucket_base_volume,
                )
            )
            bucket_start = None

    return out

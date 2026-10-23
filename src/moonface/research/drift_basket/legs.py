from __future__ import annotations

from statistics import pstdev

from moonface.core.indicators import donchian_channel
from moonface.core.models import Candle

_DAY_MS = 86_400_000


def utc_day(ts_ms: int) -> int:
    return (ts_ms // _DAY_MS) * _DAY_MS


def donchian_long_state(candles: list[Candle], n: int, h: int) -> list[tuple[int, bool]]:
    """(ts_ms, is_long) per bar. is_long iff a donchian_break long entry
    (close > prior n-bar high, exclusive of i) fired on any bar in (i-h, i].
    Strictly causal: bar i uses only candles[:i+1]."""
    breakout = [False] * len(candles)
    for i in range(n, len(candles)):
        prior_high, _ = donchian_channel(candles, i, n)
        breakout[i] = candles[i].close > prior_high
    out: list[tuple[int, bool]] = []
    for i, c in enumerate(candles):
        lo = max(0, i - h + 1)
        out.append((c.timestamp_ms, any(breakout[lo:i + 1])))
    return out


def daily_long_flags(candles: list[Candle], n: int, h: int) -> dict[int, bool]:
    """UTC-day -> long-state at that day's LAST 4h bar (later bars overwrite)."""
    flags: dict[int, bool] = {}
    for ts, is_long in donchian_long_state(candles, n, h):
        flags[utc_day(ts)] = is_long
    return flags


def daily_close_returns(candles: list[Candle]) -> dict[int, float]:
    """UTC-day -> close-to-close return using each day's last 4h close."""
    last_close: dict[int, float] = {}
    for c in candles:
        last_close[utc_day(c.timestamp_ms)] = c.close
    days = sorted(last_close)
    rets: dict[int, float] = {}
    for i in range(1, len(days)):
        prev, cur = last_close[days[i - 1]], last_close[days[i]]
        if prev:
            rets[days[i]] = cur / prev - 1.0
    return rets


def trailing_vol(returns: list[float], window: int) -> float:
    w = returns[-window:]
    return pstdev(w) if len(w) >= 2 else 0.0

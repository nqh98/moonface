from __future__ import annotations

from moonface.core.models import Candle


def sma(closes: list[float], period: int) -> float:
    """Simple moving average of the last `period` closes. Caller ensures len >= period."""
    window = closes[-period:]
    return sum(window) / len(window)


def rolling_std(closes: list[float], period: int) -> float:
    """Population std (ddof=0) of the last `period` closes. Caller ensures len >= period."""
    window = closes[-period:]
    m = sum(window) / period
    return (sum((x - m) ** 2 for x in window) / period) ** 0.5


def ema(closes: list[float], period: int) -> float:
    """Exponential moving average of the provided closes (alpha = 2/(period+1)),
    seeded by the first close. Caller passes a bounded, past-only window; this
    function never reads beyond the list it is given (lookahead-free by contract)."""
    if not closes:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    e = closes[0]
    for c in closes[1:]:
        e = alpha * c + (1.0 - alpha) * e
    return e


def roc(closes: list[float], period: int) -> float:
    """Fractional rate of change over `period` bars; 0.0 if not enough data or zero base."""
    if len(closes) <= period:
        return 0.0
    base = closes[-period - 1]
    if base == 0:
        return 0.0
    return (closes[-1] - base) / base


def rsi(closes: list[float], period: int) -> float:
    """Wilder-style RSI over the last `period` deltas. 50.0 if too short, 100.0 if no losses."""
    if len(closes) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for j in range(-period, 0):
        delta = closes[j] - closes[j - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return round(100 - 100 / (1 + rs), 4)


def donchian_channel(candles: list[Candle], i: int, n: int) -> tuple[float, float]:
    """(prior_high, prior_low) over the n bars BEFORE bar i (exclusive of i).
    Mirrors the breakout window used by donchian_break."""
    window = candles[i - n:i]
    return max(c.high for c in window), min(c.low for c in window)

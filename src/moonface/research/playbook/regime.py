from __future__ import annotations

from moonface.core.indicators import sma
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.playbook.config import (PlaybookParams, UPTREND, DOWNTREND,
                                               RANGE_CHOP, VOL_COMPRESSION,
                                               VOL_EXPANSION, OVEREXTENDED, NO_TRADE)


def ma_slope(closes: list[float], period: int, n: int) -> float:
    """Fractional change of the period-SMA between bar -n and the last bar."""
    if len(closes) < period + n:
        return 0.0
    now = sma(closes, period)
    past = sma(closes[:-n], period)
    if past == 0:
        return 0.0
    return (now - past) / past


def atr_percentile(candles: list[Candle], params: PlaybookParams) -> float:
    """Percentile rank (0-100) of the latest ATR within the trailing window."""
    window = params.atr_pct_window
    if len(candles) < params.atr_period + 2:
        return 50.0
    series = []
    start = max(params.atr_period + 1, len(candles) - window)
    for j in range(start, len(candles) + 1):
        series.append(atr(candles[:j], params.atr_period))
    if not series:
        return 50.0
    latest = series[-1]
    below = sum(1 for a in series if a <= latest)
    return 100.0 * below / len(series)


def efficiency_ratio(closes: list[float], n: int) -> float:
    """|net move| / sum|bar move| over the last n bars (0=chop, 1=trend)."""
    if len(closes) < n + 1:
        return 0.0
    seg = closes[-(n + 1):]
    net = abs(seg[-1] - seg[0])
    path = sum(abs(seg[k] - seg[k - 1]) for k in range(1, len(seg)))
    return net / path if path > 0 else 0.0


def classify_regime(h4_prefix: list[Candle], params: PlaybookParams) -> str:
    if len(h4_prefix) < params.ma_slow + params.slope_n:
        return NO_TRADE
    closes = [c.close for c in h4_prefix]
    close = closes[-1]
    _ma_fast = sma(closes, params.ma_fast)
    ma_mid = sma(closes, params.ma_mid)
    ma_slow = sma(closes, params.ma_slow)
    slope = ma_slope(closes, params.ma_mid, params.slope_n)
    a = atr(h4_prefix, params.atr_period)
    pct = atr_percentile(h4_prefix, params)

    # post-pump stretch dominates (checked before plain uptrend)
    if a > 0 and close > ma_mid + params.overext_k * a:
        return OVEREXTENDED
    if close > ma_mid > ma_slow and slope > params.slope_eps:
        return UPTREND
    if close < ma_mid < ma_slow and slope < -params.slope_eps:
        return DOWNTREND
    if pct < params.compress_pct:
        return VOL_COMPRESSION
    if pct > params.expand_pct:
        return VOL_EXPANSION
    if abs(slope) <= params.slope_eps:
        return RANGE_CHOP
    return NO_TRADE

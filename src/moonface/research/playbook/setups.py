"""1h setup detection with 2h confirmation. Each detector is a mechanical rule
over the closed prefix; detect_setup returns the highest-priority match. Entry
is the latest close; invalidation is the setup's structural stop anchor."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.indicators import donchian_channel, sma
from moonface.core.models import Candle
from moonface.research.playbook.config import (PlaybookParams, UPTREND,
                                               VOL_COMPRESSION, VOL_EXPANSION)

FORMING = "forming"
TRIGGERED = "triggered"
_NEAR = 0.005   # within 0.5% of a level = "forming"


@dataclass(frozen=True)
class Setup:
    name: str
    phase: str
    entry: float
    invalidation: float
    ref_level: float


def two_h_confirms(h2_prefix: list[Candle], params: PlaybookParams) -> bool:
    closes = [c.close for c in h2_prefix]
    if len(closes) < params.ma_fast:
        return False
    return closes[-1] > sma(closes, params.ma_fast)


def _bar_range(c: Candle) -> float:
    return c.high - c.low


def detect_setup(h1_prefix: list[Candle], h2_prefix: list[Candle], regime: str,
                 params: PlaybookParams) -> Setup | None:
    L = len(h1_prefix) - 1
    n = params.donchian_n
    if L < max(n, params.ma_mid) + 1:
        return None
    closes = [c.close for c in h1_prefix]
    close = closes[-1]
    prev = closes[-2]
    prior_high, prior_low = donchian_channel(h1_prefix, L - 1, n)
    ma_fast = sma(closes, params.ma_fast)
    ma_mid = sma(closes, params.ma_mid)

    # priority 1: failed_breakdown_reclaim (bear trap)
    if h1_prefix[-2].low < prior_low <= close and prev <= prior_low:
        return Setup("failed_breakdown_reclaim", TRIGGERED, close, prior_low, prior_low)

    # priority 2: trend / continuation breakout
    if close > prior_high:
        name = ("continuation_breakout"
                if close > ma_mid > sma(closes, params.ma_slow if L >= params.ma_slow else params.ma_mid)
                else "trend_breakout")
        return Setup(name, TRIGGERED, close, ma_mid, prior_high)
    if prior_high * (1 - _NEAR) <= close <= prior_high:
        return Setup("trend_breakout", FORMING, close, ma_mid, prior_high)

    # priority 3: pullback_reclaim (dip to mid then reclaim)
    if prev <= ma_mid < close:
        return Setup("pullback_reclaim", TRIGGERED, close, min(c.low for c in h1_prefix[-n:]), ma_mid)

    # priority 4: vol_compression -> expansion thrust
    if regime in (VOL_COMPRESSION, VOL_EXPANSION):
        a_range = _bar_range(h1_prefix[-1])
        from moonface.core.risk import atr
        a = atr(h1_prefix, params.atr_period)
        if a > 0 and a_range >= params.min_expansion_atr * a and close > h1_prefix[-2].high:
            return Setup("vol_compression_expansion", TRIGGERED, close,
                         h1_prefix[-1].low, h1_prefix[-2].high)

    # priority 5: higher_low_reclaim
    if regime == UPTREND and prev <= ma_fast < close:
        recent_low = min(c.low for c in h1_prefix[-n:])
        older_low = min(c.low for c in h1_prefix[-2 * n:-n]) if L >= 2 * n else recent_low
        if recent_low > older_low:
            return Setup("higher_low_reclaim", TRIGGERED, close, recent_low, ma_fast)

    return None

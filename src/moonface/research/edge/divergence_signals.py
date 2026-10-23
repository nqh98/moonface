"""price_oi_divergence entry family (spec 2026-07-08).

Standardized z-gap divergence: over window W, z_r is the z-score of the price
log-return at lookback L and z_o the z-score of the OI log-change at the same
L. The mechanism is unbacked-breakout exhaustion, so the direction is
pre-committed SHORT: fire only when price is extended up (z_r >= +k) while open
interest contracts (z_o <= -k). The control drops the OI gate to isolate the
marginal value of open interest.
"""
from __future__ import annotations

from math import log
from statistics import fmean, pstdev

from moonface.core.models import Candle

Entry = tuple[int, str]
FeatureSeries = list


def _log_changes(values: list, lookback: int, n: int) -> list:
    out: list = [None] * n
    for i in range(lookback, min(n, len(values))):
        now, then = values[i], values[i - lookback]
        if now is not None and then is not None and now > 0 and then > 0:
            out[i] = log(now / then)
    return out


def _zscore(series: list, i: int, window: int) -> float | None:
    x = series[i]
    if x is None:
        return None
    sample = [v for v in series[i - window + 1:i + 1] if v is not None]
    if len(sample) < window // 2:
        return None
    if all(v > 0 for v in sample):
        return float("inf")
    if all(v < 0 for v in sample):
        return float("-inf")
    sd = pstdev(sample)
    if sd == 0:
        if x > 0:
            return float("inf")
        if x < 0:
            return float("-inf")
        return None
    return (x - fmean(sample)) / sd


def make_price_oi_divergence(feature: FeatureSeries):
    oi = list(feature)

    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        window, lookback, k = params["window"], params["lookback"], params["k"]
        n = len(candles)
        r_log = _log_changes([c.close for c in candles], lookback, n)
        o_log = _log_changes(oi, lookback, n)
        out: list[Entry] = []
        for i in range(window + lookback, n - 1):
            z_r = _zscore(r_log, i, window)
            z_o = _zscore(o_log, i, window)
            if z_r is None or z_o is None:
                continue
            if z_r >= k and z_o <= -k:
                out.append((i, "SHORT"))
        return out

    return gen


def price_extension_short(candles: list[Candle], params: dict) -> list[Entry]:
    window, lookback, k = params["window"], params["lookback"], params["k"]
    n = len(candles)
    r_log = _log_changes([c.close for c in candles], lookback, n)
    out: list[Entry] = []
    for i in range(window + lookback, n - 1):
        z_r = _zscore(r_log, i, window)
        if z_r is None:
            continue
        if z_r >= k:
            out.append((i, "SHORT"))
    return out

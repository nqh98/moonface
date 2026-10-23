"""Point-in-time volatility-regime features + per-bar allow flags.

Every feature at bar i uses only bars <= i (no look-ahead). Warm-up bars where a
window is unavailable classify as not-allowed (the Donchian engine needs >=40 bars
before it can enter anyway, so warm-up carries no trades).
"""
from __future__ import annotations

import math
from statistics import median, pstdev
from typing import Any

Candle = Any


def true_range(candles: list[Candle]) -> list[float]:
    n = len(candles)
    tr = [0.0] * n
    for i in range(n):
        hi = float(candles[i].high)
        lo = float(candles[i].low)
        if i == 0:
            tr[i] = hi - lo
        else:
            pc = float(candles[i - 1].close)
            tr[i] = max(hi - lo, abs(hi - pc), abs(lo - pc))
    return tr


def atr_series(candles: list[Candle], period: int) -> list[float]:
    """Simple rolling-mean ATR (mean true range over trailing `period` bars).

    atr[i] is 0.0 until `period` true-range values are available."""
    if period <= 0:
        raise ValueError("period must be positive")
    tr = true_range(candles)
    n = len(candles)
    out = [0.0] * n
    run = 0.0
    for i in range(n):
        run += tr[i]
        if i >= period:
            run -= tr[i - period]
        if i >= period - 1:
            out[i] = run / period
    return out


def hv_series(candles: list[Candle], period: int) -> list[float]:
    """Historical volatility = population stdev of log close-to-close returns over
    the trailing `period` bars. 0.0 until enough returns exist."""
    if period <= 0:
        raise ValueError("period must be positive")
    closes = [float(c.close) for c in candles]
    n = len(closes)
    rets = [0.0] * n
    for i in range(1, n):
        if closes[i - 1] > 0.0 and closes[i] > 0.0:
            rets[i] = math.log(closes[i] / closes[i - 1])
    out = [0.0] * n
    for i in range(n):
        if i >= period:  # need `period` returns ending at i (rets[i-period+1..i])
            window = rets[i - period + 1 : i + 1]
            out[i] = pstdev(window)
    return out


def rolling_percentile(values: list[float], i: int, window: int) -> float | None:
    """Fraction of the trailing `window` values (ending at i) that are <= values[i].

    Returns None until `window` observations are available. Range [0, 1]."""
    if i + 1 < window:
        return None
    lo = i - window + 1
    ref = values[i]
    seg = values[lo : i + 1]
    le = sum(1 for v in seg if v <= ref)
    return le / len(seg)


def rolling_median(values: list[float], i: int, window: int) -> float | None:
    if i + 1 < window:
        return None
    return median(values[i - window + 1 : i + 1])


def _donchian_width(candles: list[Candle], i: int, n: int) -> float | None:
    """(highest high - lowest low) of the prior-n bars [i-n, i-1]. None if too early."""
    if i < n:
        return None
    hi = max(float(candles[j].high) for j in range(i - n, i))
    lo = min(float(candles[j].low) for j in range(i - n, i))
    return hi - lo


def allow_flags(candles: list[Candle], cell_id: str, cfg: dict) -> list[bool]:
    """Per-bar boolean: True iff bar i is in the cell's allowed regime.

    cfg keys: pct_hi, expansion_min, pct_window, atr_short, atr_long, hv_period,
    don_n.
    """
    n = len(candles)
    atr_s = atr_series(candles, cfg["atr_short"])
    flags = [False] * n

    if cell_id in ("atr_pct", "hivol_expansion"):
        atr_pct = [rolling_percentile(atr_s, i, cfg["pct_window"]) for i in range(n)]
    if cell_id == "hv_pct":
        hv = hv_series(candles, cfg["hv_period"])
        hv_pct = [rolling_percentile(hv, i, cfg["pct_window"]) for i in range(n)]
    if cell_id in ("expansion", "hivol_expansion"):
        atr_l = atr_series(candles, cfg["atr_long"])
    if cell_id == "not_compressed":
        width = [_donchian_width(candles, i, cfg["don_n"]) for i in range(n)]
        norm = [
            (width[i] / atr_s[i]) if (width[i] is not None and atr_s[i] > 0.0) else None
            for i in range(n)
        ]
        norm_clean = [v if v is not None else 0.0 for v in norm]

    for i in range(n):
        if cell_id == "atr_pct":
            p = atr_pct[i]
            flags[i] = p is not None and p >= cfg["pct_hi"]
        elif cell_id == "hv_pct":
            p = hv_pct[i]
            flags[i] = p is not None and p >= cfg["pct_hi"]
        elif cell_id == "expansion":
            if atr_l[i] > 0.0:
                flags[i] = (atr_s[i] / atr_l[i]) >= cfg["expansion_min"]
        elif cell_id == "not_compressed":
            if norm[i] is not None:
                med = rolling_median(norm_clean, i, cfg["pct_window"])
                flags[i] = med is not None and norm[i] >= med
        elif cell_id == "hivol_expansion":
            p = atr_pct[i]
            exp_ok = atr_l[i] > 0.0 and (atr_s[i] / atr_l[i]) >= cfg["expansion_min"]
            flags[i] = p is not None and p >= cfg["pct_hi"] and exp_ok
        else:
            raise ValueError(f"unknown cell id: {cell_id!r}")
    return flags

"""Family signal generators missing from edge/signals.py, needed by the
system-level strategy search. Each returns (entry_index, side) using only bars
at/<=i (no lookahead); the last bar is never an entry (it has no fill bar).
Side strings are 'LONG'/'SHORT' to match the Entry contract in entries.py."""
from __future__ import annotations

from moonface.core.indicators import sma
from moonface.core.models import Candle
from moonface.core.risk import atr

Entry = tuple[int, str]


def vol_compression_breakout(candles: list[Candle], params: dict) -> list[Entry]:
    """Squeeze then expand: when the prior squeeze_n bars' high-low range is at
    its own trailing minimum, take the breakout beyond that range by k*ATR."""
    n, ap, k = params["squeeze_n"], params["atr_period"], params["k"]
    out: list[Entry] = []
    for i in range(n + ap, len(candles) - 1):
        prior = candles[i - n:i]
        hi = max(c.high for c in prior)
        lo = min(c.low for c in prior)
        a = atr(candles[max(0, i - ap): i + 1], ap)
        if a <= 0:
            continue
        # squeeze: prior range no wider than k*ATR (a quiet base)
        if (hi - lo) > k * a * 2:
            continue
        if candles[i].close > hi:
            out.append((i, "LONG"))
        elif candles[i].close < lo:
            out.append((i, "SHORT"))
    return out


def vol_expansion(candles: list[Candle], params: dict) -> list[Entry]:
    """Enter in the direction of a bar whose true range exceeds mult x the
    trailing-lookback ATR (a volatility-expansion thrust)."""
    ap, lb, mult = params["atr_period"], params["lookback"], params["mult"]
    out: list[Entry] = []
    for i in range(lb + ap, len(candles) - 1):
        a = atr(candles[i - lb: i], ap)
        if a <= 0:
            continue
        rng = candles[i].high - candles[i].low
        if rng < mult * a:
            continue
        if candles[i].close > candles[i].open:
            out.append((i, "LONG"))
        elif candles[i].close < candles[i].open:
            out.append((i, "SHORT"))
    return out


def trend_pullback(candles: list[Candle], params: dict) -> list[Entry]:
    """In an up-trend (close>MA and MA rising) buy a pullback that dips
    pull_atr x ATR below the MA; symmetric short in a down-trend."""
    ma_n, pull, ap = params["ma"], params["pull_atr"], params["atr_period"]
    closes = [c.close for c in candles]
    out: list[Entry] = []
    for i in range(ma_n + ap, len(candles) - 1):
        # sma/atr read only their trailing window; bound the slice to avoid the
        # O(n^2) full-prefix recomputation. Values are identical to [:i+1].
        ma_now = sma(closes[max(0, i - ma_n): i + 1], ma_n)
        ma_prev = sma(closes[max(0, i - 1 - ma_n): i], ma_n)
        a = atr(candles[max(0, i - ap): i + 1], ap)
        if a <= 0:
            continue
        up = ma_now > ma_prev
        down = ma_now < ma_prev
        if up and candles[i].low <= ma_now - pull * a and candles[i].close > ma_now - pull * a:
            out.append((i, "LONG"))
        elif down and candles[i].high >= ma_now + pull * a and candles[i].close < ma_now + pull * a:
            out.append((i, "SHORT"))
    return out


def liquidity_sweep_reclaim(candles: list[Candle], params: dict) -> list[Entry]:
    """Failed breakdown/breakout: a bar wicks beyond the prior swing_n
    extreme but closes back inside -> fade the sweep (LONG on a swept low)."""
    n = params["swing_n"]
    out: list[Entry] = []
    for i in range(n, len(candles) - 1):
        prior = candles[i - n:i]
        lo = min(c.low for c in prior)
        hi = max(c.high for c in prior)
        if candles[i].low < lo <= candles[i].close:
            out.append((i, "LONG"))
        elif candles[i].high > hi >= candles[i].close:
            out.append((i, "SHORT"))
    return out

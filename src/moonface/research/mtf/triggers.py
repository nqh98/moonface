"""LTF entry triggers for the MTF lane.

Run 1 showed momentum-on-momentum (HTF trend + LTF breakout) has the regime
filter working but the wrong entry style: a breakout buys the local high, which
maximises adverse excursion -- the exact drawdown the program keeps dying on.
These counter-trend triggers invert the entry: they fire on LTF weakness so that,
once the HTF bias keeps only the in-trend side, the result is "buy the dip in an
uptrend / sell the rip in a downtrend" -- better entry price, less drawdown.

The HTF bias filter (combine.mtf_entries) keeps only the side matching the
regime, so a SHORT oversold signal in an uptrend is dropped, etc. Triggers stay
in the mtf package so the frozen signals.py grid is untouched."""
from __future__ import annotations

from moonface.core.indicators import rsi, sma
from moonface.core.models import Candle

Entry = tuple[int, str]


def rsi_reversion(h1: list[Candle], params: dict) -> list[Entry]:
    """Counter-trend: LONG when RSI is oversold (<= low), SHORT when overbought
    (>= high). The HTF bias keeps only the in-trend side, turning this into a
    pullback-in-trend entry. Bounded window keeps per-bar cost O(n)."""
    n, low, high = params["n"], params["low"], params["high"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(n + 1, len(h1) - 1):
        v = rsi(closes[max(0, i - n): i + 1], n)
        if v <= low:
            out.append((i, "LONG"))
        elif v >= high:
            out.append((i, "SHORT"))
    return out


def ma_reclaim(h1: list[Candle], params: dict) -> list[Entry]:
    """Pullback reclaim: LONG when close crosses back UP through its SMA (a dip
    that resumes), SHORT when it crosses DOWN. Distinct from a breakout -- it
    enters after a pullback to the mean rather than at a fresh extreme."""
    n = params["n"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(n, len(h1) - 1):
        ma_now = sma(closes[max(0, i - n + 1): i + 1], n)
        ma_prev = sma(closes[max(0, i - n): i], n)
        if closes[i - 1] <= ma_prev and closes[i] > ma_now:
            out.append((i, "LONG"))
        elif closes[i - 1] >= ma_prev and closes[i] < ma_now:
            out.append((i, "SHORT"))
    return out

"""Pivot-based confluence filters for entry signals."""

from __future__ import annotations

from typing import Callable

from moonface.research.edge.pivots import PivotCtx
from moonface.core.models import Candle
from moonface.core.risk import atr

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Entry = tuple[int, str]  # (entry_index, "LONG" | "SHORT")
Filter = Callable[
    [list[Candle], list[Entry], list[PivotCtx | None], dict],
    list[Entry],
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _levels(ctx: PivotCtx) -> tuple[float, ...]:
    """Return all 7 pivot levels as a tuple."""
    return (ctx.p, ctx.s1, ctx.r1, ctx.s2, ctx.r2, ctx.s3, ctx.r3)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
def pivot_bias(
    h1: list[Candle],
    entries: list[Entry],
    pivots: list[PivotCtx | None],
    params: dict,
) -> list[Entry]:
    """Keep LONG iff close > central pivot P; keep SHORT iff close < P."""
    kept: list[Entry] = []
    for idx, side in entries:
        ctx = pivots[idx]
        if ctx is None:
            continue
        close = h1[idx].close
        if side == "LONG" and close > ctx.p:
            kept.append((idx, side))
        elif side == "SHORT" and close < ctx.p:
            kept.append((idx, side))
    return kept


def pivot_proximity(
    h1: list[Candle],
    entries: list[Entry],
    pivots: list[PivotCtx | None],
    params: dict,
) -> list[Entry]:
    """Keep iff close is within x * ATR of any pivot level."""
    x: float = params["x"]
    atr_period: int = params["atr_period"]
    kept: list[Entry] = []
    for idx, side in entries:
        ctx = pivots[idx]
        if ctx is None:
            continue
        a = atr(h1[: idx + 1], atr_period)
        if a <= 0:
            continue
        close = h1[idx].close
        threshold = x * a
        if any(abs(close - lv) <= threshold for lv in _levels(ctx)):
            kept.append((idx, side))
    return kept


def pivot_levelbreak(
    h1: list[Candle],
    entries: list[Entry],
    pivots: list[PivotCtx | None],
    params: dict,
) -> list[Entry]:
    """Keep LONG iff bar clears a level upward; SHORT iff downward."""
    kept: list[Entry] = []
    for idx, side in entries:
        ctx = pivots[idx]
        if ctx is None:
            continue
        if idx == 0:
            continue
        close = h1[idx].close
        prev_close = h1[idx - 1].close
        levels = _levels(ctx)
        if side == "LONG":
            # prev_close <= level < close  (bar clears level upward)
            if any(prev_close <= lv < close for lv in levels):
                kept.append((idx, side))
        elif side == "SHORT":
            # close < level <= prev_close  (bar clears level downward)
            if any(close < lv <= prev_close for lv in levels):
                kept.append((idx, side))
    return kept

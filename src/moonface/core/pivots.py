"""Traditional daily pivot levels, lookahead-free."""

from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle

_DAY_MS = 86_400_000


@dataclass(frozen=True)
class PivotCtx:
    """Traditional pivot levels computed from the prior day's HLC."""

    p: float
    s1: float
    r1: float
    s2: float
    r2: float
    s3: float
    r3: float


def _traditional(high: float, low: float, close: float) -> PivotCtx:
    """Compute Traditional pivot levels from a single day's H, L, C."""
    p = (high + low + close) / 3.0
    r1 = 2.0 * p - low
    s1 = 2.0 * p - high
    r2 = p + (high - low)
    s2 = p - (high - low)
    r3 = high + 2.0 * (p - low)
    s3 = low - 2.0 * (high - p)
    return PivotCtx(p=p, s1=s1, r1=r1, s2=s2, r2=r2, s3=s3, r3=r3)


def daily_pivots(h1: list[Candle]) -> list[PivotCtx | None]:
    """Compute daily pivot levels for each bar based on the prior day's HLC.

    First pass: aggregate H/L/C per UTC calendar day (timestamp_ms // 86_400_000).
    Second pass: for each bar, look up the PRIOR day's HLC and compute pivots.
    First-day bars (no prior day available) get ``None``.
    Lookahead-free: pivot depends only on strictly-earlier days.
    """
    if not h1:
        return []

    # --- Pass 1: aggregate per UTC day ---
    daily_hlc: dict[int, tuple[float, float, float]] = {}
    for bar in h1:
        day = bar.timestamp_ms // _DAY_MS
        if day not in daily_hlc:
            daily_hlc[day] = (bar.high, bar.low, bar.close)
        else:
            prev_h, prev_l, prev_c = daily_hlc[day]
            daily_hlc[day] = (max(prev_h, bar.high),
                              min(prev_l, bar.low),
                              bar.close)  # close of last bar wins

    # --- Pass 2: assign pivots from the prior day ---
    result: list[PivotCtx | None] = []
    for bar in h1:
        day = bar.timestamp_ms // _DAY_MS
        prior_day = day - 1
        hlc = daily_hlc.get(prior_day)
        if hlc is None:
            result.append(None)
        else:
            result.append(_traditional(hlc[0], hlc[1], hlc[2]))

    return result

__all__ = ["PivotCtx", "daily_pivots"]

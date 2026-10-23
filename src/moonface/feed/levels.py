"""Derive entry zone / TP1-3 / SL / confidence for a Setup. Levels are a
transparent mapping from SMC structure + daily pivots; confidence is setup
quality, NOT a probability of profit."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.pivots import PivotCtx
from moonface.feed.setups import Setup

_BUFFER_ATR = 0.10  # SL sits this fraction of ATR beyond the invalidation level


@dataclass(frozen=True)
class Levels:
    entry: float
    entry_low: float
    entry_high: float
    stop: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float


def derive_levels(setup: Setup, pivots: PivotCtx | None,
                  atr_value: float) -> Levels:
    long_ = setup.side == "LONG"
    entry = setup.entry_close
    entry_low = entry - 0.25 * atr_value
    entry_high = entry + 0.25 * atr_value

    ref = setup.swept_level if setup.swept_level is not None else setup.struct_level
    if ref is None:
        stop = entry - 1.5 * atr_value if long_ else entry + 1.5 * atr_value
    else:
        stop = ref - _BUFFER_ATR * atr_value if long_ else ref + _BUFFER_ATR * atr_value
    risk = (entry - stop) if long_ else (stop - entry)
    if risk <= 0:                       # invalidation landed on the wrong side
        stop = entry - 1.5 * atr_value if long_ else entry + 1.5 * atr_value
        risk = abs(entry - stop)

    if pivots is not None:
        raw = [pivots.r1, pivots.r2, pivots.r3] if long_ else [pivots.s1, pivots.s2, pivots.s3]
        tps = [p for p in raw if (p > entry if long_ else p < entry)]
        tps.sort(reverse=not long_)
        tps = tps[:3]
    else:
        tps = []
    mults = (1.0, 2.0, 3.0)
    while len(tps) < 3:
        m = mults[len(tps)]
        tps.append(entry + m * risk if long_ else entry - m * risk)
    tp1, tp2, tp3 = tps[0], tps[1], tps[2]

    # confidence: transparent composite (NOT P(profit)).
    conf = 0.50
    if setup.struct_level is not None:
        conf += 0.10
    if setup.swept_level is not None:
        conf += 0.10
    conf += 0.10                       # the finder already required a displacement candle
    conf = max(0.0, min(1.0, conf))
    return Levels(entry, entry_low, entry_high, stop, tp1, tp2, tp3, round(conf, 2))

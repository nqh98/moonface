"""Four frozen portfolio combination operators (all per-bar, on the 1h grid)."""
from __future__ import annotations

import math

from moonface.core.models import Candle


def vote(positions_by_comp: list[list[float]], k) -> list[float]:
    """Equal-weight vote: +1 if >=k components long (and more long than short),
    -1 mirrored, else flat."""
    n = len(positions_by_comp)
    thresh = (n // 2 + 1) if k == "majority" else int(k)
    T = len(positions_by_comp[0]) if positions_by_comp else 0
    out = []
    for t in range(T):
        longs = sum(1 for p in positions_by_comp if p[t] > 0)
        shorts = sum(1 for p in positions_by_comp if p[t] < 0)
        if longs >= thresh and longs > shorts:
            out.append(1.0)
        elif shorts >= thresh and shorts > longs:
            out.append(-1.0)
        else:
            out.append(0.0)
    return out


def long_short_net(positions_by_comp: list[list[float]]) -> list[float]:
    """Time-varying net exposure = signed agreement, clipped to [-1, 1]."""
    T = len(positions_by_comp[0]) if positions_by_comp else 0
    out = []
    for t in range(T):
        net = sum(1.0 if p[t] > 0 else (-1.0 if p[t] < 0 else 0.0)
                  for p in positions_by_comp)
        out.append(max(-1.0, min(1.0, net)))
    return out


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def vol_target(base: list[float], asset_bar_r: list[float], *,
               target_vol: float = 1.0, vol_lookback: int = 48) -> list[float]:
    """Scale base direction by target_vol / realized_vol (lookback, causal)."""
    out = []
    for t in range(len(base)):
        window = asset_bar_r[max(0, t - vol_lookback):t + 1]
        rv = _std(window) or 1.0
        out.append(base[t] * (target_vol / rv))
    return out


def regime_switch(positions_by_comp: list[list[float]], grid_candles: list[Candle],
                  *, floor: float = 0.10, lookback: int = 50) -> list[float]:
    """Trend regime = |momentum(lookback)| >= floor; active -> vote(majority), else flat.

    ADX is not in foundation; a momentum-magnitude proxy is the frozen boundary
    set (spec allows adx/vol_state)."""
    base = vote(positions_by_comp, "majority")
    out = []
    for t in range(len(base)):
        lo = max(0, t - lookback)
        p0 = grid_candles[lo].close if grid_candles[lo].close else 1.0
        mom = abs((grid_candles[t].close - grid_candles[lo].close) / p0) if p0 else 0.0
        out.append(base[t] if mom >= floor else 0.0)
    return out

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernorParams:
    target_vol: float
    size_min: float
    size_max: float
    dd_budget: float


def _clip(value: float, lower: float, upper: float) -> float:
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def size_stream(raw: list[tuple[float, float]], params: GovernorParams) -> list[float]:
    sizes: list[float] = []
    governed_cum = 0.0
    governed_peak = 0.0

    for r_t, vol_forecast in raw:
        drawdown_before_t = governed_peak - governed_cum
        g_t = (_clip((params.dd_budget - drawdown_before_t) / params.dd_budget,
                     0.0, 1.0)
               if params.dd_budget > 0 else 0.0)
        vol_scale = (_clip(params.target_vol / vol_forecast,
                           params.size_min, params.size_max)
                     if vol_forecast > 0 else params.size_min)
        size_t = vol_scale * g_t
        sizes.append(size_t)

        governed_cum += size_t * r_t
        if governed_cum > governed_peak:
            governed_peak = governed_cum

    return sizes

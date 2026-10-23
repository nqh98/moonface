"""Distribution -> LONG/SHORT/WAIT decision with conviction sizing.

The edge is exp_ret_r / |exp_mae_r| (drift per unit of predicted adverse
excursion) — the quantity the prior program could never harvest. WAIT is the
default; |edge| must clear edge_threshold (calibrated on training folds) to
trade. Size scales with the excess edge, hard-capped at max_fraction."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Distribution:
    p_up: float
    exp_ret_r: float
    exp_mae_r: float   # <= 0
    exp_mfe_r: float   # >= 0


@dataclass(frozen=True)
class Decision:
    action: str        # "LONG" | "SHORT" | "WAIT"
    size: float        # fraction of equity, >= 0


def decide(dist: Distribution, edge_threshold: float, kelly_scale: float,
           max_fraction: float) -> Decision:
    denom = abs(dist.exp_mae_r)
    if denom <= 0.0:
        return Decision("WAIT", 0.0)
    edge = dist.exp_ret_r / denom
    if abs(edge) < edge_threshold:
        return Decision("WAIT", 0.0)
    size = min(max_fraction, (abs(edge) - edge_threshold) * kelly_scale)
    if size <= 0.0:
        return Decision("WAIT", 0.0)
    return Decision("LONG" if edge > 0 else "SHORT", round(size, 6))

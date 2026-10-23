"""Pre-registered selection rule (train-only) + sealed-holdout verdict labels."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from moonface.research.donchian_filter.grid import (
    ACTIVITY_FRAC,
    HOLDOUT_MIN_TRADES,
    NEUTRAL_TOL_R,
    TREND_CAPTURE_FRAC,
)

IMPROVES = "IMPROVES"
NEUTRAL = "NEUTRAL"
DESTROYS_INACTIVE = "DESTROYS_INACTIVE"


def _metric(mapping: Mapping[str, Any], *names: str) -> float:
    for name in names:
        if name in mapping:
            return float(mapping[name])
    raise KeyError(f"missing metric key; expected one of {names!r}")


def _count(mapping: Mapping[str, Any], *names: str) -> float:
    for name in names:
        if name in mapping:
            return float(mapping[name])
    raise KeyError(f"missing count key; expected one of {names!r}")


def qualifies(base_m, gated_m, base_rf, gated_rf) -> tuple[bool, list[str]]:
    """A threshold qualifies iff ALL train conditions hold."""
    reasons: list[str] = []
    base_net = _metric(base_m, "net_r")
    gated_net = _metric(gated_m, "net_r")
    if gated_net < TREND_CAPTURE_FRAC * base_net:
        reasons.append("trend capture: gated net_r below 90% of base")

    base_dd = _metric(base_m, "max_dd_r", "drawdown")
    gated_dd = _metric(gated_m, "max_dd_r", "drawdown")
    if not (gated_dd > base_dd):
        reasons.append("drawdown: gated max_dd not strictly less negative than base")

    if isinstance(base_rf, Mapping):
        base_robust = _metric(base_rf, "robust_frac", "robustness")
    else:
        base_robust = float(base_rf)
    if isinstance(gated_rf, Mapping):
        gated_robust = _metric(gated_rf, "robust_frac", "robustness")
    else:
        gated_robust = float(gated_rf)
    if gated_robust < base_robust:
        reasons.append("robustness: gated robust_frac below base")

    if isinstance(base_rf, Mapping) and "activity" in base_rf:
        base_activity = float(base_rf["activity"])
        gated_activity = float(gated_rf["activity"])
    else:
        base_activity = _count(base_m, "n", "trade_count")
        gated_activity = _count(gated_m, "n", "trade_count")
    if gated_activity < ACTIVITY_FRAC * base_activity:
        reasons.append("activity: gated trades below 50% of base")

    return (not reasons, reasons)


def select_threshold(rows) -> int | None:
    """Among qualifiers, pick least-negative train max_dd; tie-break robust_frac, net_r."""
    qs = [r for r in rows if r["qualifies"]]
    if not qs:
        return None
    qs.sort(key=lambda r: (r["gated"]["max_dd_r"], r["robust_frac"], r["gated"]["net_r"]),
            reverse=True)
    return qs[0]["threshold"]


def holdout_verdict(base_m, gated_m) -> str:
    if gated_m["n"] < HOLDOUT_MIN_TRADES:
        return DESTROYS_INACTIVE
    if gated_m["max_dd_r"] > base_m["max_dd_r"] and gated_m["net_r"] > base_m["net_r"]:
        return IMPROVES
    if gated_m["net_r"] < base_m["net_r"] - NEUTRAL_TOL_R:
        return DESTROYS_INACTIVE
    return NEUTRAL

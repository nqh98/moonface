from __future__ import annotations

from moonface.research.regime_overlay.evaluate import (practical_pass,
                                                       vector_from_rt)
from moonface.research.regime_selector.selector import control_rt, selector_rt

__all__ = ["cell_vector", "control_vector", "beats_controls", "practical_pass"]


def _vector_with_cost(rt_at, first_ts, last_ts) -> dict:
    rt1 = rt_at(1.0)
    v = vector_from_rt(rt1, first_ts, last_ts)
    v["cost_stress"] = {
        "net_r_1x": round(sum(r for _, r in rt1), 4),
        "net_r_2x": round(sum(r for _, r in rt_at(2.0)), 4),
        "net_r_3x": round(sum(r for _, r in rt_at(3.0)), 4),
    }
    return v


def cell_vector(candles, macro, regime_def, riskoff_action,
                first_ts, last_ts) -> dict:
    return _vector_with_cost(
        lambda m: selector_rt(candles, macro, regime_def, riskoff_action, m),
        first_ts, last_ts)


def control_vector(candles, macro, regime_def, kind, first_ts, last_ts) -> dict:
    return _vector_with_cost(
        lambda m: control_rt(candles, macro, regime_def, kind, m),
        first_ts, last_ts)


def beats_controls(cell, trend_ctrl, mr_ctrl, recent: bool = True) -> dict:
    beats_net = (cell["net_r"] > trend_ctrl["net_r"]
                 and cell["net_r"] > mr_ctrl["net_r"])
    out = {"beats_net": beats_net}
    if not recent:
        out["beats_both"] = beats_net
        return out
    beats_recent = (
        cell["trailing_365d_net_r"] > trend_ctrl["trailing_365d_net_r"]
        and cell["trailing_365d_net_r"] > mr_ctrl["trailing_365d_net_r"])
    out["beats_recent"] = beats_recent
    out["beats_both"] = beats_net and beats_recent
    return out

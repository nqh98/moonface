# src/moonface/signal/engine/honesty.py
"""Pure honesty metrics for the live-faithful engine verdict report.

These quantify *how* a net-R result is earned, so a thin-but-positive headline
cannot hide a frozen sub-period or outlier dependence. A trade is the tuple
(exit_ts_ms, r, atr_frac, fraction); r is already net of 1x COST_FRACTION.
No data fetch, no engine state — pure functions over the closed-trade list."""
from __future__ import annotations

from moonface.core.metrics import COST_FRACTION, summarize_r

_YEAR_MS = 365 * 24 * 3_600_000


def _seg(rs: list[float]) -> dict:
    s = summarize_r(rs)
    return {"trades": len(rs), "net_r": round(s.total_r, 4),
            "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "win_rate": s.win_rate, "max_drawdown_r": s.max_drawdown_r}


def recency_breakdown(trades: list[tuple], first_ts: int,
                      last_ts: int) -> dict:
    """Segment closed trades by exit time: full / first-half / second-half /
    last-365d. Reveals a kill-switch freeze (e.g. all trades in first_half,
    zero in second_half/last_365d)."""
    span = last_ts - first_ts
    mid = first_ts + span // 2
    last_yr_cut = last_ts - _YEAR_MS
    return {
        "full": _seg([r for _, r, _, _ in trades]),
        "first_half": _seg([r for ts, r, _, _ in trades if ts < mid]),
        "second_half": _seg([r for ts, r, _, _ in trades if ts >= mid]),
        "last_365d": _seg([r for ts, r, _, _ in trades
                           if ts >= last_yr_cut]),
    }


def outlier_dependence(rs: list[float]) -> dict:
    """How much of the net result rides on the few best trades. net_r_ex_best3
    going negative means the edge is a handful of captures, not a population."""
    if not rs:
        return {"net_r": 0.0, "best_trade_r": 0.0, "worst_trade_r": 0.0,
                "median_trade_r": 0.0, "net_r_ex_best1": 0.0,
                "net_r_ex_best3": 0.0, "net_r_ex_best5": 0.0,
                "best1_share_of_gross_profit": None,
                "top3_share_of_gross_profit": None}
    so = sorted(rs)
    net = sum(rs)
    gw = sum(r for r in rs if r > 0)
    return {
        "net_r": round(net, 4),
        "best_trade_r": round(so[-1], 4),
        "worst_trade_r": round(so[0], 4),
        "median_trade_r": round(so[len(so) // 2], 4),
        "net_r_ex_best1": round(net - sum(so[-1:]), 4),
        "net_r_ex_best3": round(net - sum(so[-3:]), 4),
        "net_r_ex_best5": round(net - sum(so[-5:]), 4),
        "best1_share_of_gross_profit": round(so[-1] / gw, 4) if gw > 0 else None,
        "top3_share_of_gross_profit": (round(sum(so[-3:]) / gw, 4)
                                       if gw > 0 else None),
    }


def cost_stress(trades: list[tuple], base: float = COST_FRACTION) -> dict:
    """Net R if per-trade cost (fee + slippage) were k× the base. r already
    nets 1x base, so re-subtract (k-1)*base/atr_frac per trade."""
    def net_at(mult: float) -> float:
        return round(sum(r - (mult - 1.0) * base / af if af > 0 else r
                         for _, r, af, _ in trades), 4)
    return {"cost_fraction_base": base, "net_r_1x": net_at(1.0),
            "net_r_2x": net_at(2.0), "net_r_3x": net_at(3.0),
            "net_r_5x": net_at(5.0)}

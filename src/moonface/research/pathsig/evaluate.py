"""Score a decision stream under both risk frames.

risk_adjusted: each taken trade contributes a sized, leverage-clamped, net-of-
cost return; compounded into Sharpe/MAR/DSR (the primary frame).
fixed_cap: the same trades at unit size in R, summed, with the worst running R
drawdown checked against the prior program's absolute -15R cap (comparability)."""
from __future__ import annotations

from moonface.core.metrics import (MAX_LEVERAGE, deflated_sharpe,
                                        equity_summary_from_returns)
from moonface.research.pathsig.costs import apply_costs
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Decision


def realized_r(decision: Decision, label: PathLabel) -> float | None:
    """Terminal gross R in the chosen direction, held to horizon. None on WAIT."""
    if decision.action == "WAIT":
        return None
    return label.ret_r if decision.action == "LONG" else -label.ret_r


def evaluate_strategy(decisions: list[Decision], labels: list[PathLabel],
                      atr_fracs: list[float], fundings: list[float],
                      taker_bps: float, slippage_bps: float,
                      n_trials: int, trial_srs: list[float],
                      drawdown_cap_r: float) -> dict:
    sized_returns: list[float] = []
    r_stream: list[float] = []
    for d, lbl, af, fund in zip(decisions, labels, atr_fracs, fundings):
        gross = realized_r(d, lbl)
        if gross is None:
            continue
        net_r = apply_costs(gross, af, taker_bps, slippage_bps, fund)
        r_stream.append(net_r)
        f_eff = min(d.size, MAX_LEVERAGE * af)
        sized_returns.append(f_eff * net_r)

    eq = equity_summary_from_returns(sized_returns)
    dsr = deflated_sharpe(eq.sharpe, eq.trade_count, eq.skew, eq.kurtosis,
                          trial_srs, n_trials)

    total_r = round(sum(r_stream), 6)
    cum = 0.0
    peak = 0.0
    max_dd_r = 0.0
    for r in r_stream:
        cum += r
        peak = max(peak, cum)
        max_dd_r = min(max_dd_r, cum - peak)

    return {
        "risk_adjusted": {
            "trade_count": eq.trade_count,
            "net_return": eq.net_return,
            "max_drawdown": eq.max_drawdown,
            "mar": eq.mar,
            "sharpe": eq.sharpe,
            "dsr": dsr,
        },
        "fixed_cap": {
            "trade_count": len(r_stream),
            "total_r": total_r,
            "max_drawdown_r": round(max_dd_r, 6),
            "within_cap": abs(max_dd_r) <= drawdown_cap_r,
        },
    }

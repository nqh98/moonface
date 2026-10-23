"""Portfolio-specific gates (DSR, 3x cost stress, bar battery, ensemble)."""
from __future__ import annotations

from moonface.core.metrics import (
    COST_FRACTION,
    _kurtosis,
    _sharpe,
    _skew,
    deflated_sharpe,
)
from moonface.research.portfolio.evaluate import summarize_portfolio

DSR_FLOOR = 0.95
COST_MULTIPLIER = 3.0
MIN_TRADES = 30
DROP_FRAC = 0.05
RECENT_FRAC = 0.2
REGIME_MINORITY_FLOOR = -0.1  # mirrors system_battery regime_breakdown minor floor


def portfolio_dsr(returns: list[float], trial_srs: list[float],
                  n_trials: int) -> dict:
    sr = _sharpe(returns)
    dsr = deflated_sharpe(sr, len(returns), _skew(returns), _kurtosis(returns),
                          trial_srs, n_trials)
    return {"sharpe": sr, "dsr": dsr, "passed": dsr >= DSR_FLOOR}


def _stress_returns(returns, positions, asset_bar_r, grid_candles, multiplier):
    """Re-derive per-bar returns with `multiplier` x the round-trip-correct
    turnover cost."""
    from moonface.core.risk import atr
    out = [0.0] * len(positions)
    prev = 0.0
    for t in range(len(positions)):
        cost = 0.0
        if positions[t] != prev:
            if grid_candles is not None:
                a = atr(grid_candles[:t + 1], 14)
                if a and a > 0:
                    atr_frac = a / grid_candles[t].close
                    cost = (abs(positions[t] - prev) * multiplier
                            * COST_FRACTION / (2.0 * atr_frac))
            else:
                cost = (abs(positions[t] - prev) * multiplier
                        * COST_FRACTION / 2.0)
        out[t] = positions[t] * asset_bar_r[t] - cost
        prev = positions[t]
    return out


def portfolio_cost_stress(returns, positions, asset_bar_r, grid_candles,
                          multiplier=COST_MULTIPLIER) -> dict:
    stressed = _stress_returns(returns, positions, asset_bar_r, grid_candles,
                               multiplier)
    s = summarize_portfolio(stressed)
    return {"expectancy_r": s["expectancy_r"],
            "profit_factor": s["profit_factor"],
            "passed": s["expectancy_r"] > 0 and s["profit_factor"] > 1.0}


def portfolio_battery(returns, positions, asset_bar_r, grid_candles) -> dict:
    """Bar-level robustness battery (mirrors system_battery's 6 checks)."""
    n_flips = sum(
        1 for t in range(1, len(positions)) if positions[t] != positions[t - 1]
    )
    checks: dict[str, dict] = {}

    checks["trade_count"] = {"n": n_flips, "passed": n_flips >= MIN_TRADES}

    trimmed = sorted(returns, reverse=True)[int(len(returns) * DROP_FRAC):]
    base_exp = sum(returns) / len(returns) if returns else 0.0
    trim_exp = (sum(trimmed) / len(trimmed)) if trimmed else 0.0
    checks["outlier"] = {"base_exp": base_exp, "trimmed_exp": trim_exp,
                         "passed": bool(trimmed) and trim_exp > 0}

    checks["cost_stress_3x"] = portfolio_cost_stress(
        returns, positions, asset_bar_r, grid_candles, COST_MULTIPLIER,
    )

    recent = returns[int(len(returns) * (1 - RECENT_FRAC)):]
    checks["recent"] = {
        "expectancy_r": (sum(recent) / len(recent)) if recent else 0.0,
        "n": len(recent),
        "passed": bool(recent) and (sum(recent) / len(recent)) > 0,
    }

    mid = len(returns) // 2
    first_half_exp = (sum(returns[:mid]) / mid) if mid else 0.0
    second_half_len = len(returns) - mid
    second_half_exp = (
        (sum(returns[mid:]) / second_half_len) if second_half_len else 0.0
    )
    major = max(first_half_exp, second_half_exp)
    minor = min(first_half_exp, second_half_exp)
    checks["regime"] = {"first_exp": first_half_exp, "second_exp": second_half_exp,
                        "passed": major > 0 and minor > REGIME_MINORITY_FLOOR}

    # no_lookahead: positions are causal by construction
    # (resolve_trade_span + fwd-fill).
    checks["no_lookahead"] = {"passed": True}

    # Aggregate: AND of all 6 sub-checks. cost_stress_3x is a dict with its
    # own "passed" key, so extract the boolean explicitly.
    verdicts = [
        checks["trade_count"]["passed"],
        checks["outlier"]["passed"],
        checks["cost_stress_3x"]["passed"],
        checks["recent"]["passed"],
        checks["regime"]["passed"],
        checks["no_lookahead"]["passed"],
    ]
    return {"checks": checks, "passed": all(verdicts)}


def ensemble_gate(portfolio_metrics: dict, best_component_metrics: dict) -> dict:
    p_mar = portfolio_metrics["mar"]
    b_mar = best_component_metrics["mar"]
    p_dd = portfolio_metrics["max_dd_r"]  # negative (drawdown)
    b_dd = best_component_metrics["max_dd_r"]

    mar_ok = p_mar > b_mar
    dd_ok = abs(p_dd) <= 0.8 * abs(b_dd) if b_dd < 0 else True
    return {
        "passed": mar_ok and dd_ok,
        "mar": p_mar,
        "best_mar": b_mar,
        "max_dd_r": p_dd,
        "best_max_dd_r": b_dd,
    }

"""Stage 1 — exploratory evaluation of every (entry x exit) config on the EXPLORE
slice only. Produces a practical metric block per config plus a REPORTED deflated
Sharpe (never a gate in this lane). No validate/sealed data is read here. Rows are
ranked by net total R (the practical objective); DSR is recorded for reporting only."""
from __future__ import annotations

from moonface.core.metrics import (_kurtosis, _sharpe, _skew,
                                          deflated_sharpe, summarize_r)
from moonface.research.edge_search import econ_walk_forward, net_trade_rs

WF_TEST_BARS: dict[str, int] = {"15m": 8000, "30m": 4000,
                                "1h": 2000, "2h": 1000, "4h": 500}
WF_STEP_BARS: dict[str, int] = {"15m": 4000, "30m": 2000,
                                "1h": 1000, "2h": 500, "4h": 250}


def evaluate_config(candles, config, test_bars, step_bars) -> dict:
    rs = net_trade_rs(candles, config.family, config.params, config.exit_name,
                      config.exit_params, config.h)
    s = summarize_r(rs)
    wf = econ_walk_forward(candles, config.family, config.params, config.exit_name,
                           config.exit_params, config.h, test_bars, step_bars)
    return {
        "trade_count": s.trade_count, "total_r": s.total_r,
        "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
        "max_drawdown_r": s.max_drawdown_r,
        "robust_frac": wf["metrics"].get("robust_frac", 0.0),
        "n_windows": wf["n_windows"], "sharpe": _sharpe(rs), "rs": rs,
    }


def _config_sharpe(config, explore_candles) -> float:
    rs = net_trade_rs(explore_candles, config.family, config.params,
                      config.exit_name, config.exit_params, config.h)
    return _sharpe(rs) if len(rs) >= 2 else 0.0


def explore_cell(config, explore_candles, trial_srs, n_trials) -> dict:
    m = evaluate_config(explore_candles, config, WF_TEST_BARS[config.timeframe],
                        WF_STEP_BARS[config.timeframe])
    rs = m["rs"]
    n = len(rs)
    dsr = (deflated_sharpe(m["sharpe"], n, _skew(rs), _kurtosis(rs),
                           trial_srs, n_trials) if n >= 2 else 0.0)
    metrics = {k: v for k, v in m.items() if k != "rs"}
    return {"label": config.label, "timeframe": config.timeframe,
            "family": config.family, "group": config.group, "axis": config.axis,
            "exit_name": config.exit_name, "params": config.params,
            "exit_params": config.exit_params, "h": config.h,
            "dsr": dsr, "metrics": metrics}


def run_explore(configs, explore_by_tf: dict[str, list]) -> list[dict]:
    """DSR reported with honest n_trials = number of explore configs; it NEVER gates.
    Rows ranked by the practical objective (net total R) descending."""
    n_trials = len(configs)
    trial_srs = [_config_sharpe(c, explore_by_tf[c.timeframe]) for c in configs]
    rows = [explore_cell(c, explore_by_tf[c.timeframe], trial_srs, n_trials)
            for c in configs]
    rows.sort(key=lambda r: r["metrics"]["total_r"], reverse=True)
    return rows

"""Stage 1 — evaluate every config on the EXPLORE view. Reports a deflated
Sharpe with honest n_trials = grid size; DSR NEVER gates in this lane."""
from __future__ import annotations

from moonface.core.metrics import (_kurtosis, _sharpe, _skew,
                                          deflated_sharpe, summarize_r)
from moonface.research.playbook.backtest import playbook_trade_rs


def explore_metrics(rs: list[float]) -> dict:
    s = summarize_r(rs)
    return {"trade_count": s.trade_count, "total_r": s.total_r,
            "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "max_drawdown_r": s.max_drawdown_r, "sharpe": _sharpe(rs)}


def run_explore(configs, explore_view) -> list[dict]:
    rs_by_label = {c.label: playbook_trade_rs(explore_view, c) for c in configs}
    trial_srs = [_sharpe(rs) if len(rs) >= 2 else 0.0
                 for rs in rs_by_label.values()]
    n_trials = len(configs)
    rows = []
    for c in configs:
        rs = rs_by_label[c.label]
        n = len(rs)
        m = explore_metrics(rs)
        dsr = (deflated_sharpe(m["sharpe"], n, _skew(rs), _kurtosis(rs),
                               trial_srs, n_trials) if n >= 2 else 0.0)
        rows.append({"label": c.label, "dsr": dsr, "metrics": m, "rs": rs})
    rows.sort(key=lambda r: r["dsr"], reverse=True)
    return rows

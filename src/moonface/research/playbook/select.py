"""Stage 2 — conjunctive selection on EXPLORE metrics + reused robustness checks.
DSR is not consulted. Parameter-island is intentionally omitted (the grid is not
a 1-D axis sweep); dual-segment same-sign replication is the overfit guard."""
from __future__ import annotations

from moonface.core.metrics import single_trade_r, summarize_r
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR
from moonface.research.system_battery import (outlier_dependence_ok,
                                              trade_count_ok)
from moonface.research.playbook.backtest import playbook_trade_rs, replay
from moonface.research.playbook.mtf import MTFView


def passes_core(m: dict) -> dict:
    checks = {
        "net_r_pos": m["total_r"] > 0,
        "expectancy_pos": m["expectancy_r"] > 0,
        "profit_factor": m["profit_factor"] >= PF_FLOOR,
        "drawdown": abs(m["max_drawdown_r"]) <= MAX_DD_R,
        "trade_count": m["trade_count"] >= MIN_TRADES,
    }
    return {"checks": checks, "passed": all(checks.values())}


def playbook_cost_stress_ok(view, config, extra_cost: float = 0.0005) -> dict:
    trades, _ = replay(view, config)
    rs: list[float] = []
    for t in trades:
        res = single_trade_r(view.h1, t.entry_index, "LONG", config.exit_name,
                             config.exit_params)
        if res is None:
            continue
        net_r, atr_frac = res
        rs.append(net_r - extra_cost / atr_frac if atr_frac > 0 else net_r)
    s = summarize_r(rs)
    return {"expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "passed": s.expectancy_r > 0 and s.profit_factor > 1.0}


def _recent_view(view, recent_frac: float) -> MTFView:
    n = len(view.h1)
    cut_ms = view.h1[int((1 - recent_frac) * n)].timestamp_ms
    h1 = [c for c in view.h1 if c.timestamp_ms >= cut_ms]
    h2 = [c for c in view.h2 if c.timestamp_ms >= cut_ms]
    h4 = [c for c in view.h4 if c.timestamp_ms >= cut_ms]
    return MTFView.build(h1, h2, h4)


def playbook_recent_ok(full_view, config, recent_frac: float = 0.2) -> dict:
    rv = _recent_view(full_view, recent_frac)
    rs = playbook_trade_rs(rv, config)
    s = summarize_r(rs)
    return {"expectancy_r": s.expectancy_r, "n": len(rs),
            "passed": len(rs) > 0 and s.expectancy_r > 0}


def select(explore_rows, explore_view, configs_by_label) -> list[dict]:
    survivors: list[dict] = []
    for r in explore_rows:
        m = r["metrics"]
        core = passes_core(m)
        if not core["passed"]:
            continue
        cfg = configs_by_label[r["label"]]
        rs = r["rs"]
        outlier = outlier_dependence_ok(rs, 0.05)
        cost = playbook_cost_stress_ok(explore_view, cfg)
        recent = playbook_recent_ok(explore_view, cfg)
        tc = trade_count_ok(rs, MIN_TRADES)
        checks = {**core["checks"], "outlier": outlier["passed"],
                  "cost_stress": cost["passed"], "recent": recent["passed"],
                  "trade_count_battery": tc["passed"]}
        if all(checks.values()):
            survivors.append({**r, "selection": {"checks": checks, "passed": True}})
    return survivors

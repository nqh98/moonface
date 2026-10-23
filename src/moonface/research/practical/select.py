"""Stage 2 — practical candidate-selection gates on EXPLORE metrics. A config
survives only if it clears the core economic thresholds AND a parameter-island
check (no lone spike) AND the reused robustness battery checks (outlier
dependence, cost-stress, recent-period). DSR is not consulted here."""
from __future__ import annotations

from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR
from moonface.research.edge_search import net_trade_rs
from moonface.research.system_battery import (cost_stress_ok,
                                              outlier_dependence_ok,
                                              recent_period_ok, trade_count_ok)

RECENT_FRAC = 0.2


def m_rs(candles, row) -> list[float]:
    """Net per-trade R on the given candles for a row's config (battery input)."""
    return net_trade_rs(candles, row["family"], row["params"], row["exit_name"],
                        row["exit_params"], row["h"])


def passes_core(metrics: dict) -> dict:
    checks = {
        "net_r_pos": metrics["total_r"] > 0,
        "expectancy_pos": metrics["expectancy_r"] > 0,
        "profit_factor": metrics["profit_factor"] >= PF_FLOOR,
        "drawdown": abs(metrics["max_drawdown_r"]) <= MAX_DD_R,
        "trade_count": metrics["trade_count"] >= MIN_TRADES,
    }
    return {"checks": checks, "passed": all(checks.values())}


def island_ok(row, rows_by_group) -> bool:
    members = sorted(rows_by_group[row["group"]], key=lambda r: r["axis"])
    idx = next(k for k, r in enumerate(members) if r["label"] == row["label"])
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(members) and members[j]["metrics"]["profit_factor"] >= PF_FLOOR:
            return True
    return False


def select(explore_rows, explore_by_tf) -> list[dict]:
    by_group: dict[str, list] = {}
    for r in explore_rows:
        by_group.setdefault(r["group"], []).append(r)
    survivors: list[dict] = []
    for r in explore_rows:
        m = r["metrics"]
        core = passes_core(m)
        if not core["passed"]:
            continue
        if not island_ok(r, by_group):
            continue
        cand = explore_by_tf[r["timeframe"]]  # battery inputs from the explore slice
        outlier = outlier_dependence_ok(m_rs(cand, r), 0.05)
        cost = cost_stress_ok(cand, r["family"], r["params"], r["exit_name"],
                              r["exit_params"], r["h"], 0.0005)
        recent = recent_period_ok(cand, r["family"], r["params"], r["exit_name"],
                                  r["exit_params"], r["h"],
                                  int(RECENT_FRAC * len(cand)))
        tc = trade_count_ok(m_rs(cand, r), MIN_TRADES)
        checks = {**core["checks"], "island": True,
                  "outlier": outlier["passed"], "cost_stress": cost["passed"],
                  "recent": recent["passed"], "trade_count_battery": tc["passed"]}
        passed = all(checks.values())
        if passed:
            r = {**r, "selection": {"checks": checks, "passed": True}}
            survivors.append(r)
    return survivors

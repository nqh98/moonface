"""Stage-2 selection for the practical-full lane: the reused practical select
gates, PLUS the user's multiplicative cost robustness — a survivor must remain
expectancy>0 / PF>1 when the modelled round-trip cost is charged at 2x AND 3x
(in addition to the +5 bps stress already inside practical.select). DSR is never
consulted (reported only, upstream)."""
from __future__ import annotations

from moonface.research import system_battery as sb
from moonface.research.practical.select import select


def _cost_multiple_checks(candles, row) -> dict:
    two = sb.cost_multiple_ok(candles, row["family"], row["params"],
                              row["exit_name"], row["exit_params"], row["h"], 2.0)
    three = sb.cost_multiple_ok(candles, row["family"], row["params"],
                                row["exit_name"], row["exit_params"], row["h"], 3.0)
    return {"cost_2x": two["passed"], "cost_3x": three["passed"],
            "cost_2x_metrics": two, "cost_3x_metrics": three}


def select_full(explore_rows, explore_by_tf) -> list[dict]:
    base = select(explore_rows, explore_by_tf)
    survivors: list[dict] = []
    for r in base:
        cand = explore_by_tf[r["timeframe"]]
        cm = _cost_multiple_checks(cand, r)
        checks = {**r["selection"]["checks"], "cost_2x": cm["cost_2x"],
                  "cost_3x": cm["cost_3x"]}
        if cm["cost_2x"] and cm["cost_3x"]:
            survivors.append({**r, "selection": {"checks": checks, "passed": True},
                              "cost_multiple": cm})
    return survivors

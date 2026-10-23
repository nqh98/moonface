"""Stage 2 — frozen HYBRID validation for the BTC-Specialized lane. Each frozen
candidate is run UNTOUCHED (no refit). First a walk-forward robustness gate on the
VALIDATE segment (robust_frac >= 0.60); the single best survivor by validate aggregate
net R then has the SEALED tail opened EXACTLY ONCE under the full locked econ bar plus
added OOS checks. Accept => PAPER ONLY."""
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.research.btcspec.explore import WF_STEP_BARS, WF_TEST_BARS
from moonface.research.edge_search import econ_walk_forward, net_trade_rs
from moonface.research.system_battery import cost_stress_ok, recent_period_ok

ROBUST_FLOOR = 0.60
TRADE_FLOOR = {"15m": 100, "30m": 80, "1h": 60, "2h": 40, "4h": 30}
RECENT_FRAC = 0.2
EXTRA_COST = 0.0005  # +5 bps/side slippage stress


def _rs(candles, row):
    return net_trade_rs(candles, row["family"], row["params"], row["exit_name"],
                        row["exit_params"], row["h"])


def outlier_topk_ok(rs, ks=(1, 3)) -> dict:
    """Expectancy stays > 0 after dropping the top-k trades, for each k in ks."""
    if not rs:
        return {"passed": False, "drops": {}}
    ordered = sorted(rs, reverse=True)
    drops, ok = {}, True
    for k in ks:
        trimmed = ordered[k:]
        exp = summarize_r(trimmed).expectancy_r if trimmed else 0.0
        drops[f"drop{k}_exp"] = exp
        ok = ok and bool(trimmed) and exp > 0
    return {"passed": ok, "drops": drops}


def walkforward_robust(validate_candles, row) -> dict:
    tf = row["timeframe"]
    wf = econ_walk_forward(validate_candles, row["family"], row["params"],
                           row["exit_name"], row["exit_params"], row["h"],
                           WF_TEST_BARS[tf], WF_STEP_BARS[tf])
    agg = summarize_r(_rs(validate_candles, row))
    return {"robust_frac": wf["metrics"].get("robust_frac", 0.0),
            "agg_total_r": agg.total_r, "n_windows": wf["n_windows"]}


def sealed_gate(sealed_candles, row, extra_cost: float = EXTRA_COST) -> dict:
    tf = row["timeframe"]
    wf = econ_walk_forward(sealed_candles, row["family"], row["params"],
                           row["exit_name"], row["exit_params"], row["h"],
                           WF_TEST_BARS[tf], WF_STEP_BARS[tf])
    rs = _rs(sealed_candles, row)
    s = summarize_r(rs)
    outlier = outlier_topk_ok(rs)
    cost = cost_stress_ok(sealed_candles, row["family"], row["params"],
                          row["exit_name"], row["exit_params"], row["h"], extra_cost)
    recent = recent_period_ok(sealed_candles, row["family"], row["params"],
                              row["exit_name"], row["exit_params"], row["h"],
                              int(RECENT_FRAC * len(sealed_candles)))
    checks = {
        "econ_bar": wf["passed"],
        "net_r_pos": s.total_r > 0,
        "trade_count": s.trade_count >= TRADE_FLOOR[tf],
        "outlier": outlier["passed"],
        "cost_stress": cost["passed"],
        "recent": recent["passed"],
    }
    metrics = {"trade_count": s.trade_count, "total_r": s.total_r,
               "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
               "max_drawdown_r": s.max_drawdown_r,
               "robust_frac": wf["metrics"].get("robust_frac", 0.0),
               "mar": wf["metrics"].get("mar", 0.0)}
    return {"checks": checks, "metrics": metrics, "passed": all(checks.values())}


def validate_all(frozen_rows, validate_by_tf, sealed_by_tf,
                 extra_cost: float = EXTRA_COST) -> list[dict]:
    scored = []
    for row in frozen_rows:
        wf = walkforward_robust(validate_by_tf[row["timeframe"]], row)
        scored.append((row, wf))
    survivors = [(r, wf) for r, wf in scored
                 if wf["robust_frac"] >= ROBUST_FLOOR and wf["agg_total_r"] > 0]
    best_label = None
    if survivors:
        best_row, _ = max(survivors, key=lambda t: t[1]["agg_total_r"])
        best_label = best_row["label"]
    out: list[dict] = []
    for row, wf in scored:
        rec = {**row, "validate": wf, "sealed": None}
        if row["label"] == best_label:
            seg = sealed_gate(sealed_by_tf[row["timeframe"]], row, extra_cost)
            rec["sealed"] = seg
            rec["verdict"] = "paper_accept" if seg["passed"] else "rejected"
        else:
            rec["verdict"] = "rejected"
            rec["reject_reason"] = ("robust_fail"
                                    if wf["robust_frac"] < ROBUST_FLOOR
                                    else "not_selected")
        out.append(rec)
    return out

"""Stage 3+4 — frozen dual-replication. Each frozen candidate is re-run UNTOUCHED
on the validate and sealed segments; accepted as PAPER ONLY iff it independently
clears the practical economic thresholds on BOTH, with the same expectancy sign.
No parameter is re-fit here."""
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.research.edge_search import net_trade_rs
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR
from moonface.research.system_battery import cost_stress_ok


def segment_metrics(candles, row) -> dict:
    rs = net_trade_rs(candles, row["family"], row["params"], row["exit_name"],
                      row["exit_params"], row["h"])
    s = summarize_r(rs)
    cost = cost_stress_ok(candles, row["family"], row["params"], row["exit_name"],
                          row["exit_params"], row["h"], 0.0005)
    return {"trade_count": s.trade_count, "total_r": s.total_r,
            "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "max_drawdown_r": s.max_drawdown_r, "cost_stress_ok": cost["passed"]}


def segment_pass(seg: dict) -> bool:
    return (seg["profit_factor"] >= PF_FLOOR and seg["expectancy_r"] > 0
            and abs(seg["max_drawdown_r"]) <= MAX_DD_R
            and seg["trade_count"] >= MIN_TRADES and seg["cost_stress_ok"])


def validate_candidate(row, validate_candles, sealed_candles) -> dict:
    v = segment_metrics(validate_candles, row)
    s = segment_metrics(sealed_candles, row)
    same_sign = (v["expectancy_r"] > 0) == (s["expectancy_r"] > 0)
    accept = segment_pass(v) and segment_pass(s) and same_sign
    return {**row, "validate": v, "sealed": s,
            "verdict": "paper_accept" if accept else "rejected"}


def validate_all(frozen_rows, validate_by_tf, sealed_by_tf) -> list[dict]:
    return [validate_candidate(r, validate_by_tf[r["timeframe"]],
                               sealed_by_tf[r["timeframe"]])
            for r in frozen_rows]

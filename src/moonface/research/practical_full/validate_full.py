"""Stage 3+4 dual replication for the practical-full lane. Each frozen candidate
is re-run UNTOUCHED on the validate and sealed segments; accepted PAPER-ONLY iff
it clears the practical economic thresholds (practical.validate.segment_pass) on
BOTH, with the same expectancy sign, AND clears the 2x/3x multiplicative cost
gate on BOTH. No parameter is re-fit here."""
from __future__ import annotations

from moonface.research import system_battery as sb
from moonface.research.practical.validate import segment_metrics, segment_pass


def _segment(candles, row) -> dict:
    m = segment_metrics(candles, row)
    two = sb.cost_multiple_ok(candles, row["family"], row["params"],
                              row["exit_name"], row["exit_params"], row["h"], 2.0)
    three = sb.cost_multiple_ok(candles, row["family"], row["params"],
                                row["exit_name"], row["exit_params"], row["h"], 3.0)
    return {**m, "cost_2x_ok": two["passed"], "cost_3x_ok": three["passed"]}


def _seg_full_pass(seg: dict) -> bool:
    return segment_pass(seg) and seg["cost_2x_ok"] and seg["cost_3x_ok"]


def validate_candidate_full(row, validate_candles, sealed_candles) -> dict:
    v = _segment(validate_candles, row)
    s = _segment(sealed_candles, row)
    same_sign = (v["expectancy_r"] > 0) == (s["expectancy_r"] > 0)
    accept = _seg_full_pass(v) and _seg_full_pass(s) and same_sign
    return {**row, "validate": v, "sealed": s,
            "verdict": "paper_accept" if accept else "rejected"}


def validate_all_full(frozen_rows, validate_by_tf, sealed_by_tf) -> list[dict]:
    return [validate_candidate_full(r, validate_by_tf[r["timeframe"]],
                                    sealed_by_tf[r["timeframe"]])
            for r in frozen_rows]

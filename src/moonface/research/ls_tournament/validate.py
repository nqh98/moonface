"""Validate/sealed verdict assembly for the BTC long/short tournament."""
from __future__ import annotations

from moonface.core.metrics import COST_FRACTION, summarize_r
from moonface.research.ls_tournament.explore import _evaluate_records
from moonface.research.ls_tournament.grid import ExploreConfig
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR

EXTRA_COST = 0.0005


def _cost_stress(records: list[dict], extra_cost: float = EXTRA_COST) -> dict:
    stressed = [r["net_r"] - extra_cost / r["atr_frac"] if r["atr_frac"] > 0 else r["net_r"]
                for r in records]
    s = summarize_r(stressed)
    return {"expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "passed": s.expectancy_r > 0 and s.profit_factor > 1.0}


def _cost_multiple(records: list[dict], mult: float) -> dict:
    """Charge `mult`x the modelled round-trip cost; mirrors select._cost_multiple."""
    return _cost_stress(records, extra_cost=(mult - 1.0) * COST_FRACTION)


def _segment(candles, config: ExploreConfig, context=None) -> dict:
    scored = _evaluate_records(candles, config, context)
    metrics = scored["metrics"]
    cost = _cost_stress(scored["records"])
    checks = {
        "practical": metrics["profit_factor"] >= PF_FLOOR and metrics["expectancy_r"] > 0
        and abs(metrics["max_drawdown_r"]) <= MAX_DD_R and metrics["trade_count"] >= MIN_TRADES,
        "cost_stress": cost["passed"],
        "cost_2x": _cost_multiple(scored["records"], 2.0)["passed"],
        "cost_3x": _cost_multiple(scored["records"], 3.0)["passed"],
        "twin": metrics["total_r"] > metrics["twin_total_r"],
    }
    return {"metrics": metrics, "cost_stress": cost, "checks": checks, "passed": all(checks.values())}


def validate_candidate(row, validate_candles, sealed_candles, context_validate=None,
                       context_sealed=None, train_candles=None, context_train=None) -> dict:
    config = ExploreConfig(
        label=row["label"], timeframe=row["timeframe"],
        long_rule=row["long_rule"], short_rule=row["short_rule"],
        filters=tuple(row["filters"]), exit_name=row["exit_name"],
        exit_params=row["exit_params"], h=row["h"], group=row["group"],
        axis=row["axis"],
    )
    v = _segment(validate_candles, config, context_validate)
    s = _segment(sealed_candles, config, context_sealed)
    same_sign = (v["metrics"]["expectancy_r"] > 0) == (s["metrics"]["expectancy_r"] > 0)
    accept = v["passed"] and s["passed"] and same_sign
    out = {**row, "validate": v["metrics"], "sealed": s["metrics"],
           "verdict": "paper_candidate" if accept else "negative"}
    if train_candles is not None:
        t = _segment(train_candles, config, context_train)
        out["train"] = t["metrics"]
        out["train_passed"] = t["passed"]
    return out


def validate_all(frozen_rows, train_by_tf, validate_by_tf, sealed_by_tf,
                 context_validate_by_tf: dict | None = None,
                 context_sealed_by_tf: dict | None = None,
                 context_train_by_tf: dict | None = None) -> list[dict]:
    out: list[dict] = []
    for row in frozen_rows:
        tf = row["timeframe"]
        tv = None if context_validate_by_tf is None else context_validate_by_tf.get(tf)
        ts = None if context_sealed_by_tf is None else context_sealed_by_tf.get(tf)
        tt = None if context_train_by_tf is None else context_train_by_tf.get(tf)
        out.append(validate_candidate(row, validate_by_tf[tf], sealed_by_tf[tf],
                                      context_validate=tv, context_sealed=ts,
                                      train_candles=train_by_tf[tf], context_train=tt))
    return out

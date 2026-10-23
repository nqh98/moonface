"""Stage 3+4 — frozen dual replication. Each config is re-run UNTOUCHED on the
validate and sealed views; PAPER ONLY accept iff it clears the practical
thresholds on BOTH with the same expectancy sign. No parameter is re-fit."""
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.research.practical.validate import segment_pass
from moonface.research.playbook.backtest import playbook_trade_rs
from moonface.research.playbook.select import playbook_cost_stress_ok


def segment_metrics(view, config) -> dict:
    rs = playbook_trade_rs(view, config)
    s = summarize_r(rs)
    cost = playbook_cost_stress_ok(view, config)
    return {"trade_count": s.trade_count, "total_r": s.total_r,
            "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "max_drawdown_r": s.max_drawdown_r, "cost_stress_ok": cost["passed"]}


def validate_candidate(config, validate_view, sealed_view) -> dict:
    v = segment_metrics(validate_view, config)
    s = segment_metrics(sealed_view, config)
    same_sign = (v["expectancy_r"] > 0) == (s["expectancy_r"] > 0)
    accept = segment_pass(v) and segment_pass(s) and same_sign
    return {"label": config.label, "validate": v, "sealed": s,
            "verdict": "paper_accept" if accept else "rejected"}


def validate_all(configs, validate_view, sealed_view) -> list[dict]:
    return [validate_candidate(c, validate_view, sealed_view) for c in configs]

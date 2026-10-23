from __future__ import annotations

from dataclasses import dataclass

from moonface.core.metrics import (equity_summary,
                                         equity_summary_from_returns,
                                         summarize_r)


@dataclass(frozen=True)
class AdapterResult:
    key: str
    lane: str
    unit: str
    config: dict
    config_source: str
    exit_name: str
    current_signal: str
    records: list[dict] | None = None
    r_stream: list[float] | None = None


def metric_block(res: "AdapterResult") -> dict:
    if res.records is not None:
        rs = [r["net_r"] for r in res.records]
        trades = [(r["net_r"], r["atr_frac"]) for r in res.records]
        mar = equity_summary(trades, 0.01).mar if trades else 0.0
    else:
        rs = list(res.r_stream or [])
        mar = equity_summary_from_returns([0.01 * r for r in rs]).mar if rs else 0.0
    s = summarize_r(rs)
    pf = s.profit_factor
    return {
        "expectancy_r": round(s.expectancy_r, 6),
        "pf": None if pf == float("inf") else round(pf, 4),
        "max_dd_r": round(s.max_drawdown_r, 4),
        "n": s.trade_count,
        "total_r": round(s.total_r, 4),
        "mar": None if mar == float("inf") else round(mar, 4),
    }

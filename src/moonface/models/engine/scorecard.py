# src/moonface/signal/engine/scorecard.py
from __future__ import annotations

from moonface.core.metrics import (MAX_LEVERAGE,
                                         equity_summary_from_returns,
                                         summarize_r)
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.discipline import (closed_trades, engine_entries,
                                               hard_breaker_tripped,
                                               in_cooldown, is_paused,
                                               realized_drawdown_r,
                                               windowed_drawdown_r)


def engine_scorecard(entries: list[dict], cfg: EngineConfig) -> dict:
    version = engine_hash(cfg)
    mine = engine_entries(entries, version)
    trades = closed_trades(entries, version)
    rs = [r for r, _, _ in trades]
    summ = summarize_r(rs)
    returns = [min(frac, MAX_LEVERAGE * atr_frac) * r
               for r, atr_frac, frac in trades]
    eq = equity_summary_from_returns(returns)

    n = len(mine)
    in_pos = sum(1 for e in mine if e.get("action") in ("OPEN", "HOLD"))
    waits = sum(1 for e in mine if e.get("action") == "WAIT")

    now_ms = max((int(e.get("ts_ms") or 0) for e in mine), default=0)
    pause_reason = None
    if is_paused(entries, cfg, version, now_ms):
        state = "paused"
        pause_reason = ("hard_breaker"
                        if hard_breaker_tripped(entries, cfg, version)
                        else "trailing_window")
    elif in_cooldown(entries, cfg, version):
        state = "cooldown"
    else:
        state = "active"

    return {
        "signals": n,
        "closed_trades": len(trades),
        "net_r": round(summ.total_r, 4),
        "expectancy_r": summ.expectancy_r,
        "profit_factor": summ.profit_factor,
        "win_rate": summ.win_rate,
        "max_drawdown_r": summ.max_drawdown_r,
        "equity_net_return": eq.net_return,
        "equity_max_drawdown": eq.max_drawdown,
        "mar": eq.mar,
        "pct_in_position": round(in_pos / n, 4) if n else 0.0,
        "pct_wait": round(waits / n, 4) if n else 0.0,
        "realized_drawdown_r": round(realized_drawdown_r(entries, version), 4),
        "windowed_drawdown_r": round(
            windowed_drawdown_r(entries, cfg, version, now_ms), 4),
        "state": state,
        "pause_reason": pause_reason,
    }

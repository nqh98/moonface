"""Isolated research-side forward paper-watch for a practical-full finalist.

Accrues CLOSED forward trades (entry at/after t0, fully resolved within available
data) from the research replay and applies a FROZEN forward gate whose thresholds
mirror moonface.signal.journal.forward_report exactly — 20 closed trades, 12
wall-clock weeks, net_r>0, and equity drawdown within the locked 0.30 budget
(= econ-bar MaxDD 30R @ f=0.01 as an equity fraction). Read-only and
self-contained: never reads or writes promotion/ or journal/signals.jsonl.
Per-trade math is single_trade_r / equity_summary, so forward and backtest
numbers are directly comparable.
"""
from __future__ import annotations

from moonface.core.metrics import equity_summary, single_trade_r
from moonface.research.entries import PRICE_FAMILIES
from moonface.features.oi_features import nonoverlap

FORWARD_MIN_TRADES = 20
FORWARD_MIN_WEEKS = 12.0
MAX_DD_BUDGET = 0.30      # locked econ-bar MaxDD (30R @ f=0.01) as equity fraction
_WEEK_MS = 7 * 86_400_000


def _forward_trades(candles, cfg, t0_ms):
    """((net_r, atr_frac) closed trades, open_count, first_forward_entry_ts).

    An entry counts as CLOSED only when its full max_bars holding window fits
    inside the available data (entry_idx + max_bars <= last_idx), so a position
    still resolving at the data edge is reported open, never marked-to-end."""
    events = nonoverlap(PRICE_FAMILIES[cfg["family"]](candles, cfg["params"]),
                        cfg["h"])
    last = len(candles) - 1
    max_bars = cfg["exit_params"].get("max_bars", 0)
    trades: list[tuple[float, float]] = []
    open_trades = 0
    first_ts: int | None = None
    for i, side in events:
        if candles[i].timestamp_ms < t0_ms:
            continue
        first_ts = (candles[i].timestamp_ms if first_ts is None
                    else min(first_ts, candles[i].timestamp_ms))
        if i + max_bars > last:
            open_trades += 1
            continue
        res = single_trade_r(candles, i, side, cfg["exit_name"],
                             cfg["exit_params"])
        if res is None:
            open_trades += 1
            continue
        trades.append(res)
    return trades, open_trades, first_ts


def forward_report(candles, cfg, t0_ms: int, now_ms: int) -> dict:
    trades, open_trades, first_ts = _forward_trades(candles, cfg, t0_ms)
    eq = equity_summary(trades, cfg["fraction"])
    net_r = round(sum(r for r, _ in trades), 4)
    elapsed_weeks = 0.0
    if first_ts is not None and candles:
        elapsed_weeks = max(0.0, (candles[-1].timestamp_ms - first_ts) / _WEEK_MS)
    gate = {
        "min_trades": len(trades) >= FORWARD_MIN_TRADES,
        "min_weeks": elapsed_weeks >= FORWARD_MIN_WEEKS,
        "net_positive": net_r > 0,
        "drawdown_within_p95": eq.max_drawdown >= -MAX_DD_BUDGET,
    }
    gate["passed"] = all(gate.values())
    return {
        "closed_trades": len(trades),
        "open_trades": open_trades,
        "net_r": net_r,
        "expectancy_r": round(net_r / len(trades), 4) if trades else 0.0,
        "max_drawdown": eq.max_drawdown,
        "elapsed_weeks": round(elapsed_weeks, 2),
        "wall_clock_weeks_since_t0": round(max(0.0, (now_ms - t0_ms) / _WEEK_MS), 2),
        "gate": gate,
    }

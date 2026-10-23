from __future__ import annotations

FORWARD_MIN_TRADES = 20
FORWARD_MIN_WEEKS = 12.0
MAX_DD_BUDGET = 0.30
WEEK_MS = 7 * 24 * 3600 * 1000


def _max_drawdown(trades: list[float]) -> float:
    peak = eq = 0.0
    mdd = 0.0
    for r in trades:
        eq += r
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    return mdd


def forward_report(trades: list[float], t0_ms: int, now_ms: int) -> dict:
    n = len(trades)
    elapsed_weeks = max(0.0, (now_ms - t0_ms) / WEEK_MS)
    net_r = round(sum(trades), 6)
    mdd = _max_drawdown(trades)
    dd_ok = mdd >= -MAX_DD_BUDGET
    min_trades = n >= FORWARD_MIN_TRADES
    min_weeks = elapsed_weeks >= FORWARD_MIN_WEEKS
    gate_passed = min_trades and min_weeks and net_r > 0 and dd_ok

    if n >= 1 and not dd_ok:
        outcome = "DOWNGRADE_DD"
    elif gate_passed:
        outcome = "REAFFIRM"
    elif min_trades and min_weeks and not gate_passed:
        outcome = "DOWNGRADE_HORIZON"
    else:
        outcome = "INCONCLUSIVE"

    return {
        "closed_trades": n,
        "elapsed_weeks": round(elapsed_weeks, 2),
        "net_r": net_r,
        "max_drawdown": round(mdd, 6),
        "gate": {"passed": gate_passed, "drawdown_within_p95": dd_ok},
        "outcome": outcome,
    }

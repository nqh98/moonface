from __future__ import annotations

from moonface.core.metrics import deflated_sharpe, equity_summary_from_returns
from moonface.research.ladder import (
    DRAWDOWN_BUDGET,
    DSR_THRESHOLD,
    LOCKBOX_MIN_MAR,
    LOCKBOX_MIN_TRADES,
    SCREEN_FRACTION,
    SCREEN_MIN_TRADES,
)


def gate_stages(returns: list[float], fence_idx: int) -> dict:
    """Standard 4-stage ladder on a daily-return series. One frozen design, so
    the DSR deflation count is n_trials=1. The tail [fence_idx:] is one-touch
    and only meaningful once stages 1-3 pass."""
    research, tail = returns[:fence_idx], returns[fence_idx:]
    split = int(len(research) * SCREEN_FRACTION)
    screen, holdout = research[:split], research[split:]
    screen_mean = sum(screen) / len(screen) if screen else 0.0

    hold = equity_summary_from_returns(holdout)
    full = equity_summary_from_returns(research)
    tail_s = equity_summary_from_returns(tail)
    dsr = deflated_sharpe(full.sharpe, full.trade_count, full.skew,
                          full.kurtosis, [full.sharpe], 1)

    s1 = len(screen) >= SCREEN_MIN_TRADES and screen_mean > 0.0
    s2 = hold.mar > 0.0 and hold.max_drawdown >= DRAWDOWN_BUDGET
    s3 = dsr >= DSR_THRESHOLD
    s4 = (tail_s.mar >= LOCKBOX_MIN_MAR
          and tail_s.trade_count >= LOCKBOX_MIN_TRADES
          and tail_s.max_drawdown >= DRAWDOWN_BUDGET)
    verdict = "paper_candidate" if (s1 and s2 and s3 and s4) else "closed_negative"

    return {
        "screen_days": len(screen),
        "screen_mean": round(screen_mean, 8),
        "holdout_mar": hold.mar,
        "holdout_drawdown": hold.max_drawdown,
        "research_days": full.trade_count,
        "research_net": full.net_return,
        "research_mar": full.mar,
        "research_sharpe": full.sharpe,
        "research_skew": full.skew,
        "research_kurtosis": full.kurtosis,
        "dsr": round(dsr, 6),
        "tail_days": tail_s.trade_count,
        "tail_net": tail_s.net_return,
        "tail_mar": tail_s.mar,
        "tail_drawdown": tail_s.max_drawdown,
        "stage1_pass": s1,
        "stage2_pass": s2,
        "stage3_pass": s3,
        "stage4_pass": s4,
        "verdict": verdict,
    }

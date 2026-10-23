"""Kernel-side DSR gate and lockbox-tail evaluation.

Both operate on already-computed metrics or an already-generated trade
stream -- pure verification, no trade simulation -- so kernel/runner.py's DSR
and lockbox gating no longer needs research.ladder for these two pieces.
Moved out of research/ladder.py at G3; r_stream and the screen/holdout gates
(stage1_passed, stage2_passed, evaluate_research) stay a lane concern there,
since those generate trades rather than gate an already-computed number."""
from __future__ import annotations

from moonface.core.metrics import deflated_sharpe, equity_summary, summarize_r
from moonface.kernel.spec import HypothesisSpec

DSR_THRESHOLD = 0.95


def stage3_dsr(rows: list[dict], grid_size: int) -> dict[str, float]:
    """Deflated Sharpe for every oos_pass row. Trial-SR variance comes from
    every row that produced a research Sharpe (including rejects); the trial
    COUNT is the full registered grid, so screened-out rows still deflate."""
    trial_srs = [r["stage_results"]["research_sharpe"] for r in rows
                 if "research_sharpe" in r["stage_results"]]
    out: dict[str, float] = {}
    for r in rows:
        if r["status"] != "oos_pass":
            continue
        m = r["stage_results"]
        out[r["spec_hash"]] = round(deflated_sharpe(
            m["research_sharpe"], m["research_trades"], m["research_skew"],
            m["research_kurtosis"], trial_srs, grid_size), 6)
    return out


def evaluate_lockbox(stream: list[tuple[int, float, float]],
                     spec: HypothesisSpec, fence_index: int) -> dict:
    """One-touch tail evaluation over an already-generated (entry_index, net_r,
    atr_frac) stream. The caller (runner) must have spent the domain's
    lockbox flag via Store.touch_lockbox, and generated stream from the
    unfenced data, before calling this."""
    tail = [(r, af) for i, r, af in stream if i >= fence_index]
    eq = equity_summary(tail, spec.fraction)
    tail_screen = summarize_r([r for r, _ in tail])
    return {
        "tail_trades": eq.trade_count,
        "tail_mar": eq.mar,
        "tail_net_return": eq.net_return,
        "tail_sharpe": eq.sharpe,
        "tail_drawdown": eq.max_drawdown,
        "tail_expectancy_r": tail_screen.expectancy_r,
    }

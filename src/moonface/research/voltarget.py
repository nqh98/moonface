# src/moonface/research/voltarget.py
"""Vol/risk-targeted sizing for funding_fade + fixed_bracket (spec 2026-07-02).

The treatment sizes each trade so stop-risk is constant (notional inversely
proportional to ATR), iso-average-risk calibrated to the fixed-fractional
control. Pure functions over the (entry_index, net_R, atr_frac) stream from
ladder.r_stream; sizing math only — no entry/exit logic of its own, and no
store/lockbox imports (those live in voltarget_runner)."""
from __future__ import annotations

from moonface.core.metrics import (
    EquitySummary, MAX_LEVERAGE, equity_summary, equity_summary_from_returns, summarize_r)
from moonface.research.ladder import (
    DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR, LOCKBOX_MIN_TRADES, SCREEN_FRACTION,
    SCREEN_MIN_TRADES, r_stream)

CONTROL_FRACTION = 0.01            # fixed-fractional baseline (== funding_fade_transfer)
ISO_MEAN_FRACTION = 0.01           # treatment calibrated so mean(f_i) == this

# Frozen construction (spec §4).
VOLTARGET_ENTRY = ("funding_fade", {"window": 60, "z_thr": 1.5})
VOLTARGET_EXIT = ("fixed_bracket", {"atr_period": 14, "k_stop": 2.0, "m_tp": 4.0})


def vol_fraction(atr_frac: float, target_risk: float) -> float:
    """Per-trade notional fraction that equalizes stop-risk: target_risk/atr_frac,
    clamped to [0, MAX_LEVERAGE*atr_frac] (the program's leverage clamp)."""
    raw = target_risk / atr_frac
    return max(0.0, min(raw, MAX_LEVERAGE * atr_frac))


def calibrate_target_risk(atr_fracs: list[float],
                          mean_fraction: float = ISO_MEAN_FRACTION) -> float:
    """Scalar target_risk s.t. mean(vol_fraction(af, target_risk)) == mean_fraction.
    vol_fraction is non-decreasing in target_risk, so a unique root exists when
    the saturated mean (MAX_LEVERAGE*mean(af)) reaches mean_fraction."""
    if not atr_fracs or mean_fraction <= 0.0:
        return 0.0

    def mean_at(tr: float) -> float:
        return sum(vol_fraction(af, tr) for af in atr_fracs) / len(atr_fracs)

    hi = mean_fraction
    while mean_at(hi) < mean_fraction and hi < 1.0:
        hi *= 2.0
    if mean_at(hi) < mean_fraction:
        raise ValueError("iso-average-risk target unreachable under the leverage clamp")
    lo = 0.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mean_at(mid) < mean_fraction:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def treatment_returns(trades: list[tuple[float, float]],
                      target_risk: float) -> list[float]:
    """Per-trade sized returns f_i * R_i for the vol-targeted treatment."""
    return [vol_fraction(af, target_risk) * r for r, af in trades]


def paired_dominance(treatment: EquitySummary,
                     control: EquitySummary) -> bool:
    """Strict: treatment beats control on BOTH MAR and Sharpe."""
    return treatment.mar > control.mar and treatment.sharpe > control.sharpe


def evaluate_paired(stream: list[tuple[int, float, float]], split_index: int,
                    control_fraction: float = CONTROL_FRACTION) -> dict:
    """One pass over a research-window stream split at bar index `split_index`.
    target_risk is calibrated on screen trades (no lookahead) and applied
    unchanged to holdout and full. Returns both arms + stage metrics + paired
    dominance on the holdout."""
    screen = [(r, af) for i, r, af in stream if i < split_index]
    holdout = [(r, af) for i, r, af in stream if i >= split_index]
    full = [(r, af) for _, r, af in stream]
    screen_summary = summarize_r([r for r, _ in screen])

    target_risk = calibrate_target_risk([af for _, af in screen]) if screen else 0.0
    ctrl_hold = equity_summary(holdout, control_fraction)
    trt_hold = equity_summary_from_returns(treatment_returns(holdout, target_risk))
    ctrl_full = equity_summary(full, control_fraction)
    trt_full = equity_summary_from_returns(treatment_returns(full, target_risk))
    return {
        "screen_trades": screen_summary.trade_count,
        "screen_expectancy_r": screen_summary.expectancy_r,
        "holdout_trades": ctrl_hold.trade_count,
        "holdout_control_mar": ctrl_hold.mar,
        "holdout_treatment_mar": trt_hold.mar,
        "holdout_treatment_dd": trt_hold.max_drawdown,
        "holdout_dominance": paired_dominance(trt_hold, ctrl_hold),
        "research_sharpe": trt_full.sharpe,
        "research_skew": trt_full.skew,
        "research_kurtosis": trt_full.kurtosis,
        "research_trades": trt_full.trade_count,
        "research_control_mar": ctrl_full.mar,
        "research_treatment_mar": trt_full.mar,
        "target_risk": round(target_risk, 8),
    }


def stage1_paired(m: dict) -> bool:
    return m["screen_trades"] >= SCREEN_MIN_TRADES and m["screen_expectancy_r"] > 0.0


def stage2_paired(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def paired_research(spec, research, screen_fraction: float = SCREEN_FRACTION) -> dict:
    stream = r_stream(spec, research)
    split = int(len(research.candles) * screen_fraction)
    return evaluate_paired(stream, split)


def paired_lockbox(spec, full, fence_index: int,
                   screen_fraction: float = SCREEN_FRACTION) -> dict:
    """Tail (entry_index >= fence_index) for both arms. target_risk calibrated on
    the screen window of the research region (bars < screen_fraction*fence) —
    identical to paired_research's calibration, so no tail lookahead."""
    stream = r_stream(spec, full)
    screen_split = int(fence_index * screen_fraction)
    screen_afs = [af for i, r, af in stream if i < screen_split]
    target_risk = calibrate_target_risk(screen_afs) if screen_afs else 0.0
    tail = [(r, af) for i, r, af in stream if i >= fence_index]
    ctrl = equity_summary(tail, CONTROL_FRACTION)
    trt = equity_summary_from_returns(treatment_returns(tail, target_risk))
    return {
        "tail_trades": trt.trade_count,
        "tail_control_mar": ctrl.mar,
        "tail_treatment_mar": trt.mar,
        "tail_treatment_dd": trt.max_drawdown,
        "tail_dominance": paired_dominance(trt, ctrl),
        "target_risk": round(target_risk, 8),
    }


def stage4_paired(m: dict) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= LOCKBOX_MIN_TRADES
            and m["tail_dominance"])

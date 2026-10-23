# src/moonface/research/ladder.py
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.core.metrics import COST_FRACTION, single_trade_r  # noqa: F401
from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.core.metrics import equity_summary
from moonface.kernel.dsr import DSR_THRESHOLD, stage3_dsr  # noqa: F401 -- re-export, back-compat
from moonface.kernel import dsr as _kernel_dsr
from moonface.kernel.spec import HypothesisSpec

# Pre-committed gates (design spec section 3-4). Production code uses these
# constants; keyword overrides exist for tests only. Functions read the
# constants at call time so unittest.mock.patch.object works.
SCREEN_FRACTION = 0.7
SCREEN_MIN_TRADES = 30
LOCKBOX_MIN_MAR = 1.0
LOCKBOX_MIN_TRADES = 10
DRAWDOWN_BUDGET = -0.30  # worst acceptable peak-to-trough equity fraction
R_SANITY_CAP = 20.0  # any |net R| above this is a data/realism anomaly


def r_stream(spec: HypothesisSpec, bundle: DataBundle) -> list[tuple[int, float, float]]:
    """(entry_index, net R, atr_frac) triples for the hypothesis.

    net R subtracts the round-trip trading cost converted to R units:
    COST_FRACTION / atr_frac, where atr_frac = (1xATR at entry) / entry price.
    None exits (untradeable entries) are dropped, mirroring the exit battery."""
    entries = generate_entries(spec.entry["family"], spec.entry["params"], bundle)
    candles = bundle.candles
    out: list[tuple[int, float, float]] = []
    for i, side in entries:
        res = single_trade_r(candles, i, side, spec.exit["name"], spec.exit["params"])
        if res is None:
            continue
        net_r, atr_frac = res
        out.append((i, net_r, atr_frac))
    return out


def evaluate_research(spec: HypothesisSpec, research: DataBundle,
                      screen_fraction: float | None = None) -> dict:
    """One pass over the research window. Stages 1 and 2 both gate on this
    output, so the expensive generator/exit evaluation runs exactly once."""
    frac = SCREEN_FRACTION if screen_fraction is None else screen_fraction
    stream = r_stream(spec, research)
    split = int(len(research.candles) * frac)
    screen_rs = [r for i, r, _ in stream if i < split]
    holdout_trades = [(r, af) for i, r, af in stream if i >= split]
    screen = summarize_r(screen_rs)
    holdout = equity_summary(holdout_trades, spec.fraction)
    full = equity_summary([(r, af) for _, r, af in stream], spec.fraction)
    return {
        "screen_trades": screen.trade_count,
        "screen_expectancy_r": screen.expectancy_r,
        "holdout_trades": holdout.trade_count,
        "holdout_mar": holdout.mar,
        "holdout_net_return": holdout.net_return,
        "holdout_drawdown": holdout.max_drawdown,
        "research_trades": full.trade_count,
        "research_mar": full.mar,
        "research_sharpe": full.sharpe,
        "research_skew": full.skew,
        "research_kurtosis": full.kurtosis,
        "max_abs_r": round(max((abs(r) for _, r, _ in stream), default=0.0), 4),
    }


def stage1_passed(m: dict, min_trades: int | None = None) -> bool:
    floor = SCREEN_MIN_TRADES if min_trades is None else min_trades
    return m["screen_trades"] >= floor and m["screen_expectancy_r"] > 0.0


def stage2_passed(m: dict) -> bool:
    return m["holdout_mar"] > 0.0 and m["holdout_drawdown"] >= DRAWDOWN_BUDGET


def evaluate_lockbox(spec: HypothesisSpec, full: DataBundle,
                     fence_index: int) -> dict:
    """Back-compat wrapper: generates the trade stream, then delegates to
    kernel.dsr.evaluate_lockbox (moved there at G3 -- pure verification over
    an already-generated stream, so kernel/ no longer needs to reach into
    this module for the lockbox tail evaluation itself)."""
    return _kernel_dsr.evaluate_lockbox(r_stream(spec, full), spec, fence_index)


def stage4_passed(m: dict, min_mar: float | None = None,
                  min_trades: int | None = None) -> bool:
    mar_floor = LOCKBOX_MIN_MAR if min_mar is None else min_mar
    trade_floor = LOCKBOX_MIN_TRADES if min_trades is None else min_trades
    return (m["tail_mar"] >= mar_floor and m["tail_trades"] >= trade_floor
            and m["tail_drawdown"] >= DRAWDOWN_BUDGET)

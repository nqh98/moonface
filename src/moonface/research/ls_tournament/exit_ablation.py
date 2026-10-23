"""Exit ablation for the frozen BTC 4h long/short donchian_break n=100 survivor.

The entry is held BYTE-IDENTICAL to the tournament survivor (donchian_break n=100,
symmetric long+short, 4h, non-overlap horizon h=48). Only the exit/stop mechanism
varies. The question this lane answers: is `atr_trail` helping or hurting — and is
any exit able to make the recent (sealed, ~2025-2026) window positive, or is the
entry/regime itself out of edge?

The three NEW exit functions here (breakeven_r, lock_profit, partial_tp_trail) are
deliberately kept OUT of foundation.exits.EXIT_REGISTRY / EXECUTABLE_EXITS so the
academic research grid and every concluded domain's DSR calibration are unchanged
(`tests/test_ls_tournament_isolation.py` guards that membership). They share the
registry's gross-R-in-1xATR-units convention; costs are applied by the scorer here,
exactly as foundation.metrics.single_trade_r does.
"""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.exits import (
    _fill,
    _r_unit,
    atr_trail,
    chandelier,
    donchian_trail,
    fixed_bracket,
    horizon_hold,
    horizon_wide_stop,
)
from moonface.core.metrics import COST_FRACTION, summarize_r
from moonface.core.models import Candle
from moonface.core.risk import risk_unit
from moonface.research.ls_tournament.explore import _rule_entries
from moonface.features.oi_features import nonoverlap
from moonface.research import system_battery as sb
from moonface.kernel.power_harness import MAX_DD_R, MIN_TRADES, PF_FLOOR

# ---------------------------------------------------------------------------
# Frozen entry (the tournament survivor) — never varied across the ablation.
# ---------------------------------------------------------------------------
ENTRY_FAMILY = "donchian_break"
ENTRY_PARAMS = {"n": 100}
ENTRY_H = 48
TIMEFRAME = "4h"
_AP = 14
_MAX_BARS = 120  # the survivor's atr_trail cap; reused so every capped exit is apples-to-apples


# ---------------------------------------------------------------------------
# NEW local exits (NOT registered). gross R in 1xATR-at-entry units.
# ---------------------------------------------------------------------------
def breakeven_r(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Hold n_bars with an initial k_stop*ATR stop; once price reaches +be_trigger R
    favorable, move the stop to entry (breakeven). Generalises breakeven_horizon,
    whose trigger is hard-wired to +1R. Arming happens AFTER the bar's fill check
    (lookahead-free, conservative)."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    n_bars, k_stop, be_trigger = params["n_bars"], params["k_stop"], params["be_trigger"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    target = entry + be_trigger * unit if side == "LONG" else entry - be_trigger * unit
    armed = False
    end = min(i + n_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
        if not armed:
            reached = bar.high >= target if side == "LONG" else bar.low <= target
            if reached:
                stop = entry
                armed = True
    return round(sign * (h1[end].close - entry) / unit, 4)


def lock_profit(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Hold n_bars with an initial k_stop*ATR stop; once price reaches +lock_trigger R
    favorable, ratchet the stop to +lock_level R (lock in profit) and hold for more.
    Arming happens AFTER the bar's fill check (lookahead-free)."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    n_bars, k_stop = params["n_bars"], params["k_stop"]
    lock_trigger, lock_level = params["lock_trigger"], params["lock_level"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    trigger = entry + lock_trigger * unit if side == "LONG" else entry - lock_trigger * unit
    lock = entry + lock_level * unit if side == "LONG" else entry - lock_level * unit
    armed = False
    end = min(i + n_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            return round(sign * (hit - entry) / unit, 4)
        if not armed:
            reached = bar.high >= trigger if side == "LONG" else bar.low <= trigger
            if reached:
                stop = lock
                armed = True
    return round(sign * (h1[end].close - entry) / unit, 4)


def partial_tp_trail(i: int, side: str, h1: list[Candle], params: dict) -> float | None:
    """Scale out tp_frac of the position at a +tp_level R limit, then trail the
    remainder with a k_trail*ATR stop from the running extreme. The whole position
    starts behind an initial k_stop*ATR stop; the trail only ratchets toward price.
    Pessimistic fill: stop is checked before the TP limit on each bar. Returns the
    POSITION-weighted gross R (booked partial + remaining*exit). The extra exit leg's
    cost is charged by the scorer via cost_legs, not here."""
    unit = _r_unit(h1, i, params["atr_period"])
    if unit is None:
        return None
    k_trail, k_stop = params["k_trail"], params["k_stop"]
    tp_level, tp_frac, max_bars = params["tp_level"], params["tp_frac"], params["max_bars"]
    entry = h1[i].close
    sign = 1.0 if side == "LONG" else -1.0
    trail = k_trail * unit
    extreme = entry
    stop = entry - k_stop * unit if side == "LONG" else entry + k_stop * unit
    tp = entry + tp_level * unit if side == "LONG" else entry - tp_level * unit
    booked = 0.0
    remaining = 1.0
    end = min(i + max_bars, len(h1) - 1)
    for j in range(i + 1, end + 1):
        bar = h1[j]
        hit = _fill(bar, side, stop, None)
        if hit is not None:
            r = sign * (hit - entry) / unit
            return round(booked + remaining * r, 4)
        if remaining == 1.0:  # partial leg not yet taken
            tp_hit = bar.high >= tp if side == "LONG" else bar.low <= tp
            if tp_hit:
                booked += tp_frac * tp_level
                remaining = 1.0 - tp_frac
        if side == "LONG":
            extreme = max(extreme, bar.high)
            stop = max(stop, extreme - trail)
        else:
            extreme = min(extreme, bar.low)
            stop = min(stop, extreme + trail)
    r = sign * (h1[end].close - entry) / unit
    return round(booked + remaining * r, 4)


# Local exit fns callable by name; foundation fns reused directly.
_LOCAL_FNS = {
    "breakeven_r": breakeven_r,
    "lock_profit": lock_profit,
    "partial_tp_trail": partial_tp_trail,
    "atr_trail": atr_trail,
    "chandelier": chandelier,
    "donchian_trail": donchian_trail,
    "fixed_bracket": fixed_bracket,
    "horizon_hold": horizon_hold,
    "horizon_wide_stop": horizon_wide_stop,
}


# ---------------------------------------------------------------------------
# The ablation grid: one frozen entry, many exits. atr_trail k=2.0 is the
# BASELINE (the deployed survivor's exit); every other arm is judged against it.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ExitSpec:
    key: str            # short stable id
    label: str          # human label for the report
    exit_name: str      # dispatch name in _LOCAL_FNS
    params: dict        # exit params (includes atr_period)
    cost_legs: float    # round-trips charged (partial scale-out = 1.5)
    requested: str      # which item of the user's list this realises


ABLATION_EXITS: tuple[ExitSpec, ...] = (
    ExitSpec("atr_trail_2", "atr_trail k=2.0 (BASELINE)", "atr_trail",
             {"k_trail": 2.0, "max_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "current atr_trail baseline"),
    ExitSpec("hard_stop_2", "hard stop k=2.0, no trail/TP", "horizon_wide_stop",
             {"n_bars": _MAX_BARS, "k_stop": 2.0, "atr_period": _AP}, 1.0,
             "no ATR trail, hard stop only"),
    ExitSpec("fixed_bracket_2_4", "fixed bracket stop=2.0 / TP=4.0", "fixed_bracket",
             {"k_stop": 2.0, "m_tp": 4.0, "atr_period": _AP}, 1.0,
             "fixed bracket stop/target"),
    ExitSpec("donchian_exit", "donchian channel trail (k=2.0,n=20)", "donchian_trail",
             {"k_stop": 2.0, "trail_n": 20, "max_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "Donchian channel exit"),
    ExitSpec("atr_trail_3", "atr_trail k=3.0 (wider)", "atr_trail",
             {"k_trail": 3.0, "max_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "wider ATR trail"),
    ExitSpec("atr_trail_4", "atr_trail k=4.0 (widest)", "atr_trail",
             {"k_trail": 4.0, "max_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "wider ATR trail"),
    ExitSpec("chandelier_3", "chandelier atr_mult=3.0", "chandelier",
             {"atr_mult": 3.0, "max_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "Chandelier exit"),
    ExitSpec("chandelier_4", "chandelier atr_mult=4.0", "chandelier",
             {"atr_mult": 4.0, "max_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "Chandelier exit"),
    ExitSpec("breakeven_1r", "breakeven after +1R", "breakeven_r",
             {"n_bars": _MAX_BARS, "k_stop": 2.0, "be_trigger": 1.0, "atr_period": _AP}, 1.0,
             "breakeven after +1R"),
    ExitSpec("breakeven_1_5r", "breakeven after +1.5R", "breakeven_r",
             {"n_bars": _MAX_BARS, "k_stop": 2.0, "be_trigger": 1.5, "atr_period": _AP}, 1.0,
             "breakeven after +1.5R"),
    ExitSpec("lock_profit_2r", "lock +1R after +2R reached", "lock_profit",
             {"n_bars": _MAX_BARS, "k_stop": 2.0, "lock_trigger": 2.0, "lock_level": 1.0,
              "atr_period": _AP}, 1.0,
             "lock-profit after +2R"),
    ExitSpec("time_stop_48", "time stop @48 bars (no stop)", "horizon_hold",
             {"n_bars": 48, "atr_period": _AP}, 1.0,
             "time stop"),
    ExitSpec("time_stop_120", "time stop @120 bars (no stop)", "horizon_hold",
             {"n_bars": _MAX_BARS, "atr_period": _AP}, 1.0,
             "time stop"),
    ExitSpec("partial_tp_2r", "partial 50% @+2R + trail remainder", "partial_tp_trail",
             {"tp_level": 2.0, "tp_frac": 0.5, "k_trail": 2.0, "k_stop": 2.0,
              "max_bars": _MAX_BARS, "atr_period": _AP}, 1.5,
             "partial take-profit + trailing remainder"),
)

BASELINE_KEY = "atr_trail_2"
EXTRA_COST = 0.0005  # +5bps additive cost stress, matching the tournament


# ---------------------------------------------------------------------------
# Scoring — frozen entry stream + per-exit net R, mirroring single_trade_r.
# ---------------------------------------------------------------------------
def entry_stream(candles) -> list[tuple[int, str]]:
    """The survivor's exact entry stream: symmetric donchian_break n=100,
    long+short merged, then non-overlap by h=48 (identical to the tournament's
    _evaluate_records with empty filters)."""
    rule = {"family": ENTRY_FAMILY, "params": dict(ENTRY_PARAMS)}
    long_e = _rule_entries(candles, rule, "LONG")
    short_e = _rule_entries(candles, rule, "SHORT")
    return nonoverlap(sorted(long_e + short_e), ENTRY_H)


def score_exit(candles, spec: ExitSpec) -> list[dict]:
    """Net-R records for one exit over the survivor's entry stream. Cost math is
    identical to foundation.metrics.single_trade_r (net = gross - cost/atr_frac),
    scaled by cost_legs so a scale-out exit pays its extra execution leg."""
    fn = _LOCAL_FNS[spec.exit_name]
    ap = spec.params["atr_period"]
    out: list[dict] = []
    for i, side in entry_stream(candles):
        unit = risk_unit(candles, i, 1.0, ap)
        if unit is None:
            continue
        gross = fn(i, side, candles, spec.params)
        if gross is None:
            continue
        atr_frac = unit / candles[i].close
        net = gross - spec.cost_legs * COST_FRACTION / atr_frac
        out.append({"i": i, "side": side, "net_r": net, "atr_frac": atr_frac})
    return out


def _cost_stress(records: list[dict], extra_cost: float) -> dict:
    if not records:
        return {"expectancy_r": 0.0, "profit_factor": 0.0, "passed": False}
    stressed = [r["net_r"] - extra_cost / r["atr_frac"] if r["atr_frac"] > 0 else r["net_r"]
                for r in records]
    s = summarize_r(stressed)
    return {"expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
            "passed": s.expectancy_r > 0 and s.profit_factor > 1.0}


def _block(records: list[dict], cost_legs: float) -> dict:
    """Metric block for one (segment, side) slice."""
    if not records:
        return {"trade_count": 0, "total_r": 0.0, "expectancy_r": 0.0,
                "profit_factor": 0.0, "max_drawdown_r": 0.0, "win_rate": 0.0,
                "cost_5bps": {"passed": False}, "cost_2x": {"passed": False},
                "cost_3x": {"passed": False}, "outlier": {"passed": False}}
    rs = [r["net_r"] for r in records]
    s = summarize_r(rs)
    return {
        "trade_count": s.trade_count, "total_r": s.total_r,
        "expectancy_r": s.expectancy_r, "profit_factor": s.profit_factor,
        "max_drawdown_r": s.max_drawdown_r, "win_rate": s.win_rate,
        "cost_5bps": _cost_stress(records, EXTRA_COST * cost_legs),
        "cost_2x": _cost_stress(records, (2.0 - 1.0) * COST_FRACTION * cost_legs),
        "cost_3x": _cost_stress(records, (3.0 - 1.0) * COST_FRACTION * cost_legs),
        "outlier": (sb.outlier_dependence_ok(rs, 0.05) if len(rs) >= 2
                    else {"passed": False}),
    }


def _practical_pass(block: dict) -> bool:
    """The tournament's practical bar applied to a single slice."""
    return (block["profit_factor"] >= PF_FLOOR and block["expectancy_r"] > 0
            and abs(block["max_drawdown_r"]) <= MAX_DD_R
            and block["trade_count"] >= MIN_TRADES)


def score_segment(candles, spec: ExitSpec) -> dict:
    """combined/long/short metric blocks for one exit on one data segment."""
    records = score_exit(candles, spec)
    longs = [r for r in records if r["side"] == "LONG"]
    shorts = [r for r in records if r["side"] == "SHORT"]
    combined = _block(records, spec.cost_legs)
    return {
        "combined": combined,
        "long": _block(longs, spec.cost_legs),
        "short": _block(shorts, spec.cost_legs),
        "practical_pass": _practical_pass(combined),
    }


def _full_bar_pass(seg_scores: dict) -> bool:
    """The honest 'recent edge' bar: the recent (sealed) window must clear the
    FULL risk-controlled practical bar (PF>=1.15, exp>0, |maxDD|<=30R, n>=30),
    survive 2x AND 3x cost, NOT be outlier-dependent, and the prior (validate)
    window must share the positive sign. Anything short of this is, at best,
    improves-but-no-edge — raw R bought by relaxing risk control is not an edge."""
    sealed = seg_scores["sealed"]["combined"]
    validate = seg_scores["validate"]["combined"]
    return (_practical_pass(sealed)
            and sealed["cost_2x"]["passed"] and sealed["cost_3x"]["passed"]
            and sealed["outlier"]["passed"]
            and validate["expectancy_r"] > 0)


def _verdict(seg_scores: dict, baseline_sealed_total: float) -> str:
    """Classify an exit by the recent (sealed) window, per the user's rule:
    a true edge is PASS only if it clears the full risk-controlled bar; merely
    losing less than the baseline (or going marginally positive on raw R while
    breaching the drawdown/cost/outlier gates) is improves-but-no-edge."""
    total = seg_scores["sealed"]["combined"]["total_r"]
    if _full_bar_pass(seg_scores):
        return "PASS (recent edge survives full risk-controlled bar, paper-only)"
    if total > baseline_sealed_total:
        if total > 0:
            return "improves: +raw R but fails risk/cost/outlier bar -> no edge"
        return "improves-but-no-edge (loses less than baseline, still negative)"
    return "no-improvement (no better than baseline)"


def run_ablation(segments: dict[str, list]) -> dict:
    """segments maps 'train'/'validate'/'sealed' to 4h candle slices. Returns a
    structured result: per-exit per-segment blocks + a sealed-window verdict."""
    rows: list[dict] = []
    baseline_sealed_total = 0.0
    scored_by_key: dict[str, dict] = {}
    for spec in ABLATION_EXITS:
        seg_scores = {name: score_segment(candles, spec)
                      for name, candles in segments.items()}
        scored_by_key[spec.key] = seg_scores
        if spec.key == BASELINE_KEY:
            baseline_sealed_total = seg_scores["sealed"]["combined"]["total_r"]
    for spec in ABLATION_EXITS:
        seg_scores = scored_by_key[spec.key]
        rows.append({
            "key": spec.key,
            "label": spec.label,
            "requested": spec.requested,
            "exit_name": spec.exit_name,
            "params": spec.params,
            "cost_legs": spec.cost_legs,
            "segments": seg_scores,
            "verdict": _verdict(seg_scores, baseline_sealed_total),
            "full_bar_pass": _full_bar_pass(seg_scores),
        })
    return {"baseline_sealed_total_r": baseline_sealed_total, "rows": rows}


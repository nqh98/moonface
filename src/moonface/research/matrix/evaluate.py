"""Governed metrics + pre-registered Slice-1 evaluation for the signal matrix.

Plugs the governed MatrixTrade stream into the existing honest-eval toolkit
(segment_panel / block_ci_q / replay_metrics / cost_stress) unchanged. The only
fitted object is a 6-config governor grid; horizon and Donchian params are frozen.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from moonface.core.models import Candle
from moonface.research.trend_sim import TrendParams
from moonface.core.stats import series_fingerprint
from moonface.models.engine.repair import (
    PURGE_MS, block_ci_q, replay_metrics, segment_panel)
from moonface.models.matrix.governor import GovernorParams, size_stream
from moonface.research.matrix.primaries import (
    MatrixTrade, funding_panel, momentum_panel)

SPAN_START_TS_MS = 1577836800000
TRAIN_END_TS_MS = 1704067200000
SEALED_START_TS_MS = 1751328000000
SPAN_END_TS_MS = 1782316800000
FAMILY_ALPHA = 0.05
N_PRIMARIES = 2
MIN_TRANSFER_TRADES = 20

VOL_LOOKBACK = 100
FUNDING_HORIZON = 48
FUNDING_WINDOW = 60
FUNDING_Z_THR = 1.5
MATRIX_K = 2.0
# Slice-1b: non-overlapping (one-position) streams fire ~66 entries/yr on 4h, so
# the ~18mo validation window tops out near ~100 even ungoverned. The v3 overlapping
# PANEL_FLOOR=200 is structurally unreachable here; the deflated block-CI is the real
# power control. Floor set to a non-overlapping-appropriate minimum.
MIN_VAL_TRADES = 40

MATRIX_VERDICTS = (
    "CLOSED_NEGATIVE_VALIDATION", "CLOSED_NEGATIVE_SEALED_BTC",
    "CLOSED_NEGATIVE_TRANSFER", "ALL_GATES_PASSED_HUMAN_DECISION_PENDING")

EFFECTIVE_TRIALS = 6 * N_PRIMARIES  # 12
CI_LO_Q = FAMILY_ALPHA / EFFECTIVE_TRIALS / 2.0
CI_HI_Q = 1.0 - CI_LO_Q


@dataclass(frozen=True)
class GovernedTrade:
    entry_index: int
    entry_ts_ms: int
    exit_ts_ms: int
    net_r: float


class _Cfg:
    """replay_metrics/cost_stress only need a base_fraction attribute to exist."""
    base_fraction = 1.0
    atr_period = 14


def _grid(dd_budget: float) -> list[GovernorParams]:
    return [GovernorParams(target_vol=tv, size_min=0.0, size_max=sm,
                           dd_budget=dd_budget)
            for tv in (0.015, 0.02, 0.03) for sm in (1.0, 2.0)]


def vol_forecast(candles: list[Candle], i: int, lookback: int) -> float:
    """Trailing close-to-close return stdev up to bar i (causal)."""
    lo = max(1, i - lookback + 1)
    rets = [(candles[m].close - candles[m - 1].close) / candles[m - 1].close
            for m in range(lo, i + 1) if candles[m - 1].close > 0]
    return statistics.pstdev(rets) if len(rets) >= 2 else 0.0


def govern(panel: list[MatrixTrade], candles: list[Candle],
           params: GovernorParams, vol_lookback: int
           ) -> list[tuple[GovernedTrade, float]]:
    """Apply the governor; emit (GovernedTrade, atr_frac_eff) pairs.

    atr_frac_eff = atr_frac / size makes cost_stress scale k-cost with size:
    net_at(k) = Sum size*(gross - k*cost/atr_frac). Slice-1b: zero-size (throttled)
    trades are RETAINED as net_r=0, atr_frac_eff=0 (cost_stress adds nothing when
    af<=0) so n reflects realized entries and the sample cannot self-collapse.
    """
    ordered = sorted(panel, key=lambda t: t.exit_ts_ms)
    raw = [(t.net_r_ungoverned, vol_forecast(candles, t.entry_index, vol_lookback))
           for t in ordered]
    sizes = size_stream(raw, params)
    out: list[tuple[GovernedTrade, float]] = []
    for t, s in zip(ordered, sizes):
        if s <= 0.0:
            gt = GovernedTrade(entry_index=t.entry_index, entry_ts_ms=t.entry_ts_ms,
                               exit_ts_ms=t.exit_ts_ms, net_r=0.0)
            out.append((gt, 0.0))
            continue
        gt = GovernedTrade(entry_index=t.entry_index, entry_ts_ms=t.entry_ts_ms,
                           exit_ts_ms=t.exit_ts_ms, net_r=s * t.net_r_ungoverned)
        out.append((gt, t.atr_frac / s))
    return out


def governed_metrics(pairs) -> dict:
    return replay_metrics(pairs, _Cfg())


def fit_governor(train_panel, candles, baseline_dd: float,
                 vol_lookback: int) -> GovernorParams:
    """Highest train governed net_r whose train governed maxDD <= |baseline_dd|;
    ties broken by lowest size_max (least leverage)."""
    dd_budget = abs(baseline_dd)
    best = None
    best_key = None
    for p in _grid(dd_budget):
        pairs = govern(train_panel, candles, p, vol_lookback)
        m = governed_metrics(pairs)
        if abs(m["max_dd_r"]) > dd_budget:
            continue
        key = (m["net_r"], -p.size_max)
        if best is None or key > best_key:
            best, best_key = p, key
    return best if best is not None else _grid(dd_budget)[0]


def _mean_r(pairs):
    return sum(t.net_r for t, _ in pairs) / len(pairs) if pairs else None


def gate1_validation(val_pairs, baseline_val_dd: float) -> dict:
    m = governed_metrics(val_pairs)
    ci = block_ci_q(val_pairs, lambda p: p[0].entry_index, _mean_r,
                    CI_LO_Q, CI_HI_Q)
    passed = (len(val_pairs) >= MIN_VAL_TRADES
              and m["cost_stress"]["net_r_3x"] > 0
              and ci is not None and ci[0] > 0
              and abs(m["max_dd_r"]) <= abs(baseline_val_dd))
    return {"n": m["n"], "net_r": m["net_r"],
            "net_r_3x": m["cost_stress"]["net_r_3x"], "max_dd_r": m["max_dd_r"],
            "baseline_max_dd_r": baseline_val_dd,
            "ci": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "passed": passed}


def gate2_sealed(sealed_pairs, baseline_sealed_dd: float) -> dict:
    m = governed_metrics(sealed_pairs)
    passed = (m["n"] > 0 and m["cost_stress"]["net_r_3x"] > 0
              and abs(m["max_dd_r"]) <= abs(baseline_sealed_dd))
    return {"n": m["n"], "net_r_3x": m["cost_stress"]["net_r_3x"],
            "max_dd_r": m["max_dd_r"], "baseline_max_dd_r": baseline_sealed_dd,
            "passed": passed}


def _leg(pairs) -> dict:
    m = governed_metrics(pairs)
    return {"n": m["n"], "net_r_3x": m["cost_stress"]["net_r_3x"]}


def gate3_transfer(eth_pairs, sol_pairs) -> dict:
    eth, sol = _leg(eth_pairs), _leg(sol_pairs)
    passed = all(leg["n"] >= MIN_TRANSFER_TRADES and leg["net_r_3x"] > 0
                 for leg in (eth, sol))
    return {"eth": eth, "sol": sol, "passed": passed}


def _build_panel(candles, funding, cfg_donchian: TrendParams) -> list[MatrixTrade]:
    return (momentum_panel(candles, cfg_donchian, cfg_donchian.atr_period)
            + funding_panel(candles, funding, FUNDING_WINDOW, FUNDING_Z_THR,
                            FUNDING_HORIZON, MATRIX_K, cfg_donchian.atr_period))


def build_matrix_report(btc, eth, sol, funding_btc, funding_eth, funding_sol,
                        cfg_donchian: TrendParams, baseline_val_dd: float,
                        baseline_sealed_dd: float,
                        vol_lookback: int = VOL_LOOKBACK) -> dict:
    """Single registered evaluation with sealed protection."""
    panel = _build_panel(btc, funding_btc, cfg_donchian)
    segs, _ = segment_panel(panel, TRAIN_END_TS_MS, SEALED_START_TS_MS, PURGE_MS)
    params = fit_governor(segs["train"], btc, baseline_val_dd, vol_lookback)

    # Slice-1b: govern each segment INDEPENDENTLY (DD state resets per window) so the
    # throttle's budget and the per-window gate maxDD are the same curve, and
    # validation does not inherit train's drawdown.
    val = govern(segs["validation"], btc, params, vol_lookback)
    sealed = govern(segs["sealed"], btc, params, vol_lookback)

    gate1 = gate1_validation(val, baseline_val_dd)
    gate2 = gate3 = None
    if not gate1["passed"]:
        verdict = "CLOSED_NEGATIVE_VALIDATION"
    else:
        gate2 = gate2_sealed(sealed, baseline_sealed_dd)
        if not gate2["passed"]:
            verdict = "CLOSED_NEGATIVE_SEALED_BTC"
        else:
            eth_segs, _ = segment_panel(_build_panel(eth, funding_eth, cfg_donchian),
                                        TRAIN_END_TS_MS, SEALED_START_TS_MS, PURGE_MS)
            sol_segs, _ = segment_panel(_build_panel(sol, funding_sol, cfg_donchian),
                                        TRAIN_END_TS_MS, SEALED_START_TS_MS, PURGE_MS)
            eth_pairs = govern(eth_segs["sealed"], eth, params, vol_lookback)
            sol_pairs = govern(sol_segs["sealed"], sol, params, vol_lookback)
            gate3 = gate3_transfer(eth_pairs, sol_pairs)
            verdict = ("ALL_GATES_PASSED_HUMAN_DECISION_PENDING"
                       if gate3["passed"] else "CLOSED_NEGATIVE_TRANSFER")

    return {
        "label": "matrix slice-1b — per-segment govern, retain-zeros, "
                 "recalibrated floor; pre-registered; read-only; human promotion",
        "data": {"btc_candles": len(btc),
                 "btc_fingerprint": series_fingerprint(btc)},
        "frozen_constants": {
            "span_start_ts_ms": SPAN_START_TS_MS,
            "train_end_ts_ms": TRAIN_END_TS_MS,
            "sealed_start_ts_ms": SEALED_START_TS_MS,
            "span_end_ts_ms": SPAN_END_TS_MS, "purge_ms": PURGE_MS,
            "effective_trials": EFFECTIVE_TRIALS, "ci_lo_q": CI_LO_Q,
            "min_val_trades": MIN_VAL_TRADES,
            "govern_scope": "per_segment_reset",
            "retain_zero_size": True,
            "funding": {"window": FUNDING_WINDOW, "z_thr": FUNDING_Z_THR,
                        "horizon": FUNDING_HORIZON},
            "vol_lookback": vol_lookback},
        "fitted_governor": {"target_vol": params.target_vol,
                            "size_max": params.size_max,
                            "dd_budget": params.dd_budget},
        "segments": {"train": len(segs["train"])},
        "gate1": gate1, "gate2": gate2, "gate3": gate3, "verdict": verdict}

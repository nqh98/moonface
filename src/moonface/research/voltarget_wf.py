# src/moonface/research/voltarget_wf.py
"""Rolling walk-forward for funding_fade + fixed_bracket (spec §6.4, stage 3.5).

Train strictly precedes test; target_risk is calibrated in each fold's TRAIN
window only (no lookahead); control uses constant CONTROL_FRACTION. Aggregates
pooled TEST-window returns for both arms. Adapts research/walkforward.py's
geometry to the r_stream primitive with NO param selection (frozen construction)."""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.metrics import MAX_LEVERAGE, equity_summary_from_returns
from moonface.research.ladder import r_stream
from moonface.research.voltarget import (CONTROL_FRACTION,
                                         calibrate_target_risk,
                                         paired_dominance, treatment_returns)

_BARS_PER_DAY = 6                          # 4h bars
TRAIN_BARS = 3 * 365 * _BARS_PER_DAY       # 3-year train  (= 6570)
TEST_BARS = int(0.5 * 365 * _BARS_PER_DAY)  # 6-month test  (= 1095)
STEP_BARS = TEST_BARS                       # non-overlapping 6-month steps


def _sub_bundle(bundle: DataBundle, lo: int, hi: int) -> DataBundle:
    def cut(seq):
        return seq[lo:hi] if seq is not None else None
    return DataBundle(candles=bundle.candles[lo:hi], funding=cut(bundle.funding),
                      basis=cut(bundle.basis), feature=cut(bundle.feature))


def walk_forward_paired(spec, research: DataBundle, train_bars: int = TRAIN_BARS,
                        test_bars: int = TEST_BARS,
                        step_bars: int = STEP_BARS) -> dict:
    n = len(research.candles)
    ctrl_returns: list[float] = []
    trt_returns: list[float] = []
    folds = 0
    start = train_bars
    while start + test_bars <= n:
        train = _sub_bundle(research, start - train_bars, start)
        test = _sub_bundle(research, start, start + test_bars)
        train_afs = [af for _, _, af in r_stream(spec, train)]
        target_risk = calibrate_target_risk(train_afs) if train_afs else 0.0
        test_trades = [(r, af) for _, r, af in r_stream(spec, test)]
        for r, af in test_trades:
            ctrl_returns.append(min(CONTROL_FRACTION, MAX_LEVERAGE * af) * r)
        trt_returns.extend(treatment_returns(test_trades, target_risk))
        folds += 1
        start += step_bars
    ctrl = equity_summary_from_returns(ctrl_returns)
    trt = equity_summary_from_returns(trt_returns)
    return {
        "folds": folds,
        "aggregate_control_mar": ctrl.mar,
        "aggregate_treatment_mar": trt.mar,
        "aggregate_treatment_sharpe": trt.sharpe,
        "aggregate_trades": trt.trade_count,
        "dominance": paired_dominance(trt, ctrl),
    }


def stage35_paired(wf: dict) -> bool:
    return (wf["folds"] >= 1 and wf["aggregate_treatment_mar"] > 0.0
            and wf["dominance"])

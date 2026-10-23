# src/moonface/research/orderflow_wf.py
"""Rolling walk-forward for orderflow_microstructure (spec §4, stage 3.5).

Adapts voltarget_wf's geometry to the entry-pair control-dominance design:
NO param selection and NO calibration (the construction is frozen per spec),
so there is no train window — TRAIN_BARS is only the warm-up offset before
the first test window. Aggregates pooled TEST-window returns for the treatment
spec and its donchian_break control, then checks dominance."""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.metrics import (MAX_LEVERAGE,
                                         equity_summary_from_returns)
from moonface.research.ladder import r_stream
from moonface.research.orderflow import ORDERFLOW_FRACTION, dominates

_BARS_PER_DAY = 96                           # 15m bars
TRAIN_BARS = 180 * _BARS_PER_DAY             # 6-month warm-up offset (= 17280)
TEST_BARS = 60 * _BARS_PER_DAY               # 2-month test window  (= 5760)
STEP_BARS = TEST_BARS                        # non-overlapping 2-month steps


def _sub_bundle(bundle: DataBundle, lo: int, hi: int) -> DataBundle:
    def cut(seq):
        return seq[lo:hi] if seq is not None else None
    return DataBundle(candles=bundle.candles[lo:hi], funding=cut(bundle.funding),
                      basis=cut(bundle.basis), feature=cut(bundle.feature),
                      bookdepth=cut(bundle.bookdepth))


def walk_forward(spec, research: DataBundle, control_spec,
                 train_bars: int = TRAIN_BARS, test_bars: int = TEST_BARS,
                 step_bars: int = STEP_BARS) -> dict:
    n = len(research.candles)
    trt_returns: list[float] = []
    ctrl_returns: list[float] = []
    folds = 0
    start = train_bars
    while start + test_bars <= n:
        test = _sub_bundle(research, start, start + test_bars)
        for _, r, af in r_stream(spec, test):
            trt_returns.append(min(ORDERFLOW_FRACTION, MAX_LEVERAGE * af) * r)
        for _, r, af in r_stream(control_spec, test):
            ctrl_returns.append(min(ORDERFLOW_FRACTION, MAX_LEVERAGE * af) * r)
        folds += 1
        start += step_bars
    trt = equity_summary_from_returns(trt_returns)
    ctrl = equity_summary_from_returns(ctrl_returns)
    return {
        "folds": folds,
        "aggregate_treatment_mar": trt.mar,
        "aggregate_treatment_sharpe": trt.sharpe,
        "aggregate_control_mar": ctrl.mar,
        "aggregate_trades": trt.trade_count,
        "dominance": dominates(trt.mar, trt.sharpe, ctrl.mar, ctrl.sharpe),
    }


def stage35_of(wf: dict) -> bool:
    return (wf["folds"] >= 1 and wf["aggregate_treatment_mar"] > 0.0
            and wf["dominance"])

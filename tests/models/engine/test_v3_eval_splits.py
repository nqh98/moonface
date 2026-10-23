"""Frozen eval constants + leakage-safe chronological segmentation."""

from moonface.models.engine.config import EngineConfig
from moonface.models.engine.v3.evaluate import (
    ATR_PERIOD,
    CI_LO_Q,
    EFFECTIVE_TRIALS,
    K_STOP,
    K_TRAIL,
    MAX_BARS,
    SEALED_START_TS_MS,
    TRAIN_END_TS_MS,
    V3Trade,
    segment_v3,
)

H = 3_600_000


def _t(entry_i, exit_i):
    return V3Trade(
        entry_index=entry_i,
        exit_index=exit_i,
        entry_ts_ms=entry_i * H,
        exit_ts_ms=exit_i * H,
        direction=1,
        mechanism="BREAKOUT",
        quality=0.5,
        risk_fraction=0.005,
        net_r=0.1,
        bars_held=exit_i - entry_i,
        exit_reason="target",
        cell="TRENDING_UP/NORMAL",
    )


def test_frozen_constants():
    assert TRAIN_END_TS_MS == 1704067200000
    assert SEALED_START_TS_MS == 1751328000000
    assert EFFECTIVE_TRIALS == 12
    assert abs(CI_LO_Q - 0.05 / 12 / 2) < 1e-15


def test_bracket_consts_match_v22_defaults():
    d = EngineConfig()
    assert (K_STOP, K_TRAIL, MAX_BARS, ATR_PERIOD) == (
        d.k_stop,
        d.k_trail,
        d.max_bars,
        d.atr_period,
    )


def test_segment_v3_routes_by_boundaries():
    train_end_h = TRAIN_END_TS_MS // H
    sealed_start_h = SEALED_START_TS_MS // H
    trades = [
        _t(train_end_h - 20, train_end_h - 10),
        _t(train_end_h + 200, sealed_start_h - 10),
        _t(sealed_start_h + 200, sealed_start_h + 210),
    ]
    segs, dropped = segment_v3(trades)
    assert len(segs["train"]) == 1
    assert len(segs["validation"]) == 1
    assert len(segs["sealed"]) == 1
    assert dropped == 0
